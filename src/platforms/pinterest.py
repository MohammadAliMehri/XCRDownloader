"""Pinterest downloader — Videos, Images, GIFs. Custom scraper + yt-dlp fallback."""
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from .base import BaseDownloader
from src.utils.helpers import sanitize_filename

# ---- Helpers for extracting from Pinterest relay/JSON payloads ----

def _balanced_json_object(text: str, start: int) -> str | None:
    """Return JSON object substring starting at text[start] == '{'."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None

RELAY_CALL_RE = re.compile(
    r"window\.__PWS_RELAY_REGISTER_COMPLETED_REQUEST__\(\s*\"([^\"]+)\"\s*,",
    re.S,
)

def _extract_relay_payloads(html: str) -> list:
    payloads = []
    for m in RELAY_CALL_RE.finditer(html):
        j = m.end()
        while j < len(html) and html[j].isspace():
            j += 1
        blob = _balanced_json_object(html, j)
        if blob:
            try:
                payloads.append(json.loads(blob))
            except json.JSONDecodeError:
                continue
    return payloads

def _walk_pins(obj) -> list:
    """Recursively find dicts that look like Pinterest Pin objects."""
    found = []

    def looks_like_pin(d):
        if any(k.startswith("images_") for k in d):
            return True
        if isinstance(d.get("images"), dict):
            return True
        if d.get("imageSignature") or d.get("image_signature"):
            return True
        if d.get("__typename") == "Pin":
            return True
        if isinstance(d.get("videos"), (dict, list)) and (d.get("entityId") or d.get("id")):
            return True
        return False

    def walk(o):
        if isinstance(o, dict):
            if looks_like_pin(o):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return found

def _collect_video_urls(pin: dict) -> list:
    """Collect progressive/HLS video URLs from classic or GraphQL pin payloads."""
    found = []

    def add(u):
        if isinstance(u, str) and u.startswith("http") and ("pinimg.com" in u or ".mp4" in u):
            if u not in found:
                found.append(u)

    videos = pin.get("videos")
    if isinstance(videos, dict):
        for key in ("videoUrls", "video_urls"):
            raw = videos.get(key)
            if isinstance(raw, list):
                for u in raw:
                    add(u)
        vlist = videos.get("video_list") or videos.get("videoList") or {}
        if isinstance(vlist, dict):
            for key, fmt in vlist.items():
                if key in {"__typename", "id", "type"}:
                    continue
                if isinstance(fmt, dict):
                    add(fmt.get("url"))
                    add(fmt.get("thumbnail"))
                elif isinstance(fmt, str):
                    add(fmt)
        for key, val in videos.items():
            if isinstance(val, str) and ("/videos/" in val or val.endswith(".mp4")):
                add(val)
    elif isinstance(videos, list):
        for entry in videos:
            if isinstance(entry, str):
                add(entry)
            elif isinstance(entry, dict):
                add(entry.get("url"))

    # story pins
    story = pin.get("storyPinData") or pin.get("story_pin_data")
    if isinstance(story, dict):
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in {"url", "videoUrl", "video_url"} and isinstance(v, str):
                        add(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(story)

    return found

def _rank_video_url(url: str) -> tuple:
    """Lower is better. Prefer progressive H.264 720p MP4."""
    ul = url.lower()
    score = 100
    if ul.endswith(".m3u8") or "/hls/" in ul or "/h265/" in ul:
        score += 10000
    if not (ul.endswith(".mp4") or ".mp4?" in ul):
        score += 5000
    if "/720p/" in ul:
        score -= 200
    if re.search(r"/\d{3,4}p/", ul) and "/720p/" not in ul:
        score -= 80
    if "hevc" in ul:
        score += 120
    if "expmp4" in ul:
        score += 90
    if re.search(r"_t\d+\.mp4(?:\?|$)", ul):
        score += 150
    return score, -len(url)

def _pick_best_video_url(urls: list) -> str | None:
    if not urls:
        return None
    mp4s = [u for u in urls if u.lower().endswith(".mp4") or ".mp4?" in u.lower()]
    pool = mp4s or urls
    return sorted(pool, key=_rank_video_url)[0]


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
        match = re.search(r'/pin/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'pin/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def _resolve_short_url(self, url: str) -> str:
        if "pin.it" in url:
            try:
                resp = self.session.head(url, allow_redirects=True, timeout=10)
                return resp.url
            except Exception:
                pass
        return url

    def _extract_media_from_html(self, html: str, source_url: str) -> dict:
        """Extract media URLs using relay payloads, PWS data, and meta tags."""
        result = {"media_urls": [], "title": "", "error": None}

        # 1) Relay payloads (most reliable)
        for payload in _extract_relay_payloads(html):
            for pin in _walk_pins(payload):
                video_urls = _collect_video_urls(pin)
                best_video = _pick_best_video_url(video_urls)
                if best_video:
                    result["media_urls"].append({"url": best_video, "type": "video"})
                # Also grab any image from pin
                images = pin.get("images") or {}
                for key, val in images.items():
                    if isinstance(val, dict) and val.get("url"):
                        img_url = val["url"]
                        if img_url not in [m["url"] for m in result["media_urls"]]:
                            result["media_urls"].append({"url": img_url, "type": "image"})
                # title
                title = pin.get("gridTitle") or pin.get("title") or pin.get("seoTitle") or ""
                if title and not result["title"]:
                    result["title"] = title

        # 2) Parse __PWS_DATA__ (fallback)
        pws_match = re.search(r'__PWS_DATA__\s*=\s*({.+?})\s*;', html, re.S)
        if pws_match:
            try:
                pws = json.loads(pws_match.group(1))
                # recursively extract URLs
                def walk(o):
                    if isinstance(o, dict):
                        for k, v in o.items():
                            if k in ("url", "orig_url", "video_url") and isinstance(v, str) and v.startswith("http"):
                                media_type = "video" if any(x in v.lower() for x in [".mp4", "video"]) else "image"
                                if v not in [m["url"] for m in result["media_urls"]]:
                                    result["media_urls"].append({"url": v, "type": media_type})
                            else:
                                walk(v)
                    elif isinstance(o, list):
                        for item in o:
                            walk(item)
                walk(pws)
            except json.JSONDecodeError:
                pass

        # 3) OG meta tags
        soup = BeautifulSoup(html, "lxml")
        og_video = soup.find("meta", property="og:video") or soup.find("meta", property="og:video:url")
        if og_video and og_video.get("content"):
            vurl = og_video["content"]
            if vurl not in [m["url"] for m in result["media_urls"]]:
                result["media_urls"].append({"url": vurl, "type": "video"})

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            iurl = og_image["content"]
            if iurl not in [m["url"] for m in result["media_urls"]]:
                result["media_urls"].append({"url": iurl, "type": "image"})

        # Title from meta
        title_tag = soup.find("meta", property="og:title")
        if title_tag and title_tag.get("content") and not result["title"]:
            result["title"] = title_tag["content"]

        # If we have no title, fallback
        if not result["title"]:
            title_tag = soup.find("meta", property="twitter:title")
            if title_tag and title_tag.get("content"):
                result["title"] = title_tag["content"]

        # Deduplicate
        seen = set()
        unique = []
        for item in result["media_urls"]:
            if item["url"] not in seen:
                seen.add(item["url"])
                unique.append(item)
        result["media_urls"] = unique

        if not result["media_urls"]:
            result["error"] = "No media found on page"

        return result

    def _scrape_media(self, url: str) -> dict:
        """Scrape media URLs directly from Pinterest page."""
        url = self._resolve_short_url(url)
        result = {"success": False, "media_urls": [], "title": "", "error": None}

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            html = resp.text

            extracted = self._extract_media_from_html(html, url)
            result["media_urls"] = extracted.get("media_urls", [])
            result["title"] = extracted.get("title", "pinterest_pin")
            result["success"] = len(result["media_urls"]) > 0
            if not result["success"]:
                result["error"] = extracted.get("error", "No media found")
        except requests.RequestException as e:
            result["error"] = f"Request failed: {str(e)}"

        return result

    def _download_url(self, url: str, media_type: str, title: str) -> dict:
        """Download a single media URL using requests."""
        ext = ".mp4" if media_type == "video" else ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".gif" in url.lower():
            ext = ".gif"

        safe_title = sanitize_filename(title or "pinterest_pin")
        out_dir = os.path.join(self.output_dir, "pinterest")
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, f"{safe_title}{ext}")

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
            "headers": self.session.headers,
        }

        fallback = self._ytdlp_download(url, opts)
        if fallback["success"]:
            return fallback

        result["error"] = f"Scraping: {scraped.get('error', 'failed')}. yt-dlp: {fallback.get('error', 'failed')}"
        return result

    def get_info(self, url: str) -> dict:
        """Get Pinterest content info."""
        url = self._resolve_short_url(url)
        scraped = self._scrape_media(url)
        if scraped["success"]:
            return {"success": True, "info": scraped}
        return self._ytdlp_extract_info(url)