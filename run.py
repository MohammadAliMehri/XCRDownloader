#!/usr/bin/env python3
"""XCRDownloader — Quick start script."""
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (sys.path hack removed — packaging handles imports)

from src.utils.helpers import print_banner


def main():
    print_banner()
    print("""
  Quick Start:
  ═══════════════════════════════════════════════════

  1. CLI Mode:
     python cli.py <URL>
     python cli.py https://www.instagram.com/reel/ABC123/
     python cli.py --quality hd https://www.tiktok.com/@user/video/123
     python cli.py --audio https://twitter.com/user/status/456
     python cli.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
     python cli.py https://music.youtube.com/watch?v=abc
     python cli.py https://soundcloud.com/artist/track-name

  2. Web UI Mode:
     python cli.py --web
     python cli.py --web --port 9090

  3. Batch Download:
     python cli.py -u URL1 -u URL2 -u URL3
     python cli.py -f urls.txt

  4. Preview / Info (no download):
     python cli.py --info <URL>

  Supported Platforms:
    ▶️  YouTube     — Videos, Music, Playlists, Shorts
    🎶 YT Music    — Songs, Albums, Playlists (auto MP3)
    🔊 SoundCloud  — Tracks, Playlists, Albums (auto MP3)
    📸 Instagram   — Reels, Stories, Posts, IGTV
    🎵 TikTok      — Videos, No Watermark, Audio
    🐦 X/Twitter   — Videos, Images, GIFs
    📌 Pinterest   — Videos, Images, GIFs
    🌐 1800+ sites via yt-dlp

  ═══════════════════════════════════════════════════
    """)


if __name__ == "__main__":
    main()
