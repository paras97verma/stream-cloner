#!/usr/bin/env bash
# ==============================================================================
# Stream Cloner — macOS & Linux Launcher (Ultra-HD Video, Playlists & Audio)
# Usage: ./scripts/launch/launch.sh [--reinstall | --update]
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="$PROJECT_ROOT/.venv"
MARKER_FILE="$VENV_DIR/.setup_version"
PID_FILE="$VENV_DIR/app.pid"
CURRENT_SETUP_VER="7"

# Ensure Homebrew paths are visible on Apple Silicon (/opt/homebrew) and Intel (/usr/local)
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}   Stream Cloner — YouTube Video, Playlist & Audio Studio     ${NC}"
echo -e "${CYAN}==============================================================${NC}"

FORCE_SETUP=0
UPDATE_YTDLP=0
for arg in "$@"; do
    case "$arg" in
        --reinstall|--setup)
            FORCE_SETUP=1
            ;;
        --update)
            UPDATE_YTDLP=1
            ;;
    esac
done

# If already running and not updating/reinstalling, bring window to front
if [ "$FORCE_SETUP" -eq 0 ] && [ "$UPDATE_YTDLP" -eq 0 ] && [ -f "$PID_FILE" ]; then
    EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo -e "${GREEN}[✓] Stream Cloner is already running (PID: $EXISTING_PID). Bringing to foreground...${NC}"
        if [ "$(uname -s)" = "Darwin" ]; then
            osascript -e "tell application \"System Events\" to set frontmost of every process whose unix id is $EXISTING_PID to true" 2>/dev/null || true
        fi
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Locate Python 3.12 / 3.13 / 3.11 / 3.10
find_python() {
    for ver in 3.12 3.13 3.11 3.10 3 3.14; do
        for prefix in "/opt/homebrew/bin" "/usr/local/bin" "$(command -v "python$ver" 2>/dev/null | xargs dirname 2>/dev/null || echo "")"; do
            if [ -n "$prefix" ] && [ -x "$prefix/python$ver" ]; then
                if "$prefix/python$ver" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
                    echo "$prefix/python$ver"
                    return 0
                fi
            fi
        done
    done
    for candidate in "/opt/homebrew/bin/python3" "/usr/local/bin/python3" "$(command -v python3 2>/dev/null || true)" "/usr/bin/python3"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

HAS_UV=0
if command -v uv >/dev/null 2>&1; then
    HAS_UV=1
fi

PYTHON_BIN="$(find_python || true)"
if [ "$HAS_UV" -eq 0 ] && [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}[!] Python 3.10+ was not found on this system.${NC}"
    echo -e "${YELLOW}Install Python via Homebrew: brew install python@3.12 (or https://www.python.org/downloads/)${NC}"
    exit 1
fi

INSTALLED_VER="0"
if [ -f "$MARKER_FILE" ]; then
    INSTALLED_VER="$(cat "$MARKER_FILE" 2>/dev/null || echo "0")"
fi

NEEDS_FULL_SETUP=0
NEEDS_UPDATE=0

if [ "$FORCE_SETUP" -eq 1 ] || [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
    NEEDS_FULL_SETUP=1
else
    if ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        NEEDS_FULL_SETUP=1
    elif [ "$INSTALLED_VER" != "$CURRENT_SETUP_VER" ] || [ "$UPDATE_YTDLP" -eq 1 ]; then
        NEEDS_UPDATE=1
    fi
fi

if [ "$NEEDS_FULL_SETUP" -eq 1 ]; then
    echo -e "${BLUE}[1/3] Creating Python virtual environment in .venv ...${NC}"
    rm -rf "$VENV_DIR"

    if [ "$HAS_UV" -eq 1 ]; then
        echo -e "${GREEN}[*] Using fast uv environment manager...${NC}"
        uv venv --python 3.12 "$VENV_DIR" 2>/dev/null || \
        uv venv --python 3.13 "$VENV_DIR" 2>/dev/null || \
        uv venv --python 3.11 "$VENV_DIR" 2>/dev/null || \
        uv venv "$VENV_DIR"
    else
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi

    echo -e "${BLUE}[2/3] Installing dependencies (yt-dlp, pywebview, bottle, Pillow, FFmpeg)...${NC}"
    if [ "$HAS_UV" -eq 1 ]; then
        uv pip install --python "$VENV_DIR/bin/python" -U -r "$PROJECT_ROOT/requirements.txt"
        uv pip install --python "$VENV_DIR/bin/python" -U "yt-dlp[default]" deno yt-dlp-ejs 2>/dev/null || true
    else
        "$VENV_DIR/bin/python" -m pip install --upgrade pip wheel setuptools --quiet
        "$VENV_DIR/bin/pip" install -U -r "$PROJECT_ROOT/requirements.txt"
        "$VENV_DIR/bin/pip" install -U "yt-dlp[default]" deno yt-dlp-ejs 2>/dev/null || true
    fi

    echo -e "${BLUE}[3/3] Configuring FFmpeg & JS runtime...${NC}"
    if ! command -v ffmpeg >/dev/null 2>&1; then
        FFMPEG_EXE="$("$VENV_DIR/bin/python" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || true)"
        if [ -n "$FFMPEG_EXE" ] && [ -x "$FFMPEG_EXE" ]; then
            ln -sf "$FFMPEG_EXE" "$VENV_DIR/bin/ffmpeg"
            echo -e "${GREEN}[✓] Configured standalone FFmpeg binary in .venv/bin/ffmpeg${NC}"
        fi
    else
        echo -e "${GREEN}[✓] Detected system FFmpeg: $(command -v ffmpeg)${NC}"
    fi

    echo "$CURRENT_SETUP_VER" > "$MARKER_FILE"
    echo -e "${GREEN}[✓] Setup complete!${NC}"

elif [ "$NEEDS_UPDATE" -eq 1 ]; then
    echo -e "${BLUE}[*] Updating dependencies...${NC}"
    if [ "$HAS_UV" -eq 1 ]; then
        uv pip install --python "$VENV_DIR/bin/python" -U -r "$PROJECT_ROOT/requirements.txt"
    else
        "$VENV_DIR/bin/pip" install -U -r "$PROJECT_ROOT/requirements.txt" --quiet
    fi
    echo "$CURRENT_SETUP_VER" > "$MARKER_FILE"
    echo -e "${GREEN}[✓] Environment updated to v${CURRENT_SETUP_VER}.${NC}"
else
    echo -e "${GREEN}[✓] Environment verified.${NC}"
fi

# Ensure Vue.js frontend is compiled
DIST_INDEX="$PROJECT_ROOT/src/stream_cloner/web/dist/index.html"
if [ ! -f "$DIST_INDEX" ]; then
    echo -e "${BLUE}[*] Building production Vue.js frontend assets...${NC}"
    npm --prefix "$PROJECT_ROOT/frontend" run build
fi

export PATH="$VENV_DIR/bin:$PATH"
export PYTHONWARNINGS="ignore:urllib3 v2 only supports OpenSSL:UserWarning"

CERT_PATH="$("$VENV_DIR/bin/python" -c "import certifi; print(certifi.where())" 2>/dev/null || true)"
if [ -n "$CERT_PATH" ]; then
    export SSL_CERT_FILE="$CERT_PATH"
    export REQUESTS_CA_BUNDLE="$CERT_PATH"
fi

echo -e "${CYAN}[*] Launching Stream Cloner GUI...${NC}"
"$VENV_DIR/bin/python" "$PROJECT_ROOT/app.py" &
APP_PID=$!
echo "$APP_PID" > "$PID_FILE"
wait "$APP_PID"
EXIT_CODE=$?
rm -f "$PID_FILE"
exit "$EXIT_CODE"
