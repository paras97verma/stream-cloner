# Stream Cloner

[![Build & Release Installers](https://github.com/paras97verma/stream-cloner/actions/workflows/build-installers.yml/badge.svg)](https://github.com/paras97verma/stream-cloner/actions/workflows/build-installers.yml)
[![GitHub Releases](https://img.shields.io/github/v/release/paras97verma/stream-cloner?label=Latest%20Release&color=blue)](https://github.com/paras97verma/stream-cloner/releases/latest)
[![macOS Download](https://img.shields.io/badge/Download-macOS%20.dmg-38bdf8?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/paras97verma/stream-cloner/releases/latest/download/Stream-Cloner-macOS.dmg)
[![Windows Download](https://img.shields.io/badge/Download-Windows%20.exe-a855f7?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/paras97verma/stream-cloner/releases/latest/download/Stream-Cloner-Windows.exe)

**Stream Cloner** is a production-grade, cross-platform YouTube media studio engineered for ultra-high-resolution video (12K, 8K, 5K, 4K UHD, 1440p, 1080p at 24–240 FPS with HDR), full YouTube playlist downloads, and high-fidelity audio extraction.

Built with a high-performance **Vue 3 + Tailwind CSS** dark glassmorphism interface and a native **Python 3.12 / PyWebView** engine with multi-threaded parallel downloads.

---

## 📥 Direct Downloads & Installers

| Platform | Installer / Executable | Version Pinning | Architecture |
| :--- | :--- | :--- | :--- |
| **macOS** | [**Download `.dmg` (Latest)**](https://github.com/paras97verma/stream-cloner/releases/latest/download/Stream-Cloner-macOS.dmg) | [All Pinned Versions](https://github.com/paras97verma/stream-cloner/releases) | Universal (Apple Silicon M1-M4 & Intel x64) |
| **Windows** | [**Download `.exe` (Latest)**](https://github.com/paras97verma/stream-cloner/releases/latest/download/Stream-Cloner-Windows.exe) | [All Pinned Versions](https://github.com/paras97verma/stream-cloner/releases) | x64 Architecture |

> **Automated Builds:** Every commit pushed to `main` triggers automated GitHub Actions builds that compile, test, and release fresh version-pinned DMG and EXE installers to the [Releases page](https://github.com/paras97verma/stream-cloner/releases).

---

## Key Features

- **Dynamic Format Discovery (Zero Hardcoding):**
  - Eliminates static resolution menus. Formats are inspected dynamically using live YouTube stream metadata.
  - Automatically identifies resolutions, actual frame rates (24–240 FPS), HDR variants, container types, and modern codecs (AV1, VP9, H.264).
  - Defaults to the **highest available quality** discovered for each media item.
- **Apple-Inspired Dark Glassmorphism Design:**
  - Modern translucent glass card aesthetics, high contrast dark theme, vibrant gradient accents, and subtle micro-animations.
  - Native system typography stack (`Plus Jakarta Sans`, `JetBrains Mono`).
- **Parallel Multi-Download Concurrency:**
  - Configurable simultaneous download worker slots (1 to 5 concurrent streams).
  - Live per-slot progress bars, speed, and ETA monitoring.
- **High-Fidelity Audio Extraction:**
  - Uncompressed source audio extraction or high-bitrate MP3 transcoding (320 kbps Studio Master, 256 kbps, 192 kbps, 128 kbps).
- **Safety, Reliability & Concurrency:**
  - Non-blocking asynchronous background execution for format analysis and downloading.
  - Safe argument arrays without shell interpolation to prevent command injection.
  - Safe Unicode filename sanitization and atomic file finalization.
  - Clean cancellation support that immediately releases system resources.
- **Download History:**
  - Built-in history drawer recording recent downloads with one-click "Show in Finder / Show in Explorer".

---

## Architecture Overview

Stream Cloner follows **SOLID principles** and a layered separation of concerns:

```text
Stream-Cloner/
├── Makefile                          # Unified build and automation targets
├── run.sh                            # Root interactive control menu (macOS / Linux)
├── run.bat                           # Root interactive control menu (Windows)
├── app.py                            # Thin application entry point
├── pyproject.toml                    # Standard Python package and build metadata
├── requirements.txt                  # Production dependencies
├── README.md                         # Documentation
├── frontend/                         # Standalone Vue.js 3 + Tailwind CSS frontend
│   ├── src/
│   │   ├── App.vue                   # High-contrast glassmorphic UI component
│   │   ├── api.js                    # Dual-mode pywebview & REST client
│   │   └── style.css                 # Glass tokens, 3D perspective, responsive rules
│   └── vite.config.js                # Vite build pipeline compiling to web/dist
├── scripts/
│   ├── build/
│   │   ├── build_installer.py        # Standalone .dmg (macOS) and .exe (Windows) builder
│   │   ├── build-macos-dmg.sh        # macOS one-command installer script
│   │   └── build-windows-exe.bat     # Windows one-command installer script
│   └── launch/
│       ├── launch.sh                 # macOS / Linux instant launcher
│       ├── launch.bat                # Windows instant launcher
│       └── launch.ps1                # Windows PowerShell launcher
├── src/
│   └── stream_cloner/
│       ├── __init__.py
│       ├── config.py                 # Persistent settings and theme preferences
│       ├── bootstrap.py              # Application lifecycle and fallback launcher
│       ├── domain/
│       │   ├── enums.py              # DownloadMode, ScopeMode, ThemePreference, ActiveTheme
│       │   ├── models.py             # VideoFormatOption, AudioFormatOption, MediaMetadata
│       │   └── exceptions.py         # StreamClonerError and domain exception hierarchy
│       ├── application/
│       │   ├── format_service.py     # Dynamic format discovery, filtering, and selector construction
│       │   ├── playlist_service.py   # Playlist parsing and per-item fallback resolution
│       │   ├── validation_service.py # URL validation and directory security checks
│       └── download_service.py       # Orchestration, verification, and history tracking
│       ├── infrastructure/
│       │   ├── youtube_client.py     # yt-dlp client wrapper with client strategy fallbacks
│       │   ├── media_processor.py    # FFmpeg, FFprobe, and JS runtime resolvers
│       │   ├── filesystem.py         # Filename sanitization, atomic paths, and OS reveal
│       │   └── logging.py            # Structured logging
│       ├── presentation/
│       │   ├── api.py                # BridgeAPI exposing operations to Vue.js
│       │   └── web_window.py         # Standalone pywebview window & embedded Bottle server
│       └── web/
│           └── dist/                 # Compiled production Vue.js distribution bundle
└── tests/
    ├── conftest.py                   # Pytest fixtures and sample metadata
    ├── unit/                         # Unit tests for domain, config, validation, formatting, bridge
    └── integration/                  # Integration tests for download services and web server API
```

---

## Prerequisites

- **Python:** 3.10, 3.11, 3.12, 3.13, or 3.14 (Python 3.12 recommended).
- **FFmpeg:** Required for merging DASH video + audio streams and transcoding MP3s. Stream Cloner automatically detects system FFmpeg (`/opt/homebrew/bin/ffmpeg`, `/usr/local/bin/ffmpeg`, or PATH) or downloads standalone FFmpeg via `imageio-ffmpeg`.
- **Deno or Node (Optional):** Automatically detected if installed to assist with JavaScript-challenge extraction on certain high-resolution YouTube streams.

---

## Installation & Quick Start

### 1. Interactive Operations Menu (Recommended)

From the project root, launch the unified interactive operations menu:

```bash
# Using Make:
make

# Or running the root script directly:
./run.sh
```

On Windows, double-click `run.bat` or execute `.\run.bat` in Command Prompt / PowerShell.

The interactive menu presents 4 options:
1. **Run App** — Bootstraps environment and launches Stream Cloner GUI.
2. **Generate macOS DMG** — Packages standalone `.app` and creates `.dmg` installer.
3. **Generate Windows EXE/MSI** — Builds standalone `.exe` using PyInstaller.
4. **Quit** — Exits cleanly.

### 2. Direct Makefile Targets

You can also bypass the menu and execute operations directly via `make`:

```bash
make run    # Option 1: Run app directly
make dmg    # Option 2: Generate macOS DMG installer (alias: make mac)
make exe    # Option 3: Generate Windows EXE/MSI installer (alias: make win)
make test   # Run pytest test suite
make clean  # Remove dist/, build/, caches, and temporary files
make help   # View all available targets
```

### 3. Direct Script Launch

#### On macOS & Linux:
```bash
./scripts/launch/launch.sh
```

#### On Windows:
Double-click `scripts\launch\launch.bat` (or execute `.\scripts\launch\launch.ps1` in PowerShell).

The launcher script will automatically:
1. Verify or create a Python virtual environment in `.venv`.
2. Install or upgrade dependencies from `requirements.txt`.
3. Verify FFmpeg availability.
4. Launch the Stream Cloner interface.

### 4. Manual Environment Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

---

## Building Standalone Distributables

### macOS `.dmg` Installer
To build a self-contained macOS drag-and-drop installer (`dist/Stream-Cloner-macOS.dmg`):

```bash
chmod +x scripts/build/build-macos-dmg.sh
./scripts/build/build-macos-dmg.sh
```

### Windows `.exe` Standalone Executable
On Windows, double-click `scripts\build\build-windows-exe.bat` or run:

```bat
python scripts/build/build_installer.py
```

The compiled single-file binary is generated at `dist\Stream-Cloner-Windows.exe`.

---

## Running the Test Suite

Stream Cloner includes a comprehensive suite of unit and integration tests covering configuration, format parsing, playlist resolution, theme management, filesystem security, and UI state transitions:

```bash
# Run all tests
.venv/bin/pytest

# Run tests with coverage or verbose output
.venv/bin/pytest -v
```

---

## Quality & Playlist Policies

### Automatic Best-Available Quality
When you load any video, Stream Cloner queries the live stream formats and places **"Best Available (Highest Resolution + FPS)"** as the selected option by default.

### Playlist Fallback Policy
Playlists frequently contain videos with varying maximum resolutions (e.g. some videos are available in 4K, while others max out at 1080p or 720p).
- In **Automatic/Best Available Mode (Default)**: Each video downloads at its own independent highest available quality.
- In **Target Ceiling Mode (e.g. 1080p selected)**: If a video supports 1080p, it downloads in 1080p. If a video only reaches 720p, Stream Cloner cleanly falls back to the video's highest available resolution (720p) rather than failing or downscaling the rest of the playlist.

---

## Troubleshooting

- **FFmpeg Missing Warning:**
  - macOS: Install via Homebrew: `brew install ffmpeg`
  - Windows: The launcher will automatically configure `imageio-ffmpeg` or you can install FFmpeg via `winget install Gyan.FFmpeg`.
- **Private or Unavailable Videos:**
  - If a video in a playlist has been removed or set to private, Stream Cloner automatically flags and skips the deleted item while continuing to process the remaining queue.
- **SSL Certificate Errors:**
  - Stream Cloner explicitly configures Python's SSL context using `certifi` bundles to ensure reliable downloads on fresh macOS and Windows installations.

---

## Legal & Compliance Notice

Stream Cloner is designed for personal archiving, educational use, and downloading content that you own or have explicit permission to access. Users are responsible for complying with applicable copyright laws, YouTube terms of service, and the rights of content creators.

---

<div align="center">

Made with ❤️ by [**~peivee**](https://linkedin.com/in/paras0397)

</div>

