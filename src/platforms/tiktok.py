"""TikTok downloader — Videos, Slideshows, No Watermark."""
import os
import re
import requests
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename


class TikTokDownloader(BaseDownloader):
    """Download from TikTok: Videos without watermark, slideshows, audio."""

    PLATFORM = "tiktok"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        })

    def download(self, url: str, quality: str = "best", no_watermark: bool = True,
                 audio_only: bool = False, **kwargs) -> dict:
        """Download TikTok video without watermark."""
        output_tpl = os.path.join(
            self.output_dir,
            "tiktok",
            "%(uploader)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        if audio_only:
            format_spec = "bestaudio/best"
            output_tpl = output_tpl.replace(".%(ext)s", ".mp3")
            opts = {
                "outtmpl": output_tpl,
                "format": format_spec,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
            }
        else:
            format_spec = "best"
            if quality == "hd":
                format_spec = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            elif quality == "sd":
                format_spec = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"

            opts = {
                "outtmpl": output_tpl,
                "format": format_spec,
                "merge_output_format": "mp4",
            }

        # TikTok-specific: try to get no-watermark version
        if no_watermark:
            opts["extractor_args"] = {
                "tiktok": {
                    "api_hostname": ["api-h2.tiktokv.com"],
                }
            }

        opts["writeinfojson"] = False
        opts["writethumbnail"] = False

        return self._ytdlp_download(url, opts)

    def download_audio(self, url: str, **kwargs) -> dict:
        """Extract audio only from TikTok video."""
        return self.download(url, audio_only=True, **kwargs)

    def download_batch(self, urls: list, **kwargs) -> list:
        """Download multiple TikTok URLs."""
        results = []
        for url in urls:
            results.append(self.download(url, **kwargs))
        return results

    def get_info(self, url: str) -> dict:
        """Get TikTok content info without downloading."""
        return self._ytdlp_extract_info(url)
