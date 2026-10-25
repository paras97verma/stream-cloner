"""Bridge API exposing Python services to the Vue.js desktop frontend."""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from stream_cloner.application.download_service import DownloadService
from stream_cloner.application.format_service import FormatService
from stream_cloner.application.validation_service import ValidationService
from stream_cloner.config import AppConfig
from stream_cloner.domain.enums import DownloadMode, ThemePreference
from stream_cloner.domain.exceptions import DownloadCancelledError, DownloadError
from stream_cloner.domain.models import DownloadProgress, DownloadRequest, PlaylistEntry
from stream_cloner.infrastructure.filesystem import get_file_manager_name, reveal_in_file_manager
from stream_cloner.infrastructure.logging import get_logger
from stream_cloner.infrastructure.media_processor import (
    resolve_ffmpeg_executable,
    resolve_js_runtimes,
)

logger = get_logger("bridge_api")

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


class BridgeAPI:
    """Python API bridge consumed by Vue.js via window.pywebview.api or HTTP endpoints."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        download_service: Optional[DownloadService] = None,
    ):
        self.config = config or AppConfig.load()
        self.download_service = download_service or DownloadService()
        self.window = None  # Reference to pywebview window set after creation
        self.cancel_event = threading.Event()
        self.download_thread: Optional[threading.Thread] = None
        self._is_downloading = False

    def set_window(self, window):
        """Bind active pywebview window instance for JS event dispatch."""
        self.window = window

    def _dispatch_js(self, func_name: str, data: Any):
        """Safely evaluate JavaScript in the frontend."""
        if self.window:
            try:
                serialized = json.dumps(data)
                script = f"if (window.{func_name}) {{ window.{func_name}({serialized}); }}"
                self.window.evaluate_js(script)
            except Exception as e:
                logger.debug(f"JS evaluation error ({func_name}): {e}")

    def get_initial_state(self) -> Dict[str, Any]:
        """Fetch bootstrap config, platform metadata, and tool dependencies."""
        has_ffmpeg = bool(resolve_ffmpeg_executable())
        has_js = bool(resolve_js_runtimes())

        default_audio_options = [
            {
                "bitrate_kbps": opt.bitrate_kbps,
                "label": opt.label,
                "display_label": opt.display_label,
                "approx_size": opt.approx_size,
                "is_default": opt.is_default,
            }
            for opt in FormatService.parse_audio_formats({})
        ]

        return {
            "theme": self.config.theme_preference.value,
            "download_dir": self.config.download_dir,
            "max_parallel": self.config.max_parallel_downloads,
            "has_ffmpeg": has_ffmpeg,
            "has_js": has_js,
            "file_manager_name": get_file_manager_name(),
            "is_macos": IS_MACOS,
            "is_windows": IS_WINDOWS,
            "default_audio_formats": default_audio_options,
        }

    def set_theme(self, theme_val: Union[str, Dict[str, Any]]) -> bool:
        """Update and persist theme preference."""
        if isinstance(theme_val, dict):
            theme_val = theme_val.get("theme", "")
        try:
            pref = ThemePreference(str(theme_val))
            self.config.theme_preference = pref
            self.config.save()
            return True
        except ValueError:
            return False

    def set_max_parallel(self, max_parallel: Union[int, Dict[str, Any]]) -> bool:
        """Update and persist simultaneous downloads limit."""
        if isinstance(max_parallel, dict):
            max_parallel = max_parallel.get("max_parallel", 2)
        try:
            val = max(1, min(int(max_parallel), 10))
            self.config.max_parallel_downloads = val
            self.config.save()
            return True
        except Exception:
            return False

    def choose_directory(self) -> Dict[str, Any]:
        """Open native folder picker dialog."""
        if self.window:
            import webview
            chosen = self.window.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=self.config.download_dir,
            )
            if chosen and len(chosen) > 0:
                selected_dir = chosen[0]
                self.config.download_dir = selected_dir
                self.config.save()
                return {"success": True, "download_dir": selected_dir}
        return {"success": False, "download_dir": self.config.download_dir}

    def open_folder(self, target_path: Optional[Union[str, Dict[str, Any]]] = None) -> bool:
        """Reveal file or folder in native file manager (Finder/Explorer)."""
        if isinstance(target_path, dict):
            target_path = target_path.get("path")
        target = target_path or self.config.download_dir
        return reveal_in_file_manager(str(target))

    def open_url(self, target_url: Union[str, Dict[str, Any]]) -> bool:
        """Open an external web URL in the operating system's default browser."""
        import webbrowser
        if isinstance(target_url, dict):
            target_url = target_url.get("url", "")
        url_str = str(target_url or "").strip()
        if url_str.startswith("http://") or url_str.startswith("https://"):
            return webbrowser.open(url_str)
        return False

    def discover_media(self, url: Union[str, Dict[str, Any]], fetch_playlist: bool = False) -> Dict[str, Any]:
        """Discover formats, resolutions, or playlist items for a YouTube link or multi-URL list."""
        if isinstance(url, dict):
            fetch_playlist = url.get("fetch_playlist", fetch_playlist)
            url = url.get("url", "")

        url_str = str(url or "").strip()
        if not url_str:
            return {"success": False, "error": "Please enter or paste a valid YouTube link."}

        try:
            metadata = self.download_service.discover_media(
                url=url_str,
                fetch_playlist=fetch_playlist,
            )

            video_formats = [
                {
                    "height": opt.height,
                    "fps": opt.fps,
                    "approx_size": opt.approx_size,
                    "display_label": opt.display_label,
                    "selection_key": list(opt.selection_key),
                    "is_default": opt.is_default,
                    "is_hdr": opt.is_hdr,
                    "codec_hint": opt.codec_hint,
                }
                for opt in metadata.video_formats
            ]

            audio_formats = [
                {
                    "bitrate_kbps": opt.bitrate_kbps,
                    "label": opt.label,
                    "display_label": opt.display_label,
                    "approx_size": opt.approx_size,
                    "is_default": opt.is_default,
                }
                for opt in metadata.audio_formats
            ]

            playlist_entries = [
                {
                    "index": entry.index,
                    "video_id": entry.video_id,
                    "title": entry.title,
                    "url": entry.url,
                    "duration": entry.duration,
                    "thumbnail_url": entry.thumbnail_url,
                }
                for entry in metadata.playlist_entries
            ]

            return {
                "success": True,
                "url": metadata.url,
                "title": metadata.title,
                "raw_title": metadata.raw_title,
                "uploader": metadata.uploader,
                "duration": metadata.duration,
                "view_count": metadata.view_count,
                "thumbnail_url": metadata.thumbnail_url,
                "is_playlist": metadata.is_playlist,
                "has_list_param": metadata.has_list_param,
                "video_formats": video_formats,
                "audio_formats": audio_formats,
                "playlist_entries": playlist_entries,
                "winning_client": metadata.winning_client,
            }
        except Exception as exc:
            logger.error(f"Media discovery failed: {exc}")
            return {"success": False, "error": str(exc)}

    def start_download(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute video, audio, or playlist download in a background thread."""
        if self._is_downloading:
            return {"success": False, "error": "A download is already in progress."}

        url = payload.get("url", "").strip()
        mode_str = payload.get("mode", "video").lower()
        mode = DownloadMode.AUDIO if mode_str == "audio" else DownloadMode.VIDEO
        target_height = int(payload.get("target_height", 0))
        target_fps = payload.get("target_fps")
        audio_bitrate = str(payload.get("audio_bitrate", "320"))
        preferred_client = payload.get("preferred_client")
        playlist_title = payload.get("playlist_title")

        # Parse selected playlist items
        raw_items = payload.get("playlist_items") or []
        playlist_items: List[PlaylistEntry] = []
        for idx, item in enumerate(raw_items, start=1):
            playlist_items.append(
                PlaylistEntry(
                    index=item.get("index", idx),
                    video_id=item.get("video_id", f"v_{idx}"),
                    title=item.get("title", f"Video {idx}"),
                    url=item.get("url", url),
                    duration=item.get("duration"),
                )
            )

        # Multi-URL fallback if direct comma-separated URLs given without queue
        if not playlist_items:
            multi = ValidationService.parse_multi_urls(url)
            if len(multi) > 1:
                playlist_items = [
                    PlaylistEntry(index=i + 1, video_id=u, title=f"Video {i + 1}", url=u)
                    for i, u in enumerate(multi)
                ]
                playlist_title = playlist_title or "Multi_URL_Downloads"

        max_parallel = int(payload.get("max_parallel", self.config.max_parallel_downloads))
        request = DownloadRequest(
            url=url,
            output_dir=self.config.download_dir,
            mode=mode,
            target_height=target_height,
            target_fps=target_fps,
            audio_bitrate=audio_bitrate,
            preferred_client=preferred_client,
            playlist_items=playlist_items,
            playlist_title=playlist_title,
            max_parallel=max_parallel,
        )

        self.cancel_event.clear()
        self._is_downloading = True

        def download_worker():
            try:
                def on_progress(p: DownloadProgress):
                    # Dispatch overall progress
                    self._dispatch_js(
                        "onDownloadProgress",
                        {
                            "overall_percentage": p.overall_percentage if p.overall_percentage > 0 else p.percentage,
                            "percentage": p.percentage,
                            "status_message": p.status_message,
                            "downloaded_bytes": p.downloaded_bytes,
                            "total_bytes": p.total_bytes,
                            "speed_bytes": p.speed_bytes,
                            "eta_seconds": p.eta_seconds,
                            "current_item": p.current_item,
                            "total_items": p.total_items,
                        },
                    )
                    # Dispatch slot progress if in multi-download
                    if p.slot_index >= 0 and p.item_title:
                        self._dispatch_js(
                            "onSlotProgress",
                            {
                                "slot_index": p.slot_index,
                                "item_title": p.item_title,
                                "percentage": p.percentage,
                                "status_message": p.status_message,
                            },
                        )

                out_path = self.download_service.execute_download(
                    request=request,
                    progress_callback=on_progress,
                    cancel_event=self.cancel_event,
                )
                count = len(request.playlist_items) if request.playlist_items else 1
                self._dispatch_js("onDownloadFinished", {"output_path": out_path, "count": count})
            except DownloadCancelledError:
                self._dispatch_js("onDownloadFailed", {"error": "Download cancelled by user.", "cancelled": True})
            except Exception as exc:
                logger.error(f"Download execution error: {exc}")
                self._dispatch_js("onDownloadFailed", {"error": str(exc), "cancelled": False})
            finally:
                self._is_downloading = False

        self.download_thread = threading.Thread(target=download_worker, daemon=True)
        self.download_thread.start()
        return {"success": True, "active_slots": min(max_parallel, len(playlist_items)) if len(playlist_items) > 1 else 1}

    def cancel_download(self) -> bool:
        """Cancel ongoing download immediately."""
        if self._is_downloading:
            self.cancel_event.set()
            return True
        return False

    def get_history(self) -> List[Dict[str, Any]]:
        """Retrieve completed downloads history."""
        items = self.download_service.load_history()
        return [
            {
                "id": h.id,
                "timestamp": h.timestamp,
                "title": h.title,
                "file_path": h.file_path,
                "file_size": h.file_size,
                "mode": h.mode,
                "quality_label": h.quality_label,
            }
            for h in items
        ]

    def delete_history_item(self, item_id: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove a record from history."""
        if isinstance(item_id, dict):
            item_id = item_id.get("id", "")
        items = self.download_service.delete_history_item(str(item_id))
        return [
            {
                "id": h.id,
                "timestamp": h.timestamp,
                "title": h.title,
                "file_path": h.file_path,
                "file_size": h.file_size,
                "mode": h.mode,
                "quality_label": h.quality_label,
            }
            for h in items
        ]

    def clear_history(self) -> bool:
        """Clear all download history records."""
        self.download_service.clear_history()
        return True
