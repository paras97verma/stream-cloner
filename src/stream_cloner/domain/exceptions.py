"""Domain-specific exceptions for Stream Cloner."""


class StreamClonerError(Exception):
    """Base exception for all Stream Cloner domain errors."""


class ValidationError(StreamClonerError):
    """Raised when user-provided input fails validation rules."""


class MediaDiscoveryError(StreamClonerError):
    """Raised when metadata or stream format discovery fails."""


class DownloadError(StreamClonerError):
    """Raised when a download operation fails."""


class DownloadCancelledError(StreamClonerError):
    """Raised when a download is cancelled by the user."""


class DependencyNotFoundError(StreamClonerError):
    """Raised when an external dependency (FFmpeg, JS runtime) is missing."""


class FilesystemError(StreamClonerError):
    """Raised when file or directory operations fail."""
