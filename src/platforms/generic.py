"""Generic downloader — handles any URL via yt-dlp (1800+ sites)."""
import os
from .base import BaseDownloader


class GenericDownloader(BaseDownloader):
    """Generic downloader using yt-dlp for any supported URL."""

    PLATFORM = "generic"

    def download(self, url: str, quality: str = "best", audio_only: bool = False,
                 **kwargs) -> dict:
        """Download from any yt-dlp supported URL."""
        output_tpl = os.path.join(
            self.output_dir,
            "other",
            "%(extractor_key)s",
            "%(uploader|Unknown)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        if audio_only:
            opts = {
                "outtmpl": output_tpl.replace(".%(ext)s", ".mp3"),
                "format": "bestaudio/best",
                "postprocessors": self._build_audio_postprocessors(),
                "writeinfojson": False,
            }
        else:
            format_spec = self._build_format_spec(quality, audio_only=False)

            opts = {
                "outtmpl": output_tpl,
                "format": format_spec,
                "merge_output_format": "mp4",
                "writeinfojson": False,
                "writethumbnail": False,
            }

        return self._ytdlp_download(url, opts)

    def get_info(self, url: str) -> dict:
        """Get info from any URL."""
        return self._ytdlp_extract_info(url)
