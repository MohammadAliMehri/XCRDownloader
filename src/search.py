"""Music search engine — Deezer (free, no key) + YouTube (yt-dlp).

Fan out to multiple free providers in parallel, merge results by
relevance. No API keys needed.

Deezer's public API at api.deezer.com requires no authentication and
provides clean metadata (title, artist, album art, 30s preview).
YouTube search via yt-dlp `ytsearch:` gives full playback URLs.
"""
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yt_dlp


# ---------------------------------------------------------------------------
# Deezer — free public API, no key, no account
# ---------------------------------------------------------------------------
_DEEZER_API = "https://api.deezer.com"
_DEEZER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def _deezer_get(path: str, **params) -> dict:
    url = f"{_DEEZER_API}{path}"
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": _DEEZER_UA})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _deezer_track(item: dict) -> dict:
    """Convert a Deezer track result to our unified format."""
    artist = (item.get("artist") or {}).get("name", "Unknown")
    album = item.get("album") or {}
    return {
        "id": f"dz_{item['id']}",
        "source": "deezer",
        "kind": "track",
        "title": item.get("title", "Unknown"),
        "artist": artist,
        "duration": int(item.get("duration") or 0),
        "cover": album.get("cover_medium") or album.get("cover"),
        "preview_url": item.get("preview"),  # 30s MP3 preview
        "source_url": item.get("link", f"https://www.deezer.com/track/{item['id']}"),
        "album": album.get("title", ""),
    }


def _deezer_album(item: dict) -> dict:
    artist = (item.get("artist") or {}).get("name", "")
    year = (item.get("release_date") or "")[:4]
    subtitle = " · ".join(p for p in (artist, year) if p)
    return {
        "id": f"dz_album_{item['id']}",
        "source": "deezer",
        "kind": "album",
        "title": item.get("title", ""),
        "artist": subtitle,
        "duration": 0,
        "cover": item.get("cover_medium"),
        "preview_url": None,
        "source_url": item.get("link", f"https://www.deezer.com/album/{item['id']}"),
        "album": "",
        "track_count": item.get("nb_tracks", 0),
    }


def _deezer_artist(item: dict) -> dict:
    return {
        "id": f"dz_artist_{item['id']}",
        "source": "deezer",
        "kind": "artist",
        "title": item.get("name", ""),
        "artist": f"{item.get('nb_album', 0)} releases",
        "duration": 0,
        "cover": item.get("picture_medium"),
        "preview_url": None,
        "source_url": item.get("link", f"https://www.deezer.com/artist/{item['id']}"),
        "album": "",
    }


def _search_deezer(query: str, page: int = 0) -> list[dict]:
    """Search Deezer for tracks, albums, and artists in parallel."""
    limit = 25
    index = page * limit
    results = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        tracks_f = pool.submit(
            _deezer_get, "/search/track", q=query, limit=limit, index=index
        )
        albums_f = pool.submit(
            _deezer_get, "/search/album", q=query, limit=15, index=index
        )
        artists_f = pool.submit(
            _deezer_get, "/search/artist", q=query, limit=10, index=index
        )

    tracks_data = tracks_f.result()
    for item in tracks_data.get("data") or []:
        results.append(_deezer_track(item))

    albums_data = albums_f.result()
    for item in albums_data.get("data") or []:
        results.append(_deezer_album(item))

    artists_data = artists_f.result()
    for item in artists_data.get("data") or []:
        results.append(_deezer_artist(item))

    return results


def _deezer_resolve_tracks(url: str) -> list[dict]:
    """Resolve a Deezer album/playlist URL to a list of track dicts."""
    album_match = re.search(r"deezer\.com/(?:[a-z]{2}/)?album/(\d+)", url)
    playlist_match = re.search(r"deezer\.com/(?:[a-z]{2}/)?playlist/(\d+)", url)

    if album_match:
        album = _deezer_get(f"/album/{album_match.group(1)}")
        cover = album.get("cover_big") or album.get("cover_medium")
        tracks = []
        for item in (album.get("tracks") or {}).get("data") or []:
            t = _deezer_track(item)
            t["cover"] = t["cover"] or cover
            tracks.append(t)
        return tracks

    if playlist_match:
        data = _deezer_get(f"/playlist/{playlist_match.group(1)}")
        cover = data.get("picture_big") or data.get("picture_medium")
        tracks_page = data.get("tracks") or {}
        items = list(tracks_page.get("data") or [])
        next_url = tracks_page.get("next")
        while next_url:
            req = Request(next_url, headers={"User-Agent": _DEEZER_UA})
            page = json.loads(urlopen(req, timeout=15).read().decode())
            items.extend(page.get("data") or [])
            next_url = page.get("next")
        tracks = []
        for item in items:
            t = _deezer_track(item)
            t["cover"] = t["cover"] or cover
            tracks.append(t)
        return tracks

    return []


# ---------------------------------------------------------------------------
# YouTube — via yt-dlp ytsearch
# ---------------------------------------------------------------------------

def _search_youtube(query: str, page: int = 0) -> list[dict]:
    """Search YouTube via yt-dlp ytsearch."""
    count = 25
    offset = page * count + 1  # ytsearch is 1-indexed

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch",
        "no_color": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
    except Exception:
        return []

    results = []
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        duration = entry.get("duration") or 0
        results.append({
            "id": f"yt_{entry.get('id', '')}",
            "source": "youtube",
            "kind": "track",
            "title": entry.get("title", "Unknown"),
            "artist": entry.get("uploader") or entry.get("channel", "Unknown"),
            "duration": int(duration),
            "cover": entry.get("thumbnails", [{}])[-1].get("url") if entry.get("thumbnails") else None,
            "preview_url": None,  # YouTube doesn't give preview URLs; we stream via yt-dlp
            "source_url": entry.get("url") or entry.get("webpage_url", ""),
            "album": "",
        })

    return results


# ---------------------------------------------------------------------------
# SoundCloud — via yt-dlp scsearch
# ---------------------------------------------------------------------------

def _search_soundcloud(query: str, page: int = 0) -> list[dict]:
    """Search SoundCloud via yt-dlp scsearch."""
    count = 15

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "scsearch",
        "no_color": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch{count}:{query}", download=False)
    except Exception:
        return []

    results = []
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        results.append({
            "id": f"sc_{entry.get('id', '')}",
            "source": "soundcloud",
            "kind": "track",
            "title": entry.get("title", "Unknown"),
            "artist": entry.get("uploader") or entry.get("creator", "Unknown"),
            "duration": int(entry.get("duration") or 0),
            "cover": (entry.get("thumbnails") or [{}])[-1].get("url") if entry.get("thumbnails") else entry.get("artwork_url"),
            "preview_url": None,
            "source_url": entry.get("url") or entry.get("webpage_url", ""),
            "album": "",
        })

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _relevance(result: dict, query: str) -> float:
    """Score how well a result matches the query (0-1)."""
    q = _squash(query)
    name = _squash(result.get("title", ""))
    both = f"{name} {_squash(result.get('artist', ''))}".strip()

    score = max(
        SequenceMatcher(None, q, name).ratio(),
        SequenceMatcher(None, q, both).ratio(),
    )
    if name == q:
        score = 1.0
    elif name.startswith(q):
        score = max(score, 0.93)
    elif q in name:
        score = max(score, 0.86)

    tokens = set(q.split())
    if tokens and tokens <= set(both.split()):
        score = max(score, 0.8)

    # Prefer sources with preview URLs (Deezer)
    source_weight = {"deezer": 1.0, "soundcloud": 0.9, "youtube": 0.85}
    return score * source_weight.get(result.get("source", ""), 0.8)


def _dedup_key(result: dict) -> str:
    artist = _squash(result.get("artist", "")).replace(" ", "")
    title = _squash(result.get("title", "")).replace(" ", "")
    return f"{result.get('kind', 'track')}:{title}:{artist}"


def search_music(query: str, page: int = 0) -> dict:
    """Search across all providers and return merged, ranked results.

    Returns {"results": [...], "page": N, "has_more": bool}
    """
    query = query.strip()
    if not query:
        return {"results": [], "page": 0, "has_more": False}

    # Fan out to all providers in parallel
    providers = [_search_deezer, _search_youtube, _search_soundcloud]
    all_results = []

    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(p, query, page): p.__name__ for p in providers}
        for future in as_completed(futures, timeout=25):
            try:
                all_results.extend(future.result())
            except Exception:
                pass

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = _dedup_key(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Sort by relevance
    unique.sort(key=lambda r: _relevance(r, query), reverse=True)

    return {
        "results": unique,
        "page": page,
        "has_more": len(unique) >= 20,
    }


def get_stream_url(source_url: str) -> dict:
    """Get a playable/streamable audio URL for a track.

    For Deezer tracks: returns the 30s preview MP3 directly.
    For YouTube/SoundCloud: extracts the bestaudio stream URL via yt-dlp.
    """
    if not source_url:
        return {"success": False, "error": "No source URL provided"}

    # Deezer preview is already a direct MP3 URL — no extraction needed
    if "deezer.com" in source_url:
        return {
            "success": True,
            "stream_url": source_url,  # Will be the preview_url from search results
            "source": "deezer",
        }

    # YouTube / SoundCloud — extract streamable audio URL via yt-dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best",
        "no_color": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
            if info is None:
                return {"success": False, "error": "Could not extract stream URL"}

            # Get the best audio format URL
            stream_url = info.get("url")

            # If formats list available, pick best audio
            if not stream_url and info.get("formats"):
                audio_formats = [
                    f for f in info["formats"]
                    if f.get("acodec") != "none" and f.get("url")
                ]
                if audio_formats:
                    # Prefer opus/m4a for streaming
                    stream_url = audio_formats[-1]["url"]

            if stream_url:
                return {
                    "success": True,
                    "stream_url": stream_url,
                    "title": info.get("title", ""),
                    "duration": info.get("duration"),
                    "source": "youtube" if "youtube" in source_url else "soundcloud",
                }

            return {"success": False, "error": "No audio stream found"}

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def resolve_for_download(source_url: str) -> str:
    """Convert a search result source_url into a downloadable URL.

    Returns a URL that yt-dlp can download directly.
    """
    return source_url
