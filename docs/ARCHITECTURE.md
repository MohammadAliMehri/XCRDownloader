# XCRDownloader Architecture

## Overview

XCRDownloader is a Python-based universal media downloader with a web UI, CLI, and embedded media player. It leverages `yt-dlp` for most platform downloads and adds custom logic for TikTok, Pinterest, and anime streaming.

## High-Level Components

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI       │     │   Web UI    │     │   Docker    │
│  (cli.py)   │     │ (Flask app) │     │ (compose)   │
└──────┬──────┘     └──────┬──────┘     └─────────────┘
       │                   │
       └─────────┬─────────┘
                 │
          ┌──────▼──────┐
          │   Engine    │
          │ (engine.py) │
          └──────┬──────┘
                 │
    ┌────────────┼────────────┬────────────┐
    │            │            │            │
┌───▼───┐  ┌────▼────┐ ┌─────▼─────┐ ┌───▼───┐
│Platform│  │  Search │ │   Anime   │ │Relay  │
│Providers│  │(search.py)│ │(anime/*) │ │(relay.py)│
└───────┘  └─────────┘ └───────────┘ └───────┘
```

## Core Data Flow

### Download Flow (Web UI)

1. User submits URL via Web UI (`/api/download`).
2. Web UI creates a job via `JobManager` and returns `job_id`.
3. Background thread calls `Engine.download()`.
4. Engine detects platform via `detect_platform()` helper.
5. Engine lazily instantiates the corresponding `BaseDownloader` subclass.
6. Downloader uses `yt-dlp` (or custom logic for Pinterest/TikTok) to download.
7. Result is stored in job and frontend polls `/api/job/<id>` until complete.

### Search Flow (Music Player)

1. User searches via Player tab (`/api/search`).
2. Web UI fans out to `search_music()` which queries YouTube, YouTube Music, and SoundCloud in parallel using `yt-dlp` extractors.
3. Results are merged, deduplicated, and returned.
4. User clicks play: frontend calls `/api/stream` to get a fresh playable URL.
5. Server uses `get_stream_url()` to resolve a browser-compatible format.

### Anime Streaming Flow

1. User searches via Anime tab (`/api/anime/search`).
2. `search_anime()` fans out to all registered providers (Yomi, AniWatchTV, Miruro, Film2Media).
3. User selects a series → frontend fetches episodes (`/api/anime/episodes`).
4. User clicks play: frontend calls `/api/anime/stream` with episode details.
5. Provider returns either a direct stream URL (Yomi) or an embed URL (others).
6. If direct stream, the URL is relayed through `/api/anime/media` to set correct Referer and rewrite HLS playlists.
7. Frontend uses hls.js to play the m3u8 with subtitles.

### Media Relay (HLS)

- Upstream CDNs (MegaPlay, TikTok CDN) enforce a `Referer` header that browsers cannot send.
- The relay fetches the media with the correct Referer, rewrites all URIs in the playlist to go through the relay, and de‑wraps TikTok‑CDN segments that have a 252‑byte wrapper.
- All redirects are validated against a strict allow‑list to prevent SSRF.

## Component Descriptions

### `src/engine.py` — DownloaderEngine
- Manages lazy instantiation of platform providers.
- Provides `download()`, `download_batch()`, `get_info()`, `detect()`.
- Error normalisation via `_humanize_error()`.

### `src/platforms/` — Platform Providers
Each provider subclasses `BaseDownloader` which wraps `yt-dlp` and adds:
- FFmpeg auto-detection.
- Common format spec and audio postprocessors.
- `download()` and `get_info()` methods.
- Custom logic: TikTok UA rotation, Pinterest scraping→yt-dlp fallback, YouTube client rotation.

### `src/anime/` — Anime Providers
- Interface `AnimeProvider` with `search()`, `episodes()`, `stream()`.
- Registry pattern: `registry.get(name)`.
- Providers: Yomi (AniList + MegaPlay), AniWatchTV (WordPress + MegaPlay), Miruro (WordPress + dramastream), Film2Media (WordPress download portal).
- Shared helpers (`_shared.py`) for WordPress search, episode extraction, OG image fetching.

### `src/api/` — API Blueprints
- `download.py`: `/api/detect`, `/api/preview`, `/api/download`, `/api/batch`, `/api/job/<id>`, `/api/history`, `/api/stats`, `/api/download-track`.
- `search.py`: `/api/search`, `/api/stream`.
- `anime.py`: `/api/anime/search`, `/api/anime/episodes`, `/api/anime/stream`, `/api/anime/media`.
- All return consistent JSON error responses.

### `src/services/jobs.py` — JobManager
- In‑memory job store with TTL, bounded size (default 100 jobs), and thread‑safe operations.
- Automatic cleanup thread.

### `src/relay.py` — Media Relay
- `_media_fetch_url()` determines if a URL needs de‑wrapping.
- `_safe_fetch_url()` performs manual redirect validation against allow‑list and private IP blocks.
- `_rewrite_playlist()` rewrites HLS playlists to relay all URIs.
- `_strip_wrapper_stream()` buffers and strips the 252‑byte wrapper from TikTok‑CDN segments.

### `src/config.py` — Configuration
- Dataclass with environment‑based overrides (`XCR_*` vars).
- Defaults for server, downloads, jobs, timeouts, relay allow‑lists, anime allow‑lists.

### `src/logging.py` — Logging Setup
- Configures logging level from config, sets noisy libraries to WARNING.
- Provides `get_logger()` for modules.

### `src/network/client.py` — Shared HTTP Client
- `_safe_fetch_url()` with retries, redirect validation, host allow‑listing.
- Wrappers: `fetch_text()`, `fetch_json()`, `post_json()`.

### `cli.py` — CLI Entry Point
- Argparse for download, search, web UI, batch, quality, JSON output.
- UTF‑8 fixes for Windows.
- Launches Web UI with browser open.

### `src/web.py` — Flask Application Factory
- Creates Flask app with CORS, registers blueprints, serves `index.html`.
- Provides healthcheck endpoint (implicit via root).
- Integrates `JobManager` and `Engine` via app config.

### `static/js/app.js` — Frontend
- Vanilla JavaScript with modular functions.
- XSS hardened with `esc()`.
- Polls job status, updates progress, renders results.
- Uses hls.js for anime playback.

### `static/css/style.css` — Dark Theme
- CSS variables for easy theming.

## Dependencies

- **yt-dlp**: core download engine (1800+ sites).
- **curl_cffi**: TLS impersonation for YouTube anti‑bot.
- **Flask + flask‑cors**: Web UI.
- **requests**: HTTP client for relay and anime fetches.
- **beautifulsoup4 + lxml**: HTML parsing for anime and Pinterest.
- **gallery-dl**: fallback for some platforms (optional).
- **imageio‑ffmpeg**: FFmpeg wrapper (optional).
- **aiohttp**: used in some sub‑dependencies.

## Configuration

All settings are via environment variables (prefixed `XCR_`). See `.env.example`.

Key settings:
- `XCR_SERVER_HOST`, `XCR_SERVER_PORT`, `XCR_DEBUG`
- `XCR_DOWNLOAD_DIR`, `XCR_MAX_WORKERS`
- `XCR_JOB_TTL_SECONDS`, `XCR_MAX_JOBS`
- `XCR_CONNECT_TIMEOUT`, `XCR_READ_TIMEOUT`
- `XCR_RELAY_ALLOWED_HOSTS` (comma‑separated)
- `XCR_LOG_LEVEL`

## Security Design

- **SSRF protection**: Relay and anime fetches validate every host against allow‑lists and reject private IPs, loopback, link‑local, reserved, and multicast addresses.
- **Input sanitisation**: Frontend `esc()` prevents XSS.
- **Non‑root Docker**: Runs as user 1000.
- **No secrets**: No API keys or credentials stored.
- **TLS**: `nocheckcertificate` removed from global defaults; only used in specific contexts where needed (e.g., some yt‑dlp extractors).
- **CORS**: Limited to same origin in production (configurable).

## Testing

- Unit tests in `tests/` (23 tests) cover security, engine, and helpers.
- Live E2E test `test_browser_flow.py` uses Playwright (requires running server).

## Future Extensibility

- Adding a new platform: subclass `BaseDownloader` and add to engine's registry.
- Adding a new anime provider: implement `AnimeProvider` and register.
- Adding a new API endpoint: add route to the appropriate blueprint.
- Adding a new job type: extend `JobManager` with custom data.

## Performance Considerations

- **Parallel downloads**: ThreadPoolExecutor with configurable workers.
- **Batch ordering**: Preserves input order despite parallel execution.
- **Job TTL**: Prevents unbounded memory growth.
- **Lazy provider initialisation**: Avoids loading unused providers.
- **Caching**: No external cache; in‑memory only.
- **Timeout**: Configurable connect/read timeouts to avoid hanging.

---
Last updated: 2026-08-17 for v1.8.0