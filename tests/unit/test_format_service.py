"""Unit tests for FormatService dynamic format parsing and selector logic."""

from typing import Any, Dict

from stream_cloner.application.format_service import FormatService
from stream_cloner.domain.models import VideoFormatOption


def test_dynamic_format_discovery(sample_video_info: Dict[str, Any]):
    options = FormatService.parse_video_formats(sample_video_info)

    assert len(options) > 0
    # First option must be Best Available
    top = options[0]
    assert top.height == 0
    assert top.is_default is True
    assert "Best Available" in top.display_label
    assert "2160p" in top.display_label

    # Discovered heights must only include formats present in sample_video_info (2160, 1440, 1080, 720, 360)
    discovered_heights = [opt.height for opt in options[1:]]
    assert discovered_heights == [2160, 1440, 1080, 720, 360]

    # No hardcoded 12K, 8K, 5K, 480p, 240p, 144p when not present in metadata!
    assert 6480 not in discovered_heights
    assert 4320 not in discovered_heights
    assert 2880 not in discovered_heights
    assert 480 not in discovered_heights


def test_hdr_and_codec_detection(sample_video_info: Dict[str, Any]):
    options = FormatService.parse_video_formats(sample_video_info)
    opt_2160 = [opt for opt in options if opt.height == 2160][0]

    assert opt_2160.is_hdr is True
    assert opt_2160.codec_hint in ("AV1", "VP9")
    assert opt_2160.fps == 60


def test_empty_formats_handling():
    empty_info = {"formats": []}
    options = FormatService.parse_video_formats(empty_info)
    assert options == []

    no_formats_info = {}
    options = FormatService.parse_video_formats(no_formats_info)
    assert options == []


def test_audio_format_parsing(sample_video_info: Dict[str, Any]):
    audio_options = FormatService.parse_audio_formats(sample_video_info)
    assert len(audio_options) >= 5

    # Top audio option is best source quality
    best_audio = audio_options[0]
    assert best_audio.is_source is True
    assert best_audio.is_default is True
    assert "160 kbps OPUS" in best_audio.label


def test_build_video_selector():
    # Best available with ffmpeg
    sel_best = FormatService.build_video_selector(target_height=0, target_fps=None, has_ffmpeg=True)
    assert "bv*+ba/b" in sel_best

    # Best available without ffmpeg
    sel_best_no_ff = FormatService.build_video_selector(target_height=0, target_fps=None, has_ffmpeg=False)
    assert "best" in sel_best_no_ff

    # Specific 1080p 60fps with ffmpeg
    sel_1080 = FormatService.build_video_selector(target_height=1080, target_fps=60, has_ffmpeg=True)
    assert "height=1080" in sel_1080
    assert "fps=60" in sel_1080
    assert "+ba" in sel_1080
    assert "height<=1080" in sel_1080  # Fallback ladder

    # Specific height without ffmpeg
    sel_720_no_ff = FormatService.build_video_selector(target_height=720, target_fps=None, has_ffmpeg=False)
    assert "best[height=720]" in sel_720_no_ff


def test_build_audio_selector():
    sel = FormatService.build_audio_selector()
    assert sel == "ba/b"
