"""SoundCloud downloader — Tracks, Playlists, Albums with embedded cover art."""
import os
import sys
import yt_dlp
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename, format_filesize


class SoundCloudDownloader(BaseDownloader):
    """Download from SoundCloud: Tracks, Playlists, Albums."""

    PLATFORM = "soundcloud"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)

    def download(self, url: str, quality: str = "best", audio_only: bool = True,
                 **kwargs) -> dict:
        """Download SoundCloud track or playlist as MP3 with embedded cover art."""
        output_tpl = os.path.join(
            self.output_dir, "soundcloud",
            "%(uploader|Unknown)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        opts = {
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
        }

        result = self._ytdlp_download(url, opts)

        # Only keep audio files — thumbnail is now embedded in the MP3
        if result.get("success"):
            cleaned = []
            for f in result.get("files", []):
                ext = f.get("ext", "")
                if ext in (".mp3", ".m4a", ".opus", ".wav", ".flac"):
                    cleaned.append(f)
                else:
                    # Leftover thumbnail sidecar — delete it
                    try:
                        os.remove(f["path"])
                    except OSError:
                        pass
            if cleaned:
                result["files"] = cleaned

        return result

    def get_info(self, url: str) -> dict:
        """Get SoundCloud track info with preview data."""
        raw = self._ytdlp_extract_info(url)
        if not raw.get("success"):
            return raw

        info = raw["info"]
        raw["preview"] = {
            "title": info.get("title", "Unknown"),
            "uploader": info.get("uploader") or info.get("artist", "Unknown"),
            "duration": info.get("duration"),
            "duration_str": self._format_duration(info.get("duration")),
            "view_count": info.get("view_count") or info.get("playback_count"),
            "like_count": info.get("like_count") or info.get("favorit_count"),
            "thumbnail": info.get("thumbnail") or (info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None),
            "description": (info.get("description") or "")[:300],
            "genre": info.get("genre"),
            "tag_list": info.get("tag_list"),
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
