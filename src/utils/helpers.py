"""Utility helpers for XCRDownloader."""
import os
import re
import unicodedata
from urllib.parse import urlparse


PLATFORM_PATTERNS = {
    "instagram": [
        r"instagram\.com",
        r"instagr\.am",
    ],
    "tiktok": [
        r"tiktok\.com",
        r"vm\.tiktok\.com",
        r"vt\.tiktok\.com",
    ],
    "pinterest": [
        r"pinterest\.(com|ca|co\.uk|fr|de|it|es|ru|jp|kr|au|in|nz)",
        r"pin\.it",
    ],
    "twitter": [
        r"twitter\.com",
        r"(?:^|(?<=/))x\.com",
        r"t\.co",
    ],
}


def detect_platform(url: str) -> str:
    """Detect which social media platform a URL belongs to."""
    url_lower = url.lower()
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return platform
    return "generic"


def sanitize_filename(name: str, max_len: int = 200) -> str:
    """Sanitize a string for use as a filename."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name)
    if len(name) > max_len:
        name = name[:max_len]
    return name or "download"


def get_media_info(filepath: str) -> dict:
    """Get basic info about a downloaded file."""
    if not os.path.exists(filepath):
        return {"error": "File not found"}
    stat = os.stat(filepath)
    return {
        "path": os.path.abspath(filepath),
        "size": stat.st_size,
        "size_human": format_filesize(stat.st_size),
        "extension": os.path.splitext(filepath)[1].lower(),
    }


def format_filesize(size_bytes: int) -> str:
    """Format bytes into human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def extract_urls(text: str) -> list:
    """Extract all URLs from a text string."""
    url_pattern = r'https?://[^\s<>"\')\]]+'
    return re.findall(url_pattern, text)


def print_banner():
    """Print the XCRDownloader banner."""
    banner = """
\033[36m╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ██╗  ██╗ ██████╗██████╗ ██████╗  ██████╗ ██╗    ██╗   ║
║   ╚██╗██╔╝██╔════╝██╔══██╗██╔══██╗██╔═══██╗██║    ██║   ║
║    ╚███╔╝ ██║     ██████╔╝██║  ██║██║   ██║██║ █╗ ██║   ║
║    ██╔██╗ ██║     ██╔══██╗██║  ██║██║   ██║██║███╗██║   ║
║   ██╔╝ ██╗╚██████╗██║  ██║██████╔╝╚██████╔╝╚███╔███╔╝   ║
║   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝  ╚═════╝  ╚══╝╚══╝   ║
║                                                          ║
║   ⚡ Universal Social Media Downloader v1.0.0             ║
║   📥 Instagram · TikTok · X/Twitter · Pinterest          ║
║   🔓 Free · Unlimited · No API Keys Required             ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝\033[0m"""
    print(banner)
