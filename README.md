<p align="center">
  <img src="https://img.shields.io/badge/XCRDownloader-v1.1.0-6c5ce7?style=for-the-badge" alt="XCRDownloader">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Sites-1800+-ff6b6b?style=for-the-badge" alt="Sites">
</p>

<h1 align="center">⚡ XCRDownloader</h1>

<p align="center">
  <strong>Free · Unlimited · No API Keys · No Rate Limits</strong><br>
  Download videos, music, and images from YouTube, SoundCloud, Instagram, TikTok, X/Twitter, Pinterest, and 1800+ sites.
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#web-ui">Web UI</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#docker">Docker</a> ·
  <a href="#build-exe">Build .exe</a>
</p>

---

## ✨ Features

- 🚀 **No API keys required** — works out of the box, completely free
- ▶️ **YouTube** — Videos, Music, Playlists, Shorts (with preview)
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
- 📦 **Standalone .exe** — double-click to launch Web UI, no Python needed
- 🐳 **Docker** — ready to deploy
- ⚡ **Parallel downloads** — configurable worker threads
- 🎧 **Audio extraction** — extract MP3 from any video
- 📊 **Quality selection** — Best, HD (1080p), SD (480p)
- 🛡️ **Error handling** — human-readable error messages

## 🚀 Quick Start

### Option A: Download the .exe (easiest)

1. Download `XCRDownloader.exe` from [Releases](https://github.com/MohammadAliMehri/XCRDownloader/releases)
2. Double-click to open the Web UI in your browser
3. Paste any URL and click Download

### Option B: Run from source

```bash
# Clone
git clone https://github.com/MohammadAliMehri/XCRDownloader.git
cd XCRDownloader

# One-command setup (installs venv + deps + builds .exe)
# Windows:
setup.bat

# Linux/macOS:
chmod +x setup.sh && ./setup.sh

# Then run:
python cli.py <URL>
python cli.py --web
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
5. Optionally build a standalone `.exe`

### Manual Install

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### Docker

```bash
docker-compose up -d
# Open http://localhost:8080
```

## 🌐 Web UI

```bash
python cli.py --web
python cli.py --web --port 9090
```

Features:
- 🔍 **Auto-preview** — paste a URL and see title, thumbnail, duration, views before downloading
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
```

## 🔨 Build .exe

```bash
# From venv:
python build.py

# Output: dist/XCRDownloader.exe (29 MB)
# Double-click opens Web UI automatically
# No CMD window — runs in background
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
├── build.py               # PyInstaller .exe builder
├── setup.bat              # Windows automated setup
├── setup.sh               # Linux/macOS automated setup
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker build
├── docker-compose.yml     # Docker Compose
├── src/
│   ├── __init__.py
│   ├── engine.py          # Download engine + error humanizer
│   ├── web.py             # Flask Web UI backend (+ /api/preview)
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
  Made with ⚡ by <a href="https://github.com/MohammadAliMehri">MohammadAliMehri</a>
</p>
