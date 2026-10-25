#!/usr/bin/env bash
# ==============================================================================
# Stream Cloner — One-Command macOS .DMG Installer Builder
# Usage: ./scripts/build/build-macos-dmg.sh
# Produces: dist/Stream-Cloner-macOS.dmg (and dist/Stream Cloner.app)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}   Building Standalone macOS Installer: Stream-Cloner.dmg     ${NC}"
echo -e "${CYAN}==============================================================${NC}"

VENV_DIR="$PROJECT_ROOT/.venv"

# Ensure environment is initialized with Python 3.12+ and PyInstaller
if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.12 "$VENV_DIR" 2>/dev/null || uv venv "$VENV_DIR"
    else
        /opt/homebrew/bin/python3.12 -m venv "$VENV_DIR" 2>/dev/null || python3 -m venv "$VENV_DIR"
    fi
fi

echo -e "${BLUE}[1/2] Installing PyInstaller & bundling dependencies...${NC}"
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VENV_DIR/bin/python" -U -r "$PROJECT_ROOT/requirements.txt"
    uv pip install --python "$VENV_DIR/bin/python" -U "yt-dlp[default]" deno yt-dlp-ejs pyinstaller
else
    "$VENV_DIR/bin/pip" install -U -r "$PROJECT_ROOT/requirements.txt"
    "$VENV_DIR/bin/pip" install -U "yt-dlp[default]" deno yt-dlp-ejs pyinstaller
fi

echo -e "${BLUE}[2/2] Compiling Stream Cloner.app and packaging Stream-Cloner-macOS.dmg ...${NC}"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/build_installer.py"

echo -e "${GREEN}[✓] Done! Your distributable macOS installer is ready at:${NC}"
echo -e "${GREEN}    $PROJECT_ROOT/dist/Stream-Cloner-macOS.dmg${NC}"
if [ "$(uname -s)" = "Darwin" ]; then
    open -R "$PROJECT_ROOT/dist/Stream-Cloner-macOS.dmg" 2>/dev/null || true
fi
