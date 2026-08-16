# XCRDownloader v1.8.0 — Architecture & Security Audit

**Date:** 2026-08-15
**Scope:** Read-only audit of the current codebase (v1.7.0) prior to the v1.8.0 stabilization refactor.
**Method:** Full inspection of every Python module, all platform handlers, the media relay, Docker files, entry points, requirements, tests, and git history. Findings below cite `file:line` and are confirmed by direct code review unless stated otherwise.

> No application code was modified during this audit.

---

## 1. Current Architecture (as it actually is)

```
cli.py ──► DownloaderEngine ──► platform handlers (detect_platform → dict lookup)
   │              │
   └── --web ─► src/web.py (Flask) ──► /api/search, /api/stream, /api/anime/*
                    │
                    └── media relay (Referer-rewriting HLS proxy + 252-byte CDN de-wrap)
```

Two independent HTTP stacks plus yt-dlp coexist (see §4). The Flask app lives in one 452-line module (`src/web.py`) that contains **routes, business logic, AND the media-relay CDN-unwrapping logic** in the same file. Anime providers are four functions dispatched by `if provider == ...` inside one 519-line module (`src/anime.py`). The download engine (`src/engine.py`) is clean and does one thing well — URL routing.

### Module inventory

| File | LOC | Responsibility |
|---|---|---|
| `cli.py` | 243 | argparse CLI + auto Web UI launcher + Windows UTF-8 fix |
| `run.py` | 55 | Quick-start help banner only |
| `app.py` | 4 | WSGI entry for `flask run` |
| `src/engine.py` | 131 | URL router, batch download, error humanizer |
| `src/search.py` | 310 | YouTube / YT Music / SoundCloud search + playback URL resolution |
| `src/anime.py` | 519 | **Largest module** — 4 anime providers + AniList + episode scraping |
| `src/web.py` | 452 | Flask app + all REST routes + **media relay + CDN de-wrap** |
| `src/platforms/base.py` | 155 | yt-dlp wrapper + ffmpeg auto-detect |
| `src/platforms/*.py` | ~1,071 | 7 platform downloaders (youtube, tiktok, instagram, twitter, pinterest, soundcloud, generic) |
| `src/utils/helpers.py` | 108 | Platform detection, filename sanitization, banner |
| `templates/index.html` | 282 | SPA shell |
| `static/js/app.js` | 744 | **All frontend logic in one file** (downloader + player + anime) |
| `static/css/style.css` | 612 | Dark theme |

---

## 2. Dependency & Coupling

- `src/web.py` imports `src.engine`, `src.search`, `src.anime`, and `src.utils.helpers`, and also defines its own relay/rewrite helpers (`_media_fetch_url`, `_media_url_allowed`, `_rewrite_playlist`) — **the relay subsystem is tangled into the route module**.
- `src/anime.py` and `src/search.py` both implement their own `_fetch`/`_post_json` over `urllib.request` — **duplicated networking**. `src/web.py` and the platform handlers use `requests` — a second stack. yt-dlp is a third.
- Three separate `sys.path.insert(...)` hacks: `cli.py:15`, `run.py:9`, `web.py:16`. The project is not an installable package.
- Import-time side effect: `src/platforms/base.py:39` computes `FFMPEG_DIR = _find_ffmpeg()` at import.
- No circular imports, but coupling is high: provider-specific constants (CDN hosts, strip bytes, proxy host) live in `web.py:29-31`, not in any provider module.

---

## 3. Findings by Severity

### CRITICAL

**C1 — Media relay redirect-to-private SSRF.** `_media_url_allowed()` (`web.py:47-57`) resolves the host once with `socket.gethostbyname()` and rejects private/loopback/reserved IPs, **but the actual request is issued with `allow_redirects=True`** (`web.py:411`) and the redirect target is never re-validated. `http://attacker.example/redirect` → `http://169.254.169.254/latest/meta-data/` passes the initial check (attacker.example is public) and the relay then fetches cloud metadata. This is a confirmed-by-code path, not theoretical.

**C2 — Media relay is an open proxy for arbitrary public URLs.** `_media_url_allowed()` only rejects non-HTTP and private/loopback addresses. Any caller can drive `GET /api/anime/media?url=<any-public-url>&ref=<anything>` to make the server fetch and relay arbitrary content (bandwidth amplification, anonymity proxy, abuse). Combined with the `0.0.0.0` bind (H1) and no auth, the relay is remotely usable on a LAN.

### HIGH

**H1 — Default bind address is `0.0.0.0`.** Both `cli.py:58` (`--host` default `"0.0.0.0"`) and `web.py:452` (`app.run(host="0.0.0.0")`). Combined with C2, this exposes the unauthenticated relay/open-proxy to the local network.

**H2 — No redirect re-validation in the relay (component of C1).** Even where the initial URL is safe, redirects are followed blindly. Should re-run `_media_url_allowed` on each hop, or disable auto-redirects and follow them manually with validation.

**H3 — No tests exist for any security control.** There is not a single unit test for `_media_url_allowed`, `_rewrite_playlist`, `_media_fetch_url`, or the 252-byte CDN strip. The only test file (`test_browser_flow.py`) is a live E2E that depends on a running server AND live third-party sites.

**H4 — Silent exception swallowing is pervasive.** `except Exception: pass` / bare `except: return []` appear in `anime.py:129-130, 167-169, 188-189, 218-219, 410, 473-474`; `search.py:216, 242-243, 299-300`; `pinterest.py:42-44, 105-106`. Some are legitimate fail-safe fan-out, but failures are invisible — no log line is emitted anywhere, so a provider that silently breaks is undiagnosable. §10 of the mandate explicitly forbids this pattern.

### MEDIUM

**M1 — Duplicated HTTP/networking across three stacks** (`urllib` in anime/search, `requests` in web/platforms, yt-dlp). No centralized timeouts, retries, backoff, proxy support, or error normalization. Each provider invents its own UA string.

**M2 — No centralized configuration.** Hardcoded: `_MEDIA_UA`, `_STRIP_HOSTS`, `_STRIP_BYTES=252`, `_TIKTOK_PROXY_HOST` (`web.py:24-31`); `_WP` base URLs (`anime.py:40-44`); timeouts scattered (10/15/25/30); worker counts; bind host/port. No `.env.example`, no env loading.

**M3 — Provider logic is coupled into the route/dispatch layers.** `if provider == "yomi"... elif provider == "aniwatchtv"...` chains in `anime.py:316-343` and `anime.py:496-519`. CDN de-wrap constants and logic are in `web.py`, not in an anime/media provider abstraction. Upstream breakage in one provider currently risks touching the shared dispatch path.

**M4 — TLS verification disabled globally.** `nocheckcertificate: True` in `base.py:49` and `search.py:43, 292`. Necessary for some CDNs, but it is applied everywhere rather than scoped to the endpoints that need it — this silently disables MITM protection across all downloads.

**M5 — `jobs` dict in `web.py:99` grows unbounded** with no eviction, no size cap, and no locking (dict ops are GIL-atomic but the pattern invites future races). Job state is also lost on restart (in-memory only).

**M6 — Error surface is inconsistent.** `engine.py` has a good `_humanize_error` map, but web routes return raw `str(e)[:200]`/`str(e)[:160]` (`web.py:281, 350, 361, 414, 502`) — the humanizer is only used on the CLI download path, not the API.

**M7 — The `web.py:451-452` `__main__` block** binds `0.0.0.0` and duplicates the CLI launch path rather than reusing `create_app` + config.

### LOW

**L1 — `Dockerfile` is single-stage**, no healthcheck, runs as root, no `STOPSIGNAL`/`init`. `docker-compose.yml` has `restart: unless-stopped` but no healthcheck or resource limits.

**L2 — `requirements.txt` pins `yt-dlp>=2026.7.4` but everything else is loose** (`requests>=2.31.0` etc.) — no upper bounds, so a future breakage is unpinned.

**L3 — Frontend is one 744-line `app.js`** with downloader + player + anime logic interleaved. Functional, but the mandate's own frontend phase will need to be surgical to avoid regressions.

**L4 — `gallery-dl` and `rich`** in `requirements.txt` are not referenced anywhere in the code I read (`gallery-dl>=1.28.0`, `rich>=13.7.0`) — candidates for removal in the dependency-cleanup phase.

**L5 — `sanitize_filename` (`helpers.py:50-59`)** does NFKD + ASCII-strip, which silently mangles non-Latin titles (e.g. anime titles in Japanese). Acceptable for now, worth documenting.

---

## 4. Provider Fragility Status (all upstreams, not just anime)

| Provider | Mechanism | Fragility | Notes |
|---|---|---|---|
| YouTube | client rotation + curl_cffi impersonation | **Medium** | Well-hardened (`android_vr`/`web_safari` → `tv_downgraded` → `ios/android` → legacy). 403 drift is constant but rotation handles it. |
| TikTok | yt-dlp + Chrome-140 UA rotation | **High** | Actively fighting yt-dlp #17403 WAF challenge. UA rotation + 2s backoff is a band-aid; upstream can break it overnight. |
| Instagram | yt-dlp `login_required:false` | **High** | No fallback, no cookie support. Common yt-dlp breakage surface. |
| X/Twitter | yt-dlp, x.com→twitter.com normalization | **High** | No guest-token/cookie handling. |
| Pinterest | custom scraper (JSON-LD, og tags, `__PWS_DATA__` regex) + yt-dlp fallback | **High** | `_scrape_media` regexes are brittle against theme changes; fallback exists but error text is concatenated raw. |
| SoundCloud | yt-dlp | **Medium** | Relies on yt-dlp's client_id; no API key by design. |
| Generic (1800+) | yt-dlp | **Low** | Inherits yt-dlp's own maintenance. |
| **Yomi** | AniList GraphQL + MegaPlay HLS | **High** | Hardcoded `megaplay.buzz` endpoints, `data-id` regex, `getSourcesNew` AJAX. Relies on TikTok-CDN 252-byte wrapper behavior staying stable. |
| **AniWatchTV** | gogoanime→megaplay iframe chain | **Very high** | Multi-hop iframe resolution; embed hosts (kwik.cx/streamwish) 403 non-browser fetches; falls back to `embed_only`. |
| **Miruro** | dramastream iframe + base64 `url=` param | **Very high** | Double-base64 decode; random slug suffixes (`-5rn3`) already required `_strip_random_slug_suffix`. |
| **Film2Media** | WordPress REST (`f2mc.top`) | **High** | Download portal only; title is `{rendered}` dict + UTF-8 BOM handling. No streaming. |

**Conclusion:** anime providers and the media relay are correctly identified as the most fragile, but TikTok, Instagram, X, and Pinterest are equally break-prone and currently share the same un-isolated pattern. The mandate's decision to isolate *all* providers (not just anime) is the right call.

---

## 5. Testing Gaps (current state)

- **Unit tests: none.** No `tests/` directory, no pytest suite, no fixtures.
- **Security tests: none.** No regression tests for SSRF/redirect/localhost/private-IP.
- **Provider tests: none.** No mocks or recorded fixtures.
- **CDN fixtures: none.** The 252-byte strip logic (`web.py:426-438`) has zero coverage and no captured real segments.
- **The single test** (`test_browser_flow.py`) is a Playwright E2E that requires a **live server + live YouTube/AniList/MegaPlay**. It cannot run in CI and will flake on any upstream outage. It is a useful smoke test but is not a substitute for a mocked suite.

The audit confirms the mandate's ordering is correct: **add regression tests around current behavior before refactoring the relay or providers.**

---

## 6. Recommended Implementation Order

1. **C1/C2 + H1 (security) first** — relay redirect re-validation + strict allow-list of upstream media hosts + default `127.0.0.1` bind + `docs/SECURITY.md`. This is the only genuinely dangerous surface and it is reachable by default.
2. **Add regression tests for the relay/rewrite/strip** before touching it further (Phase 3 of the mandate), capturing real CDN byte fixtures.
3. **Centralized HTTP layer** (Phase 2) — one client with timeout/retry/backoff/UA, then migrate providers onto it.
4. **Provider isolation** (Phase 1) — extract each of the 4 anime providers and each platform handler behind a stable interface; move CDN de-wrap constants out of `web.py`.
5. **Error system + logging** (Phases 6–7) — exception hierarchy + structured logs with request IDs; replace silent `except: pass` with logged, categorized failures.
6. **Configuration** (Phase 5) — `.env.example`, typed config, remove hardcoded constants.
7. **Dependencies + Docker** (Phases 12–13) — remove unused (`gallery-dl`, `rich`?), add healthcheck + non-root + `STOPSIGNAL`.
8. **Frontend** (Phase 10) — **last**, surgical cleanup only; no React migration in v1.8.0.

**Version note:** backend hardening + provider isolation + security + tests = `v1.8.0`. FastAPI/React remain documented-only recommendations for a future `v2.0.0` (per the mandate).

---

## 7. Honest Assessment

The codebase is in **good shape for a personal tool but not yet production-hardened**: the download engine and YouTube resilience are genuinely well done, the media relay works but is the single most dangerous component, and the total absence of a test suite means every future refactor currently lands without a net. The v1.8.0 stabilization plan is well-scoped; the critical security items (C1/C2/H1) should be resolved before any cosmetic refactoring.