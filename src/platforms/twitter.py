"""X/Twitter downloader — Videos, Images, GIFs."""
import os
import re
import requests
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename


class TwitterDownloader(BaseDownloader):
    """Download from X/Twitter: Videos, Images, GIFs."""

    PLATFORM = "twitter"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        })

    def download(self, url: str, quality: str = "best", media_type: str = "all",
                 **kwargs) -> dict:
        """Download X/Twitter media."""
        # Normalize x.com -> twitter.com for yt-dlp compatibility
        normalized = url.replace("x.com", "twitter.com")

        output_tpl = os.path.join(
            self.output_dir,
            "twitter",
            "%(uploader)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        format_spec = self._build_format_spec(quality, audio_only=False)

        opts = {
            "outtmpl": output_tpl,
            "format": format_spec,
            "merge_output_format": "mp4",
            "writeinfojson": False,
            "writethumbnail": False,
        }

        return self._ytdlp_download(normalized, opts)

    def download_images(self, url: str, **kwargs) -> dict:
        """Download images from a tweet."""
        normalized = url.replace("x.com", "twitter.com")

        output_tpl = os.path.join(
            self.output_dir,
            "twitter",
            "%(uploader)s",
            "images_%(title).80s_%(id)s.%(ext)s",
        )

        opts = {
            "outtmpl": output_tpl,
            "format": "best",
            "writeinfojson": False,
            "writethumbnail": False,
            "write_thumbnail": False,
        }

        return self._ytdlp_download(normalized, opts)

    # download_batch removed — use engine.download_batch for parallel downloads.

    def get_info(self, url: str) -> dict:
        """Get X/Twitter content info without downloading."""
        normalized = url.replace("x.com", "twitter.com")
        return self._ytdlp_extract_info(normalized)
