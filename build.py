#!/usr/bin/env python3
"""Build XCRDownloader standalone executable with PyInstaller."""
import os
import sys
import shutil
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
IS_WINDOWS = sys.platform == "win32"

# PyInstaller arguments
ARGS = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--name", "XCRDownloader",
    "--add-data", f"templates{os.pathsep}templates",
    "--add-data", f"static{os.pathsep}static",
    "--add-data", f"src{os.pathsep}src",
    "--hidden-import", "src.engine",
    "--hidden-import", "src.web",
    "--hidden-import", "src.platforms.instagram",
    "--hidden-import", "src.platforms.tiktok",
    "--hidden-import", "src.platforms.twitter",
    "--hidden-import", "src.platforms.pinterest",
    "--hidden-import", "src.platforms.youtube",
    "--hidden-import", "src.platforms.soundcloud",
    "--hidden-import", "src.platforms.generic",
    "--hidden-import", "src.platforms.base",
    "--hidden-import", "src.utils.helpers",
    "--hidden-import", "yt_dlp",
    "--hidden-import", "flask",
    "--hidden-import", "flask_cors",
    "--hidden-import", "bs4",
    "--hidden-import", "lxml",
    "--hidden-import", "requests",
    "--hidden-import", "rich",
    "--hidden-import", "gallery_dl",
    "--collect-all", "yt_dlp",
    "--collect-all", "flask",
    "--collect-all", "gallery_dl",
]

# Windows: use --noconsole to hide the CMD window when double-clicking
# The browser opens automatically, user sees the Web UI directly
if IS_WINDOWS:
    ARGS.append("--noconsole")
else:
    ARGS.append("--console")

# Icon
ICON = os.path.join(PROJECT_DIR, "assets", "icon.ico")
if os.path.exists(ICON):
    ARGS.extend(["--icon", ICON])

ARGS.append("cli.py")


def build():
    print("=" * 50)
    print("  Building XCRDownloader executable")
    print("=" * 50)
    print()

    for d in [BUILD_DIR, DIST_DIR]:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

    print(f"  Python:     {sys.executable}")
    print(f"  Platform:   {sys.platform}")
    print(f"  Console:    {'no (hidden)' if IS_WINDOWS else 'yes'}")
    print(f"  Output:     {DIST_DIR}")
    print()

    result = subprocess.run(ARGS, cwd=PROJECT_DIR)

    if result.returncode != 0:
        print("\n❌ Build failed!")
        return False

    ext = ".exe" if IS_WINDOWS else ""
    exe_path = os.path.join(DIST_DIR, f"XCRDownloader{ext}")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n✅ Build successful!")
        print(f"   Executable: {exe_path}")
        print(f"   Size: {size_mb:.1f} MB")
        print()
        print("   Double-click XCRDownloader.exe to:")
        print("   → Start the server")
        print("   → Open the Web UI in your browser")
        print()
        print("   CLI usage:")
        print(f"     {exe_path} <URL>")
        print(f"     {exe_path} --audio https://youtube.com/watch?v=abc")
        print(f"     {exe_path} -f urls.txt")
        return True
    else:
        print("\n❌ Build completed but executable not found!")
        return False


if __name__ == "__main__":
    ok = build()
    sys.exit(0 if ok else 1)
