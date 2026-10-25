"""Integration tests for Stream Cloner web window server and BridgeAPI communication."""

import json
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stream_cloner.application.download_service import DownloadService
from stream_cloner.config import AppConfig
from stream_cloner.domain.enums import DownloadMode, ThemePreference
from stream_cloner.domain.models import MediaMetadata
from stream_cloner.presentation.api import BridgeAPI
from stream_cloner.presentation.web_window import (
    find_free_port,
    resolve_web_dist_dir,
    start_local_server,
)


@pytest.fixture
def running_server(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = AppConfig(
        download_dir=str(tmp_path / "downloads"),
        theme_preference=ThemePreference.DARK,
        max_parallel_downloads=3,
        config_file_path=cfg_file,
    )
    mock_service = MagicMock(spec=DownloadService)
    mock_service.load_history.return_value = []
    api = BridgeAPI(config=cfg, download_service=mock_service)

    port = find_free_port()
    dist_dir = resolve_web_dist_dir()
    server_thread = start_local_server(dist_dir, port, api)

    base_url = f"http://127.0.0.1:{port}"
    return {"url": base_url, "api": api, "config": cfg, "mock_service": mock_service}


def test_server_serves_frontend_html(running_server):
    req = urllib.request.Request(f"{running_server['url']}/")
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        content = res.read().decode("utf-8")
        assert '<div id="app">' in content


def test_api_state_endpoint(running_server):
    req = urllib.request.Request(f"{running_server['url']}/api/state")
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["theme"] == "dark"
        assert data["max_parallel"] == 3
        assert "has_ffmpeg" in data
        assert "has_js" in data
        assert "file_manager_name" in data


def test_api_theme_toggle_endpoint(running_server):
    payload = json.dumps({"theme": "dark"}).encode("utf-8")
    req = urllib.request.Request(
        f"{running_server['url']}/api/theme",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True

    assert running_server["config"].theme_preference == ThemePreference.DARK


def test_api_parallel_downloads_endpoint(running_server):
    payload = json.dumps({"max_parallel": 5}).encode("utf-8")
    req = urllib.request.Request(
        f"{running_server['url']}/api/parallel",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True

    assert running_server["config"].max_parallel_downloads == 5


def test_api_discover_endpoint(running_server):
    mock_meta = MediaMetadata(
        url="https://www.youtube.com/watch?v=mock123",
        title="Test YouTube Video",
        raw_title="Test YouTube Video",
        duration=300,
        uploader="Channel 1",
    )
    running_server["mock_service"].discover_media.return_value = mock_meta

    payload = json.dumps({"url": "https://www.youtube.com/watch?v=mock123"}).encode("utf-8")
    req = urllib.request.Request(
        f"{running_server['url']}/api/discover",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert data["title"] == "Test YouTube Video"
        assert data["duration"] == 300


def test_api_history_endpoints(running_server):
    # GET /api/history
    req = urllib.request.Request(f"{running_server['url']}/api/history")
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert "items" in data
        assert isinstance(data["items"], list)

    # POST /api/history/clear
    req = urllib.request.Request(
        f"{running_server['url']}/api/history/clear",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
