"""Integration tests for DownloadService with mocked YouTube backend."""

import threading
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from stream_cloner.application.download_service import DownloadService
from stream_cloner.domain.enums import DownloadMode
from stream_cloner.domain.exceptions import DownloadCancelledError, DownloadError
from stream_cloner.domain.models import DownloadProgress, DownloadRequest, PlaylistEntry
from stream_cloner.infrastructure.youtube_client import YouTubeClient


def test_discover_single_video(sample_video_info: Dict[str, Any]):
    mock_client = MagicMock(spec=YouTubeClient)
    mock_client.extract_info.return_value = sample_video_info

    service = DownloadService(youtube_client=mock_client)
    metadata = service.discover_media("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert metadata.title == "Never Gonna Give You Up"
    assert metadata.uploader == "Rick Astley"
    assert metadata.is_playlist is False
    assert len(metadata.video_formats) > 0
    # First option must be Best Available
    assert metadata.video_formats[0].height == 0
    assert metadata.video_formats[0].is_default is True


def test_discover_playlist(sample_playlist_info: Dict[str, Any], sample_video_info: Dict[str, Any]):
    mock_client = MagicMock(spec=YouTubeClient)

    def side_effect(url, flat_playlist=False, **kwargs):
        if flat_playlist:
            return sample_playlist_info
        return sample_video_info

    mock_client.extract_info.side_effect = side_effect

    service = DownloadService(youtube_client=mock_client)
    metadata = service.discover_media("https://www.youtube.com/playlist?list=PL1234567890", fetch_playlist=True)

    assert metadata.is_playlist is True
    assert len(metadata.playlist_entries) == 3
    assert metadata.playlist_entries[0].video_id == "vid1"


def test_execute_download_single_video(temp_dir: Path):
    mock_client = MagicMock(spec=YouTubeClient)

    # Simulate yt-dlp creating an output file
    def download_side_effect(url, ydl_opts, **kwargs):
        outtmpl = ydl_opts["outtmpl"]
        out_file = outtmpl.replace("%(title).155B", "My_Video").replace("[Best]", "[Best]").replace("%(ext)s", "mp4")
        Path(out_file).write_text("dummy video content", encoding="utf-8")
        # Trigger progress hook
        for hook in ydl_opts.get("progress_hooks", []):
            hook({"status": "downloading", "total_bytes": 1000, "downloaded_bytes": 500, "speed": 100000, "eta": 5})
            hook({"status": "finished"})
        return {"id": "test_id", "title": "My Video"}

    mock_client.download_media.side_effect = download_side_effect

    service = DownloadService(youtube_client=mock_client)
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=test_id",
        output_dir=str(temp_dir),
        mode=DownloadMode.VIDEO,
        target_height=0,
    )

    progresses = []
    cancel_event = threading.Event()

    result_path = service.execute_download(
        request=req,
        progress_callback=lambda p: progresses.append(p),
        cancel_event=cancel_event,
    )

    assert Path(result_path).exists()
    assert len(progresses) > 0


def test_execute_download_cancellation(temp_dir: Path):
    mock_client = MagicMock(spec=YouTubeClient)
    cancel_event = threading.Event()
    cancel_event.set()  # Cancelled before start

    mock_client.download_media.side_effect = DownloadCancelledError("Cancelled")

    service = DownloadService(youtube_client=mock_client)
    req = DownloadRequest(
        url="https://www.youtube.com/watch?v=test_id",
        output_dir=str(temp_dir),
        mode=DownloadMode.VIDEO,
    )

    with pytest.raises(DownloadCancelledError):
        service.execute_download(
            request=req,
            progress_callback=lambda _: None,
            cancel_event=cancel_event,
        )


def test_execute_download_playlist(temp_dir: Path):
    mock_client = MagicMock(spec=YouTubeClient)

    def download_side_effect(url, ydl_opts, **kwargs):
        outtmpl = ydl_opts["outtmpl"]
        vid_id = "v1" if "vid1" in url else "v2"
        out_file = outtmpl.replace("%(title).155B", f"Item_{vid_id}").replace("[Best]", "[Best]").replace("%(ext)s", "mp4")
        Path(out_file).write_text("video stream content", encoding="utf-8")
        return {"id": vid_id, "title": f"Item {vid_id}"}

    mock_client.download_media.side_effect = download_side_effect

    service = DownloadService(youtube_client=mock_client)
    items = [
        PlaylistEntry(index=1, video_id="v1", title="Item 1", url="https://www.youtube.com/watch?v=v1"),
        PlaylistEntry(index=2, video_id="v2", title="Item 2", url="https://www.youtube.com/watch?v=v2"),
    ]
    req = DownloadRequest(
        url="https://www.youtube.com/playlist?list=pl_test",
        output_dir=str(temp_dir),
        mode=DownloadMode.VIDEO,
        target_height=0,
        playlist_items=items,
        playlist_title="Test_Playlist",
    )

    cancel_event = threading.Event()
    folder_result = service.execute_download(
        request=req,
        progress_callback=lambda _: None,
        cancel_event=cancel_event,
    )

    assert Path(folder_result).is_dir()
    # History was recorded
    history = service.load_history()
    assert len(history) >= 1


def test_discover_multi_urls(sample_video_info: Dict[str, Any]):
    mock_client = MagicMock(spec=YouTubeClient)
    mock_client.extract_info.return_value = sample_video_info

    service = DownloadService(youtube_client=mock_client)
    multi_url_text = "https://www.youtube.com/watch?v=vid1, https://www.youtube.com/watch?v=vid2"
    metadata = service.discover_media(multi_url_text)

    assert metadata.is_playlist is True
    assert len(metadata.playlist_entries) == 2
    assert metadata.playlist_entries[0].url == "https://www.youtube.com/watch?v=vid1"
    assert metadata.playlist_entries[1].url == "https://www.youtube.com/watch?v=vid2"


def test_execute_parallel_download_with_slot_tracking(temp_dir: Path):
    mock_client = MagicMock(spec=YouTubeClient)

    def download_side_effect(url, ydl_opts, **kwargs):
        outtmpl = ydl_opts["outtmpl"]
        vid_id = "v1" if "vid1" in url else ("v2" if "vid2" in url else "v3")
        out_file = outtmpl.replace("%(title).150B", f"Item_{vid_id}").replace("[Best]", "[Best]").replace("%(ext)s", "mp4")
        Path(out_file).write_text("video stream content", encoding="utf-8")
        # trigger hook
        for hook in ydl_opts.get("progress_hooks", []):
            hook({"status": "downloading", "total_bytes": 1000, "downloaded_bytes": 500, "speed": 50000, "eta": 10})
        return {"id": vid_id, "title": f"Item {vid_id}"}

    mock_client.download_media.side_effect = download_side_effect

    service = DownloadService(youtube_client=mock_client)
    items = [
        PlaylistEntry(index=1, video_id="vid1", title="Item 1", url="https://www.youtube.com/watch?v=vid1"),
        PlaylistEntry(index=2, video_id="vid2", title="Item 2", url="https://www.youtube.com/watch?v=vid2"),
        PlaylistEntry(index=3, video_id="vid3", title="Item 3", url="https://www.youtube.com/watch?v=vid3"),
    ]
    req = DownloadRequest(
        url="https://www.youtube.com/playlist?list=batch",
        output_dir=str(temp_dir),
        mode=DownloadMode.VIDEO,
        target_height=0,
        playlist_items=items,
        playlist_title="Parallel_Test",
        max_parallel=2,
    )

    reported_slots = set()
    captured_progress = []

    def on_prog(p: DownloadProgress):
        reported_slots.add(p.slot_index)
        captured_progress.append(p)

    cancel_event = threading.Event()
    service.execute_download(request=req, progress_callback=on_prog, cancel_event=cancel_event)

    # Max parallel is 2, so slots used should be 0 and 1
    assert reported_slots.issubset({0, 1})
    assert len(captured_progress) > 0
    # Final progress reaches 100%
    assert captured_progress[-1].overall_percentage == 100.0

