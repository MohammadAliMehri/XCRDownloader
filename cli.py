#!/usr/bin/env python3
"""XCRDownloader CLI — command-line interface for the universal downloader."""
import os
import sys
import argparse
import json

# Windows UTF-8 fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from src.engine import DownloaderEngine
from src.search import search_music
from src.utils.helpers import print_banner, format_filesize, detect_platform


def main():
    parser = argparse.ArgumentParser(
        prog="xcrdownloader",
        description="⚡ XCRDownloader — Universal Social Media Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  xcrdownloader https://www.instagram.com/reel/ABC123/
  xcrdownloader https://www.tiktok.com/@user/video/1234567890
  xcrdownloader https://twitter.com/user/status/1234567890
  xcrdownloader https://www.pinterest.com/pin/1234567890/
  xcrdownloader https://www.youtube.com/watch?v=dQw4w9WgXcQ
  xcrdownloader https://music.youtube.com/watch?v=abc123
  xcrdownloader https://soundcloud.com/artist/track-name
  xcrdownloader -u URL1 -u URL2 -u URL3
  xcrdownloader -f urls.txt
  xcrdownloader --info URL
  xcrdownloader --web
        """,
    )

    parser.add_argument("urls", nargs="*", help="URL(s) to download")
    parser.add_argument("-u", "--url", action="append", help="Add URL (repeatable)")
    parser.add_argument("-f", "--file", help="File containing URLs (one per line)")
    parser.add_argument("-q", "--quality", choices=["best", "hd", "sd"],
                        default="best", help="Video quality (default: best)")
    parser.add_argument("-o", "--output", default="downloads",
                        help="Output directory (default: downloads)")
    parser.add_argument("--audio", action="store_true", help="Extract audio only (MP3)")
    parser.add_argument("--info", action="store_true", help="Get info/preview without downloading")
    parser.add_argument("--detect", action="store_true", help="Detect platform only")
    parser.add_argument("--workers", type=int, default=3,
                        help="Parallel download workers (default: 3)")
    parser.add_argument("--web", action="store_true", help="Launch web UI")
    parser.add_argument("--port", type=int, default=8080, help="Web UI port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Web UI host (default: 0.0.0.0)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--search", action="store_true", help="Search YouTube, YouTube Music, and SoundCloud")
    parser.add_argument("-v", "--version", action="version", version="XCRDownloader v1.7.0")

    args = parser.parse_args()

    # Collect all URLs
    all_urls = list(args.urls or [])
    if args.url:
        all_urls.extend(args.url)
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        all_urls.append(line)
        except FileNotFoundError:
            print(f"\n  ❌ File not found: {args.file}\n")
            return
        except Exception as e:
            print(f"\n  ❌ Error reading file: {e}\n")
            return

    # No args = double-click = launch Web UI automatically
    if not all_urls and not args.web and not args.file:
        args.web = True

    # Launch web UI if requested
    if args.web:
        import webbrowser
        import threading
        from src.web import create_app
        print_banner()
        port = args.port
        host = args.host
        url = f"http://127.0.0.1:{port}"
        print(f"\n  🌐 Starting XCRDownloader Web UI on {url}")
        print(f"  📁 Downloads will be saved to: {os.path.abspath(args.output)}")
        print(f"  🖥️  Browser will open automatically...")
        print(f"  ⛔ Press Ctrl+C to stop\n")
        app = create_app(args.output)
        # Open browser after a short delay
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        try:
            app.run(host=host, port=port, debug=False)
        except KeyboardInterrupt:
            print("\n  👋 Shutting down...")
        return

    print_banner()
    engine = DownloaderEngine(output_dir=args.output)

    # Detect mode
    if args.detect:
        for url in all_urls:
            info = engine.detect(url)
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                print(f"  🔍 {info['platform'].upper()} → {info['handler']}")
                print(f"     URL: {info['url']}")
        return

    # Info / Preview mode
    if args.info:
        for url in all_urls:
            print(f"\n  📋 Fetching preview: {url}")
            try:
                result = engine.get_info(url)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                if result.get("success"):
                    preview = result.get("preview", {})
                    info = result.get("info", {})
                    p = preview or info
                    platform = result.get("platform", "Unknown").upper()
                    print(f"  ✅ Platform: {platform}")
                    print(f"     Title:    {p.get('title', 'N/A')}")
                    print(f"     Author:   {p.get('uploader', 'N/A')}")
                    if p.get("duration_str"):
                        print(f"     Duration: {p['duration_str']}")
                    elif p.get("duration"):
                        print(f"     Duration: {p['duration']}s")
                    if p.get("view_count"):
                        print(f"     Views:    {p['view_count']:,}")
                    if p.get("like_count"):
                        print(f"     Likes:    {p['like_count']:,}")
                    if p.get("thumbnail"):
                        print(f"     Thumb:    {p['thumbnail']}")
                    if p.get("description"):
                        desc = p["description"][:200].replace("\n", " ")
                        print(f"     Desc:     {desc}")
                else:
                    print(f"  ❌ Error: {result.get('error', 'Unknown')}")
        return

    # Search mode
    if args.search:
        query = " ".join(all_urls) if all_urls else ""
        if not query:
            print("\n  ❌ Provide a search query: python cli.py --search 'query'\n")
            return
        print(f"\n  🔍 Searching: \"{query}\"")
        print(f"  📡 Sources: YouTube · YouTube Music · SoundCloud\n")
        try:
            result = search_music(query)
        except Exception as e:
            print(f"  ❌ Search error: {e}\n")
            return
        results = result.get("results", [])
        if not results:
            print("  No results found.\n")
            return
        for i, r in enumerate(results[:30], 1):
            src = r.get("source", "?").upper()
            kind = r.get("kind", "track")
            icon = {"track": "🎵", "album": "💿", "artist": "👤"}.get(kind, "🎵")
            title = r.get("title", "?")
            artist = r.get("artist", "")
            dur = ""
            if r.get("duration"):
                m, s = divmod(int(r["duration"]), 60)
                dur = f" [{m}:{s:02d}]"
            preview = " 🎧" if r.get("preview_url") else ""
            print(f"  {i:2d}. {icon} {title}")
            if artist:
                print(f"      {artist}{dur}  [{src}]{preview}")
            if args.json:
                import json as _json
                print(_json.dumps(r, indent=2, default=str))
        print(f"\n  📊 {len(results)} results found")
        print(f"  💡 Use the Web UI (--web) to play and download search results\n")
        return

    # Download mode
    kwargs = {}
    if args.audio:
        kwargs["audio_only"] = True

    print(f"\n  📥 Downloading {len(all_urls)} URL(s) [quality={args.quality}]")
    print(f"  📁 Output: {os.path.abspath(args.output)}\n")

    if len(all_urls) == 1:
        result = engine.download(all_urls[0], quality=args.quality, **kwargs)
        _print_result(result, args.json)
    else:
        results = engine.download_batch(all_urls, quality=args.quality,
                                         max_workers=args.workers, **kwargs)
        success = sum(1 for r in results if r.get("success"))
        print(f"\n  📊 Results: {success}/{len(results)} downloaded successfully\n")
        for result in results:
            _print_result(result, args.json)


def _print_result(result: dict, as_json: bool = False):
    """Print a download result."""
    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    url = result.get("url", "")
    platform = result.get("platform", "Unknown").upper()

    if result.get("success"):
        print(f"  ✅ [{platform}] Downloaded successfully!")
        for f in result.get("files", []):
            print(f"     📄 {f['path']}")
            print(f"        Size: {f.get('size_human', format_filesize(f.get('size', 0)))}")
        info = result.get("info", {})
        if info.get("title"):
            print(f"     📌 Title: {info['title'][:80]}")
    else:
        print(f"  ❌ [{platform}] Failed: {result.get('error', 'Unknown error')}")
        print(f"     URL: {url}")

    print()


if __name__ == "__main__":
    main()
