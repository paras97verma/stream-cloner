#!/usr/bin/env python3
"""
Stream Cloner — Thin Application Entry Point.
Production-ready YouTube Ultra-HD Video, Playlist & Audio Studio.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to Python search path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stream_cloner.bootstrap import main

if __name__ == "__main__":
    sys.exit(main())
