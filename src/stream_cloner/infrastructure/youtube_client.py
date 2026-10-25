"""YouTube client abstraction wrapping yt-dlp with client strategies and cancellation."""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Dict, List, Optional

import certifi
import yt_dlp

from stream_cloner.config import CLIENT_STRATEGIES
from stream_cloner.domain.exceptions import DownloadCancelledError, MediaDiscoveryError
from stream_cloner.infrastructure.logging import get_logger
from stream_cloner.infrastructure.media_processor import resolve_ffmpeg_executable, resolve_js_runtimes

logger = get_logger("youtube_client")

# Ensure certificates are configured
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())


class YouTubeClient:
    """Wrapper around yt-dlp for discovery and media downloads."""

    def __init__(self, timeout_seconds: int = 20):
        self.timeout_seconds = timeout_seconds

    def extract_info(
        self,
        url: str,
        download: bool = False,
        flat_playlist: bool = False,
        preferred_client: Optional[List[str]] = None,
        extra_opts: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract media information from YouTube with client strategy retries."""
        js_runtimes = resolve_js_runtimes()
        ffmpeg_exe = resolve_ffmpeg_executable()

        candidates: List[Optional[List[str]]] = []
        if preferred_client not in candidates:
            candidates.append(preferred_client)
        for client in CLIENT_STRATEGIES:
            if client not in candidates:
                candidates.append(client)

        last_error: Optional[Exception] = None

        for client_list in candidates:
            opts: Dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": self.timeout_seconds,
            }
            if flat_playlist:
                opts["extract_flat"] = "in_playlist"
                opts["noplaylist"] = False
            else:
                opts["noplaylist"] = True

            if js_runtimes:
                opts["js_runtimes"] = js_runtimes
            if ffmpeg_exe:
                opts["ffmpeg_location"] = ffmpeg_exe
            if client_list is not None:
                opts["extractor_args"] = {"youtube": {"player_client": client_list}}
            if extra_opts:
                opts.update(extra_opts)

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=download)
                    if info:
                        info["_winning_client"] = client_list
                        return info
            except Exception as exc:
                last_error = exc
                logger.debug(f"Client strategy {client_list} failed for {url}: {exc}")
                continue

        if last_error:
            raise MediaDiscoveryError(f"Could not retrieve info from YouTube: {last_error}") from last_error
        raise MediaDiscoveryError("No YouTube client strategy succeeded.")

    def download_media(
        self,
        url: str,
        ydl_opts: Dict[str, Any],
        preferred_client: Optional[List[str]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        """Download media using yt-dlp with cancellation checks and client retries."""
        js_runtimes = resolve_js_runtimes()
        ffmpeg_exe = resolve_ffmpeg_executable()

        candidates: List[Optional[List[str]]] = []
        if preferred_client not in candidates:
            candidates.append(preferred_client)
        for client in CLIENT_STRATEGIES:
            if client not in candidates:
                candidates.append(client)

        last_error: Optional[Exception] = None

        for client_list in candidates:
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelledError("Download cancelled by user.")

            opts = dict(ydl_opts)
            if js_runtimes and "js_runtimes" not in opts:
                opts["js_runtimes"] = js_runtimes
            if ffmpeg_exe and "ffmpeg_location" not in opts:
                opts["ffmpeg_location"] = ffmpeg_exe
            if client_list is not None:
                opts["extractor_args"] = {"youtube": {"player_client": client_list}}

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    info["_winning_client"] = client_list
                    return info
            except DownloadCancelledError:
                raise
            except Exception as exc:
                if cancel_event and cancel_event.is_set():
                    raise DownloadCancelledError("Download cancelled by user.") from exc
                last_error = exc
                logger.debug(f"Download with client strategy {client_list} failed: {exc}")
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Download failed across all available YouTube client strategies.")
