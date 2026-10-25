#!/usr/bin/env bash
set -e

echo "====================================================="
echo "  🚀 Installing Stream Cloner for macOS"
echo "====================================================="

REPO="paras97verma/stream-cloner"
TMP_DIR=$(mktemp -d -t stream_cloner_install)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "📦 Fetching latest macOS release..."
LATEST_RELEASE=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null || true)
DOWNLOAD_URL=$(echo "$LATEST_RELEASE" | grep -o 'https://[^"]*Stream-Cloner-macOS\.dmg' | head -n 1)

if [ -z "$DOWNLOAD_URL" ]; then
    DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/Stream-Cloner-macOS.dmg"
fi

DMG_PATH="${TMP_DIR}/Stream-Cloner-macOS.dmg"
echo "⬇️  Downloading Stream Cloner DMG..."
curl -fL "$DOWNLOAD_URL" -o "$DMG_PATH"

# Strip quarantine extended attributes
xattr -cr "$DMG_PATH" 2>/dev/null || true

echo "💿 Mounting disk image..."
MOUNT_DIR=$(hdiutil attach "$DMG_PATH" -nobrowse -noverify 2>/dev/null | grep -o '/Volumes/.*' | head -n 1)

if [ -z "$MOUNT_DIR" ] || [ ! -d "$MOUNT_DIR" ]; then
    echo "❌ Failed to mount installer disk image."
    exit 1
fi

echo "📂 Installing to /Applications/Stream Cloner.app..."
rm -rf "/Applications/Stream Cloner.app"
cp -R "${MOUNT_DIR}/Stream Cloner.app" /Applications/

# Remove quarantine from installed app bundle
xattr -cr "/Applications/Stream Cloner.app" 2>/dev/null || true

echo "⏏️  Ejecting installer..."
hdiutil detach "$MOUNT_DIR" -quiet 2>/dev/null || true

echo "====================================================="
echo "  ✅ Stream Cloner installed successfully!"
echo "  🎉 Launch it from Applications or Spotlight Search"
echo "====================================================="
