"""Domain layer for Stream Cloner."""

from stream_cloner.domain.enums import (
    ActiveTheme,
    DownloadMode,
    DownloadStatus,
    FallbackPolicy,
    ScopeMode,
    ThemePreference,
)
from stream_cloner.domain.exceptions import (
    DependencyNotFoundError,
    DownloadCancelledError,
    DownloadError,
    FilesystemError,
    MediaDiscoveryError,
    StreamClonerError,
    ValidationError,
)
from stream_cloner.domain.models import (
    AudioFormatOption,
    DownloadProgress,
    DownloadRequest,
    HistoryItem,
    MediaMetadata,
    PlaylistEntry,
    VideoFormatOption,
    format_bytes,
    format_duration,
)

__all__ = [
    "ActiveTheme",
    "DownloadMode",
    "DownloadStatus",
    "FallbackPolicy",
    "ScopeMode",
    "ThemePreference",
    "StreamClonerError",
    "DependencyNotFoundError",
    "DownloadCancelledError",
    "DownloadError",
    "FilesystemError",
    "MediaDiscoveryError",
    "ValidationError",
    "AudioFormatOption",
    "DownloadProgress",
    "DownloadRequest",
    "HistoryItem",
    "MediaMetadata",
    "PlaylistEntry",
    "VideoFormatOption",
    "format_bytes",
    "format_duration",
]
