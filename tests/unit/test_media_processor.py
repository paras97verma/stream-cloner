"""Unit tests for media processing dependencies and FFmpeg transcoding."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stream_cloner.domain.exceptions import DependencyNotFoundError
from stream_cloner.infrastructure.media_processor import (
    convert_audio_with_ffmpeg,
    has_ffprobe,
    resolve_ffmpeg_executable,
    resolve_js_runtimes,
)


def test_resolve_ffmpeg_returns_valid_path_if_present():
    ff = resolve_ffmpeg_executable()
    # On the test system, ffmpeg was found at /opt/homebrew/bin/ffmpeg
    if ff:
        assert Path(ff).exists()


def test_resolve_js_runtimes():
    runtimes = resolve_js_runtimes()
    assert isinstance(runtimes, dict)


@patch("stream_cloner.infrastructure.media_processor.resolve_ffmpeg_executable", return_value=None)
def test_convert_audio_missing_ffmpeg(mock_resolve):
    with pytest.raises(DependencyNotFoundError):
        convert_audio_with_ffmpeg(
            input_file="input.webm",
            output_file="output.mp3",
            bitrate_kbps="320",
            ffmpeg_exe=None,
        )


@patch("subprocess.run")
@patch("os.path.exists")
@patch("os.path.getsize")
def test_convert_audio_command_arguments(mock_getsize, mock_exists, mock_run, temp_dir: Path):
    mock_run.return_value = MagicMock(returncode=0)
    mock_exists.return_value = True
    mock_getsize.return_value = 1024

    in_file = str(temp_dir / "audio.webm")
    out_file = str(temp_dir / "audio.mp3")

    result = convert_audio_with_ffmpeg(
        input_file=in_file,
        output_file=out_file,
        bitrate_kbps="320",
        ffmpeg_exe="/mock/bin/ffmpeg",
    )

    assert result == out_file
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]

    # Verify safe argument array without shell=True
    assert cmd[0] == "/mock/bin/ffmpeg"
    assert cmd[1] == "-y"
    assert cmd[2] == "-i"
    assert cmd[3] == in_file
    assert "-vn" in cmd
    assert "libmp3lame" in cmd
    assert "320k" in cmd
    assert cmd[-1] == out_file
