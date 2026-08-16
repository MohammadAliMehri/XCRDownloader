"""Base class for anime providers."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class AnimeProvider(ABC):
    """Abstract base class for anime search and streaming providers."""

    @abstractmethod
    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """Search for anime by query."""
        pass

    @abstractmethod
    def episodes(self, anime_id: Optional[int] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
        """Get episode list for an anime."""
        pass

    @abstractmethod
    def stream(
        self,
        anime_id: Optional[int] = None,
        episode: int = 1,
        dub: bool = False,
        page_url: Optional[str] = None,
        episode_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get stream URL or embed info for an episode."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    def supports_dub(self) -> bool:
        """Whether this provider supports dubbed audio."""
        return False