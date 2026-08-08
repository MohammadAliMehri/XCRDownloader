from .instagram import InstagramDownloader
from .tiktok import TikTokDownloader
from .twitter import TwitterDownloader
from .pinterest import PinterestDownloader
from .generic import GenericDownloader

__all__ = [
    "InstagramDownloader",
    "TikTokDownloader",
    "TwitterDownloader",
    "PinterestDownloader",
    "GenericDownloader",
]
