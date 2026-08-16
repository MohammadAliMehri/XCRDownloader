"""Shared helpers for anime providers (temporary, will be refactored)."""
import re
import html
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from ..network.client import fetch_text, fetch_json
from ..config import config as _config
from ..logging import get_logger

logger = get_logger(__name__)

PROVIDER_LABELS = {
    "yomi": "Yomi",
    "aniwatchtv": "AniWatchTV",
    "f2mc": "Film2Media",
    "miruro": "Miruro",
}

_WP = {
    "f2mc": {"base": "https://www.f2mc.top"},
    "aniwatchtv": {"base": "https://aniwatchtv.com.ro"},
    "miruro": {"base": "https://miruro.ro"},
}

def _norm_wp(item: dict, provider: str, cover: str | None = None) -> dict:
    title_raw = item.get("title") or ""
    if isinstance(title_raw, dict):
        title_raw = title_raw.get("rendered") or ""
    title = html.unescape(re.sub(r"<[^>]+>", "", title_raw)).strip()
    return {
        "id": f"{provider}_{item.get('id')}",
        "provider": provider,
        "title": title or "Unknown",
        "url": item.get("url") or item.get("link") or "",
        "cover": cover,
        "subtype": item.get("subtype", ""),
        "kind": "anime",
    }

def _wp_search(provider: str, query: str, per_page: int = 15) -> List[Dict[str, Any]]:
    cfg = _WP.get(provider)
    if not cfg:
        return []
    base = cfg["base"]
    allowed = _config.anime_allowed_hosts.get(provider, [])
    logger.debug(f"WP search {provider} for '{query}'")
    if provider == "f2mc":
        try:
            items = fetch_json(f"{base}/wp-json/wp/v2/series?search={quote(query)}&per_page={per_page}&_embed=1",
                               allowed_hosts=allowed)
            out = []
            for i in items:
                fm = (i.get("_embedded") or {}).get("wp:featuredmedia") or [{}]
                cover = fm[0].get("source_url") if fm and fm[0] else None
                out.append(_norm_wp(i, provider, cover))
            if out:
                logger.debug(f"WP search {provider} returned {len(out)} results")
                return out
        except Exception as e:
            logger.warning(f"WP search {provider} f2mc failed: {e}")
    try:
        items = fetch_json(f"{base}/wp-json/wp/v2/search?search={quote(query)}&per_page={per_page}",
                           allowed_hosts=allowed)
    except Exception as e:
        logger.warning(f"WP search {provider} failed: {e}")
        return []
    logger.debug(f"WP search {provider} returned {len(items)} results")
    return [_norm_wp(i, provider) for i in items]

def _strip_random_slug_suffix(slug: str) -> str:
    m = re.search(r"-([a-z0-9]{3,6})$", slug)
    if m and any(ch.isdigit() for ch in m.group(1)):
        return slug[:m.start()]
    return slug

def _series_episode_url(page_url: str, episode: int) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(page_url)
    slug = _strip_random_slug_suffix(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    return f"{parsed.scheme}://{parsed.netloc}/{slug}-episode-{episode}/"

def _extract_episodes(html: str, page_url: str) -> List[Dict[str, Any]]:
    raw_slug = page_url.rstrip("/").rsplit("/", 1)[-1]
    series_slug = _strip_random_slug_suffix(raw_slug)
    pattern = re.compile(r'href="([^"]*-episode-(\d+)/)"')
    found = {}
    for full_url, num_str in pattern.findall(html):
        num = int(num_str)
        if num in found:
            continue
        url_path = full_url.rstrip("/").rsplit("/", 1)[-1]
        ep_slug = url_path.rsplit("-episode-", 1)[0]
        if ep_slug == series_slug or ep_slug.startswith(series_slug + "-") or ep_slug == raw_slug or ep_slug.startswith(raw_slug + "-"):
            found[num] = full_url
    return [{"episode": n, "title": f"Episode {n}", "url": found[n]} for n in sorted(found)]

def _fetch_og_image(page_url: str, provider: str | None = None) -> str | None:
    allowed = _config.anime_allowed_hosts.get(provider, []) if provider else []
    try:
        text = fetch_text(page_url, timeout=15, allowed_hosts=allowed)
        m = re.search(r'<meta\s+property=["\']og:image["\'][^\>]+content=["\']([^"\']+)["\']', text)
        if m:
            return m.group(1)
        m2 = re.search(r'<meta\s+content=["\']([^"\']+)["\'][^\>]+property=["\']og:image["\']', text)
        if m2:
            return m2.group(1)
    except Exception:
        pass
    return None

def _search_fanout(query: str, provider: str = "all", page: int = 1) -> dict:
    from . import registry
    if not query.strip():
        return {"results": [], "page": 1, "has_more": False, "provider": provider}
    provider = (provider or "all").lower()
    providers = []
    if provider == "all":
        providers = registry.all()
    else:
        p = registry.get(provider)
        if p:
            providers = [p]

    logger.info(f"Anime search '{query}' across {len(providers)} providers")
    results = []
    with ThreadPoolExecutor(max_workers=min(4, len(providers))) as pool:
        futures = [pool.submit(p.search, query, page) for p in providers]
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as e:
                logger.warning(f"Anime search provider failed: {e}")
                pass
    logger.info(f"Anime search returned {len(results)} raw results")

    # dedupe
    seen, unique = set(), []
    for r in results:
        key = f"{r['provider']}:{re.sub(r'[^a-z0-9]+', ' ', r['title'].lower()).strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # enrich covers for WP providers
    def _try_og_cover(item: dict) -> dict:
        if item.get("provider") in ("aniwatchtv", "miruro", "f2mc") and not item.get("cover") and item.get("url"):
            item = dict(item)
            item["cover"] = _fetch_og_image(item["url"], provider=item["provider"])
        return item

    with ThreadPoolExecutor(max_workers=3) as pool:
        unique = list(pool.map(_try_og_cover, unique[:12])) + unique[12:]

    return {"results": unique, "page": page, "has_more": len(unique) >= 20, "provider": provider}