"""Film2Media provider (download portal)."""
from typing import Dict, List, Optional, Any
from .base import AnimeProvider


class Film2MediaProvider(AnimeProvider):
    name = "f2mc"

    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        from . import _wp_search
        return _wp_search("f2mc", query)

    def episodes(self, anime_id: Optional[int] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
        return {"success": False,
                "error": "Film2Media is a download portal — open the post page for download links",
                "provider": "f2mc", "page_url": page_url or ""}

    def stream(
        self,
        anime_id: Optional[int] = None,
        episode: int = 1,
        dub: bool = False,
        page_url: Optional[str] = None,
        episode_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {"success": False,
                "error": "Film2Media is a download portal — open the post page for download links",
                "provider": "f2mc", "page_url": page_url or ""}