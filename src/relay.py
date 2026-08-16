"""Media relay helpers for HLS streaming and CDN unwrapping."""
import ipaddress
import re
import socket
import logging
from urllib.parse import quote, urljoin, urlparse

import requests
from flask import Response, stream_with_context

from src.config import config

logger = logging.getLogger(__name__)

_MEDIA_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# MegaPlay stores segments on TikTok's ad CDN wrapped in a 252-byte header.
# They must be fetched through the player's proxy host and de-wrapped.
_STRIP_HOSTS = ("tiktokcdn.com", "ibyteimg.com", "ipstatp.com", "yoot.trycloud.pro")
_STRIP_BYTES = 252
_TIKTOK_PROXY_HOST = "yoot.trycloud.pro"

# Allowed hosts for the media relay (exact or suffix match)
_ALLOWED_RELAY_HOSTS = tuple(config.relay_allowed_hosts)


def _media_fetch_url(url: str) -> tuple[str, bool]:
    """Return (fetch_url, strip_first_bytes) for an upstream media URL."""
    host = urlparse(url).hostname or ""
    if any(h in host for h in _STRIP_HOSTS):
        parsed = urlparse(url)
        proxy = f"https://{_TIKTOK_PROXY_HOST}{parsed.path}"
        if parsed.query:
            proxy += "?" + parsed.query
        proxy += ("&" if "?" in proxy else "?") + f"domain={host}"
        return proxy, True
    return url, False


def _is_allowed_relay_host(host: str) -> bool:
    """Check if the host is in the allowed list (exact or suffix match)."""
    if not host:
        return False
    host = host.lower()
    for allowed in _ALLOWED_RELAY_HOSTS:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def _media_url_allowed(url: str) -> bool:
    """Reject non-http, private/loopback hosts, and hosts not in the allow-list."""
    if not url.startswith(("http://", "https://")):
        return False
    try:
        host = urlparse(url).hostname or ""
        if not _is_allowed_relay_host(host):
            logger.warning(f"Relay blocked host {host} for URL {url}")
            return False
        ip = socket.gethostbyname(host)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            logger.warning(f"Relay blocked private IP {ip} for URL {url}")
            return False
        return True
    except Exception as e:
        logger.error(f"Relay validation error for {url}: {e}")
        return False


def _relay_url(url: str, referer: str) -> str:
    return f"/api/anime/media?url={quote(url, safe='')}&ref={quote(referer, safe='')}"


def _rewrite_playlist(text: str, base_url: str, referer: str) -> str:
    """Rewrite every URI in an HLS playlist to go through the local relay."""
    base = base_url.rsplit("/", 1)[0] + "/"
    out = []

    def relay(u: str) -> str:
        abs_url = u if u.startswith("http") else urljoin(base, u)
        return _relay_url(abs_url, referer)

    def fix_tag(match: re.Match) -> str:
        return f'URI="{relay(match.group(1))}"'

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            out.append(re.sub(r'URI="([^"]+)"', fix_tag, line))
        else:
            out.append(relay(line))
    return "\n".join(out) + "\n"


def _safe_fetch_url(url: str, headers: dict, timeout: int = 30, max_redirects: int = 10):
    """Fetch a URL with manual redirect validation. Raises ValueError on blocked redirect."""
    logger.debug(f"Fetching relay URL: {url}")
    for redirect_count in range(max_redirects):
        if not _media_url_allowed(url):
            raise ValueError(f"Blocked URL: {url}")
        resp = requests.get(url, headers=headers, stream=True, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                resp.close()
                raise ValueError("Redirect missing Location header")
            # Resolve relative redirects
            if not location.startswith(("http://", "https://")):
                location = urljoin(resp.url, location)
            logger.debug(f"Relay redirect {redirect_count+1}: {url} -> {location}")
            url = location
            resp.close()
            continue
        return resp
    raise ValueError("Too many redirects")


def _strip_wrapper_stream(response, strip_bytes: int = 252):
    """Stream a response body, stripping the first `strip_bytes` bytes after buffering."""
    buffer = b""
    stripped = False
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        buffer += chunk
        if not stripped and len(buffer) >= strip_bytes:
            # We have enough bytes to strip
            yield buffer[strip_bytes:]
            buffer = b""
            stripped = True
        elif stripped:
            yield buffer
            buffer = b""
    # Any remaining buffer after the loop
    if buffer and stripped:
        yield buffer
    # If we never stripped (response shorter than strip_bytes), we yield nothing
    # This matches the intention: discard the wrapper, no payload