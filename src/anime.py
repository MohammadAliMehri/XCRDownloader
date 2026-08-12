"""Anime search & streaming providers.

All providers use keyless public endpoints:

- yomi       — AniList GraphQL metadata + MegaPlay (megaplay.buzz) HLS streams,
               with sub/dub variants and subtitle tracks.
- aniwatchtv — WordPress anime site; direct m3u8 from the MegaPlay.SU JWPlayer embed.
- f2mc       — Film2Media (Persian movies/series/anime download portal);
               search results link to post pages with download links.
- miruro     — WordPress anime site; episodes play through the embedded
               dramastream player (iframe).

MegaPlay source flow (yomi / aniwatchtv):
  1. GET https://megaplay.buzz/stream/ani/{anilist_id}/{ep}/{sub|dub}
     -> player page, parse data-id from the #megaplay-player element
  2. GET https://megaplay.buzz/stream/getSourcesNew?id={data_id}
     (headers: X-Requested-With: XMLHttpRequest + Referer: megaplay.buzz)
     -> JSON { sources: { file: master.m3u8 }, tracks: [ {label, file} ] }
  3. Media CDNs enforce Referer: https://megaplay.buzz/ — browsers cannot set
     that header, so the Flask app relays media through /api/anime/media.
"""
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from urllib.request import Request, urlopen

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

PROVIDER_LABELS = {
    "yomi": "Yomi",
    "aniwatchtv": "AniWatchTV",
    "f2mc": "Film2Media",
    "miruro": "Miruro",
}

_WP = {
    "f2mc": {"base": "https://www.f2mc.top"},
    "aniwatchtv": {"base": "https://aniwatchtv.com.ro"},
    "miruro": {"base": "https://miruro.ro"},
}


# ---- HTTP helpers ---------------------------------------------------------

def _fetch(url: str, headers: dict | None = None, timeout: int = 25) -> str:
    req = Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json, text/html, */*",
        **(headers or {}),
    })
    with urlopen(req, timeout=timeout) as resp:
        # utf-8-sig: f2mc responses carry a UTF-8 BOM
        return resp.read().decode("utf-8-sig", "replace")


def _json(url: str, headers: dict | None = None, timeout: int = 25) -> dict:
    return json.loads(_fetch(url, headers=headers, timeout=timeout))


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode()
    req = Request(url, data=body, method="POST", headers={
        "User-Agent": _UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
        **(headers or {}),
    })
    with urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


# ---- AniList (Yomi metadata) ---------------------------------------------

_ANILIST_SEARCH = """query($s:String,$page:Int){Page(page:$page,perPage:24){
media(search:$s,type:ANIME,isAdult:false){
id title{romaji english native} coverImage{extraLarge large} bannerImage
episodes duration format seasonYear averageScore popularity genres
description(asHtml:false) status
}}}"""

_ANILIST_BY_ID = """query($id:Int){Media(id:$id,type:ANIME){
id title{romaji english native} coverImage{extraLarge large} bannerImage
episodes duration format seasonYear averageScore popularity genres
description(asHtml:false) status
}}"""


def _anilist(query: str, variables: dict) -> dict:
    return _post_json("https://graphql.anilist.co", {"query": query, "variables": variables})


def _norm_anilist(media: dict) -> dict:
    t = media.get("title") or {}
    title = t.get("english") or t.get("romaji") or t.get("native") or "Unknown"
    cover = (media.get("coverImage") or {}).get("extraLarge") \
        or (media.get("coverImage") or {}).get("large")
    return {
        "id": f"yomi_{media.get('id')}",
        "provider": "yomi",
        "anime_id": media.get("id"),
        "title": title,
        "alt_title": t.get("romaji") or "",
        "cover": cover,
        "banner": media.get("bannerImage"),
        "episodes": media.get("episodes"),
        "duration": media.get("duration"),
        "format": media.get("format"),
        "year": media.get("seasonYear"),
        "score": media.get("averageScore"),
        "popularity": media.get("popularity"),
        "genres": media.get("genres") or [],
        "description": re.sub(r"<[^>]+>", " ", media.get("description") or "").strip()[:600],
        "status": media.get("status"),
        "kind": "anime",
    }


def _anilist_search(query: str, page: int = 1) -> list[dict]:
    try:
        data = _anilist(_ANILIST_SEARCH, {"s": query, "page": page})
    except Exception:
        return []
    out = []
    for media in (data.get("data") or {}).get("Page", {}).get("media") or []:
        if media:
            out.append(_norm_anilist(media))
    return out


# ---- WordPress providers --------------------------------------------------

def _norm_wp(item: dict, provider: str, cover: str | None = None) -> dict:
    title_raw = item.get("title") or ""
    if isinstance(title_raw, dict):  # /wp/v2/{type} responses use {rendered: ...}
        title_raw = title_raw.get("rendered") or ""
    title = html.unescape(re.sub(r"<[^>]+>", "", title_raw)).strip()
    return {
        "id": f"{provider}_{item.get('id')}",
        "provider": provider,
        "title": title or "Unknown",
        "url": item.get("url") or item.get("link") or "",
        "cover": cover,
        "subtype": item.get("subtype", ""),
        "kind": "anime",
    }


def _wp_search(provider: str, query: str, per_page: int = 15) -> list[dict]:
    cfg = _WP.get(provider)
    if not cfg:
        return []
    base = cfg["base"]
    # Film2Media exposes its series type with embedded thumbnails
    if provider == "f2mc":
        try:
            items = _json(f"{base}/wp-json/wp/v2/series?search={quote(query)}&per_page={per_page}&_embed=1")
            out = []
            for i in items:
                fm = (i.get("_embedded") or {}).get("wp:featuredmedia") or [{}]
                cover = fm[0].get("source_url") if fm and fm[0] else None
                out.append(_norm_wp(i, provider, cover))
            if out:
                return out
        except Exception:
            pass
    try:
        items = _json(f"{base}/wp-json/wp/v2/search?search={quote(query)}&per_page={per_page}")
    except Exception:
        return []
    return [_norm_wp(i, provider) for i in items]


# ---- Public API -----------------------------------------------------------

def search_anime(query: str, provider: str = "all", page: int = 1) -> dict:
    """Search anime across the selected providers (parallel, fail-safe)."""
    if not query.strip():
        return {"results": [], "page": 1, "has_more": False, "provider": provider}
    provider = (provider or "all").lower()
    jobs = []
    if provider in ("all", "yomi"):
        jobs.append(lambda: _anilist_search(query, page))
    for p in ("f2mc", "aniwatchtv", "miruro"):
        if provider in ("all", p):
            jobs.append(lambda p=p: _wp_search(p, query))

    results: list[dict] = []
    if jobs:
        with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
            futures = [pool.submit(job) for job in jobs]
            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception:
                    pass

    # dedupe: same provider + normalized title
    seen, unique = set(), []
    for r in results:
        key = f"{r['provider']}:{re.sub(r'[^a-z0-9]+', ' ', r['title'].lower()).strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return {"results": unique, "page": page, "has_more": len(unique) >= 20, "provider": provider}


def _extract_episodes(html: str, page_url: str) -> list[dict]:
    """Scrape episode links from a WordPress series page (aniwatchtv/miruro)."""
    base = page_url.rstrip("/").rsplit("/", 1)[-1]
    core = re.sub(r"-\d[a-z0-9]{3}$", "", base)  # strip 4-char random suffix (miruro)
    pattern = re.compile(r'href="([^"]*-episode-(\d+)/)"')
    found: dict[int, str] = {}
    for full, num in pattern.findall(html):
        slug = full.rstrip("/").rsplit("/", 1)[-1]
        ep_slug = slug.rsplit("-episode-", 1)[0]
        if ep_slug == base or (core and ep_slug.startswith(core)):
            found.setdefault(int(num), full)
    return [
        {"episode": n, "title": f"Episode {n}", "url": found[n]}
        for n in sorted(found)
    ]


def get_anime_episodes(provider: str = "yomi", anime_id: int | None = None,
                       page_url: str | None = None) -> dict:
    """List episodes for an anime from the selected provider."""
    provider = (provider or "yomi").lower()
    if provider == "yomi" and anime_id:
        try:
            data = _anilist(_ANILIST_BY_ID, {"id": int(anime_id)})
            media = (data.get("data") or {}).get("Media") or {}
            info = _norm_anilist(media)
            count = media.get("episodes") or 0
            eps = [{"episode": i, "title": f"Episode {i}"}
                   for i in range(1, min(count, 1000) + 1)] if 0 < count <= 5000 else []
            if not eps:
                return {"success": False, "error": "No episode data on AniList", "provider": "yomi"}
            return {"success": True, "provider": "yomi", "info": info, "episodes": eps}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "yomi"}
    if provider in ("aniwatchtv", "miruro") and page_url:
        try:
            html_text = _fetch(page_url)
            eps = _extract_episodes(html_text, page_url)
            if not eps:
                return {"success": False, "error": "No episodes found on the series page", "provider": provider}
            return {"success": True, "provider": provider, "episodes": eps,
                    "info": {"title": re.sub(r"[-_]", " ", page_url.rstrip("/").rsplit("/", 1)[-1]).title()}}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": provider}
    return {"success": False, "error": "Unsupported provider or missing parameters"}


def _yomi_stream(anime_id: int, episode: int, dub: bool) -> dict:
    lang = "dub" if dub else "sub"
    page_url = f"https://megaplay.buzz/stream/ani/{anime_id}/{episode}/{lang}"
    try:
        html_text = _fetch(page_url, headers={"Referer": "https://yomi.to/"})
    except Exception as exc:
        return {"success": False, "error": str(exc)[:160], "provider": "yomi", "player_url": page_url}
    m = re.search(r'data-id="(\d+)"', html_text)
    if not m:
        return {"success": False,
                "error": "Episode not found on the stream host",
                "provider": "yomi", "player_url": page_url}
    try:
        data = _json(
            f"https://megaplay.buzz/stream/getSourcesNew?id={m.group(1)}",
            headers={"Referer": "https://megaplay.buzz/", "X-Requested-With": "XMLHttpRequest"},
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)[:160], "provider": "yomi", "player_url": page_url}
    file_url = ((data.get("sources") or {}).get("file") or "").strip()
    tracks = []
    for i, t in enumerate(data.get("tracks") or []):
        tf = (t.get("file") or "").strip()
        if tf:
            tracks.append({"label": t.get("label") or f"Subtitle {i + 1}", "file": tf})
    if not file_url:
        return {"success": False, "error": "No playable source returned",
                "provider": "yomi", "player_url": page_url}
    return {
        "success": True,
        "stream_url": file_url,
        "subtitles": tracks,
        "referer": "https://megaplay.buzz/",
        "provider": "yomi",
        "player_url": page_url,
    }


def _aniwatchtv_stream(episode_url: str) -> dict:
    try:
        html_text = _fetch(episode_url, headers={"Referer": "https://aniwatchtv.com.ro/"})
    except Exception as exc:
        return {"success": False, "error": str(exc)[:160], "provider": "aniwatchtv"}
    m = re.search(r'(https://megaplay\.su/embed\.php\?sid=[^"\']+)', html_text)
    if not m:
        return {"success": False, "error": "Player embed not found on the episode page",
                "provider": "aniwatchtv", "page_url": episode_url}
    embed_url = m.group(1)
    try:
        embed_html = _fetch(embed_url, headers={"Referer": "https://aniwatchtv.com.ro/"})
        fm = re.search(r'file:\s*"([^"]+)"', embed_html)
        if fm and fm.group(1).strip():
            return {
                "success": True,
                "stream_url": fm.group(1).strip(),
                "subtitles": [],
                "referer": "https://megaplay.su/",
                "provider": "aniwatchtv",
                "player_url": embed_url,
            }
    except Exception:
        pass
    # The embed page itself is a complete player — usable as an iframe fallback
    return {"success": True, "player_url": embed_url, "embed_only": True,
            "provider": "aniwatchtv", "page_url": episode_url}


def _miruro_stream(episode_url: str) -> dict:
    try:
        html_text = _fetch(episode_url, headers={"Referer": "https://miruro.ro/"})
    except Exception as exc:
        return {"success": False, "error": str(exc)[:160], "provider": "miruro"}
    m = re.search(r'(https://miruro\.ro/wp-content/themes/dramastream-child/player/\?[^"\']+)', html_text)
    if not m:
        return {"success": False, "error": "Player embed not found on the episode page",
                "provider": "miruro", "page_url": episode_url}
    return {"success": True, "player_url": m.group(1), "embed_only": True,
            "provider": "miruro", "page_url": episode_url}


def get_anime_stream(provider: str = "yomi", anime_id: int | None = None,
                     episode: int = 1, dub: bool = False,
                     page_url: str | None = None,
                     episode_url: str | None = None) -> dict:
    """Return a playable stream (m3u8 + subtitles) or an embeddable player URL."""
    provider = (provider or "yomi").lower()
    episode = max(1, int(episode or 1))
    if provider == "yomi":
        if anime_id is None:
            return {"success": False, "error": "Missing anime_id for Yomi provider"}
        return _yomi_stream(int(anime_id), episode, bool(dub))
    if provider == "aniwatchtv":
        if not (episode_url or page_url):
            return {"success": False, "error": "Missing episode URL for AniWatchTV"}
        return _aniwatchtv_stream((episode_url or "").strip() or f"{page_url.rstrip('/')}-episode-{episode}/")
    if provider == "miruro":
        if not (episode_url or page_url):
            return {"success": False, "error": "Missing episode URL for Miruro"}
        return _miruro_stream((episode_url or "").strip() or f"{page_url.rstrip('/')}-episode-{episode}/")
    if provider == "f2mc":
        return {"success": False,
                "error": "Film2Media is a download portal — open the post page for download links",
                "provider": "f2mc", "page_url": page_url or ""}
    return {"success": False, "error": "Unsupported provider"}
