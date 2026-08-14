"""Mixed media search and online playback for YouTube, YouTube Music and SoundCloud.

YouTube Music uses the same public YouTube catalog with music-specific metadata
and URLs. SoundCloud provides full-length audio where available. Direct media
URLs are short-lived; the client requests a fresh URL whenever playback starts.
"""
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import yt_dlp

_YT_CLIENT_SETS = [
    ["android_vr", "web_safari"],
    ["tv_downgraded", "web_safari"],
    ["ios", "android"],
    ["web", "mweb"],
]
_YT_RETRY_MARKERS = (
    "no video formats found", "http error 403", "sign in to confirm",
    "captcha", "player_response", "unable to extract", "unavailable", "age",
)
_YT_SKIP_MARKERS = ("age", "captcha", "private video", "members-only", "sign in")


def _yt_impersonate():
    try:
        import curl_cffi  # noqa: F401
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str("chrome")
    except Exception:
        return None


def _yt_extract_info(url: str, extra_opts: dict | None = None) -> dict | None:
    """Extract with rotating clients; returns None when YouTube blocks access."""
    base = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "no_color": True, "nocheckcertificate": True, "extract_flat": False,
    }
    if extra_opts:
        base.update(extra_opts)
    impersonate = _yt_impersonate()
    for index, clients in enumerate(_YT_CLIENT_SETS):
        opts = dict(base)
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
        if index == 0 and impersonate:
            opts["impersonate"] = impersonate
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info:
                return info
        except Exception as exc:
            if not any(marker in str(exc).lower() for marker in _YT_RETRY_MARKERS):
                break
    return None


def _youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    if "youtube.com" in host:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1]
    return None


def _youtube_embed_result(url: str, reason: str) -> dict | None:
    video_id = _youtube_video_id(url)
    if not video_id:
        return None
    return {
        "success": True,
        "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1&playsinline=1&controls=1&rel=0",
        "video_id": video_id,
        "source": "youtube",
        "has_video": True,
        "embed_only": True,
        "reason": reason,
    }


# ---- Search providers -----------------------------------------------------

def _search_youtube(query: str, page: int = 0, music: bool = False) -> list[dict]:
    count = 25
    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "extract_flat": True, "default_search": "ytsearch", "no_color": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
    except Exception:
        return []
    results = []
    for entry in (data or {}).get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        # Skip non-video entries — ytsearch mixes in channel/playlist tabs
        # (ie_key YoutubeTab / YoutubePlaylist) whose "id" is a 24-char
        # channel handle, not an 11-char video id. Using one would mint
        # broken watch?v= URLs.
        if entry.get("ie_key") in ("YoutubeTab", "YoutubePlaylist"):
            continue
        video_id = entry.get("id") or ""
        if len(video_id) != 11:
            continue
        duration = int(entry.get("duration") or 0)
        title = entry.get("title", "Unknown")
        lower = f"{title} {entry.get('uploader') or entry.get('channel') or ''}".lower()
        podcast_terms = ("podcast", "episode", "interview", "conversation", "lecture", "audiobook")
        video_terms = ("official video", "music video", "live performance", "concert", "visualizer")
        if not music and duration > 600 and any(x in lower for x in podcast_terms):
            kind = "podcast"
        elif not music and (duration >= 300 or any(x in lower for x in video_terms)):
            kind = "video"
        else:
            kind = "track"
        thumb = entry.get("thumbnails") or []
        results.append({
            "id": f"{'ytm' if music else 'yt'}_{video_id}",
            "source": "youtube_music" if music else "youtube",
            "kind": "track" if music else kind,
            "title": title,
            "artist": entry.get("uploader") or entry.get("channel") or "YouTube",
            "duration": duration,
            "cover": thumb[-1].get("url") if thumb else None,
            "preview_url": None,
            "source_url": f"https://music.youtube.com/watch?v={video_id}" if music else f"https://www.youtube.com/watch?v={video_id}",
            "album": "",
            "has_video": not music and kind in {"video", "podcast"},
        })
    return results


def _search_soundcloud(query: str, page: int = 0) -> list[dict]:
    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "extract_flat": True, "default_search": "scsearch", "no_color": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(f"scsearch15:{query}", download=False)
    except Exception:
        return []
    results = []
    for entry in (data or {}).get("entries") or []:
        if not entry:
            continue
        duration = int(entry.get("duration") or 0)
        thumb = entry.get("thumbnails") or []
        results.append({
            "id": f"sc_{entry.get('id', '')}", "source": "soundcloud",
            "kind": "podcast" if duration > 1200 else "track",
            "title": entry.get("title", "Unknown"),
            "artist": entry.get("uploader") or entry.get("creator") or "SoundCloud",
            "duration": duration,
            "cover": thumb[-1].get("url") if thumb else entry.get("artwork_url"),
            "preview_url": None,
            "source_url": entry.get("webpage_url") or entry.get("url", ""),
            "album": "", "has_video": False,
        })
    return results


def _squash(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _relevance(result: dict, query: str) -> float:
    q = _squash(query)
    title = _squash(result.get("title", ""))
    both = f"{title} {_squash(result.get('artist', ''))}".strip()
    score = max(SequenceMatcher(None, q, title).ratio(), SequenceMatcher(None, q, both).ratio())
    if title == q: score = 1.0
    elif title.startswith(q): score = max(score, .93)
    elif q in title: score = max(score, .86)
    weights = {"soundcloud": 1.0, "youtube_music": .95, "youtube": .9}
    return score * weights.get(result.get("source"), .8)


def search_music(query: str, page: int = 0, provider: str = "all") -> dict:
    """Search one selected provider or all providers in parallel."""
    if not query.strip():
        return {"results": [], "page": 0, "has_more": False, "provider": provider}
    provider = (provider or "all").lower()
    provider_map = {
        "youtube": [lambda q, p: _search_youtube(q, p, music=False)],
        "youtube_music": [lambda q, p: _search_youtube(q, p, music=True)],
        "soundcloud": [_search_soundcloud],
        "all": [
            lambda q, p: _search_youtube(q, p, music=False),
            lambda q, p: _search_youtube(q, p, music=True),
            _search_soundcloud,
        ],
    }
    providers = provider_map.get(provider, provider_map["all"])

    results = []
    selected_provider = provider
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(search_provider, query, page) for search_provider in providers]
        for future in as_completed(futures):
            try: results.extend(future.result())
            except Exception: pass
    unique, seen = [], set()
    for result in results:
        key = f"{result['kind']}:{_squash(result['title'])}:{_squash(result['artist'])}"
        if key not in seen:
            seen.add(key); unique.append(result)
    unique.sort(key=lambda result: _relevance(result, query), reverse=True)
    return {"results": unique, "page": page, "has_more": len(unique) >= 20, "provider": selected_provider}


# ---- Full-length mixed-provider playback ---------------------------------

def _sc_find_alternative(title: str, artist: str) -> dict | None:
    query = f"{artist} {title}".strip()
    try:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist", "default_search": "scsearch", "format": "bestaudio/best"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(f"scsearch5:{query}", download=False)
        for entry in (data or {}).get("entries") or []:
            url = entry.get("webpage_url") or entry.get("url")
            if not url: continue
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            stream = (info or {}).get("url")
            if stream:
                return {"success": True, "stream_url": stream, "source": "soundcloud", "fallback": True, "fallback_provider": "soundcloud", "title": info.get("title", title), "duration": info.get("duration")}
    except Exception:
        pass
    return None


def _select_format(info: dict, want_video: bool) -> str | None:
    """Select a browser-playable format; prefer muxed MP4 for video."""
    direct = info.get("url")
    if direct and (not want_video or info.get("vcodec") != "none"):
        return direct
    formats = info.get("formats") or []
    if want_video:
        candidates = [f for f in formats if f.get("url") and f.get("protocol") not in {"mhtml", "http_dash_segments"} and f.get("vcodec") != "none" and f.get("acodec") != "none" and (f.get("ext") == "mp4" or f.get("container") == "m4v_dash")]
        if not candidates:
            candidates = [f for f in formats if f.get("url") and f.get("protocol") not in {"mhtml", "http_dash_segments"} and f.get("vcodec") != "none" and f.get("acodec") != "none"]
    else:
        candidates = [f for f in formats if f.get("url") and f.get("protocol") not in {"mhtml", "http_dash_segments"} and f.get("acodec") != "none"]
    candidates.sort(key=lambda f: (f.get("ext") != "mp4", f.get("height") or 0, f.get("abr") or 0))
    return candidates[-1].get("url") if candidates else None


def get_stream_url(source_url: str, want_video: bool = False, title: str = "", artist: str = "") -> dict:
    """Return a fresh browser URL, official embed, or a clear failure."""
    if not source_url:
        return {"success": False, "error": "No URL provided"}
    is_youtube = "youtube.com" in source_url or "youtu.be" in source_url
    if is_youtube:
        # Ask yt-dlp for a single browser-playable file.  DASH video/audio
        # pairs cannot be muxed by an HTML5 element, so never request them.
        fmt = ("best[height<=720][vcodec!=none][acodec!=none]/"
               "best[height<=720][vcodec!=none][acodec!=none]/best") if want_video else "bestaudio[acodec!=none]/best"
        info = _yt_extract_info(source_url, {
            "format": fmt,
            "check_formats": False,
            "source_address": "0.0.0.0",
            "http_headers": {"Referer": "https://www.youtube.com/", "Origin": "https://www.youtube.com"},
        })
        stream = _select_format(info or {}, want_video) if info else None
        if stream:
            return {"success": True, "stream_url": stream, "source": "youtube", "has_video": want_video, "title": info.get("title", title), "duration": info.get("duration")}
        if title and not want_video:
            alt = _sc_find_alternative(title, artist) if not want_video else None
            if alt: return alt
        embed = _youtube_embed_result(source_url, "Direct YouTube stream unavailable; using the official YouTube player.") if want_video else None
        if embed: return embed
        return {"success": False, "error": "YouTube stream is unavailable. Try another provider or use the official player."}
    # SoundCloud and YouTube Music URLs are handled by yt-dlp. YouTube Music
    # URLs resolve through the YouTube extractor but remain labeled as music.
    if "music.youtube.com" in source_url:
        source_url = source_url.replace("music.youtube.com", "www.youtube.com")
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "format": "bestaudio/best", "nocheckcertificate": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
        stream = _select_format(info or {}, False) if info else None
        if stream:
            return {"success": True, "stream_url": stream, "source": "youtube_music" if "music.youtube.com" in source_url else "soundcloud", "title": info.get("title", title), "duration": info.get("duration")}
    except Exception:
        pass
    return {"success": False, "error": "No playable stream was found."}


def resolve_for_download(source_url: str) -> str:
    return source_url


def ffmpeg_available() -> bool:
    """Whether FFmpeg is available for downloads/merging; browsers need muxed URLs."""
    return shutil.which("ffmpeg") is not None
