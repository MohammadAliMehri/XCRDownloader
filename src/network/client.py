"""Shared HTTP client with timeout, retries, and redirect validation."""

import logging
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Default timeout and retry settings
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.0


def _is_host_allowed(host: str, allowed_hosts: List[str]) -> bool:
    """Check if host is in allowed list (exact or suffix match)."""
    if not host or not allowed_hosts:
        return False
    host = host.lower()
    for allowed in allowed_hosts:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def _validate_url(url: str, allowed_hosts: List[str]) -> bool:
    """Validate that the URL's host is allowed."""
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    host = urlparse(url).hostname or ""
    return _is_host_allowed(host, allowed_hosts)


def _safe_fetch_url(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_hosts: Optional[List[str]] = None,
    method: str = "GET",
    data: Optional[Any] = None,
    json: Optional[Any] = None,
    max_redirects: int = 10,
) -> requests.Response:
    """
    Fetch a URL with manual redirect validation against allowed_hosts.

    Raises ValueError if any hop is blocked.
    """
    if allowed_hosts is None:
        allowed_hosts = []

    # Validate initial URL
    if not _validate_url(url, allowed_hosts):
        raise ValueError(f"Blocked URL: {url}")

    # Create a session with retry strategy
    session = requests.Session()
    retry = Retry(
        total=DEFAULT_RETRIES,
        backoff_factor=DEFAULT_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    current_url = url
    for _ in range(max_redirects):
        # Validate the current URL before each request
        if not _validate_url(current_url, allowed_hosts):
            raise ValueError(f"Blocked redirect URL: {current_url}")

        # Make the request without following redirects automatically
        resp = session.request(
            method=method,
            url=current_url,
            headers=headers,
            timeout=timeout,
            data=data,
            json=json,
            allow_redirects=False,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                resp.close()
                raise ValueError("Redirect missing Location header")
            # Resolve relative redirects
            if not location.startswith(("http://", "https://")):
                location = requests.compat.urljoin(resp.url, location)
            current_url = location
            resp.close()
            continue
        return resp

    raise ValueError("Too many redirects")


def fetch_text(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_hosts: Optional[List[str]] = None,
) -> str:
    """Fetch a URL and return the response text."""
    resp = _safe_fetch_url(url, headers=headers, timeout=timeout, allowed_hosts=allowed_hosts)
    try:
        return resp.text
    finally:
        resp.close()


def fetch_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_hosts: Optional[List[str]] = None,
) -> Dict:
    """Fetch a URL and parse JSON response."""
    resp = _safe_fetch_url(url, headers=headers, timeout=timeout, allowed_hosts=allowed_hosts)
    try:
        return resp.json()
    finally:
        resp.close()


def post_json(
    url: str,
    payload: Dict,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_hosts: Optional[List[str]] = None,
) -> Dict:
    """POST JSON payload and parse JSON response."""
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    resp = _safe_fetch_url(
        url,
        headers=req_headers,
        timeout=timeout,
        allowed_hosts=allowed_hosts,
        method="POST",
        json=payload,
    )
    try:
        return resp.json()
    finally:
        resp.close()