from .instagram import InstagramDownloader
from .tiktok import TikTokDownloader
from .twitter import TwitterDownloader
from .pinterest import PinterestDownloader
from .youtube import YouTubeDownloader
from .soundcloud import SoundCloudDownloader
from .generic import GenericDownloader

__all__ = [
    "InstagramDownloader",
    "TikTokDownloader",
    "TwitterDownloader",
    "PinterestDownloader",
    "YouTubeDownloader",
    "SoundCloudDownloader",
    "GenericDownloader",
]
