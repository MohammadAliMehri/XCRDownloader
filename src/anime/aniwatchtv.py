"""AniWatchTV provider."""
from typing import Dict, List, Optional, Any
import re
from .base import AnimeProvider
from ..network.client import fetch_text
from ..config import config as _config


class AniWatchTVProvider(AnimeProvider):
    name = "aniwatchtv"

    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        # Reuse the common WordPress search logic
        from . import _wp_search  # temporary import to avoid duplication
        return _wp_search("aniwatchtv", query)

    def episodes(self, anime_id: Optional[int] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
        if not page_url:
            return {"success": False, "error": "Missing page_url for AniWatchTV", "provider": "aniwatchtv"}
        try:
            from . import _extract_episodes  # temporary import to avoid duplication
            allowed = _config.anime_allowed_hosts.get("aniwatchtv", [])
            html_text = fetch_text(page_url, headers={"Referer": "https://aniwatchtv.com.ro/"}, allowed_hosts=allowed)
            eps = _extract_episodes(html_text, page_url)
            if not eps:
                return {"success": False, "error": "No episodes found on the series page", "provider": "aniwatchtv"}
            return {"success": True, "provider": "aniwatchtv", "episodes": eps,
                    "info": {"title": re.sub(r"[-_]", " ", page_url.rstrip("/").rsplit("/", 1)[-1]).title()}}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "aniwatchtv"}

    def stream(
        self,
        anime_id: Optional[int] = None,
        episode: int = 1,
        dub: bool = False,
        page_url: Optional[str] = None,
        episode_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not (episode_url or page_url):
            return {"success": False, "error": "Missing episode URL for AniWatchTV", "provider": "aniwatchtv"}
        if not episode_url:
            from . import _series_episode_url
            episode_url = _series_episode_url(page_url, episode)
        allowed = _config.anime_allowed_hosts.get("aniwatchtv", [])
        try:
            html_text = fetch_text(episode_url, headers={"Referer": "https://aniwatchtv.com.ro/"}, allowed_hosts=allowed)
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "aniwatchtv"}

        # Find gogoanime iframe
        m = re.search(r'data-litespeed-src="(https?://[^"]+)"', html_text)
        if not m:
            return {"success": False, "error": "No gogoanime iframe found", "provider": "aniwatchtv", "page_url": episode_url}
        gogo_url = m.group(1).strip()

        try:
            embed_html = fetch_text(gogo_url, headers={"Referer": episode_url}, allowed_hosts=allowed)
        except Exception:
            embed_html = ""

        # Extract megaplay iframe
        mp = re.search(r'<iframe[^>]+src="(https?://megaplay\.buzz/[^"]+)"', embed_html)
        if mp:
            return {"success": True, "player_url": mp.group(1).strip(), "embed_only": True,
                    "provider": "aniwatchtv", "page_url": episode_url}
        # Fallback to gogo iframe
        return {"success": True, "player_url": gogo_url, "embed_only": True,
                "provider": "aniwatchtv", "page_url": episode_url}