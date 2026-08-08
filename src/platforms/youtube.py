"""YouTube & YouTube Music downloader — Videos, Music, Playlists with embedded cover."""
import os
import sys
import yt_dlp
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename, format_filesize


class YouTubeDownloader(BaseDownloader):
    """Download from YouTube and YouTube Music: Videos, Audio, Playlists."""

    PLATFORM = "youtube"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)

    def _is_music_url(self, url: str) -> bool:
        """Check if URL is from YouTube Music."""
        return "music.youtube.com" in url.lower()

    def download(self, url: str, quality: str = "best", audio_only: bool = False,
                 playlist: bool = False, **kwargs) -> dict:
        """Download YouTube video or extract audio."""
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

        opts = {
            "outtmpl": output_tpl,
            "format": format_spec,
            "merge_output_format": "mp4",
            "writeinfojson": False,
            "writethumbnail": False,
            "noplaylist": not playlist,
            "ignoreerrors": True,
            "retries": 3,
            "fragment_retries": 3,
            "extractor_args": {
                "youtube": {
                    "player_client": ["mweb", "web"],
                }
            },
        }

        return self._ytdlp_download(url, opts)

    def _download_audio(self, url: str, category: str) -> dict:
        """Download audio only as high-quality MP3 with embedded cover art."""
        output_tpl = os.path.join(
            self.output_dir, category,
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
            "fragment_retries": 3,
            "extractor_args": {
                "youtube": {
                    "player_client": ["mweb", "web"],
                }
            },
        }

        result = self._ytdlp_download(url, opts)

        # Only keep audio files — thumbnail is now embedded
        if result.get("success"):
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
        """Get YouTube content info with rich metadata."""
        opts = {
            "extractor_args": {
                "youtube": {
                    "player_client": ["mweb", "web"],
                }
            },
        }
        raw = self._ytdlp_extract_info(url, opts)
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
