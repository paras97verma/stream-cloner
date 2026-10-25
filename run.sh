#!/usr/bin/env bash
# ==============================================================================
# Stream Cloner — Local Application Launcher
# Starts the standalone Vue.js + Python desktop app locally.
# Distribution packaging (DMG/EXE) is managed via Makefile ('make dmg', 'make exe').
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# Ensure Homebrew and common binary paths are in PATH
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"

# Color styling
if [ -t 1 ]; then
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    BLUE='\033[0;34m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    CYAN=''
    GREEN=''
    BLUE=''
    YELLOW=''
    RED=''
    NC=''
fi

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}   Stream Cloner — Native Desktop YouTube & Media Cloner      ${NC}"
echo -e "${CYAN}==============================================================${NC}"

VENV_DIR="$PROJECT_ROOT/.venv"
PID_FILE="$VENV_DIR/app.pid"

# If already running, bring existing window to front on macOS
if [ -f "$PID_FILE" ]; then
    EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo -e "${GREEN}[✓] Stream Cloner is already active (PID: $EXISTING_PID). Bringing window to front...${NC}"
        if [ "$(uname -s)" = "Darwin" ]; then
            osascript -e "tell application \"System Events\" to set frontmost of every process whose unix id is $EXISTING_PID to true" 2>/dev/null || true
        fi
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Ensure Python virtual environment exists
if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
    echo -e "${BLUE}[*] Initializing Python virtual environment in .venv ...${NC}"
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.12 "$VENV_DIR" 2>/dev/null || uv venv "$VENV_DIR"
    else
        python3 -m venv "$VENV_DIR"
    fi
fi

# Ensure dependencies installed
if ! "$VENV_DIR/bin/python" -c "import webview, bottle, yt_dlp" >/dev/null 2>&1; then
    echo -e "${BLUE}[*] Installing required backend dependencies...${NC}"
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$VENV_DIR/bin/python" -U -r "$PROJECT_ROOT/requirements.txt"
    else
        "$VENV_DIR/bin/python" -m ensurepip --default-pip >/dev/null 2>&1 || true
        "$VENV_DIR/bin/python" -m pip install -U -r "$PROJECT_ROOT/requirements.txt"
    fi
fi

# Ensure frontend build exists
DIST_INDEX="$PROJECT_ROOT/src/stream_cloner/web/dist/index.html"
if [ ! -f "$DIST_INDEX" ]; then
    echo -e "${BLUE}[*] Building production Vue.js frontend assets...${NC}"
    if command -v npm >/dev/null 2>&1; then
        npm --prefix "$PROJECT_ROOT/frontend" run build
    else
        echo -e "${RED}[!] Node.js / npm is required to build the frontend. Please install Node.js.${NC}"
        exit 1
    fi
fi

# Configure FFmpeg binary if needed
if ! command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_EXE="$("$VENV_DIR/bin/python" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || true)"
    if [ -n "$FFMPEG_EXE" ] && [ -x "$FFMPEG_EXE" ]; then
        mkdir -p "$VENV_DIR/bin"
        ln -sf "$FFMPEG_EXE" "$VENV_DIR/bin/ffmpeg"
    fi
fi

export PATH="$VENV_DIR/bin:$PATH"
export PYTHONWARNINGS="ignore:urllib3 v2 only supports OpenSSL:UserWarning"

CERT_PATH="$("$VENV_DIR/bin/python" -c "import certifi; print(certifi.where())" 2>/dev/null || true)"
if [ -n "$CERT_PATH" ]; then
    export SSL_CERT_FILE="$CERT_PATH"
    export REQUESTS_CA_BUNDLE="$CERT_PATH"
fi

echo -e "${GREEN}[*] Launching Stream Cloner Desktop App...${NC}"

# Execute app and track PID
"$VENV_DIR/bin/python" "$PROJECT_ROOT/app.py" "$@" &
APP_PID=$!
echo "$APP_PID" > "$PID_FILE"

trap 'rm -f "$PID_FILE"; kill "$APP_PID" 2>/dev/null || true; exit 0' SIGINT SIGTERM EXIT

wait "$APP_PID"
EXIT_CODE=$?
rm -f "$PID_FILE"
exit "$EXIT_CODE"
