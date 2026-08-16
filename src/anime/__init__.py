"""Anime provider package."""

from .base import AnimeProvider
from .registry import registry
from .yomi import YomiProvider
from .aniwatchtv import AniWatchTVProvider
from .miruro import MiruroProvider
from .film2media import Film2MediaProvider

# Register providers
registry.register(YomiProvider())
registry.register(AniWatchTVProvider())
registry.register(MiruroProvider())
registry.register(Film2MediaProvider())

# Expose public API via registry
def search_anime(query: str, provider: str = "all", page: int = 1) -> dict:
    """Search anime across providers."""
    from . import _search_fanout
    return _search_fanout(query, provider, page)

def get_anime_episodes(provider: str = "yomi", anime_id: int | None = None,
                       page_url: str | None = None) -> dict:
    """Get episodes for an anime from a provider."""
    prov = registry.get(provider)
    if not prov:
        return {"success": False, "error": f"Unknown provider: {provider}"}
    return prov.episodes(anime_id=anime_id, page_url=page_url)

def get_anime_stream(provider: str = "yomi", anime_id: int | None = None,
                     episode: int = 1, dub: bool = False,
                     page_url: str | None = None,
                     episode_url: str | None = None) -> dict:
    """Get stream for an episode."""
    prov = registry.get(provider)
    if not prov:
        return {"success": False, "error": f"Unknown provider: {provider}"}
    return prov.stream(anime_id=anime_id, episode=episode, dub=dub,
                       page_url=page_url, episode_url=episode_url)

# Import shared helpers from the old module to avoid duplication
# These will be moved later.
from ._shared import (
    _wp_search,
    _extract_episodes,
    _series_episode_url,
    _search_fanout,
    PROVIDER_LABELS,
)

# Backward compatibility for tests
from src.config import config as _config
_ALLOWED_ANIME_HOSTS = _config.anime_allowed_hosts

def _is_allowed_anime_host(provider: str, url: str) -> bool:
    """Check if URL host is allowed for provider."""
    from urllib.parse import urlparse
    if not provider or not url:
        return False
    host = urlparse(url).hostname or ""
    if not host:
        return False
    host = host.lower()
    allowed = _ALLOWED_ANIME_HOSTS.get(provider, [])
    for a in allowed:
        if host == a or host.endswith("." + a):
            return True
    return False