"""Playlist extraction, item queuing, and dynamic per-item quality resolution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from stream_cloner.application.format_service import FormatService
from stream_cloner.domain.models import PlaylistEntry
from stream_cloner.infrastructure.logging import get_logger

logger = get_logger("playlist_service")


class PlaylistService:
    """Manages playlist entry extraction and per-item quality resolution."""

    @staticmethod
    def parse_playlist_entries(raw_entries: List[Dict[str, Any]]) -> List[PlaylistEntry]:
        """Convert raw yt-dlp flat extraction entries into clean PlaylistEntry models."""
        entries: List[PlaylistEntry] = []
        for idx, item in enumerate(raw_entries, start=1):
            if not item:
                continue

            vid_id = item.get("id") or ""
            title = item.get("title") or f"Video #{idx}"
            if title in ("[Private video]", "[Deleted video]"):
                continue

            url = item.get("url") or ""
            if not url or not url.startswith("http"):
                if vid_id:
                    url = f"https://www.youtube.com/watch?v={vid_id}"

            if not url:
                continue

            thumbs = item.get("thumbnails") or []
            thumb_url = thumbs[-1].get("url") if thumbs else None

            entries.append(
                PlaylistEntry(
                    index=len(entries) + 1,
                    video_id=vid_id,
                    title=title,
                    url=url,
                    duration=item.get("duration"),
                    thumbnail_url=thumb_url,
                )
            )

        return entries

    @staticmethod
    def resolve_item_quality(
        target_height: int,
        target_fps: Optional[int],
        item_formats: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[int, Optional[int]]:
        """
        Determine target quality for an individual playlist video:
        - If target_height == 0 (Best Available), always select best available for this item.
        - If user specified a target resolution (e.g. 1080p), and this video does not offer 1080p,
          fall back to the highest available resolution for THIS video without downgrading others.
        """
        if target_height <= 0 or not item_formats:
            # 0 means automatic best available per item
            return (0, target_fps)

        discovered = FormatService.parse_video_formats({"formats": item_formats})
        available_heights = [q.height for q in discovered if q.height > 0]
        if not available_heights:
            return (target_height, target_fps)

        if target_height in available_heights:
            return (target_height, target_fps)

        # Fallback to highest available resolution <= target_height
        lower_or_equal = [h for h in available_heights if h <= target_height]
        if lower_or_equal:
            best_fallback = max(lower_or_equal)
            logger.info(f"Playlist item fallback from {target_height}p to {best_fallback}p")
            return (best_fallback, target_fps)

        # If all formats are higher, pick the lowest available or best available
        return (available_heights[-1], target_fps)
