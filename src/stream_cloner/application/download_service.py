"""Download orchestration, format selection, progress hooks, and verification."""

from __future__ import annotations

import glob
import json
import os
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from stream_cloner.application.format_service import FormatService
from stream_cloner.application.playlist_service import PlaylistService
from stream_cloner.application.validation_service import ValidationService
from stream_cloner.config import get_app_config_dir
from stream_cloner.domain.enums import DownloadMode
from stream_cloner.domain.exceptions import (
    DownloadCancelledError,
    DownloadError,
    MediaDiscoveryError,
    ValidationError,
)
from stream_cloner.domain.models import (
    DownloadProgress,
    DownloadRequest,
    HistoryItem,
    MediaMetadata,
    PlaylistEntry,
    format_bytes,
    format_duration,
)
from stream_cloner.infrastructure.filesystem import (
    ensure_directory,
    get_unique_path,
    sanitize_filename,
    sanitize_folder_name,
)
from stream_cloner.infrastructure.logging import get_logger
from stream_cloner.infrastructure.media_processor import (
    convert_audio_with_ffmpeg,
    has_ffprobe,
    resolve_ffmpeg_executable,
)
from stream_cloner.infrastructure.youtube_client import YouTubeClient

logger = get_logger("download_service")


class DownloadService:
    """Coordinates format discovery, single video, and playlist downloads."""

    def __init__(
        self,
        youtube_client: Optional[YouTubeClient] = None,
        history_file: Optional[Path] = None,
    ):
        self.client = youtube_client or YouTubeClient()
        self.history_file = history_file or (get_app_config_dir() / "history.json")
        self._history_lock = threading.Lock()

    def discover_media(
        self,
        url: str,
        fetch_playlist: bool = False,
        cancel_event: Optional[threading.Event] = None,
    ) -> MediaMetadata:
        """Analyze a video or playlist URL and discover real format options."""
        # Check if multiple URLs were provided separated by comma/semicolon/newline
        multi_urls = ValidationService.parse_multi_urls(url)
        if len(multi_urls) > 1:
            return self.discover_multi_urls(multi_urls, cancel_event=cancel_event)

        validated_url = ValidationService.validate_url(url)
        is_pure_playlist, has_list = ValidationService.inspect_playlist_url(validated_url)
        use_playlist = fetch_playlist or is_pure_playlist

        if use_playlist and has_list:
            logger.info(f"Extracting playlist metadata: {validated_url}")
            pl_info = self.client.extract_info(validated_url, flat_playlist=True)
            raw_entries = pl_info.get("entries") or []
            entries = PlaylistService.parse_playlist_entries(raw_entries)

            if not entries:
                # Fallback to single video inspection if playlist has no valid entries
                return self.discover_media(validated_url, fetch_playlist=False, cancel_event=cancel_event)

            sample_video_formats = []
            sample_audio_formats = []
            sample_thumb = None
            winning_client = pl_info.get("_winning_client")

            # Inspect the first video to extract available format sample
            try:
                first_url = entries[0].url
                first_info = self.client.extract_info(first_url, flat_playlist=False)
                sample_video_formats = FormatService.parse_video_formats(first_info)
                sample_audio_formats = FormatService.parse_audio_formats(first_info)
                sample_thumb = first_info.get("thumbnail")
                winning_client = first_info.get("_winning_client") or winning_client
            except Exception as e:
                logger.warning(f"Could not inspect first playlist video: {e}")
                sample_audio_formats = FormatService.parse_audio_formats({})

            # Thumbnail download
            thumb_url = sample_thumb or (pl_info.get("thumbnails") or [{}])[-1].get("url")
            thumb_bytes = self._fetch_thumbnail_bytes(thumb_url)

            pl_title = pl_info.get("title") or "YouTube Playlist"
            total_duration = sum(int(e.duration or 0) for e in entries) or None

            return MediaMetadata(
                url=validated_url,
                title=f"Playlist: {pl_title}",
                raw_title=pl_title,
                uploader=pl_info.get("uploader") or pl_info.get("channel") or "YouTube Playlist",
                duration=total_duration,
                view_count=pl_info.get("view_count"),
                thumbnail_url=thumb_url,
                thumbnail_bytes=thumb_bytes,
                is_playlist=True,
                has_list_param=True,
                video_formats=sample_video_formats,
                audio_formats=sample_audio_formats,
                default_video_index=0,
                default_audio_index=0,
                playlist_entries=entries,
                winning_client=winning_client,
            )

        # Single Video Discovery
        logger.info(f"Extracting single video metadata: {validated_url}")
        info = self.client.extract_info(validated_url, flat_playlist=False)
        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        video_formats = FormatService.parse_video_formats(info)
        audio_formats = FormatService.parse_audio_formats(info)

        thumb_url = info.get("thumbnail")
        thumb_bytes = self._fetch_thumbnail_bytes(thumb_url)
        v_title = info.get("title") or "Untitled YouTube Video"

        return MediaMetadata(
            url=info.get("webpage_url") or validated_url,
            title=v_title,
            raw_title=v_title,
            uploader=info.get("uploader") or info.get("channel") or "YouTube Creator",
            duration=info.get("duration"),
            view_count=info.get("view_count"),
            thumbnail_url=thumb_url,
            thumbnail_bytes=thumb_bytes,
            is_playlist=False,
            has_list_param=has_list,
            video_formats=video_formats,
            audio_formats=audio_formats,
            default_video_index=0,
            default_audio_index=0,
            playlist_entries=[],
            winning_client=info.get("_winning_client"),
        )

    def discover_multi_urls(
        self,
        urls: List[str],
        cancel_event: Optional[threading.Event] = None,
    ) -> MediaMetadata:
        """Analyze a batch of individual video URLs and assemble a multi-item queue."""
        logger.info(f"Extracting multi-URL batch metadata ({len(urls)} URLs)")
        if not urls:
            raise ValidationError("No valid URLs provided.")

        sample_info = {}
        sample_video_formats = []
        sample_audio_formats = []
        sample_thumb = None
        winning_client = None

        try:
            sample_info = self.client.extract_info(urls[0], flat_playlist=False)
            if "entries" in sample_info and sample_info["entries"]:
                sample_info = sample_info["entries"][0]
            sample_video_formats = FormatService.parse_video_formats(sample_info)
            sample_audio_formats = FormatService.parse_audio_formats(sample_info)
            sample_thumb = sample_info.get("thumbnail")
            winning_client = sample_info.get("_winning_client")
        except Exception as e:
            logger.warning(f"Could not inspect first URL in batch: {e}")
            sample_audio_formats = FormatService.parse_audio_formats({})

        entries: List[PlaylistEntry] = []
        for idx, u in enumerate(urls, start=1):
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelledError("Discovery cancelled.")
            vid_title = f"Video {idx}"
            vid_id = u
            dur = None

            if idx == 1 and sample_info:
                vid_title = sample_info.get("title") or vid_title
                vid_id = sample_info.get("id") or vid_id
                dur = sample_info.get("duration")
            else:
                try:
                    quick_info = self.client.extract_info(u, flat_playlist=False)
                    if quick_info:
                        if "entries" in quick_info and quick_info["entries"]:
                            sub_entry = next((e for e in quick_info["entries"] if e), {})
                            extracted_title = sub_entry.get("title") or sub_entry.get("fulltitle")
                            dur = sub_entry.get("duration")
                            vid_id = sub_entry.get("id") or vid_id
                        else:
                            extracted_title = quick_info.get("title") or quick_info.get("fulltitle")
                            dur = quick_info.get("duration")
                            vid_id = quick_info.get("id") or vid_id

                        if extracted_title and not extracted_title.startswith("http") and "watch?v=" not in extracted_title:
                            vid_title = extracted_title
                except Exception as e:
                    logger.warning(f"Could not extract quick info for batch URL {u}: {e}")

            entries.append(
                PlaylistEntry(
                    index=idx,
                    video_id=vid_id,
                    title=vid_title,
                    url=u,
                    duration=dur,
                )
            )

        thumb_bytes = self._fetch_thumbnail_bytes(sample_thumb)
        total_duration = sum(int(e.duration or 0) for e in entries if e.duration) or None

        return MediaMetadata(
            url=urls[0],
            title=f"Multi-URL Queue ({len(entries)} Videos)",
            raw_title="Multi_Download",
            uploader="Batch Selection",
            duration=total_duration,
            view_count=None,
            thumbnail_url=sample_thumb,
            thumbnail_bytes=thumb_bytes,
            is_playlist=True,
            has_list_param=False,
            video_formats=sample_video_formats,
            audio_formats=sample_audio_formats,
            default_video_index=0,
            default_audio_index=0,
            playlist_entries=entries,
            winning_client=winning_client,
        )

    def _fetch_thumbnail_bytes(self, url: Optional[str]) -> Optional[bytes]:
        """Fetch image bytes safely with timeout."""
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    def execute_download(
        self,
        request: DownloadRequest,
        progress_callback: Callable[[DownloadProgress], None],
        cancel_event: threading.Event,
    ) -> str:
        """Execute single or playlist download according to request parameters."""
        ValidationService.validate_output_directory(request.output_dir)

        if request.playlist_items:
            return self._download_playlist(request, progress_callback, cancel_event)
        else:
            return self._download_single_item(
                url=request.url,
                output_dir=request.output_dir,
                mode=request.mode,
                target_height=request.target_height,
                target_fps=request.target_fps,
                audio_bitrate=request.audio_bitrate,
                preferred_client=request.preferred_client,
                filename_prefix="",
                item_index=1,
                total_items=1,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )

    def _download_single_item(
        self,
        url: str,
        output_dir: str,
        mode: DownloadMode,
        target_height: int,
        target_fps: Optional[int],
        audio_bitrate: str,
        preferred_client: Optional[List[str]],
        filename_prefix: str,
        item_index: int,
        total_items: int,
        progress_callback: Callable[[DownloadProgress], None],
        cancel_event: threading.Event,
        slot_index: int = 0,
        item_title: str = "",
        item_id: str = "",
    ) -> str:
        """Download one video or audio stream with atomic finalization and verification."""
        ensure_directory(output_dir)
        ffmpeg_exe = resolve_ffmpeg_executable()
        probe_ok = has_ffprobe()

        def ydl_hook(d: Dict[str, Any]):
            if cancel_event.is_set():
                raise DownloadCancelledError("Download cancelled by user.")
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0.0
                eta = d.get("eta")
                pct = (downloaded / total * 100.0) if total > 0 else 0.0
                speed_str = f"{format_bytes(speed)}/s" if speed else "Calculating..."
                eta_str = f"{int(eta)}s" if eta is not None else "--"
                prefix_tag = f"[{item_index}/{total_items}] " if total_items > 1 else ""
                status_msg = f"{prefix_tag}Downloading: {pct:.1f}%  •  Speed: {speed_str}  •  ETA: {eta_str}"

                overall_pct = ((item_index - 1) + (pct / 100.0)) / total_items * 100.0
                progress_callback(
                    DownloadProgress(
                        percentage=pct if total_items > 1 else min(max(overall_pct, 0.0), 100.0),
                        overall_percentage=min(max(overall_pct, 0.0), 100.0),
                        status_message=status_msg,
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                        speed_bytes=speed,
                        eta_seconds=eta,
                        current_item=item_index,
                        total_items=total_items,
                        slot_index=slot_index,
                        item_id=item_id,
                        item_title=item_title,
                    )
                )
            elif status == "finished":
                prefix_tag = f"[{item_index}/{total_items}] " if total_items > 1 else ""
                progress_callback(
                    DownloadProgress(
                        percentage=100.0 if total_items > 1 else (item_index / total_items * 98.0),
                        overall_percentage=item_index / total_items * 98.0,
                        status_message=f"{prefix_tag}Stream downloaded. Finalizing container...",
                        current_item=item_index,
                        total_items=total_items,
                        slot_index=slot_index,
                        item_id=item_id,
                        item_title=item_title,
                    )
                )

        prefix_clean = filename_prefix
        outtmpl = os.path.join(output_dir, f"{prefix_clean}%(title).160B [%(id)s].%(ext)s")

        if mode == DownloadMode.AUDIO:
            ydl_opts: Dict[str, Any] = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [ydl_hook],
            }
            if ffmpeg_exe:
                ydl_opts["ffmpeg_location"] = ffmpeg_exe

            # Audio extraction postprocessor if ffmpeg + ffprobe are present
            if ffmpeg_exe and probe_ok and audio_bitrate != "source":
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(audio_bitrate),
                    }
                ]

            info = self.client.download_media(
                url=url,
                ydl_opts=ydl_opts,
                preferred_client=preferred_client,
                cancel_event=cancel_event,
            )

            # Locate downloaded output file
            base_filename = outtmpl.replace("%(title).160B", "").replace("%(id)s", info.get("id", ""))
            candidate = os.path.join(output_dir, f"{prefix_clean}{sanitize_filename(info.get('title', 'audio'))} [{info.get('id', '')}].mp3")

            final_file = self._find_downloaded_file(output_dir, info.get("id", ""))
            if not final_file:
                raise DownloadError("Could not locate downloaded audio file.")

            # If manual FFmpeg encoding is required (e.g. ffprobe was missing)
            if audio_bitrate != "source" and not final_file.endswith(".mp3") and ffmpeg_exe:
                target_mp3 = os.path.splitext(final_file)[0] + f" [{audio_bitrate}kbps].mp3"
                final_file = convert_audio_with_ffmpeg(
                    input_file=final_file,
                    output_file=target_mp3,
                    bitrate_kbps=audio_bitrate,
                    ffmpeg_exe=ffmpeg_exe,
                )

            self._record_history(info.get("title", "Audio Download"), final_file, "Audio", f"{audio_bitrate} kbps")
            return final_file

        else:
            # Video Mode
            fmt_selector = FormatService.build_video_selector(
                target_height=target_height,
                target_fps=target_fps,
                has_ffmpeg=bool(ffmpeg_exe),
            )
            res_tag = f"{target_height}p" if target_height > 0 else "Best"

            ydl_opts = {
                "format": fmt_selector,
                "outtmpl": os.path.join(output_dir, f"{prefix_clean}%(title).150B [%(id)s] [{res_tag}].%(ext)s"),
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [ydl_hook],
            }
            if ffmpeg_exe:
                ydl_opts["ffmpeg_location"] = ffmpeg_exe

            info = self.client.download_media(
                url=url,
                ydl_opts=ydl_opts,
                preferred_client=preferred_client,
                cancel_event=cancel_event,
            )

            final_file = self._find_downloaded_file(output_dir, info.get("id", ""))
            if not final_file:
                raise DownloadError("Could not locate downloaded video file.")

            self._record_history(info.get("title", "Video Download"), final_file, "Video", res_tag)
            return final_file

    def _find_downloaded_file(self, output_dir: str, video_id: str) -> Optional[str]:
        """Search directory for media file containing the given YouTube video ID with fallback."""
        if video_id:
            matches = glob.glob(os.path.join(output_dir, f"*{video_id}*.*"))
            for m in matches:
                if os.path.isfile(m) and not m.endswith((".part", ".ytdl", ".temp")):
                    if os.path.getsize(m) > 0:
                        return m

        media_extensions = (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus", ".wav")
        try:
            candidates = [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.lower().endswith(media_extensions) and not f.endswith((".part", ".ytdl", ".temp"))
            ]
            if candidates:
                candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                if os.path.getsize(candidates[0]) > 0:
                    return candidates[0]
        except OSError:
            pass

        return None

    def _download_playlist(
        self,
        request: DownloadRequest,
        progress_callback: Callable[[DownloadProgress], None],
        cancel_event: threading.Event,
    ) -> str:
        """Download multiple playlist items concurrently with worker slots into a subfolder."""
        pl_name = sanitize_folder_name(request.playlist_title or "Stream_Playlist")
        pl_dir = os.path.join(request.output_dir, pl_name)
        ensure_directory(pl_dir)

        items = request.playlist_items
        total = len(items)
        if total == 0:
            raise DownloadError("No items selected for download.")

        max_workers = max(1, min(request.max_parallel, total))
        logger.info(f"Starting playlist download: {total} items with {max_workers} parallel workers")

        slot_queue: queue.Queue[int] = queue.Queue()
        for s in range(max_workers):
            slot_queue.put(s)

        progress_lock = threading.Lock()
        item_progress_pcts: Dict[int, float] = {i: 0.0 for i in range(1, total + 1)}
        slot_speeds: Dict[int, float] = {}
        successful_downloads = 0

        def make_slot_progress_callback(slot_idx: int, item_idx: int, item_title: str, item_id: str):
            def hook(p: DownloadProgress):
                if cancel_event.is_set():
                    return
                with progress_lock:
                    item_progress_pcts[item_idx] = p.percentage
                    slot_speeds[slot_idx] = p.speed_bytes

                    overall_pct = sum(item_progress_pcts.values()) / total
                    total_speed = sum(slot_speeds.values())
                    speed_str = f"{format_bytes(total_speed)}/s" if total_speed else "Calculating..."
                    overall_msg = (
                        f"[{item_idx}/{total}] Downloading: {item_title}  •  "
                        f"Overall: {overall_pct:.1f}%  •  Total Speed: {speed_str}"
                    )

                    enriched = DownloadProgress(
                        percentage=p.percentage,
                        overall_percentage=min(max(overall_pct, 0.0), 100.0),
                        status_message=p.status_message,
                        downloaded_bytes=p.downloaded_bytes,
                        total_bytes=p.total_bytes,
                        speed_bytes=p.speed_bytes,
                        eta_seconds=p.eta_seconds,
                        current_item=item_idx,
                        total_items=total,
                        slot_index=slot_idx,
                        item_id=item_id,
                        item_title=item_title,
                    )
                progress_callback(enriched)
            return hook

        def download_item_worker(idx: int, item: PlaylistEntry) -> bool:
            if cancel_event.is_set():
                raise DownloadCancelledError("Playlist download cancelled.")

            slot_idx = slot_queue.get()
            try:
                if cancel_event.is_set():
                    raise DownloadCancelledError("Playlist download cancelled.")

                prefix = f"{idx:02d} - "
                item_h = request.target_height
                item_fps = request.target_fps

                # Resolve actual media title if item has a generic or raw URL title
                if (
                    not item.title
                    or item.title.startswith("Video ")
                    or item.title.startswith("Track ")
                    or item.title.startswith("Item ")
                    or item.title.startswith("http")
                    or "watch?v=" in item.title
                ):
                    try:
                        resolved_info = self.client.extract_info(item.url, flat_playlist=False)
                        if resolved_info:
                            cand_title = resolved_info.get("title") or resolved_info.get("fulltitle")
                            if cand_title and not cand_title.startswith("http") and "watch?v=" not in cand_title:
                                item.title = cand_title
                    except Exception as e:
                        logger.warning(f"Could not resolve item title #{idx}: {e}")

                if item_h > 0:
                    try:
                        item_info = self.client.extract_info(item.url, flat_playlist=False)
                        item_h, item_fps = PlaylistService.resolve_item_quality(
                            target_height=request.target_height,
                            target_fps=request.target_fps,
                            item_formats=item_info.get("formats"),
                        )
                        if item_info.get("title") and (not item.title or item.title.startswith("Video ") or item.title.startswith("Track ")):
                            item.title = item_info.get("title")
                    except Exception as e:
                        logger.warning(f"Could not inspect formats for playlist item #{idx}: {e}")

                slot_cb = make_slot_progress_callback(slot_idx, idx, item.title, item.video_id)

                with progress_lock:
                    slot_speeds[slot_idx] = 0.0
                    start_prog = DownloadProgress(
                        percentage=0.0,
                        overall_percentage=sum(item_progress_pcts.values()) / total,
                        status_message=f"Starting download: {item.title}...",
                        current_item=idx,
                        total_items=total,
                        slot_index=slot_idx,
                        item_id=item.video_id,
                        item_title=item.title,
                    )
                progress_callback(start_prog)

                self._download_single_item(
                    url=item.url,
                    output_dir=pl_dir,
                    mode=request.mode,
                    target_height=item_h,
                    target_fps=item_fps,
                    audio_bitrate=request.audio_bitrate,
                    preferred_client=request.preferred_client,
                    filename_prefix=prefix,
                    item_index=idx,
                    total_items=total,
                    progress_callback=slot_cb,
                    cancel_event=cancel_event,
                    slot_index=slot_idx,
                    item_title=item.title,
                    item_id=item.video_id,
                )

                with progress_lock:
                    item_progress_pcts[idx] = 100.0
                    slot_speeds[slot_idx] = 0.0
                    done_prog = DownloadProgress(
                        percentage=100.0,
                        overall_percentage=sum(item_progress_pcts.values()) / total,
                        status_message=f"Finished: {item.title}",
                        current_item=idx,
                        total_items=total,
                        slot_index=slot_idx,
                        item_id=item.video_id,
                        item_title=item.title,
                    )
                progress_callback(done_prog)
                return True
            except DownloadCancelledError:
                raise
            except Exception as e:
                logger.error(f"Error downloading playlist item #{idx} ({item.title}): {e}")
                with progress_lock:
                    slot_speeds[slot_idx] = 0.0
                    fail_prog = DownloadProgress(
                        percentage=0.0,
                        overall_percentage=sum(item_progress_pcts.values()) / total,
                        status_message=f"Failed: {e}",
                        current_item=idx,
                        total_items=total,
                        slot_index=slot_idx,
                        item_id=item.video_id,
                        item_title=item.title,
                    )
                progress_callback(fail_prog)
                return False
            finally:
                slot_queue.put(slot_idx)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(download_item_worker, idx, item)
                for idx, item in enumerate(items, start=1)
            ]
            try:
                for future in as_completed(futures):
                    if cancel_event.is_set():
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise DownloadCancelledError("Playlist download cancelled.")
                    if future.result():
                        successful_downloads += 1
            except DownloadCancelledError:
                executor.shutdown(wait=False, cancel_futures=True)
                raise

        if successful_downloads == 0:
            raise DownloadError("All items in the playlist failed to download.")

        progress_callback(
            DownloadProgress(
                percentage=100.0,
                overall_percentage=100.0,
                status_message=f"Completed {successful_downloads} of {total} items in playlist.",
                current_item=total,
                total_items=total,
            )
        )
        return pl_dir

    def _record_history(self, title: str, file_path: str, mode: str, quality_label: str) -> None:
        """Record completed download in local history cache."""
        with self._history_lock:
            try:
                sz = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                item = HistoryItem(
                    id=str(uuid.uuid4())[:8],
                    timestamp=time.time(),
                    title=title,
                    file_path=file_path,
                    file_size=sz,
                    mode=mode,
                    quality_label=quality_label,
                )

                history_list = self.load_history()
                history_list.insert(0, item)
                history_list = history_list[:50]  # Keep latest 50

                payload = [
                    {
                        "id": h.id,
                        "timestamp": h.timestamp,
                        "title": h.title,
                        "file_path": h.file_path,
                        "file_size": h.file_size,
                        "mode": h.mode,
                        "quality_label": h.quality_label,
                    }
                    for h in history_list
                ]

                self.history_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception as exc:
                logger.warning(f"Failed to record history: {exc}")

    def load_history(self) -> List[HistoryItem]:
        """Load history items from disk."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [
                HistoryItem(
                    id=x.get("id", ""),
                    timestamp=x.get("timestamp", 0.0),
                    title=x.get("title", ""),
                    file_path=x.get("file_path", ""),
                    file_size=x.get("file_size", 0),
                    mode=x.get("mode", "Video"),
                    quality_label=x.get("quality_label", ""),
                )
                for x in raw
                if isinstance(x, dict)
            ]
        except Exception:
            return []

    def clear_history(self) -> None:
        """Clear all download history records from disk."""
        with self._history_lock:
            try:
                self.history_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception as exc:
                logger.warning(f"Failed to clear history: {exc}")

    def delete_history_item(self, item_id: str) -> List[HistoryItem]:
        """Delete a single history record by ID and persist the updated list."""
        with self._history_lock:
            items = [h for h in self.load_history() if h.id != item_id]
            try:
                payload = [
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
                self.history_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception as exc:
                logger.warning(f"Failed to delete history item: {exc}")
            return items
