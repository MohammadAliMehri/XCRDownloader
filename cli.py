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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine import DownloaderEngine
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
    parser.add_argument("--info", action="store_true", help="Get info without downloading")
    parser.add_argument("--detect", action="store_true", help="Detect platform only")
    parser.add_argument("--workers", type=int, default=3,
                        help="Parallel download workers (default: 3)")
    parser.add_argument("--web", action="store_true", help="Launch web UI")
    parser.add_argument("--port", type=int, default=8080, help="Web UI port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Web UI host (default: 0.0.0.0)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-v", "--version", action="version", version="XCRDownloader v1.0.0")

    args = parser.parse_args()

    # Collect all URLs
    all_urls = list(args.urls or [])
    if args.url:
        all_urls.extend(args.url)
    if args.file:
        with open(args.file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_urls.append(line)

    # Launch web UI if requested
    if args.web:
        from src.web import create_app
        print_banner()
        print(f"\n  🌐 Starting XCRDownloader Web UI on http://{args.host}:{args.port}")
        print(f"  📁 Downloads will be saved to: {os.path.abspath(args.output)}\n")
        app = create_app(args.output)
        app.run(host=args.host, port=args.port, debug=False)
        return

    # Need at least one URL for non-web mode
    if not all_urls:
        print_banner()
        parser.print_help()
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

    # Info mode
    if args.info:
        for url in all_urls:
            print(f"\n  📋 Fetching info: {url}")
            result = engine.get_info(url)
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                if result.get("success"):
                    info = result.get("info", {})
                    print(f"  ✅ Platform: {result.get('platform', 'Unknown')}")
                    if isinstance(info, dict):
                        print(f"     Title: {info.get('title', 'N/A')}")
                        print(f"     Uploader: {info.get('uploader', 'N/A')}")
                        if info.get("duration"):
                            print(f"     Duration: {info['duration']}s")
                        if info.get("view_count"):
                            print(f"     Views: {info['view_count']:,}")
                else:
                    print(f"  ❌ Error: {result.get('error', 'Unknown')}")
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
