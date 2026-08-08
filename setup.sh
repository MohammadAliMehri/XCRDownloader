#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
#  XCRDownloader — Linux / macOS Setup Script
#  Creates venv, installs all deps, builds .exe via PyInstaller
# ═══════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════╗"
echo "║   ⚡ XCRDownloader — Linux/macOS Setup       ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Check Python ───
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo -e "${RED}❌ Python 3 not found. Install Python 3.10+ first.${NC}"
    exit 1
fi
PY_VER=$($PYTHON --version 2>&1)
echo -e "${GREEN}✅ Found: ${PY_VER}${NC}"

# ─── Check ffmpeg ───
if command -v ffmpeg &>/dev/null; then
    FF_VER=$(ffmpeg -version 2>&1 | head -1)
    echo -e "${GREEN}✅ ffmpeg: ${FF_VER}${NC}"
else
    echo -e "${YELLOW}⚠  ffmpeg not found. Installing...${NC}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y ffmpeg
    elif command -v brew &>/dev/null; then
        brew install ffmpeg
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y ffmpeg
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm ffmpeg
    else
        echo -e "${RED}❌ Cannot auto-install ffmpeg. Install it manually.${NC}"
        echo "   https://ffmpeg.org/download.html"
    fi
fi

# ─── Create venv ───
echo -e "\n${CYAN}📦 Creating virtual environment...${NC}"
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip -q

# ─── Install dependencies ───
echo -e "${CYAN}📦 Installing Python dependencies...${NC}"
pip install -r requirements.txt -q
echo -e "${GREEN}✅ All packages installed${NC}"

# ─── Build .exe (optional) ───
echo ""
read -p "🔨 Build standalone executable? (y/N): " BUILD_EXE
if [[ "$BUILD_EXE" =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}🔨 Building executable with PyInstaller...${NC}"
    python build.py
    if [ -f "dist/XCRDownloader" ] || [ -f "dist/XCRDownloader.exe" ]; then
        echo -e "${GREEN}✅ Build complete! Executable in dist/${NC}"
    else
        echo -e "${RED}❌ Build failed. Check output above.${NC}"
    fi
fi

echo -e "\n${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${GREEN} ✅ Setup complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo ""
echo "  Usage:"
echo "    source venv/bin/activate"
echo "    python cli.py <URL>"
echo "    python cli.py --web"
echo ""
echo "  Or build standalone:"
echo "    python build.py"
echo ""
