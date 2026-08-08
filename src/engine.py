"""XCRDownloader Engine — dispatches URLs to the right platform handler."""
import os
import sys
import concurrent.futures
from typing import Union
from src.platforms.instagram import InstagramDownloader
from src.platforms.tiktok import TikTokDownloader
from src.platforms.twitter import TwitterDownloader
from src.platforms.pinterest import PinterestDownloader
from src.platforms.generic import GenericDownloader
from src.utils.helpers import detect_platform, extract_urls


class DownloaderEngine:
    """Central engine that routes URLs to platform-specific downloaders."""

    def __init__(self, output_dir: str = "downloads"):
        self.output_dir = output_dir
        self.downloaders = {
            "instagram": InstagramDownloader(output_dir),
            "tiktok": TikTokDownloader(output_dir),
            "twitter": TwitterDownloader(output_dir),
            "pinterest": PinterestDownloader(output_dir),
            "generic": GenericDownloader(output_dir),
        }

    def get_downloader(self, url: str):
        """Get the appropriate downloader for a URL."""
        platform = detect_platform(url)
        return self.downloaders.get(platform, self.downloaders["generic"]), platform

    def download(self, url: str, quality: str = "best", **kwargs) -> dict:
        """Download a single URL — auto-detects platform."""
        downloader, platform = self.get_downloader(url)
        result = downloader.download(url, quality=quality, **kwargs)
        result["platform"] = platform
        result["url"] = url
        return result

    def download_batch(self, urls: list, quality: str = "best",
                       max_workers: int = 3, **kwargs) -> list:
        """Download multiple URLs with parallel execution."""
        results = []

        def _dl(url):
            return self.download(url, quality=quality, **kwargs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_dl, url): url for url in urls}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "success": False,
                        "url": url,
                        "error": str(e),
                        "platform": detect_platform(url),
                    })

        return results

    def download_text(self, text: str, **kwargs) -> list:
        """Extract all URLs from text and download them."""
        urls = extract_urls(text)
        if not urls:
            return [{"success": False, "error": "No URLs found in text"}]
        return self.download_batch(urls, **kwargs)

    def get_info(self, url: str) -> dict:
        """Get info about a URL without downloading."""
        downloader, platform = self.get_downloader(url)
        result = downloader.get_info(url)
        result["platform"] = platform
        result["url"] = url
        return result

    def detect(self, url: str) -> dict:
        """Detect platform and return downloader info."""
        platform = detect_platform(url)
        return {
            "url": url,
            "platform": platform,
            "supported": True,
            "handler": self.downloaders[platform].__class__.__name__,
        }
