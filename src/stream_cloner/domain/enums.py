"""Domain enumerations for Stream Cloner."""

from enum import Enum


class DownloadMode(str, Enum):
    """Download output mode."""
    VIDEO = "video"
    AUDIO = "audio"


class ScopeMode(str, Enum):
    """Target scope: single video or full playlist."""
    SINGLE = "single"
    PLAYLIST = "playlist"


class ThemePreference(str, Enum):
    """User-selectable theme preference (Dark mode only)."""
    DARK = "dark"


class ActiveTheme(str, Enum):
    """Resolved active theme appearance (Dark mode only)."""
    DARK = "dark"


class FallbackPolicy(str, Enum):
    """Quality fallback strategy for playlist items with differing resolutions."""
    BEST_AVAILABLE = "best_available"
    CLOSEST_LOWER = "closest_lower"


class DownloadStatus(str, Enum):
    """Status of an active or completed download operation."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
