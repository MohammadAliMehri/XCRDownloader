<p align="center">
  <img src="https://img.shields.io/badge/XCRDownloader-v1.8.0-6c5ce7?style=for-the-badge" alt="XCRDownloader">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Sites-1800+-ff6b6b?style=for-the-badge" alt="Sites">
</p>

<h1 align="center">⚡ XCRDownloader</h1>

<p align="center">
  <strong>Free · Unlimited · No API Keys · No Rate Limits</strong><br>
  Download videos, music, and images from YouTube, SoundCloud, Instagram, TikTok, X/Twitter, Pinterest, and 1800+ sites.<br>
  <strong>🎵 NEW: Search & Play</strong> — search YouTube, YouTube Music & SoundCloud, play inline, download as MP3.<br>
  <strong>🎬 NEW: Anime Stream</strong> — search and watch anime from Yomi, AniWatchTV, Film2Media & Miruro with subtitles.
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#web-ui">Web UI</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#docker">Docker</a>
</p>

---

## ✨ Features

### Core
- 🚀 **No API keys required** — works out of the box, completely free
- ▶️ **YouTube** — Videos, Music, Playlists, Shorts (with preview)
- 🛡️ **YouTube anti-bot resilience** — modern player clients + automatic client rotation + optional TLS impersonation
- 🎶 **YouTube Music** — Auto-converts to high-quality MP3
- 🔊 **SoundCloud** — Tracks, Playlists, Albums (auto MP3)
- 📸 **Instagram** — Reels, Stories, Posts, IGTV
- 🎵 **TikTok** — Videos without watermark, audio extraction
- 🐦 **X/Twitter** — Videos, images, GIFs
- 📌 **Pinterest** — Videos, images, GIFs
- 🌐 **1800+ sites** — Reddit, Facebook, Vimeo, and more via yt-dlp
- 🔍 **Auto Preview** — paste a URL → see title, thumbnail, duration, views
- 🎯 **Batch download** — download multiple URLs at once
- 🎨 **Web UI** — modern dark-themed web interface
- 💻 **CLI** — powerful command-line interface
- 🐳 **Docker** — ready to deploy
- ⚡ **Parallel downloads** — configurable worker threads
- 🎧 **Audio extraction** — extract MP3 from any video
- 🎵 **Music Search** — search across YouTube, YouTube Music & SoundCloud in one query
- ▶️ **Dedicated Player** — play tracks, videos, and podcasts with queue controls
- 🎬 **Anime Search & Stream** — search anime across Yomi, AniWatchTV, Film2Media & Miruro; watch with subtitles (Sub/Dub)
- 📺 **HLS streaming** — server-side media relay plays HLS streams in any browser (hls.js), with subtitle tracks
- 🛠️ **FFmpeg integration** — merge and convert downloads with browser-safe online playback
- 📊 **Quality selection** — Best, HD (1080p), SD (480p)
- 🛡️ **Error handling** — human-readable error messages

### Security & Reliability (v1.8.0)
- 🔒 **Media relay SSRF protection** — strict host allow‑list, manual redirect validation, private IP blocking, DNS-rebinding mitigation
- 🔒 **Anime SSRF protection** — per‑provider allow‑lists for all upstream fetches
- 🔒 **TLS hardening** — removed global certificate verification bypass; scoped only where needed
- 🔒 **Bounded job manager** — in‑memory job store with TTL, size cap, and thread‑safe operations
- 🔒 **Configurable timeouts** — connect and read timeouts for all network calls

### Architecture & Developer Experience (v1.8.0)
- 📦 **Proper packaging** — `pyproject.toml` with `pip install -e .` and `xcrdownloader` CLI command
- 🧩 **Modularised codebase** — split into `src/api/`, `src/services/`, `src/network/`, `src/anime/`, `src/relay/`
- 🧪 **Unit tests** — 23 passing tests for security, engine, and providers
- 📝 **Structured logging** — INFO/DEBUG/WARNING/ERROR with configurable levels
- ⚙️ **Centralised configuration** — environment‑based settings with `.env.example`
- 🐳 **Docker hardened** — non‑root user, healthcheck, proper signal handling, `.dockerignore`

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/MohammadAliMehri/XCRDownloader.git
cd XCRDownloader

# Setup (installs venv + deps)
# Windows:
setup.bat

# Linux/macOS:
chmod +x setup.sh && ./setup.sh

# Run Web UI (opens in browser automatically):
python cli.py

# Or CLI mode:
python cli.py https://www.youtube.com/watch?v=abc
```

## 📦 Installation

### Automated Setup (recommended)

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

Both scripts will:
1. Check Python 3.10+ is installed
2. Check/install ffmpeg
3. Create a virtual environment (`venv/`)
4. Install all Python dependencies

### Manual Install

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

### Prerequisites

- Python 3.10+
- FFmpeg (for video/audio merging and conversion)

```bash
# Windows (winget)
winget install Gyan.FFmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

## 🔧 YouTube Reliability (v1.2.0+)

YouTube periodically blocks yt-dlp's default download clients, causing `HTTP Error 403` or `No video formats found!`. XCRDownloader handles this with a **layered strategy**:

1. **Modern player clients** — uses YouTube's current recommended clients (`android_vr`, `web_safari`) instead of the deprecated `web`/`mweb` set.
2. **Automatic client rotation** — if the primary clients fail, it retries with `tv_downgraded`, then `ios`/`android`, then legacy clients, until one succeeds.
3. **TLS impersonation (optional)** — when `curl_cffi` is installed (it is by default), requests impersonate a real Chrome browser at the TLS level, defeating bot-detection 403s.

No configuration needed — it just works. To update an existing install:

```bash
pip install -r requirements.txt   # pulls yt-dlp >= 2026.7.4 + curl_cffi
```

## 🎵 Player — YouTube, YouTube Music & SoundCloud (v1.5.0)

A dedicated **Player tab** for searching, browsing, and playing content from 3 free providers:

**Online playback:** The server asks yt-dlp for a fresh URL at playback time. For video, it prefers a browser-compatible muxed MP4 format; for audio, it prefers direct audio formats. FFmpeg remains responsible for downloaded-file conversion and merging. The browser does not need FFmpeg installed to play a returned URL.

| Provider | Searches | Playback |
|----------|----------|----------|
| ▶️ YouTube | Videos, music, podcasts | Client rotation + official embed fallback |
| 🎧 YouTube Music | Music tracks and albums | Fresh online audio URLs |
| 🔊 SoundCloud | Tracks, podcasts | Full online playback |

**Features:**
- 🎬 **Video playback** — YouTube videos play in a floating video player
- 🎙️ **Podcast support** — auto-detected by duration/keywords, full playback
- 📋 **Queue** — auto-advance, prev/next, shuffle, repeat
- 🔊 **Volume control** — slider + mute toggle
- 🏷️ **Category filters** — All / Music / Videos / Podcasts / Albums / Artists
- ▶️ **Active track** — highlighted in results and queue
- ⬇️ **Download** — any track/video from the player

**Web UI:** Click the "Player" tab in the top nav, search, and play.

**Playback behavior:** YouTube and YouTube Music use fresh online URLs from yt-dlp. If YouTube direct extraction is blocked by age restrictions or captcha, the Player tries an alternate result and then the official YouTube embed player. SoundCloud is the full-length fallback for music where an equivalent upload exists. FFmpeg is used for downloads and format conversion; browser playback prefers formats that already contain both audio and video because browsers cannot mux separate DASH streams.

**CLI:**
```bash
python cli.py --search "Eminem Lose Yourself"
python cli.py --search "Joe Rogan podcast"
python cli.py --search "cooking tutorial"
```

**API:**
```
GET  /api/search?q=...&page=0    → merged search results
POST /api/stream                  → get playable audio URL
POST /api/download-track          → download as MP3
```

## 🎬 Anime Search & Stream (v1.7.0)

A dedicated **Anime tab** for searching, browsing, and watching anime from 4 free providers — no API keys, no login:

| Provider | Source | Content |
|----------|--------|---------|
| 🎌 Yomi | AniList metadata + MegaPlay HLS | Anime search, episode lists, Sub & Dub, subtitles |
| 👾 AniWatchTV | WordPress catalog + MegaPlay HLS | Anime search, episode lists, direct m3u8 |
| 🎞️ Film2Media | WordPress REST (f2mc.top) | Persian movies/series/anime download portal |
| 🌐 Miruro | WordPress catalog + dramastream player | Anime search, episode lists, embedded player |

**Features:**
- 🔍 **Search** — one query fans out to all providers in parallel (or filter by provider)
- 🖼️ **Poster grid** — cover art, year, format, score, episode counts
- 📄 **Detail panel** — synopsis, genres, full episode grid
- 🎙️ **Sub / Dub toggle** — English dub where available (Yomi)
- 💬 **Subtitles** — English VTT tracks auto-enabled on every episode
- ▶️ **HLS playback** — hls.js player with server-side media relay; streams work in Chrome, Firefox, Edge, Safari
- 🔗 **Embed fallback** — providers without direct streams fall back to their embedded player

**How streaming works:** the app resolves fresh HLS sources at play time and relays media through a local proxy — the upstream CDNs enforce a `Referer` header browsers cannot send, so the server fetches with the correct referer, rewrites HLS playlists, and de-wraps CDN segments. You just click play.

**API:**
```
GET  /api/anime/search?q=...&provider=all      → search results (provider: yomi/aniwatchtv/f2mc/miruro/all)
GET  /api/anime/episodes?provider=yomi&anime_id=20
GET  /api/anime/episodes?provider=aniwatchtv&page_url=...
POST /api/anime/stream                         → {stream_url, subtitles, player_url} for an episode
GET  /api/anime/media?url=...&ref=...          → media relay (playlists rewritten, segments de-wrapped)
```

## 🌐 Web UI

```bash
python cli.py           # launches Web UI automatically
python cli.py --web     # same thing, explicit
python cli.py --web --port 9090
```

Opens `http://127.0.0.1:8080` in your browser. Features:

- 🔍 **Auto-preview** — paste a URL → see title, thumbnail, duration, views before downloading
- 🎵 **Music Search** — search songs, videos, podcasts, and YouTube Music
- ▶️ **Dedicated Player** — queue, seek, play/pause, shuffle, repeat, volume, video mode
- 🎬 **Anime tab** — search & watch anime from 4 providers with subtitles (Sub/Dub)
- 🛠️ **FFmpeg-aware playback** — browser-safe muxed formats for online video; FFmpeg for downloads
- 🎨 Modern dark theme
- 📋 Single & batch download
- 📊 Download history & stats
- ⏳ Real-time progress
- 📱 Mobile responsive

## 💻 CLI

```bash
# Single download
python cli.py https://www.youtube.com/watch?v=abc
python cli.py https://soundcloud.com/artist/track
python cli.py https://www.instagram.com/reel/ABC123/
python cli.py https://www.tiktok.com/@user/video/123

# Audio only (MP3)
python cli.py --audio https://www.youtube.com/watch?v=abc
python cli.py --audio https://soundcloud.com/artist/track

# Quality selection
python cli.py --quality hd https://www.youtube.com/watch?v=abc

# Preview without downloading
python cli.py --info https://www.youtube.com/watch?v=abc

# Batch download
python cli.py -u URL1 -u URL2 -u URL3
python cli.py -f urls.txt

# JSON output
python cli.py --json --info URL

# Search YouTube, YouTube Music, and SoundCloud
python cli.py --search "Eminem Lose Yourself"
python cli.py --search "Adele Hello"
```

## 🐳 Docker

```bash
docker-compose up -d
# Open http://localhost:8080
```

## 📸 Supported Platforms

| Platform | Content Types | Audio Auto |
|----------|--------------|------------|
| ▶️ YouTube | Videos, Music, Playlists, Shorts | ✅ for YT Music |
| 🎶 YouTube Music | Songs, Albums, Playlists | ✅ MP3 |
| 🔊 SoundCloud | Tracks, Playlists, Albums | ✅ MP3 |
| 📸 Instagram | Reels, Stories, Posts, IGTV | |
| 🎵 TikTok | Videos (no watermark), Audio | |
| 🐦 X/Twitter | Videos, Images, GIFs | |
| 📌 Pinterest | Videos, Images, GIFs | |
| 🌐 1800+ more | YouTube, Reddit, Facebook... | |

## 📁 Project Structure

```
XCRDownloader/
├── cli.py                 # CLI entry point (+ auto Web UI launcher)
├── run.py                 # Quick start script
├── app.py                 # WSGI entry point
├── pyproject.toml         # Packaging and project metadata
├── requirements.txt       # Python dependencies
├── setup.bat              # Windows automated setup
├── setup.sh               # Linux/macOS automated setup
├── Dockerfile             # Docker build (hardened)
├── docker-compose.yml     # Docker Compose (with healthcheck)
├── .env.example           # Environment configuration template
├── src/
│   ├── api/               # API blueprints (download, search, anime)
│   │   ├── download.py
│   │   ├── search.py
│   │   └── anime.py
│   ├── anime/             # Anime providers (extracted)
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── yomi.py
│   │   ├── aniwatchtv.py
│   │   ├── miruro.py
│   │   ├── film2media.py
│   │   └── _shared.py
│   ├── network/           # Shared HTTP client with retries & validation
│   │   └── client.py
│   ├── services/          # Job manager, logging, config
│   │   └── jobs.py
│   ├── relay.py           # HLS media relay (SSRF hardened)
│   ├── engine.py          # Download engine + error humanizer
│   ├── search.py          # YouTube + YouTube Music + SoundCloud search/player
│   ├── web.py             # Flask application factory
│   ├── config.py          # Centralised configuration
│   ├── logging.py         # Structured logging setup
│   ├── platforms/         # Platform-specific downloaders
│   │   ├── base.py        # Base downloader (yt-dlp)
│   │   ├── instagram.py
│   │   ├── tiktok.py
│   │   ├── twitter.py
│   │   ├── pinterest.py
│   │   ├── youtube.py
│   │   ├── soundcloud.py
│   │   └── generic.py
│   └── utils/
│       └── helpers.py     # Platform detection, formatting
├── templates/
│   └── index.html         # Web UI template
├── static/
│   ├── css/style.css      # Dark theme + preview card
│   └── js/app.js          # Frontend + auto-preview (XSS hardened)
├── tests/                 # Unit tests (23 passing)
│   ├── test_engine.py
│   └── test_security.py
└── downloads/             # Downloaded files (gitignored)
```

## ⚠️ Legal Disclaimer

This tool is for educational purposes and personal use only. Respect copyright laws and the terms of service of each platform. Only download content you have the right to download.

## 🤝 Contributing

Contributions are welcome! Fork the repo, create a feature branch, and submit a PR.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🆕 Changelog

### v1.8.0 — Security, Architecture & Packaging Overhaul
- **Security hardening**
  - Media relay SSRF protection: strict host allow-list, manual redirect validation, private IP blocking, DNS-rebinding mitigation.
  - Anime SSRF protection: per-provider allow-lists for all upstream fetches.
  - Removed global `nocheckcertificate` from base downloader and search; scoped exceptions only where needed.
  - Frontend XSS fixes: `esc()` used everywhere (error messages, history, search results, anime cards).
- **Architecture improvements**
  - Lazy provider initialisation in engine to isolate broken providers.
  - Fixed `detect()` fallback to be consistent with `get_downloader()`.
  - Batch download preserves input order.
  - Error normalisation applied to provider-returned errors.
- **Job management**
  - Bounded in-memory job store with TTL, size cap, and thread-safe operations.
- **Configuration**
  - Centralised config system with `.env.example` and environment overrides.
- **Networking**
  - Shared HTTP client with retries, redirect validation, and host allow-listing.
- **Anime provider extraction**
  - Provider interface with registry; Yomi/AniWatchTV/Miruro/Film2Media extracted to separate modules.
- **Platform de-duplication**
  - Common format spec and audio postprocessors moved to base; removed duplicate download_batch methods.
- **API splitting**
  - Blueprints for download, search, anime with consistent JSON error responses.
- **Logging**
  - Structured logging with INFO/DEBUG/WARNING/ERROR levels.
- **Packaging**
  - Proper `pyproject.toml`, `pip install -e .` support, `xcrdownloader` CLI command.
- **Docker hardening**
  - Non-root user, healthcheck, proper signal handling, `.dockerignore`.
- **Testing**
  - 23 unit tests for security, engine, providers.

### v1.7.0 — Provider & player hardening
- **Anime player** — Miruro episode detection fix, AniWatchTV embed fallback, Yomi Sub/Dub verified, cover enrichment.
- **Music search** — YouTube results no longer include channel/playlist tabs.
- **Downloaders** — yt-dlp 2026.7.4 with client rotation + curl_cffi; TikTok UA rotation.
- **Media relay** — HLS playlist rewriting and 252-byte segment wrapper stripping verified.

---

<p align="center">
  Made with Love💙 by <a href="https://github.com/MohammadAliMehri">MohammadAliMehri</a>
</p>