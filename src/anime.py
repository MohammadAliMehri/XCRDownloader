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
import base64
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
        raw = resp.read()
        # utf-8-sig: f2mc responses carry a UTF-8 BOM; the WP providers
        # also sometimes emit one. Always decode with utf-8-sig so the BOM
        # is stripped before json.loads() sees it.
        return raw.decode("utf-8-sig", "replace")


def _json(url: str, headers: dict | None = None, timeout: int = 25) -> dict:
    text = _fetch(url, headers=headers, timeout=timeout)
    return json.loads(text)


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


def _fetch_og_image(page_url: str) -> str | None:
    """Fetch a series page and extract the og:image meta tag."""
    try:
        text = _fetch(page_url, timeout=15)
        m = re.search(r'<meta\s+property=["\']og:image["\'][^\>]+content=["\']([^"\']+)["\']', text)
        if m:
            return m.group(1)
        # Try alternate format
        m2 = re.search(r'<meta\s+content=["\']([^"\']+)["\'][^\>]+property=["\']og:image["\']', text)
        if m2:
            return m2.group(1)
    except Exception:
        pass
    return None


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

    # Enrich WP anime results (aniwatchtv, miruro, f2mc) that lack covers
    # by scraping og:image from their series pages. Capped so a slow page
    # can't stall the whole search response.
    def _try_og_cover(item: dict) -> dict:
        if item.get("provider") in ("aniwatchtv", "miruro", "f2mc") and not item.get("cover") and item.get("url"):
            item = dict(item)
            item["cover"] = _fetch_og_image(item["url"])
        return item

    with ThreadPoolExecutor(max_workers=3) as pool:
        unique = list(pool.map(_try_og_cover, unique[:12])) + unique[12:]

    return {"results": unique, "page": page, "has_more": len(unique) >= 20, "provider": provider}


def _strip_random_slug_suffix(slug: str) -> str:
    """Strip WP-theme random slugs like `-p965`, `-5rn3`, `-93rg`.

    These 3-6 char suffixes (letters+digits, always containing a digit)
    are appended by some WP anime themes and are NOT part of the real
    series slug. Pure-letter endings (e.g. `-last`, `-king`) are kept.
    """
    m = re.search(r"-([a-z0-9]{3,6})$", slug)
    if m and any(ch.isdigit() for ch in m.group(1)):
        return slug[: m.start()]
    return slug


def _series_episode_url(page_url: str, episode: int) -> str:
    """Build `https://host/slug-episode-N/` from a series page URL.

    Miruro/AniWatchTV episode pages live at the site root with the clean
    slug (`/solo-leveling-episode-12/`), while the series page URL has a
    path prefix (`/series/`, `/anime/`) and a random slug suffix.
    """
    from urllib.parse import urlparse

    parsed = urlparse(page_url)
    slug = _strip_random_slug_suffix(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    return f"{parsed.scheme}://{parsed.netloc}/{slug}-episode-{episode}/"


def _extract_episodes(html: str, page_url: str) -> list[dict]:
    """Scrape episode links from a WordPress series page (aniwatchtv/miruro).

    The page URL slug (e.g. "naruto" from /anime/naruto/) is used to filter
    episode links that belong to this series.  Episodes may live under a
    different slug variant (e.g. "naruto-dub-episode-1") so we also accept
    any slug that starts with the series slug followed by a hyphen.

    Some WP themes append a random suffix to series slugs (e.g. "name-p965").
    We strip these suffixes before matching so episode links with the clean
    slug are still recognised.
    """
    # Series slug from URL path — e.g. "naruto" from ".../anime/naruto/"
    raw_slug = page_url.rstrip("/").rsplit("/", 1)[-1]

    # Strip common random-suffix patterns: "-p965", "-5rn3", "-93rg"
    # These are added by some WP themes and are NOT part of the real slug.
    series_slug = _strip_random_slug_suffix(raw_slug)

    # All -episode-N/ links on the page
    pattern = re.compile(r'href="([^"]*-episode-(\d+)/)"')
    found: dict[int, str] = {}

    for full_url, num_str in pattern.findall(html):
        num = int(num_str)
        if num in found:
            continue  # already stored a shorter URL for this episode number

        # Derive the episode slug (the part before "-episode-N")
        url_path = full_url.rstrip("/").rsplit("/", 1)[-1]   # e.g. "naruto-dub-episode-1"
        ep_slug = url_path.rsplit("-episode-", 1)[0]          # e.g. "naruto-dub"

        # Accept if the episode slug matches the series slug (with or without
        # the random suffix stripped), or if it starts with the series slug
        # followed by a hyphen.
        if ep_slug == series_slug or ep_slug.startswith(series_slug + "-") \
           or ep_slug == raw_slug or ep_slug.startswith(raw_slug + "-"):
            found[num] = full_url

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
    """AniWatchTV uses a gogoanime iframe on episode pages which in turn
    loads a megaplay.buzz iframe. We resolve through that chain to get a
    direct megaplay embed URL for browser playback."""
    try:
        html_text = _fetch(episode_url, headers={"Referer": "https://aniwatchtv.com.ro/"})
    except Exception as exc:
        return {"success": False, "error": str(exc)[:160], "provider": "aniwatchtv"}

    # Step 1: find the gogoanime iframe (data-litespeed-src on the episode page)
    m = re.search(r'data-litespeed-src="(https?://[^"]+)"', html_text)
    if not m:
        return {
            "success": False,
            "error": "No gogoanime iframe found on the episode page",
            "provider": "aniwatchtv",
            "page_url": episode_url,
        }
    gogo_url = m.group(1).strip()

    try:
        # Step 2: fetch the gogoanime player page; it carries a megaplay iframe
        embed_html = _fetch(gogo_url, headers={"Referer": episode_url})
    except Exception:
        # Embed hosts like kwik.cx 403 non-browser requests. The gogoanime
        # player page itself is still directly iframe-able in a browser.
        embed_html = ""

    # Step 3: extract the megaplay iframe src from the gogoanime page
    mp = re.search(r'<iframe[^>]+src="(https?://megaplay\.buzz/[^"]+)"', embed_html)
    if mp:
        player_url = mp.group(1).strip()
        # The megaplay iframe is directly playable in-browser
        return {
            "success": True,
            "player_url": player_url,
            "embed_only": True,
            "provider": "aniwatchtv",
            "page_url": episode_url,
        }

    # Some series use other embed hosts (kwik.cx, streamwish, ...) that
    # 403 non-browser requests but are meant to be iframed. Return the
    # gogoanime player page itself as an embed so the browser can play it.
    return {
        "success": True,
        "player_url": gogo_url,
        "embed_only": True,
        "provider": "aniwatchtv",
        "page_url": episode_url,
    }


def _miruro_stream(episode_url: str) -> dict:
    """Miruro embeds a dramastream player iframe on episode pages. The iframe
    src contains a base64-encoded query string that resolves to a megaplay
    iframe. We decode it and return the megaplay URL for browser playback."""
    try:
        html_text = _fetch(episode_url, headers={"Referer": "https://miruro.ro/"})
    except Exception as exc:
        return {"success": False, "error": str(exc)[:160], "provider": "miruro"}

    # Find the dramastream iframe src with the base64-encoded URL
    m = re.search(
        r'<iframe[^>]+src="([^"]*dramastream[^"]+)"',
        html_text,
    )
    if not m:
        return {
            "success": False,
            "error": "No dramastream player iframe found on the episode page",
            "provider": "miruro",
            "page_url": episode_url,
        }

    iframe_src = m.group(1)

    # Extract and decode the `url=` base64 param
    url_match = re.search(r'[?&]url=([^&]+)', iframe_src)
    if not url_match:
        return {
            "success": False,
            "error": "No url param found in dramastream iframe src",
            "provider": "miruro",
            "page_url": episode_url,
        }

    try:
        decoded = base64.b64decode(url_match.group(1)).decode("utf-8")
    except Exception:
        decoded = None

    if decoded and "megaplay.buzz" in decoded:
        # Direct megaplay URL — playable as iframe
        return {
            "success": True,
            "player_url": decoded,
            "embed_only": True,
            "provider": "miruro",
            "page_url": episode_url,
        }

    # Fallback: return the full iframe src as an embed (some mirrors use it)
    return {
        "success": True,
        "player_url": iframe_src,
        "embed_only": True,
        "provider": "miruro",
        "page_url": episode_url,
    }


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
        return _aniwatchtv_stream((episode_url or "").strip() or _series_episode_url(page_url, episode))
    if provider == "miruro":
        if not (episode_url or page_url):
            return {"success": False, "error": "Missing episode URL for Miruro"}
        return _miruro_stream((episode_url or "").strip() or _series_episode_url(page_url, episode))
    if provider == "f2mc":
        return {"success": False,
                "error": "Film2Media is a download portal — open the post page for download links",
                "provider": "f2mc", "page_url": page_url or ""}
    return {"success": False, "error": "Unsupported provider"}
