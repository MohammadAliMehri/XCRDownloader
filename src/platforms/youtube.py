"""YouTube & YouTube Music downloader — Videos, Music, Playlists with embedded cover.

2026 method (yt-dlp >= 2026.7.4):
  - YouTube deprecated the old `web`/`mweb` player clients for format extraction
    ("No video formats found!" / 403). The current recommended set is
    `android_vr, web_safari` (yt-dlp's own default with a JS runtime available).
  - Client rotation fallback: if the primary set fails, retry with
    `tv_downgraded`, `ios`/`android`, then the legacy set as a last resort.
  - Optional TLS impersonation via curl_cffi (`impersonate=chrome`) to avoid
    bot-detection 403s; enabled automatically when curl_cffi is installed.
"""
import os
import sys
import yt_dlp
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename, format_filesize

# Ordered client strategies: (extractor_args, impersonate_target|None).
# Each entry is tried in turn until one yields a successful download/info.
_YOUTUBE_CLIENT_SETS = [
    ["android_vr", "web_safari"],      # current yt-dlp default (needs JS runtime)
    ["tv_downgraded", "web_safari"],   # authed-style fallback
    ["ios", "android"],                # mobile clients
    ["web", "mweb"],                   # legacy last resort
]

_FALLBACK_ERROR_MARKERS = (
    "no video formats found",
    "http error 403",
    "sign in to confirm",
    "player_response",
    "unable to extract",
    "this video is unavailable",
    "age",
)


def _build_client_strategies():
    """Yield (extractor_args, impersonate) combos, newest/most-reliable first."""
    impersonate = None
    try:
        import curl_cffi  # noqa: F401  (TLS impersonation backend)
        from yt_dlp.networking.impersonate import ImpersonateTarget
        impersonate = ImpersonateTarget.from_str("chrome")
    except Exception:
        impersonate = None

    for clients in _YOUTUBE_CLIENT_SETS:
        args = {"youtube": {"player_client": list(clients)}}
        # Prefer impersonation only on the primary strategy
        yield args, (impersonate if clients == _YOUTUBE_CLIENT_SETS[0] else None)


def _should_try_next_client(error: str) -> bool:
    """True if the failure looks like a client/anti-bot issue worth retrying."""
    if not error:
        return True
    low = error.lower()
    return any(marker in low for marker in _FALLBACK_ERROR_MARKERS)


class YouTubeDownloader(BaseDownloader):
    """Download from YouTube and YouTube Music: Videos, Audio, Playlists."""

    PLATFORM = "youtube"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)

    def _is_music_url(self, url: str) -> bool:
        """Check if URL is from YouTube Music."""
        return "music.youtube.com" in url.lower()

    def _iter_youtube_opts(self, base: dict):
        """Yield full yt-dlp opts dicts across all client strategies."""
        for extractor_args, impersonate in _build_client_strategies():
            opts = dict(base)
            opts["extractor_args"] = extractor_args
            if impersonate is not None:
                opts["impersonate"] = impersonate
            yield opts

    def download(self, url: str, quality: str = "best", audio_only: bool = False,
                 playlist: bool = False, **kwargs) -> dict:
        """Download YouTube video or extract audio, with client rotation."""
        is_music = self._is_music_url(url)
        category = "youtube_music" if is_music else "youtube"

        if is_music or audio_only:
            return self._download_audio(url, category)

        output_tpl = os.path.join(
            self.output_dir, category,
            "%(uploader|Unknown)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        format_spec = "best"
        if quality == "hd":
            format_spec = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        elif quality == "sd":
            format_spec = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"

        base = {
            "outtmpl": output_tpl,
            "format": format_spec,
            "merge_output_format": "mp4",
            "writeinfojson": False,
            "writethumbnail": False,
            "noplaylist": not playlist,
            "ignoreerrors": True,
            "retries": 3,
            "fragment_retries": 3,
        }

        last_result = None
        for opts in self._iter_youtube_opts(base):
            result = self._ytdlp_download(url, opts)
            if result.get("success"):
                return result
            last_result = result
            if not _should_try_next_client(result.get("error") or ""):
                break
        return last_result

    def _download_audio(self, url: str, category: str) -> dict:
        """Download audio only as high-quality MP3 with embedded cover art."""
        output_tpl = os.path.join(
            self.output_dir, category,
            "%(uploader|Unknown)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        base = {
            "outtmpl": output_tpl,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": False,
                },
            ],
            "writethumbnail": True,
            "writeinfojson": False,
            "keepvideo": False,
            "ignoreerrors": True,
            "retries": 3,
            "fragment_retries": 3,
        }

        last_result = None
        for opts in self._iter_youtube_opts(base):
            result = self._ytdlp_download(url, opts)
            if result.get("success"):
                break
            last_result = result
            if not _should_try_next_client(result.get("error") or ""):
                break

        if not result.get("success"):
            return result

        # Only keep audio files — thumbnail is now embedded
        cleaned = []
        for f in result.get("files", []):
            ext = f.get("ext", "")
            if ext in (".mp3", ".m4a", ".opus", ".wav", ".flac"):
                cleaned.append(f)
            else:
                try:
                    os.remove(f["path"])
                except OSError:
                    pass
        if cleaned:
            result["files"] = cleaned

        return result

    def download_audio(self, url: str, **kwargs) -> dict:
        """Public method to extract audio only."""
        return self._download_audio(url, "youtube")

    def get_info(self, url: str) -> dict:
        """Get YouTube content info with rich metadata, with client rotation."""
        last_result = None
        for opts in self._iter_youtube_opts({}):
            raw = self._ytdlp_extract_info(url, opts)
            if raw.get("success"):
                break
            last_result = raw
            if not _should_try_next_client(raw.get("error") or ""):
                break

        if not raw.get("success"):
            return raw

        info = raw["info"]
        raw["preview"] = {
            "title": info.get("title", "Unknown"),
            "uploader": info.get("uploader") or info.get("channel", "Unknown"),
            "duration": info.get("duration"),
            "duration_str": self._format_duration(info.get("duration")),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "thumbnail": info.get("thumbnail") or (info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None),
            "description": (info.get("description") or "")[:300],
            "upload_date": info.get("upload_date"),
            "is_music": self._is_music_url(url),
            "is_playlist": info.get("_type") == "playlist",
            "formats_available": len(info.get("formats", [])),
        }
        return raw

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return None
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
