"""Application bootstrap, environment setup, and lifecycle entry point."""

from __future__ import annotations

import os
import sys
import warnings

# Suppress known harmless platform and version warnings
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", message=".*Support for Python version 3.9 has been deprecated.*")

# Redirect std streams in PyInstaller windowed mode if None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure PATH includes bundle dir, virtual environment bin, Homebrew, and local bin
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
VENV_BIN = os.path.dirname(os.path.abspath(sys.executable))

if IS_WINDOWS:
    os.environ["PATH"] = f"{BUNDLE_DIR};{VENV_BIN};" + os.environ.get("PATH", "")
else:
    os.environ["PATH"] = f"{BUNDLE_DIR}:{VENV_BIN}:/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

# Ensure certifi SSL bundle
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass


def main() -> int:
    """Main application bootstrap function."""
    headless_browser = "--browser" in sys.argv
    from stream_cloner.presentation.web_window import launch_app
    return launch_app(headless_browser=headless_browser)


