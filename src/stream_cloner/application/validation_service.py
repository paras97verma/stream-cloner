"""Validation service for URLs, input fields, and output paths."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Tuple
from urllib.parse import parse_qs, urlparse

from stream_cloner.domain.exceptions import ValidationError

YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class ValidationService:
    """Validates user-provided URLs and output directories."""

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate and normalize a user-supplied YouTube URL."""
        if not url or not isinstance(url, str):
            raise ValidationError("Please provide a valid URL.")

        cleaned = url.strip()
        if not cleaned:
            raise ValidationError("URL cannot be empty.")

        if not cleaned.startswith(("http://", "https://")):
            # Prepend https if user pasted without protocol
            cleaned = "https://" + cleaned

        try:
            parsed = urlparse(cleaned)
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}") from e

        hostname = (parsed.hostname or "").lower()
        if not any(hostname == domain or hostname.endswith("." + domain) for domain in YOUTUBE_DOMAINS):
            raise ValidationError(
                f"Unsupported host '{hostname}'. Only YouTube links (youtube.com or youtu.be) are supported."
            )

        return cleaned

    @staticmethod
    def inspect_playlist_url(url: str) -> Tuple[bool, bool]:
        """
        Check if URL is a playlist or contains a playlist parameter.
        Returns:
            (is_pure_playlist, has_list_parameter)
        """
        try:
            parsed = urlparse(url.strip())
            qs = parse_qs(parsed.query)
            has_list = "list" in qs and len(qs["list"]) > 0
            is_pure = has_list and ("/playlist" in parsed.path.lower() or "v" not in qs)
            return is_pure, has_list
        except Exception:
            return False, False

    @staticmethod
    def parse_multi_urls(text: str) -> List[str]:
        """
        Extract multiple URLs separated by commas, semicolons, or newlines.
        Returns a list of cleaned, valid YouTube URLs.
        """
        if not text or not isinstance(text, str):
            return []

        raw_tokens = re.split(r"[,;\r\n]+", text.strip())
        urls = []
        for token in raw_tokens:
            cleaned = token.strip().strip("'\"`")
            if cleaned:
                try:
                    valid_u = ValidationService.validate_url(cleaned)
                    if valid_u not in urls:
                        urls.append(valid_u)
                except ValidationError:
                    pass
        return urls

    @staticmethod
    def validate_output_directory(path: str) -> str:
        """Verify output directory is writable and safe."""
        if not path or not path.strip():
            raise ValidationError("Destination folder path cannot be empty.")

        cleaned = os.path.abspath(os.path.expanduser(path.strip()))
        try:
            Path(cleaned).mkdir(parents=True, exist_ok=True)
            if not os.access(cleaned, os.W_OK):
                raise ValidationError(f"Directory is not writable: {cleaned}")
        except OSError as e:
            raise ValidationError(f"Cannot access or create destination folder: {e}") from e

        return cleaned
