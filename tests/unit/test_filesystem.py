"""Unit tests for filesystem utilities."""

from pathlib import Path

from stream_cloner.infrastructure.filesystem import (
    ensure_directory,
    get_unique_path,
    sanitize_filename,
    sanitize_folder_name,
)


def test_sanitize_filename():
    assert sanitize_filename("Test: Video / File * Name ? \" < > |") == "Test_ Video _ File _ Name _ _ _ _ _"
    assert sanitize_filename("Normal Title") == "Normal Title"
    assert sanitize_filename("") == "stream_media"
    assert sanitize_filename("   ...   ") == "stream_media"
    # Preserves Unicode
    assert sanitize_filename("音楽 - Japanese Song 🚀") == "音楽 - Japanese Song 🚀"


def test_sanitize_folder_name():
    assert sanitize_folder_name("My: Playlist / 2026") == "My_ Playlist _ 2026"
    assert sanitize_folder_name("") == "Stream_Playlist"


def test_get_unique_path(temp_dir: Path):
    f = temp_dir / "video.mp4"
    f.touch()

    # First duplicate
    unique1 = get_unique_path(str(f))
    assert Path(unique1).name == "video (1).mp4"

    # Second duplicate
    Path(unique1).touch()
    unique2 = get_unique_path(str(f))
    assert Path(unique2).name == "video (2).mp4"


def test_ensure_directory(temp_dir: Path):
    sub = temp_dir / "nested" / "dir"
    p = ensure_directory(str(sub))
    assert p.exists()
    assert p.is_dir()


def test_get_file_manager_name():
    from unittest.mock import patch
    from stream_cloner.infrastructure.filesystem import get_file_manager_name

    with patch("stream_cloner.infrastructure.filesystem.IS_MACOS", True), \
         patch("stream_cloner.infrastructure.filesystem.IS_WINDOWS", False):
        assert get_file_manager_name() == "Finder"

    with patch("stream_cloner.infrastructure.filesystem.IS_MACOS", False), \
         patch("stream_cloner.infrastructure.filesystem.IS_WINDOWS", True):
        assert get_file_manager_name() == "Explorer"

    with patch("stream_cloner.infrastructure.filesystem.IS_MACOS", False), \
         patch("stream_cloner.infrastructure.filesystem.IS_WINDOWS", False):
        assert get_file_manager_name() == "Files"


def test_reveal_in_file_manager(temp_dir: Path):
    from unittest.mock import patch
    from stream_cloner.infrastructure.filesystem import reveal_in_file_manager

    dummy_file = temp_dir / "clip.mp4"
    dummy_file.write_text("dummy", encoding="utf-8")

    with patch("subprocess.Popen") as mock_popen:
        res = reveal_in_file_manager(str(dummy_file))
        assert res is True
        assert mock_popen.called

        res_dir = reveal_in_file_manager(str(temp_dir))
        assert res_dir is True

        assert reveal_in_file_manager("") is False

