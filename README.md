<p align="center">
  <img src="https://img.shields.io/badge/XCRDownloader-v1.0.0-6c5ce7?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48dGV4dHk+JiN4MjZhMTs8L3RleHQ+PC9zdmc+" alt="XCRDownloader">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Sites-1800+-ff6b6b?style=for-the-badge" alt="Sites">
</p>

<h1 align="center">⚡ XCRDownloader</h1>

<p align="center">
  <strong>Free · Unlimited · No API Keys · No Rate Limits</strong><br>
  Download videos, images, and audio from Instagram, TikTok, X/Twitter, Pinterest, and 1800+ sites.
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#web-ui">Web UI</a> ·
  <a href="#docker">Docker</a> ·
  <a href="#supported-platforms">Platforms</a>
</p>

---

## ✨ Features

- 🚀 **No API keys required** — works out of the box, completely free
- 📥 **Instagram** — Reels, Stories, Posts, IGTV
- 🎵 **TikTok** — Videos without watermark, audio extraction
- 🐦 **X/Twitter** — Videos, images, GIFs, threads
- 📌 **Pinterest** — Videos, images, GIFs, pins
- 🌐 **1800+ sites** — YouTube, Reddit, Facebook, Vimeo, and more via yt-dlp
- 🎯 **Batch download** — download multiple URLs at once
- 🎨 **Web UI** — modern dark-themed web interface
- 💻 **CLI** — powerful command-line interface
- 🐳 **Docker** — ready to deploy
- ⚡ **Parallel downloads** — configurable worker threads
- 🎧 **Audio extraction** — extract MP3 from any video
- 📊 **Quality selection** — Best, HD (1080p), SD (480p)

## 📦 Installation

### Option 1: pip install (recommended)

```bash
pip install -r requirements.txt
```

### Option 2: Docker

```bash
docker build -t xcrdownloader .
docker run -p 8080:8080 -v ./downloads:/app/downloads xcrdownloader
```

### Option 3: Docker Compose

```bash
docker-compose up -d
```

### Prerequisites

- Python 3.10+
- FFmpeg (for video/audio merging and conversion)

Install FFmpeg:
```bash
# Windows (winget)
winget install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

## 💻 Usage

### CLI — Single Download

```bash
# Instagram Reel
python cli.py https://www.instagram.com/reel/ABC123/

# TikTok Video (no watermark)
python cli.py https://www.tiktok.com/@user/video/1234567890

# X/Twitter Video
python cli.py https://twitter.com/user/status/1234567890

# Pinterest Pin
python cli.py https://www.pinterest.com/pin/1234567890/
```

### CLI — Quality & Format Options

```bash
# HD quality
python cli.py --quality hd https://www.instagram.com/reel/ABC123/

# Audio only (MP3)
python cli.py --audio https://www.tiktok.com/@user/video/123

# Custom output directory
python cli.py -o /path/to/downloads https://twitter.com/user/status/123
```

### CLI — Batch Download

```bash
# Multiple URLs
python cli.py -u URL1 -u URL2 -u URL3

# From file
python cli.py -f urls.txt

# With parallel workers
python cli.py -f urls.txt --workers 5
```

### CLI — Info & Detection

```bash
# Get info without downloading
python cli.py --info https://www.instagram.com/reel/ABC123/

# Detect platform
python cli.py --detect https://www.tiktok.com/@user/video/123

# JSON output
python cli.py --json https://twitter.com/user/status/123
```

## 🌐 Web UI

Launch the web interface:

```bash
python cli.py --web
python cli.py --web --port 9090 --host 127.0.0.1
```

Then open `http://localhost:8080` in your browser.

Features:
- 🎨 Modern dark theme
- 📋 Paste & download — single or batch
- 🔍 Auto platform detection
- 📊 Download history & stats
- ⏳ Real-time progress tracking
- 📱 Mobile responsive

## 🐳 Docker

```bash
# Build
docker build -t xcrdownloader .

# Run
docker run -d \
  -p 8080:8080 \
  -v $(pwd)/downloads:/app/downloads \
  --name xcrdownloader \
  xcrdownloader

# Or with docker-compose
docker-compose up -d
```

## 📸 Supported Platforms

| Platform | Content Types | Method |
|----------|--------------|--------|
| 📸 Instagram | Reels, Stories, Posts, IGTV | yt-dlp |
| 🎵 TikTok | Videos (no watermark), Audio | yt-dlp |
| 🐦 X/Twitter | Videos, Images, GIFs | yt-dlp |
| 📌 Pinterest | Videos, Images, GIFs | Custom scraper + yt-dlp |
| 🌐 1800+ more | YouTube, Reddit, Facebook... | yt-dlp |

## 🔧 Configuration

Create a `config.json` (optional):

```json
{
  "output_dir": "downloads",
  "quality": "best",
  "max_workers": 3,
  "web_port": 8080,
  "web_host": "0.0.0.0"
}
```

## 📁 Project Structure

```
XCRDownloader/
├── cli.py                 # CLI entry point
├── run.py                 # Quick start script
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker build
├── docker-compose.yml     # Docker Compose
├── src/
│   ├── __init__.py
│   ├── engine.py          # Download engine (router)
│   ├── web.py             # Flask Web UI backend
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── base.py        # Base downloader (yt-dlp)
│   │   ├── instagram.py   # Instagram handler
│   │   ├── tiktok.py      # TikTok handler
│   │   ├── twitter.py     # X/Twitter handler
│   │   ├── pinterest.py   # Pinterest handler
│   │   └── generic.py     # Generic (1800+ sites)
│   └── utils/
│       ├── __init__.py
│       └── helpers.py     # Utility functions
├── templates/
│   └── index.html         # Web UI template
├── static/
│   ├── css/style.css      # Dark theme styles
│   └── js/app.js          # Frontend logic
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
