"""Unit tests for PlaylistService entry extraction and per-item quality resolution."""

from typing import Any, Dict

from stream_cloner.application.playlist_service import PlaylistService


def test_parse_playlist_entries(sample_playlist_info: Dict[str, Any]):
    raw = sample_playlist_info["entries"]
    entries = PlaylistService.parse_playlist_entries(raw)

    # vid3 was "[Deleted video]", so only 3 valid entries should be extracted
    assert len(entries) == 3
    assert entries[0].video_id == "vid1"
    assert entries[1].video_id == "vid2"
    assert entries[2].video_id == "vid4"
    assert entries[0].index == 1
    assert entries[1].index == 2
    assert entries[2].index == 3


def test_resolve_item_quality_automatic_best():
    # If target is Best Available (0), always returns 0
    h, fps = PlaylistService.resolve_item_quality(target_height=0, target_fps=None, item_formats=[])
    assert h == 0


def test_resolve_item_quality_with_fallback():
    # Video only has 720p and 360p streams
    formats = [
        {"height": 720, "fps": 30, "vcodec": "avc1"},
        {"height": 360, "fps": 30, "vcodec": "avc1"},
    ]

    # User requested 1080p, but this item only has 720p
    # Must fallback to 720p for this item
    h, fps = PlaylistService.resolve_item_quality(target_height=1080, target_fps=60, item_formats=formats)
    assert h == 720

    # User requested 720p, which is available
    h, fps = PlaylistService.resolve_item_quality(target_height=720, target_fps=30, item_formats=formats)
    assert h == 720
