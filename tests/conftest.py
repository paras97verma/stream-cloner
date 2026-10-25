"""Pytest fixtures and mock data for Stream Cloner test suite."""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Ensure src/ is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Ensure Qt runs headlessly in offscreen mode
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path, monkeypatch):
    """Ensure all tests operate in an isolated temporary config directory."""
    test_config_dir = tmp_path / "stream_cloner_config"
    test_config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("stream_cloner.config.get_app_config_dir", lambda: test_config_dir)
    monkeypatch.setattr("stream_cloner.application.download_service.get_app_config_dir", lambda: test_config_dir)
    return test_config_dir


@pytest.fixture
def sample_video_info() -> Dict[str, Any]:
    """Sample raw yt-dlp metadata with multi-tier DASH video and audio streams."""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Never Gonna Give You Up",
        "uploader": "Rick Astley",
        "duration": 213,
        "view_count": 1500000000,
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "formats": [
            # Audio streams
            {
                "format_id": "251",
                "ext": "webm",
                "vcodec": "none",
                "acodec": "opus",
                "abr": 160,
                "filesize": 4200000,
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "abr": 128,
                "filesize": 3500000,
            },
            # Video DASH streams
            {
                "format_id": "313",
                "ext": "webm",
                "vcodec": "vp09.00.51.08.01.01.01.01.00",
                "acodec": "none",
                "height": 2160,
                "fps": 60,
                "dynamic_range": "SDR",
                "filesize": 150000000,
            },
            {
                "format_id": "401",
                "ext": "mp4",
                "vcodec": "av01.0.12M.08",
                "acodec": "none",
                "height": 2160,
                "fps": 60,
                "dynamic_range": "HDR",
                "filesize": 160000000,
            },
            {
                "format_id": "271",
                "ext": "webm",
                "vcodec": "vp9",
                "acodec": "none",
                "height": 1440,
                "fps": 60,
                "dynamic_range": "SDR",
                "filesize": 85000000,
            },
            {
                "format_id": "137",
                "ext": "mp4",
                "vcodec": "avc1.640028",
                "acodec": "none",
                "height": 1080,
                "fps": 60,
                "dynamic_range": "SDR",
                "filesize": 45000000,
            },
            {
                "format_id": "136",
                "ext": "mp4",
                "vcodec": "avc1.4d401f",
                "acodec": "none",
                "height": 720,
                "fps": 30,
                "dynamic_range": "SDR",
                "filesize": 22000000,
            },
            {
                "format_id": "134",
                "ext": "mp4",
                "vcodec": "avc1.4d401e",
                "acodec": "none",
                "height": 360,
                "fps": 30,
                "dynamic_range": "SDR",
                "filesize": 8000000,
            },
        ],
    }


@pytest.fixture
def sample_playlist_info() -> Dict[str, Any]:
    """Sample raw yt-dlp flat playlist extraction."""
    return {
        "id": "PL1234567890",
        "title": "Favorite Music Videos",
        "uploader": "Test Channel",
        "thumbnails": [{"url": "https://example.com/thumb.jpg"}],
        "view_count": 50000,
        "entries": [
            {
                "id": "vid1",
                "title": "Track 01 - Rock",
                "url": "https://www.youtube.com/watch?v=vid1",
                "duration": 180,
            },
            {
                "id": "vid2",
                "title": "Track 02 - Jazz",
                "url": "https://www.youtube.com/watch?v=vid2",
                "duration": 240,
            },
            {
                "id": "vid3",
                "title": "[Deleted video]",
                "url": "https://www.youtube.com/watch?v=vid3",
                "duration": None,
            },
            {
                "id": "vid4",
                "title": "Track 04 - Electronic",
                "url": "https://www.youtube.com/watch?v=vid4",
                "duration": 210,
            },
        ],
    }


@pytest.fixture
def temp_dir():
    """Temporary test directory cleaned up automatically."""
    with tempfile.TemporaryDirectory(prefix="stream_cloner_test_") as d:
        yield Path(d)
