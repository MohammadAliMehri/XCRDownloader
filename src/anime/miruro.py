"""Miruro provider."""
from typing import Dict, List, Optional, Any
import re
import base64
from .base import AnimeProvider
from ..network.client import fetch_text
from ..config import config as _config


class MiruroProvider(AnimeProvider):
    name = "miruro"

    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        from . import _wp_search
        return _wp_search("miruro", query)

    def episodes(self, anime_id: Optional[int] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
        if not page_url:
            return {"success": False, "error": "Missing page_url for Miruro", "provider": "miruro"}
        try:
            from . import _extract_episodes
            allowed = _config.anime_allowed_hosts.get("miruro", [])
            html_text = fetch_text(page_url, headers={"Referer": "https://miruro.ro/"}, allowed_hosts=allowed)
            eps = _extract_episodes(html_text, page_url)
            if not eps:
                return {"success": False, "error": "No episodes found on the series page", "provider": "miruro"}
            return {"success": True, "provider": "miruro", "episodes": eps,
                    "info": {"title": re.sub(r"[-_]", " ", page_url.rstrip("/").rsplit("/", 1)[-1]).title()}}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "miruro"}

    def stream(
        self,
        anime_id: Optional[int] = None,
        episode: int = 1,
        dub: bool = False,
        page_url: Optional[str] = None,
        episode_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not (episode_url or page_url):
            return {"success": False, "error": "Missing episode URL for Miruro", "provider": "miruro"}
        if not episode_url:
            from . import _series_episode_url
            episode_url = _series_episode_url(page_url, episode)
        allowed = _config.anime_allowed_hosts.get("miruro", [])
        try:
            html_text = fetch_text(episode_url, headers={"Referer": "https://miruro.ro/"}, allowed_hosts=allowed)
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "miruro"}

        # Find dramastream iframe
        m = re.search(r'<iframe[^>]+src="([^"]*dramastream[^"]+)"', html_text)
        if not m:
            return {"success": False, "error": "No dramastream player iframe found", "provider": "miruro", "page_url": episode_url}
        iframe_src = m.group(1)

        # Decode url= param
        url_match = re.search(r'[?&]url=([^&]+)', iframe_src)
        if not url_match:
            return {"success": False, "error": "No url param found", "provider": "miruro", "page_url": episode_url}

        try:
            decoded = base64.b64decode(url_match.group(1)).decode("utf-8")
        except Exception:
            decoded = None

        if decoded and "megaplay.buzz" in decoded:
            return {"success": True, "player_url": decoded, "embed_only": True,
                    "provider": "miruro", "page_url": episode_url}
        return {"success": True, "player_url": iframe_src, "embed_only": True,
                "provider": "miruro", "page_url": episode_url}