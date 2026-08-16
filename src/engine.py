"""XCRDownloader Engine — dispatches URLs to the right platform handler."""
import os
import sys
import concurrent.futures
from typing import Union
from src.platforms.instagram import InstagramDownloader
from src.platforms.tiktok import TikTokDownloader
from src.platforms.twitter import TwitterDownloader
from src.platforms.pinterest import PinterestDownloader
from src.platforms.youtube import YouTubeDownloader
from src.platforms.soundcloud import SoundCloudDownloader
from src.platforms.generic import GenericDownloader
from src.utils.helpers import detect_platform, extract_urls
from src.logging import get_logger

logger = get_logger(__name__)


class DownloaderEngine:
    """Central engine that routes URLs to platform-specific downloaders."""

    def __init__(self, output_dir: str = "downloads"):
        self.output_dir = output_dir
        # Lazy initialization: store class references, not instances.
        self._downloader_classes = {
            "instagram": InstagramDownloader,
            "tiktok": TikTokDownloader,
            "twitter": TwitterDownloader,
            "pinterest": PinterestDownloader,
            "youtube": YouTubeDownloader,
            "soundcloud": SoundCloudDownloader,
            "generic": GenericDownloader,
        }
        self._downloaders = {}

    def _get_downloader_instance(self, platform: str):
        """Get or create a downloader instance for the platform."""
        if platform not in self._downloaders:
            cls = self._downloader_classes.get(platform)
            if not cls:
                # Fallback to generic
                cls = self._downloader_classes["generic"]
            # Instantiate with output_dir
            self._downloaders[platform] = cls(self.output_dir)
        return self._downloaders[platform]

    def get_downloader(self, url: str):
        """Get the appropriate downloader for a URL."""
        platform = detect_platform(url)
        # Use the same fallback logic as detect()
        if platform not in self._downloader_classes:
            platform = "generic"
        return self._get_downloader_instance(platform), platform

    def download(self, url: str, quality: str = "best", **kwargs) -> dict:
        """Download a single URL — auto-detects platform."""
        downloader, platform = self.get_downloader(url)
        logger.info(f"Downloading {url} with platform {platform} quality {quality}")
        try:
            result = downloader.download(url, quality=quality, **kwargs)
        except Exception as e:
            logger.error(f"Download error for {url}: {e}")
            result = {
                "success": False,
                "error": _humanize_error(str(e)),
                "files": [],
                "info": {},
            }
        # If the provider returned a success=False dict with an error, humanize it
        if not result.get("success") and result.get("error"):
            result["error"] = _humanize_error(str(result["error"]))
            logger.warning(f"Download failed for {url}: {result['error']}")
        result["platform"] = platform
        result["url"] = url
        return result

    def download_batch(self, urls: list, quality: str = "best",
                       max_workers: int = 3, **kwargs) -> list:
        """Download multiple URLs with parallel execution, preserving input order."""
        # Map each url to its index
        url_to_index = {url: i for i, url in enumerate(urls)}
        results_dict = {}

        def _dl(url):
            return self.download(url, quality=quality, **kwargs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_dl, url): url for url in urls}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                    # Ensure result has url field
                    result.setdefault("url", url)
                    results_dict[url_to_index[url]] = result
                except Exception as e:
                    results_dict[url_to_index[url]] = {
                        "success": False,
                        "url": url,
                        "error": _humanize_error(str(e)),
                        "platform": detect_platform(url),
                    }

        # Reconstruct in original order
        return [results_dict[i] for i in range(len(urls))]

    def download_text(self, text: str, **kwargs) -> list:
        """Extract all URLs from text and download them."""
        urls = extract_urls(text)
        if not urls:
            return [{"success": False, "error": "No URLs found in text"}]
        return self.download_batch(urls, **kwargs)

    def get_info(self, url: str) -> dict:
        """Get info about a URL without downloading (preview)."""
        downloader, platform = self.get_downloader(url)
        try:
            result = downloader.get_info(url)
        except Exception as e:
            result = {"success": False, "error": _humanize_error(str(e)), "info": {}}
        result["platform"] = platform
        result["url"] = url
        return result

    def detect(self, url: str) -> dict:
        """Detect platform and return downloader info."""
        platform = detect_platform(url)
        if platform not in self._downloader_classes:
            platform = "generic"
        downloader = self._get_downloader_instance(platform)
        return {
            "url": url,
            "platform": platform,
            "supported": True,
            "handler": downloader.__class__.__name__,
        }


# -- Error humanizer --
_ERROR_MAP = {
    "HTTP Error 403": "Access forbidden — video may be private or region-locked",
    "HTTP Error 404": "Content not found — URL may be invalid or deleted",
    "HTTP Error 429": "Rate limited — too many requests, try again later",
    "HTTP Error 503": "Service unavailable — platform may be blocking automated access",
    "Video unavailable": "This video is unavailable or has been removed",
    "Private video": "This is a private video — cannot download without access",
    "Sign in to confirm your age": "Age-restricted content — login required",
    "This video is not available": "Video is not available in your region",
    "Login required": "This content requires a login to access",
    "Geo-restricted": "This content is geo-restricted in your region",
    "ffmpeg": "FFmpeg error — ensure ffmpeg is installed and in PATH",
    "urlopen error": "Network error — check your internet connection",
    "timeout": "Connection timed out — try again or check your network",
    "certificate": "SSL certificate error — network may be blocking the request",
}


def _humanize_error(raw: str) -> str:
    """Map raw yt-dlp / network errors to human-readable messages."""
    raw_lower = raw.lower()
    for key, human in _ERROR_MAP.items():
        if key.lower() in raw_lower:
            return human
    return raw[:300]
