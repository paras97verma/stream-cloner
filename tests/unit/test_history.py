"""Unit tests for HistoryItem and DownloadService history management."""

from pathlib import Path

from stream_cloner.application.download_service import DownloadService
from stream_cloner.domain.models import HistoryItem


def test_download_service_history_management(tmp_path: Path):
    history_file = tmp_path / "test_history.json"
    service = DownloadService(history_file=history_file)

    # Empty initially
    assert service.load_history() == []

    # Record two items
    dummy_file = tmp_path / "video1.mp4"
    dummy_file.write_text("content", encoding="utf-8")
    service._record_history("Sample Video 1", str(dummy_file), "Video", "1080p")
    service._record_history("Sample Audio 2", str(dummy_file), "Audio", "320 kbps")

    items = service.load_history()
    assert len(items) == 2
    assert items[0].title == "Sample Audio 2"
    assert items[1].title == "Sample Video 1"

    # Delete one item
    del_id = items[0].id
    remaining = service.delete_history_item(del_id)
    assert len(remaining) == 1
    assert remaining[0].title == "Sample Video 1"

    # Clear all
    service.clear_history()
    assert service.load_history() == []
