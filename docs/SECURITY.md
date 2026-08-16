# XCRDownloader Security Overview

## Threat Model

XCRDownloader is a local tool with a web UI and optional Docker deployment. It processes URLs and media from user input, interacts with upstream services (YouTube, SoundCloud, anime streaming sites, etc.), and downloads media to the local filesystem.

**Primary risks:**
1. **SSRF** (Server-Side Request Forgery) — malicious URLs could make the server fetch internal or restricted resources.
2. **XSS** (Cross-Site Scripting) — untrusted data from API responses could execute in the browser.
3. **Command injection** — if user input is passed unsafely to shell commands.
4. **Resource exhaustion** — unbounded jobs or large media downloads.
5. **Information disclosure** — error messages or stack traces could leak sensitive details.
6. **Docker container escape** — if the container runs as root or has unsafe mounts.

## Mitigations Implemented

### 1. SSRF Protection (Relay and Anime)

- **Host allow-lists**: Each relay request checks the host against `XCR_RELAY_ALLOWED_HOSTS` (default: MegaPlay, TikTok CDN, etc.). Anime fetches validate against per‑provider allow‑lists.
- **Private IP blocking**: `ipaddress` module rejects private, loopback, link‑local, reserved, and multicast addresses.
- **Manual redirect validation**: Redirects are followed manually; each hop is re‑validated against the allow‑list and private IP block.
- **DNS‑rebinding mitigation**: Hostname is resolved via `socket.gethostbyname()` before each request; if the IP changes on redirect, the new IP is checked.
- **Scheme restriction**: Only `http://` and `https://` URLs are accepted.

### 2. XSS Prevention

- **`esc()` function**: All user‑supplied data rendered in `app.js` (error messages, history, search results, anime cards) is passed through `esc()` which HTML‑escapes dangerous characters.
- **No `innerHTML` with untrusted data**: All uses of `innerHTML` are now safe; dynamic content uses `textContent` or escaped interpolation.
- **Content Security Policy (future)**: Not yet enforced, but recommended to add `Content-Security-Policy` header in production.

### 3. Command Injection

- **No subprocess or shell calls**: The codebase does not use `subprocess`, `os.system`, or `shell=True`. All external operations are via Python libraries (`yt-dlp`, `requests`).
- **FFmpeg integration**: `yt-dlp` handles ffmpeg internally; we only pass `ffmpeg_location` as an option, not via shell.

### 4. Resource Exhaustion

- **Bounded job manager**: `JobManager` limits the total number of jobs (default 100) and evicts oldest entries when full.
- **TTL**: Jobs expire after `XCR_JOB_TTL_SECONDS` (default 1 hour).
- **Timeout**: All network requests have configurable connect/read timeouts (`XCR_CONNECT_TIMEOUT`, `XCR_READ_TIMEOUT`).
- **Download size**: `yt-dlp` itself caps fragment retries and chunks; no global size limit yet.

### 5. Information Disclosure

- **Error messages**: Provider exceptions are caught and returned as generic `"error"` or human‑readable messages (via `_humanize_error`); raw stack traces are never exposed to the client.
- **Logging**: Log level is configurable; in production, set `XCR_LOG_LEVEL=WARNING` to reduce verbosity.
- **Debug mode**: `XCR_DEBUG` is `false` by default; do not enable in production.

### 6. Docker Hardening

- **Non‑root user**: Container runs as `appuser` (UID 1000).
- **Healthcheck**: Prevents serving traffic until the app is ready.
- **Signal handling**: `STOP_SIGNAL=SIGINT` for graceful shutdown.
- **`.dockerignore`**: Excludes `.git`, `venv`, `__pycache__`, `downloads/`, test files, etc.
- **Read‑only filesystem (optional)**: Could add `read_only: true` in compose for extra safety.
- **No secrets in image**: No `.env` or credentials are copied.

### 7. Secure Development Practices

- **Dependency management**: `requirements.txt` pins known good versions; `pyproject.toml` declares upper bounds (e.g., `curl_cffi<0.16`).
- **No hardcoded credentials**: None exist.
- **Linter/type checking**: `ruff` and `mypy` are configured (though not enforced yet).
- **Unit tests**: 23 tests cover security‑critical functions (`_media_url_allowed`, `_safe_fetch_url`, allow‑list logic, stripping).
- **Input validation**: URL inputs are validated with `urlparse` and scheme checks.

## Remaining Risks (Accepted)

- **No authentication**: The web UI is unauthenticated; this is a local tool, not intended for public exposure.
- **No rate limiting**: Download requests are not throttled; could be abused to overload the server or upstream services.
- **No content filtering**: The tool downloads whatever URL is provided; it does not check for illegal or malicious content.
- **DNS rebinding**: While mitigated per request, a sophisticated attacker could still time a rebind between resolution and fetch. Manual redirect validation reduces the window.
- **HLS playlist injection**: The relay rewrites playlists and serves them; a malicious playlist could include external URLs that pass the allow‑list if they are in the same domain. Future: validate all URIs after rewriting.

## Recommended Additional Measures

1. **Add Content Security Policy (CSP)** headers to restrict scripts, styles, and frames.
2. **Enable rate limiting** on `/api/download` and `/api/batch` to prevent abuse.
3. **Run with `read_only: true`** in Docker Compose to prevent writes except to the mounted `downloads` volume.
4. **Add authentication** if exposing publicly (basic auth or OAuth).
5. **Implement global download size cap** to avoid filling disk.
6. **Add logging of security‑relevant events** (blocked URLs, validation failures).
7. **Regularly update dependencies** (`pip list --outdated`) to patch known vulnerabilities.

## Security Verification

- **Manual testing**: Verified SSRF protection with localhost, private IPs, and public URLs.
- **Automated tests**: `tests/test_security.py` covers allow‑list, private IP blocking, redirect validation, and stripping.
- **Static analysis**: `ruff` checks for common security issues (though not integrated into CI yet).

## Incident Response

- If a vulnerability is discovered, report via GitHub Issues (private if sensitive).
- The maintainer will patch and release a new version.
- No credentials are stored, so there is no rotation required.

---
Last updated: 2026-08-17 for v1.8.0