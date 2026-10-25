"""Unit tests for ValidationService."""

from pathlib import Path

import pytest

from stream_cloner.application.validation_service import ValidationService
from stream_cloner.domain.exceptions import ValidationError


def test_validate_valid_youtube_urls():
    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/playlist?list=PL1234567890",
    ]
    for url in valid_urls:
        normalized = ValidationService.validate_url(url)
        assert normalized.startswith("https://")


def test_validate_invalid_urls():
    invalid_urls = [
        "",
        "   ",
        "https://vimeo.com/123456",
        "https://malicious-site.com/video",
        "not a url at all",
    ]
    for url in invalid_urls:
        with pytest.raises(ValidationError):
            ValidationService.validate_url(url)


def test_inspect_playlist_url():
    is_pure, has_list = ValidationService.inspect_playlist_url("https://www.youtube.com/playlist?list=PLxyz123")
    assert is_pure is True
    assert has_list is True

    is_pure, has_list = ValidationService.inspect_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz123")
    assert is_pure is False
    assert has_list is True

    is_pure, has_list = ValidationService.inspect_playlist_url("https://www.youtube.com/watch?v=abc")
    assert is_pure is False
    assert has_list is False


def test_validate_output_directory(temp_dir: Path):
    target = temp_dir / "valid_folder"
    validated = ValidationService.validate_output_directory(str(target))
    assert Path(validated).exists()
    assert Path(validated).is_dir()

    with pytest.raises(ValidationError):
        ValidationService.validate_output_directory("")


def test_parse_multi_urls_comma_separated():
    text = "https://www.youtube.com/watch?v=dQw4w9WgXcQ, https://www.youtube.com/watch?v=jNQXAC9IVRw"
    urls = ValidationService.parse_multi_urls(text)
    assert len(urls) == 2
    assert "dQw4w9WgXcQ" in urls[0]
    assert "jNQXAC9IVRw" in urls[1]


def test_parse_multi_urls_mixed_delimiters():
    text = """
    https://youtu.be/dQw4w9WgXcQ;
    https://www.youtube.com/watch?v=jNQXAC9IVRw
    https://www.youtube.com/shorts/12345678901
    """
    urls = ValidationService.parse_multi_urls(text)
    assert len(urls) == 3


def test_parse_multi_urls_single_and_empty():
    single = ValidationService.parse_multi_urls("https://youtu.be/dQw4w9WgXcQ")
    assert len(single) == 1

    empty = ValidationService.parse_multi_urls("   ")
    assert empty == []

    invalid = ValidationService.parse_multi_urls("not a link, also not a link")
    assert invalid == []

