"""Unit tests for BridgeAPI powering Vue.js desktop application."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from stream_cloner.config import AppConfig
from stream_cloner.domain.enums import ThemePreference
from stream_cloner.domain.models import HistoryItem, MediaMetadata
from stream_cloner.presentation.api import BridgeAPI


@pytest.fixture
def test_config(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = AppConfig(
        download_dir=str(tmp_path / "downloads"),
        theme_preference=ThemePreference.DARK,
        max_parallel_downloads=3,
        config_file_path=cfg_file,
    )
    return cfg


def test_bridge_api_initial_state(test_config):
    mock_service = MagicMock()
    api = BridgeAPI(config=test_config, download_service=mock_service)

    state = api.get_initial_state()
    assert state["theme"] == "dark"
    assert state["max_parallel"] == 3
    assert state["download_dir"] == test_config.download_dir
    assert "has_ffmpeg" in state
    assert "has_js" in state
    assert "file_manager_name" in state
    assert isinstance(state["default_audio_formats"], list)


def test_bridge_api_set_theme(test_config):
    mock_service = MagicMock()
    api = BridgeAPI(config=test_config, download_service=mock_service)

    assert api.set_theme("dark") is True
    assert test_config.theme_preference == ThemePreference.DARK

    # Invalid theme
    assert api.set_theme("invalid_theme") is False


def test_bridge_api_set_max_parallel(test_config):
    mock_service = MagicMock()
    api = BridgeAPI(config=test_config, download_service=mock_service)

    assert api.set_max_parallel(5) is True
    assert test_config.max_parallel_downloads == 5

    # Bounds check
    assert api.set_max_parallel(20) is True
    assert test_config.max_parallel_downloads == 10

    assert api.set_max_parallel(0) is True
    assert test_config.max_parallel_downloads == 1


def test_bridge_api_discover_media(test_config):
    mock_service = MagicMock()
    mock_meta = MediaMetadata(
        url="https://youtube.com/watch?v=mock123",
        title="Mock Title",
        raw_title="Mock Title",
        duration=180,
        uploader="Mock Creator",
        thumbnail_url="https://img.youtube.com/vi/mock123/hqdefault.jpg",
    )
    mock_service.discover_media.return_value = mock_meta
    api = BridgeAPI(config=test_config, download_service=mock_service)

    result = api.discover_media("https://youtube.com/watch?v=mock123")
    assert result["success"] is True
    assert result["title"] == "Mock Title"
    assert result["duration"] == 180
    assert result["uploader"] == "Mock Creator"


def test_bridge_api_discover_empty_url(test_config):
    mock_service = MagicMock()
    api = BridgeAPI(config=test_config, download_service=mock_service)

    result = api.discover_media("")
    assert result["success"] is False
    assert "valid" in result["error"].lower()


def test_bridge_api_history_operations(test_config):
    mock_service = MagicMock()
    mock_item = HistoryItem(
        id="hist-123",
        timestamp=1700000000.0,
        title="Sample Video",
        file_path="/tmp/sample.mp4",
        file_size=1048576,
        mode="video",
        quality_label="1080p",
    )
    mock_service.load_history.return_value = [mock_item]
    mock_service.delete_history_item.return_value = []
    api = BridgeAPI(config=test_config, download_service=mock_service)

    history = api.get_history()
    assert len(history) == 1
    assert history[0]["id"] == "hist-123"
    assert history[0]["title"] == "Sample Video"

    remaining = api.delete_history_item("hist-123")
    assert remaining == []
    mock_service.delete_history_item.assert_called_once_with("hist-123")

    assert api.clear_history() is True
    mock_service.clear_history.assert_called_once()


def test_bridge_api_open_url(test_config, monkeypatch):
    mock_service = MagicMock()
    api = BridgeAPI(config=test_config, download_service=mock_service)

    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)

    assert api.open_url("https://linkedin.com/in/paras0397") is True
    assert "https://linkedin.com/in/paras0397" in opened

    # Test dict parameter compatibility (pywebview payloads)
    assert api.open_url({"url": "https://github.com"}) is True
    assert "https://github.com" in opened

    assert api.open_url("invalid-url") is False
    assert api.open_url("") is False

