"""Search engine — Deezer + YouTube + SoundCloud. Plays music, videos, podcasts.

Fan out to multiple free providers in parallel, merge results by relevance.
No API keys needed.

Deezer's public API at api.deezer.com requires no authentication and
provides clean metadata (title, artist, album art, 30s preview).
YouTube search via yt-dlp `ytsearch:` gives full playback URLs.
SoundCloud search via yt-dlp `scsearch:`.
"""
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yt_dlp


# ---------------------------------------------------------------------------
# YouTube client rotation — same strategy as platforms/youtube.py
# YouTube periodically blocks old player clients (403 / "No formats found").
# We rotate through 4 client sets with optional TLS impersonation.
# ---------------------------------------------------------------------------

_YT_CLIENT_SETS = [
    ["android_vr", "web_safari"],
    ["tv_downgraded", "web_safari"],
    ["ios", "android"],
    ["web", "mweb"],
]

_YT_FALLBACK_MARKERS = (
    "no video formats found",
    "http error 403",
    "sign in to confirm",
    "player_response",
    "unable to extract",
    "this video is unavailable",
    "age",
)


def _yt_impersonate():
    """Try to get a Chrome TLS impersonation target (needs curl_cffi)."""
    try:
        import curl_cffi  # noqa: F401
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str("chrome")
    except Exception:
        return None


def _yt_should_retry(error: str) -> bool:
    if not error:
        return True
    low = error.lower()
    return any(m in low for m in _YT_FALLBACK_MARKERS)


def _yt_extract_info(url: str, extra_opts: dict = None) -> dict | None:
    """Extract info from a YouTube URL with client rotation.

    Tries each client set in order. Returns the info dict on success,
    None on failure.  Applies TLS impersonation on the primary set.
    """
    impersonate = _yt_impersonate()
    base = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "no_color": True,
        "nocheckcertificate": True,
        "extract_flat": False,
    }
    if extra_opts:
        base.update(extra_opts)

    for i, clients in enumerate(_YT_CLIENT_SETS):
        opts = dict(base)
        opts["extractor_args"] = {"youtube": {"player_client": list(clients)}}
        if i == 0 and impersonate is not None:
            opts["impersonate"] = impersonate

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is not None:
                    return info
        except Exception as e:
            if not _yt_should_retry(str(e)):
                return None
            continue
    return None


def _yt_download_with_rotation(url: str, output_tpl: str, extra_opts: dict = None) -> dict:
    """Download from YouTube with client rotation. Returns result dict."""
    impersonate = _yt_impersonate()
    base = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "retries": 3,
    }
    if extra_opts:
        base.update(extra_opts)

    for i, clients in enumerate(_YT_CLIENT_SETS):
        opts = dict(base)
        opts["extractor_args"] = {"youtube": {"player_client": list(clients)}}
        if i == 0 and impersonate is not None:
            opts["impersonate"] = impersonate
        # Set output template if provided
        if output_tpl:
            opts["outtmpl"] = output_tpl

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is not None:
                    return {"success": True, "info": info}
        except Exception as e:
            if not _yt_should_retry(str(e)):
                return {"success": False, "error": str(e)}
            continue
    return {"success": False, "error": "All YouTube client strategies failed"}


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
        "preview_url": item.get("preview"),
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
    limit = 25
    index = page * limit
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        tracks_f = pool.submit(_deezer_get, "/search/track", q=query, limit=limit, index=index)
        albums_f = pool.submit(_deezer_get, "/search/album", q=query, limit=15, index=index)
        artists_f = pool.submit(_deezer_get, "/search/artist", q=query, limit=10, index=index)

    for item in (tracks_f.result().get("data") or []):
        results.append(_deezer_track(item))
    for item in (albums_f.result().get("data") or []):
        results.append(_deezer_album(item))
    for item in (artists_f.result().get("data") or []):
        results.append(_deezer_artist(item))
    return results


# ---------------------------------------------------------------------------
# YouTube — via yt-dlp ytsearch
# ---------------------------------------------------------------------------

def _classify_youtube(entry: dict) -> str:
    """Decide if a YouTube result is a video, podcast, or track.

    Heuristics:
    - Duration > 1200s (20min) + podcast-like title keywords → podcast
    - Has video codec info or is clearly a music video → video
    - Otherwise → track (audio-focused)
    """
    duration = int(entry.get("duration") or 0)
    title = (entry.get("title") or "").lower()
    channel = (entry.get("channel") or entry.get("uploader") or "").lower()

    # Podcast detection: long duration + podcast keywords
    podcast_keywords = (
        "podcast", "episode", "ep.", " ep ", "interview", "talk show",
        "discussion", "conversation", "panel", "lecture", "audiobook",
        "joe rogan", "lex fridman", "huberman", "ted talk", "keynote",
    )
    combined = f"{title} {channel}"
    if duration > 1200 or any(kw in combined for kw in podcast_keywords):
        if duration > 600:  # 10+ minutes with podcast keyword
            return "podcast"

    # Video detection: music video, official video, lyric video, etc.
    video_keywords = (
        "official video", "music video", "lyric video", "mv",
        "live performance", "concert", "visualizer", "short film",
    )
    if any(kw in title for kw in video_keywords):
        return "video"

    # Long videos (5+ minutes) are likely video content
    if duration >= 300:
        return "video"

    return "track"


def _search_youtube(query: str, page: int = 0) -> list[dict]:
    count = 25
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
        kind = _classify_youtube(entry)
        duration = int(entry.get("duration") or 0)
        thumb = entry.get("thumbnails", [{}])
        cover = thumb[-1].get("url") if thumb else None
        results.append({
            "id": f"yt_{entry.get('id', '')}",
            "source": "youtube",
            "kind": kind,
            "title": entry.get("title", "Unknown"),
            "artist": entry.get("uploader") or entry.get("channel", "Unknown"),
            "duration": duration,
            "cover": cover,
            "preview_url": None,
            "source_url": entry.get("url") or entry.get("webpage_url", ""),
            "album": "",
            "has_video": kind in ("video", "podcast"),
        })

    return results


# ---------------------------------------------------------------------------
# SoundCloud — via yt-dlp scsearch
# ---------------------------------------------------------------------------

def _search_soundcloud(query: str, page: int = 0) -> list[dict]:
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
        duration = int(entry.get("duration") or 0)
        kind = "podcast" if duration > 1200 else "track"
        results.append({
            "id": f"sc_{entry.get('id', '')}",
            "source": "soundcloud",
            "kind": kind,
            "title": entry.get("title", "Unknown"),
            "artist": entry.get("uploader") or entry.get("creator", "Unknown"),
            "duration": duration,
            "cover": (entry.get("thumbnails") or [{}])[-1].get("url") if entry.get("thumbnails") else entry.get("artwork_url"),
            "preview_url": None,
            "source_url": entry.get("url") or entry.get("webpage_url", ""),
            "album": "",
            "has_video": False,
        })

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _relevance(result: dict, query: str) -> float:
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
    source_weight = {"deezer": 1.0, "soundcloud": 0.9, "youtube": 0.85}
    return score * source_weight.get(result.get("source", ""), 0.8)


def _dedup_key(result: dict) -> str:
    artist = _squash(result.get("artist", "")).replace(" ", "")
    title = _squash(result.get("title", "")).replace(" ", "")
    return f"{result.get('kind', 'track')}:{title}:{artist}"


def search_music(query: str, page: int = 0) -> dict:
    """Search across all providers and return merged, ranked results."""
    query = query.strip()
    if not query:
        return {"results": [], "page": 0, "has_more": False}

    providers = [_search_deezer, _search_youtube, _search_soundcloud]
    all_results = []

    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(p, query, page): p.__name__ for p in providers}
        for future in as_completed(futures, timeout=25):
            try:
                all_results.extend(future.result())
            except Exception:
                pass

    seen = set()
    unique = []
    for r in all_results:
        key = _dedup_key(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    unique.sort(key=lambda r: _relevance(r, query), reverse=True)
    return {"results": unique, "page": page, "has_more": len(unique) >= 20}


# ---------------------------------------------------------------------------
# Stream extraction — with YouTube client rotation + Deezer full-song fallback
# ---------------------------------------------------------------------------

# YouTube-specific errors that mean "skip this video, try another"
_YT_SKIP_ERRORS = (
    "sign in to confirm your age",
    "video may be inappropriate",
    "captcha",
    "this video is not available",
    "private video",
    "this live event",
    "members-only",
)


def _yt_find_alternative(title: str, artist: str) -> dict | None:
    """Search YouTube for the same track by title+artist and extract its stream.

    Used when a Deezer track needs full playback (not 30s preview), or when
    the original YouTube video is age-restricted / captcha-blocked.
    """
    query = f"{artist} - {title}" if artist else title
    try:
        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "default_search": "ytsearch",
            "no_color": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            search_info = ydl.extract_info(f"ytsearch3:{query}", download=False)
        entries = (search_info or {}).get("entries") or []
        # Filter out entries that are likely age-restricted or unavailable
        candidates = [e for e in entries if e and e.get("id")]
        for entry in candidates[:3]:
            url = entry.get("url") or entry.get("webpage_url", "")
            if not url:
                continue
            info = _yt_extract_info(url, extra_opts={"format": "bestaudio/best"})
            if info is None:
                continue
            stream_url = info.get("url")
            if not stream_url and info.get("formats"):
                audio = [f for f in info["formats"]
                         if f.get("acodec") != "none" and f.get("url")]
                if audio:
                    stream_url = audio[-1]["url"]
            if stream_url:
                return {
                    "success": True,
                    "stream_url": stream_url,
                    "title": info.get("title", title),
                    "duration": info.get("duration"),
                    "source": "youtube",
                    "fallback": True,  # indicates this came from a cross-source fallback
                }
    except Exception:
        pass
    return None


def get_stream_url(source_url: str, want_video: bool = False,
                   title: str = "", artist: str = "") -> dict:
    """Get a playable stream URL for a track/video/podcast.

    Deezer → tries YouTube full-song first, falls back to 30s preview.
    YouTube → client rotation; if age-restricted, tries alternate videos.
    SoundCloud → direct extraction.
    """
    if not source_url:
        return {"success": False, "error": "No source URL provided"}

    # --- Deezer: full song via YouTube, 30s preview as fallback ---
    if "deezer.com" in source_url:
        # Try to find the full song on YouTube
        if title:
            yt_result = _yt_find_alternative(title, artist)
            if yt_result:
                return yt_result
        # Fall back to Deezer's 30s preview
        return {
            "success": True,
            "stream_url": source_url,
            "source": "deezer",
            "preview_only": True,
            "note": "30s preview — full version unavailable",
        }

    # --- YouTube: client rotation with age-restriction handling ---
    if "youtube.com" in source_url or "youtu.be" in source_url:
        fmt = "best[height<=720]/best" if want_video else "bestaudio/best"
        info = _yt_extract_info(source_url, extra_opts={"format": fmt})

        if info is None:
            # Could be age-restricted or captcha — try alternate videos
            if title:
                alt = _yt_find_alternative(title, artist)
                if alt:
                    return alt
            return {"success": False, "error": "Video unavailable (age-restricted or blocked by YouTube)"}

        # Check if extraction succeeded but returned an error marker
        raw_error = (info.get("error") or "").lower()
        if any(marker in raw_error for marker in _YT_SKIP_ERRORS):
            if title:
                alt = _yt_find_alternative(title, artist)
                if alt:
                    return alt
            return {"success": False, "error": "Video is age-restricted or requires sign-in"}

        stream_url = info.get("url")
        if not stream_url and info.get("formats"):
            if want_video:
                muxed = [f for f in info["formats"]
                         if f.get("vcodec") != "none" and f.get("acodec") != "none" and f.get("url")]
                if muxed:
                    stream_url = muxed[-1]["url"]
            else:
                audio = [f for f in info["formats"]
                         if f.get("acodec") != "none" and f.get("url")]
                if audio:
                    stream_url = audio[-1]["url"]

        if stream_url:
            return {
                "success": True,
                "stream_url": stream_url,
                "title": info.get("title", ""),
                "duration": info.get("duration"),
                "source": "youtube",
                "has_video": want_video or bool(info.get("vcodec")),
            }

        # Last resort: try alternate
        if title:
            alt = _yt_find_alternative(title, artist)
            if alt:
                return alt
        return {"success": False, "error": "No stream found"}

    # --- SoundCloud ---
    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "format": "bestaudio/best", "no_color": True, "nocheckcertificate": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
            if info is None:
                return {"success": False, "error": "Could not extract stream URL"}
            stream_url = info.get("url")
            if not stream_url and info.get("formats"):
                audio = [f for f in info["formats"]
                         if f.get("acodec") != "none" and f.get("url")]
                if audio:
                    stream_url = audio[-1]["url"]
            if stream_url:
                return {
                    "success": True, "stream_url": stream_url,
                    "title": info.get("title", ""), "duration": info.get("duration"),
                    "source": "soundcloud",
                }
            return {"success": False, "error": "No audio stream found"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def resolve_for_download(source_url: str) -> str:
    """Return a URL that yt-dlp can download directly."""
    return source_url
