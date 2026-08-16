"""Pinterest downloader — Videos, Images, GIFs. Custom scraper + yt-dlp fallback."""
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename


class PinterestDownloader(BaseDownloader):
    """Download from Pinterest: Videos, Images, GIFs using custom scraping + yt-dlp."""

    PLATFORM = "pinterest"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def _extract_pin_id(self, url: str) -> str:
        """Extract pin ID from Pinterest URL."""
        match = re.search(r'/pin/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'pin/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def _resolve_short_url(self, url: str) -> str:
        """Resolve pin.it short URLs."""
        if "pin.it" in url:
            try:
                resp = self.session.head(url, allow_redirects=True, timeout=10)
                return resp.url
            except Exception:
                pass
        return url

    def _scrape_media(self, url: str) -> dict:
        """Scrape media URLs directly from Pinterest page."""
        url = self._resolve_short_url(url)
        result = {"success": False, "media_urls": [], "title": "", "error": None}

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Try to find JSON-LD structured data
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    if "contentUrl" in data:
                        result["media_urls"].append({
                            "url": data["contentUrl"],
                            "type": "video",
                        })
                    if "image" in data:
                        img = data["image"]
                        if isinstance(img, str):
                            result["media_urls"].append({"url": img, "type": "image"})
                        elif isinstance(img, list):
                            for i in img:
                                result["media_urls"].append({"url": i, "type": "image"})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            # Try og:video / og:image meta tags
            og_video = soup.find("meta", property="og:video") or soup.find("meta", property="og:video:url")
            if og_video and og_video.get("content"):
                result["media_urls"].append({
                    "url": og_video["content"],
                    "type": "video",
                })

            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                result["media_urls"].append({
                    "url": og_image["content"],
                    "type": "image",
                })

            # Title
            title_tag = soup.find("meta", property="og:title")
            if title_tag:
                result["title"] = title_tag.get("content", "pinterest_pin")

            # Try to extract from __PWS_DATA__ JSON
            for script in soup.find_all("script"):
                if script.string and "__PWS_DATA__" in (script.string or ""):
                    try:
                        match = re.search(r'__PWS_DATA__\s*=\s*({.+?})\s*;', script.string)
                        if match:
                            pws = json.loads(match.group(1))
                            self._extract_from_pws(pws, result)
                    except (json.JSONDecodeError, AttributeError):
                        pass

            # Deduplicate
            seen = set()
            unique = []
            for item in result["media_urls"]:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique.append(item)
            result["media_urls"] = unique

            result["success"] = len(result["media_urls"]) > 0
            if not result["success"]:
                result["error"] = "No media found on page"

        except requests.RequestException as e:
            result["error"] = f"Request failed: {str(e)}"

        return result

    def _extract_from_pws(self, data: dict, result: dict):
        """Recursively search PWS data for media URLs."""
        if isinstance(data, dict):
            for key, val in data.items():
                if key in ("url", "orig_url", "video_url") and isinstance(val, str):
                    if val.startswith("http"):
                        media_type = "video" if any(x in val.lower() for x in [".mp4", "video"]) else "image"
                        result["media_urls"].append({"url": val, "type": media_type})
                elif isinstance(val, (dict, list)):
                    self._extract_from_pws(val, result)
        elif isinstance(data, list):
            for item in data:
                self._extract_from_pws(item, result)

    def _download_url(self, url: str, media_type: str, title: str) -> dict:
        """Download a single media URL."""
        ext = ".mp4" if media_type == "video" else ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".gif" in url.lower():
            ext = ".gif"

        safe_title = sanitize_filename(title or "pinterest_pin")
        out_dir = os.path.join(self.output_dir, "pinterest")
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, f"{safe_title}{ext}")

        # Avoid overwriting
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(out_dir, f"{safe_title}_{counter}{ext}")
            counter += 1

        try:
            resp = self.session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return {
                "path": os.path.abspath(filepath),
                "size": os.path.getsize(filepath),
                "ext": ext,
            }
        except Exception as e:
            return {"error": str(e)}

    def download(self, url: str, quality: str = "best", **kwargs) -> dict:
        """Download Pinterest content — tries scraping first, then yt-dlp."""
        result = {"success": False, "files": [], "error": None, "info": {}}

        # Method 1: Custom scraping
        scraped = self._scrape_media(url)
        if scraped["success"]:
            result["info"]["title"] = scraped.get("title", "pinterest_pin")
            for media in scraped["media_urls"]:
                dl = self._download_url(media["url"], media["type"], scraped.get("title", ""))
                if "error" not in dl:
                    result["files"].append(dl)

            if result["files"]:
                result["success"] = True
                return result

        # Method 2: yt-dlp fallback
        output_tpl = os.path.join(
            self.output_dir,
            "pinterest",
            "%(title).100s_%(id)s.%(ext)s",
        )

        opts = {
            "outtmpl": output_tpl,
            "format": "best",
            "merge_output_format": "mp4",
            "writeinfojson": False,
        }

        fallback = self._ytdlp_download(url, opts)
        if fallback["success"]:
            return fallback

        # Combine errors
        result["error"] = f"Scraping: {scraped.get('error', 'failed')}. yt-dlp: {fallback.get('error', 'failed')}"
        return result

    # download_batch removed — use engine.download_batch for parallel downloads.

    def get_info(self, url: str) -> dict:
        """Get Pinterest content info."""
        url = self._resolve_short_url(url)
        scraped = self._scrape_media(url)
        if scraped["success"]:
            return {"success": True, "info": scraped}
        return self._ytdlp_extract_info(url)
