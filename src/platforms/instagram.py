"""Instagram downloader — Reels, Stories, Posts, IGTV."""
import os
import re
import requests
from bs4 import BeautifulSoup
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename


class InstagramDownloader(BaseDownloader):
    """Download from Instagram: Reels, Posts, Stories, IGTV."""

    PLATFORM = "instagram"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def detect_type(self, url: str) -> str:
        """Detect content type from URL."""
        if "/reel/" in url or "/reels/" in url:
            return "reel"
        elif "/stories/" in url:
            return "story"
        elif "/tv/" in url:
            return "igtv"
        elif "/p/" in url:
            return "post"
        elif "/explore/" in url:
            return "explore"
        return "post"

    def download(self, url: str, quality: str = "best", **kwargs) -> dict:
        """Download Instagram content."""
        content_type = self.detect_type(url)
        output_tpl = os.path.join(
            self.output_dir,
            "instagram",
            "%(uploader)s",
            f"{content_type}_%(title).80s_%(id)s.%(ext)s",
        )

        format_spec = self._build_format_spec(quality, audio_only=False)

        opts = {
            "outtmpl": output_tpl,
            "format": format_spec,
            "merge_output_format": "mp4",
            "writeinfojson": False,
            "writethumbnail": False,
            "extractor_args": {
                "instagram": {
                    "login_required": ["false"],
                }
            },
        }

        return self._ytdlp_download(url, opts)

    # download_batch removed — use engine.download_batch for parallel downloads.

    def get_info(self, url: str) -> dict:
        """Get Instagram content info without downloading."""
        return self._ytdlp_extract_info(url)
