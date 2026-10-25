"""Domain data models for Stream Cloner."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from stream_cloner.domain.enums import DownloadMode


def format_bytes(num_bytes: Optional[float]) -> str:
    """Format byte counts into human-readable strings (e.g. 1.2 GB)."""
    if not num_bytes or num_bytes <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = min(int(math.log(num_bytes, 1024)), len(units) - 1)
    val = num_bytes / (1024 ** idx)
    return f"{val:.1f} {units[idx]}"


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds into HH:MM:SS or MM:SS."""
    if not seconds or seconds <= 0:
        return "Live / Unknown"
    total = int(seconds)
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


@dataclass
class VideoFormatOption:
    """Represents a dynamically discovered video resolution and frame rate."""

    height: int
    fps: Optional[int] = None
    approx_size: Optional[int] = None
    ext: str = "mp4"
    is_hdr: bool = False
    codec_hint: str = ""
    format_id: Optional[str] = None
    is_default: bool = False
    custom_label: Optional[str] = None

    @property
    def selection_key(self) -> Tuple[int, int]:
        """Returns (height, fps) for matching."""
        return (self.height, int(self.fps or 0))

    @property
    def display_label(self) -> str:
        """Formatted human-readable label for quality selection."""
        if self.custom_label:
            tag = "  ★ Best Available" if self.is_default else ""
            return f"{self.custom_label}{tag}"

        if self.height >= 6000:
            base = f"{self.height}p (12K+ UHD)"
        elif self.height >= 4000:
            base = f"{self.height}p (8K UHD)"
        elif self.height >= 2500:
            base = f"{self.height}p (5K UHD)"
        elif self.height >= 2000:
            base = f"{self.height}p (4K UHD)"
        elif self.height >= 1400:
            base = f"{self.height}p (2K QHD)"
        elif self.height >= 1000:
            base = f"{self.height}p (Full HD)"
        elif self.height >= 700:
            base = f"{self.height}p (HD)"
        elif self.height >= 450:
            base = f"{self.height}p (SD)"
        else:
            base = f"{self.height}p"

        fps_str = f" • {self.fps}fps" if self.fps and self.fps > 0 else ""
        hdr_str = " HDR" if self.is_hdr else ""
        codec_str = f" [{self.codec_hint}]" if self.codec_hint else ""
        size_str = f" (~{format_bytes(self.approx_size)})" if self.approx_size else ""
        tag = "  ★ Best Available" if self.is_default else ""
        return f"{base}{fps_str}{hdr_str}{codec_str}{size_str}{tag}"


@dataclass
class AudioFormatOption:
    """Represents an audio extraction or conversion quality."""

    bitrate_kbps: str
    label: str
    codec: str = "mp3"
    approx_size: Optional[int] = None
    is_source: bool = False
    is_default: bool = False

    @property
    def display_label(self) -> str:
        tag = "  ★ Best Quality" if self.is_default else ""
        size_str = f" (~{format_bytes(self.approx_size)})" if self.approx_size else ""
        return f"{self.label}{size_str}{tag}"


@dataclass
class PlaylistEntry:
    """Represents a single video entry inside a playlist."""

    index: int
    video_id: str
    title: str
    url: str
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None


@dataclass
class MediaMetadata:
    """Complete metadata discovered dynamically for a URL."""

    url: str
    title: str
    raw_title: str
    uploader: str
    duration: Optional[float] = None
    view_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    thumbnail_bytes: Optional[bytes] = None
    is_playlist: bool = False
    has_list_param: bool = False
    video_formats: List[VideoFormatOption] = field(default_factory=list)
    audio_formats: List[AudioFormatOption] = field(default_factory=list)
    default_video_index: int = 0
    default_audio_index: int = 0
    playlist_entries: List[PlaylistEntry] = field(default_factory=list)
    winning_client: Optional[List[str]] = None


@dataclass
class DownloadRequest:
    """Parameters defining a media download operation."""

    url: str
    output_dir: str
    mode: DownloadMode
    target_height: int = 0  # 0 indicates Best Available
    target_fps: Optional[int] = None
    audio_bitrate: str = "320"
    preferred_client: Optional[List[str]] = None
    playlist_items: List[PlaylistEntry] = field(default_factory=list)
    playlist_title: Optional[str] = None
    max_parallel: int = 2


@dataclass
class DownloadProgress:
    """Progress snapshot from an active download."""

    percentage: float
    status_message: str
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_bytes: float = 0.0
    eta_seconds: Optional[float] = None
    current_item: int = 1
    total_items: int = 1
    slot_index: int = 0
    item_id: str = ""
    item_title: str = ""
    overall_percentage: float = 0.0


@dataclass
class HistoryItem:
    """Record of a successfully completed download."""

    id: str
    timestamp: float
    title: str
    file_path: str
    file_size: int
    mode: str
    quality_label: str
