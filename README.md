<p align="center">
  <img src="https://img.shields.io/badge/XCRDownloader-v1.4.0-6c5ce7?style=for-the-badge" alt="XCRDownloader">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Sites-1800+-ff6b6b?style=for-the-badge" alt="Sites">
</p>

<h1 align="center">⚡ XCRDownloader</h1>

<p align="center">
  <strong>Free · Unlimited · No API Keys · No Rate Limits</strong><br>
  Download videos, music, and images from YouTube, SoundCloud, Instagram, TikTok, X/Twitter, Pinterest, and 1800+ sites.<br>
  <strong>🎵 NEW: Search & Play Music</strong> — search across Deezer, YouTube & SoundCloud, play inline, download as MP3.
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

- 🚀 **No API keys required** — works out of the box, completely free
- ▶️ **YouTube** — Videos, Music, Playlists, Shorts (with preview)
- 🛡️ **YouTube anti-bot resilience** — modern player clients (`android_vr`, `web_safari`) + automatic client rotation + optional TLS impersonation, so downloads keep working when YouTube blocks a client
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
- 🎵 **Music Search** — search across Deezer, YouTube & SoundCloud in one query, no API keys
- ▶️ **Inline Player** — play tracks in the browser with a Spotify-like Now Playing bar
- 📊 **Quality selection** — Best, HD (1080p), SD (480p)
- 🛡️ **Error handling** — human-readable error messages

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

## 🔧 YouTube Reliability (v1.2.0)

YouTube periodically blocks yt-dlp's default download clients, causing `HTTP Error 403` or `No video formats found!`. XCRDownloader v1.2.0 handles this with a **layered strategy**:

1. **Modern player clients** — uses YouTube's current recommended clients (`android_vr`, `web_safari`) instead of the deprecated `web`/`mweb` set.
2. **Automatic client rotation** — if the primary clients fail, it retries with `tv_downgraded`, then `ios`/`android`, then legacy clients, until one succeeds.
3. **TLS impersonation (optional)** — when `curl_cffi` is installed (it is by default), requests impersonate a real Chrome browser at the TLS level, defeating bot-detection 403s.

No configuration needed — it just works. To update an existing install:

```bash
pip install -r requirements.txt   # pulls yt-dlp >= 2026.7.4 + curl_cffi
```

## 🎵 Player — Music, Videos & Podcasts (v1.4.0)

A dedicated **Player tab** for searching, browsing, and playing content from 3 free providers:

| Provider | Searches | Playback |
|----------|----------|----------|
| 🎶 Deezer | Tracks, albums, artists | Catalog metadata; full playback requires account auth |
| ▶️ YouTube | Videos, music, podcasts | Client rotation + official embed fallback |
| 🔊 SoundCloud | Tracks, podcasts | Full playback fallback |

**Features:**
- 🎬 **Video playback** — YouTube videos play in a floating video player
- 🎙️ **Podcast support** — auto-detected by duration/keywords, full playback
- 📋 **Queue** — auto-advance, prev/next, shuffle, repeat
- 🔊 **Volume control** — slider + mute toggle
- 🏷️ **Category filters** — All / Music / Videos / Podcasts / Albums / Artists
- ▶️ **Active track** — highlighted in results and queue
- ⬇️ **Download** — any track/video from the player

**Web UI:** Click the "Player" tab in the top nav, search, and play.

**Important provider limitations:** Deezer's public API exposes 30-second previews and catalog metadata. Full Deezer playback requires Deezer's authenticated playback/SDK flow and an eligible account; this app does not bypass that restriction. For mixed full-length playback, Deezer results try a matching SoundCloud track first, then YouTube, and clearly report when no full source is available. YouTube age/captcha failures try alternate results and then use the official YouTube embed player when possible.

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

## 🌐 Web UI

```bash
python cli.py           # launches Web UI automatically
python cli.py --web     # same thing, explicit
python cli.py --web --port 9090
```

Opens `http://127.0.0.1:8080` in your browser. Features:

- 🔍 **Auto-preview** — paste a URL → see title, thumbnail, duration, views before downloading
- 🎵 **Music Search** — search songs, artists, albums across Deezer, YouTube & SoundCloud
- ▶️ **Inline Player** — click play on any search result → Now Playing bar with seek, play/pause, download
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

# Search music (Deezer + YouTube + SoundCloud)
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
├── requirements.txt       # Python dependencies
├── setup.bat              # Windows automated setup
├── setup.sh               # Linux/macOS automated setup
├── Dockerfile             # Docker build
├── docker-compose.yml     # Docker Compose
├── src/
│   ├── engine.py          # Download engine + error humanizer
│   ├── search.py          # Music search (Deezer + YouTube + SoundCloud)
│   ├── web.py             # Flask Web UI backend (+ search/stream/download-track APIs)
│   ├── platforms/
│   │   ├── base.py        # Base downloader (yt-dlp)
│   │   ├── instagram.py   # Instagram handler
│   │   ├── tiktok.py      # TikTok handler
│   │   ├── twitter.py     # X/Twitter handler
│   │   ├── pinterest.py   # Pinterest handler (custom scraper)
│   │   ├── youtube.py     # YouTube + YouTube Music handler
│   │   ├── soundcloud.py  # SoundCloud handler
│   │   └── generic.py     # Generic (1800+ sites)
│   └── utils/
│       └── helpers.py     # Platform detection, formatting
├── templates/
│   └── index.html         # Web UI template
├── static/
│   ├── css/style.css      # Dark theme + preview card
│   └── js/app.js          # Frontend + auto-preview
└── downloads/             # Downloaded files (gitignored)
```

## ⚠️ Legal Disclaimer

This tool is for educational purposes and personal use only. Respect copyright laws and the terms of service of each platform. Only download content you have the right to download.

## 🤝 Contributing

Contributions are welcome! Fork the repo, create a feature branch, and submit a PR.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with Love💙 by <a href="https://github.com/MohammadAliMehri">MohammadAliMehri</a>
</p>
