"""Yomi provider (AniList + MegaPlay)."""
from typing import Dict, List, Optional, Any
import re
from .base import AnimeProvider
from ..network.client import fetch_text, fetch_json, post_json
from ..config import config as _config


class YomiProvider(AnimeProvider):
    name = "yomi"

    # AniList GraphQL queries
    _ANILIST_SEARCH = """query($s:String,$page:Int){Page(page:$page,perPage:24){
    media(search:$s,type:ANIME,isAdult:false){
    id title{romaji english native} coverImage{extraLarge large} bannerImage
    episodes duration format seasonYear averageScore popularity genres
    description(asHtml:false) status
    }}}"""

    _ANILIST_BY_ID = """query($id:Int){Media(id:$id,type:ANIME){
    id title{romaji english native} coverImage{extraLarge large} bannerImage
    episodes duration format seasonYear averageScore popularity genres
    description(asHtml:false) status
    }}"""

    def _anilist(self, query: str, variables: dict) -> dict:
        allowed = _config.anime_allowed_hosts.get("yomi", [])
        return post_json("https://graphql.anilist.co", {"query": query, "variables": variables},
                         allowed_hosts=allowed)

    def _norm_anilist(self, media: dict) -> dict:
        t = media.get("title") or {}
        title = t.get("english") or t.get("romaji") or t.get("native") or "Unknown"
        cover = (media.get("coverImage") or {}).get("extraLarge") or (media.get("coverImage") or {}).get("large")
        return {
            "id": f"yomi_{media.get('id')}",
            "provider": "yomi",
            "anime_id": media.get("id"),
            "title": title,
            "alt_title": t.get("romaji") or "",
            "cover": cover,
            "banner": media.get("bannerImage"),
            "episodes": media.get("episodes"),
            "duration": media.get("duration"),
            "format": media.get("format"),
            "year": media.get("seasonYear"),
            "score": media.get("averageScore"),
            "popularity": media.get("popularity"),
            "genres": media.get("genres") or [],
            "description": re.sub(r"<[^>]+>", " ", media.get("description") or "").strip()[:600],
            "status": media.get("status"),
            "kind": "anime",
        }

    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        try:
            data = self._anilist(self._ANILIST_SEARCH, {"s": query, "page": page})
        except Exception:
            return []
        out = []
        for media in (data.get("data") or {}).get("Page", {}).get("media") or []:
            if media:
                out.append(self._norm_anilist(media))
        return out

    def episodes(self, anime_id: Optional[int] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
        if not anime_id:
            return {"success": False, "error": "Missing anime_id for Yomi"}
        try:
            data = self._anilist(self._ANILIST_BY_ID, {"id": int(anime_id)})
            media = (data.get("data") or {}).get("Media") or {}
            info = self._norm_anilist(media)
            count = media.get("episodes") or 0
            eps = [{"episode": i, "title": f"Episode {i}"}
                   for i in range(1, min(count, 1000) + 1)] if 0 < count <= 5000 else []
            if not eps:
                return {"success": False, "error": "No episode data on AniList", "provider": "yomi"}
            return {"success": True, "provider": "yomi", "info": info, "episodes": eps}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "yomi"}

    def stream(
        self,
        anime_id: Optional[int] = None,
        episode: int = 1,
        dub: bool = False,
        page_url: Optional[str] = None,
        episode_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if anime_id is None:
            return {"success": False, "error": "Missing anime_id for Yomi provider"}
        lang = "dub" if dub else "sub"
        page_url = f"https://megaplay.buzz/stream/ani/{anime_id}/{episode}/{lang}"
        allowed = _config.anime_allowed_hosts.get("yomi", [])
        try:
            html_text = fetch_text(page_url, headers={"Referer": "https://yomi.to/"}, allowed_hosts=allowed)
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "yomi", "player_url": page_url}
        m = re.search(r'data-id="(\d+)"', html_text)
        if not m:
            return {"success": False,
                    "error": "Episode not found on the stream host",
                    "provider": "yomi", "player_url": page_url}
        try:
            data = fetch_json(
                f"https://megaplay.buzz/stream/getSourcesNew?id={m.group(1)}",
                headers={"Referer": "https://megaplay.buzz/", "X-Requested-With": "XMLHttpRequest"},
                allowed_hosts=allowed,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)[:160], "provider": "yomi", "player_url": page_url}
        file_url = ((data.get("sources") or {}).get("file") or "").strip()
        tracks = []
        for i, t in enumerate(data.get("tracks") or []):
            tf = (t.get("file") or "").strip()
            if tf:
                tracks.append({"label": t.get("label") or f"Subtitle {i + 1}", "file": tf})
        if not file_url:
            return {"success": False, "error": "No playable source returned",
                    "provider": "yomi", "player_url": page_url}
        return {
            "success": True,
            "stream_url": file_url,
            "subtitles": tracks,
            "referer": "https://megaplay.buzz/",
            "provider": "yomi",
            "player_url": page_url,
        }

    @property
    def supports_dub(self) -> bool:
        return True