"""Dynamic stream format discovery, inspection, and selector generation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from stream_cloner.domain.models import AudioFormatOption, VideoFormatOption, format_bytes
from stream_cloner.infrastructure.logging import get_logger

logger = get_logger("format_service")


class FormatService:
    """Discovers and parses media formats strictly from live YouTube metadata."""

    @staticmethod
    def parse_video_formats(info: Dict[str, Any]) -> List[VideoFormatOption]:
        """
        Dynamically discover available video formats from yt-dlp metadata.
        NO hardcoded resolution lists are used.
        Only resolutions and frame rates present in info['formats'] are advertised.
        """
        raw_formats = info.get("formats") or []
        if not raw_formats:
            return []

        # Find best audio stream filesize to estimate combined container size
        best_audio_size = 0
        for f in raw_formats:
            if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none"):
                sz = f.get("filesize") or f.get("filesize_approx") or 0
                if sz > best_audio_size:
                    best_audio_size = sz

        by_key: Dict[Tuple[int, int], VideoFormatOption] = {}

        for f in raw_formats:
            vcodec = f.get("vcodec")
            height = f.get("height")
            if not vcodec or vcodec == "none" or not height:
                continue

            try:
                h = int(height)
            except (ValueError, TypeError):
                continue

            if h < 144:
                continue

            raw_fps = f.get("fps")
            fps = int(round(float(raw_fps))) if raw_fps else 30
            v_size = f.get("filesize") or f.get("filesize_approx") or 0
            total_est = (v_size + best_audio_size) if v_size else None
            ext = f.get("ext") or "mp4"

            dyn_range = str(f.get("dynamic_range") or "")
            is_hdr = "hdr" in dyn_range.lower() or "vp9.2" in str(vcodec).lower()

            codec_short = ""
            vc_lower = str(vcodec).lower()
            if "av01" in vc_lower:
                codec_short = "AV1"
            elif "vp9" in vc_lower or "vp09" in vc_lower:
                codec_short = "VP9"
            elif "avc" in vc_lower or "h264" in vc_lower:
                codec_short = "H.264"

            key = (h, fps)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = VideoFormatOption(
                    height=h,
                    fps=fps,
                    approx_size=total_est,
                    ext=ext,
                    is_hdr=is_hdr,
                    codec_hint=codec_short,
                    format_id=str(f.get("format_id") or ""),
                )
            else:
                # Merge superior attributes
                if total_est and (not existing.approx_size or total_est > existing.approx_size):
                    existing.approx_size = total_est
                if is_hdr:
                    existing.is_hdr = True
                if codec_short in ("AV1", "VP9") and existing.codec_hint == "H.264":
                    existing.codec_hint = codec_short

        if not by_key:
            return []

        # Sort highest resolution first, then highest FPS
        sorted_keys = sorted(by_key.keys(), key=lambda k: (k[0], k[1]), reverse=True)
        detected_options = [by_key[k] for k in sorted_keys]

        # Prepend 'Best Available' as the default selection at index 0
        top = detected_options[0]
        fps_tag = f" {top.fps}fps" if top.fps and top.fps > 30 else ""
        hdr_tag = " HDR" if top.is_hdr else ""
        best_opt = VideoFormatOption(
            height=0,
            fps=top.fps,
            approx_size=top.approx_size,
            is_hdr=top.is_hdr,
            codec_hint=top.codec_hint,
            is_default=True,
            custom_label=f"Best Available — Auto Highest ({top.height}p{fps_tag}{hdr_tag})",
        )

        return [best_opt] + detected_options

    @staticmethod
    def parse_audio_formats(info: Dict[str, Any]) -> List[AudioFormatOption]:
        """
        Discover available audio streams and generate conversion targets.
        """
        raw_formats = info.get("formats") or []
        best_abr = 0
        best_codec = "audio"
        best_audio_size = 0

        for f in raw_formats:
            if f.get("acodec") not in (None, "none"):
                abr = f.get("abr") or f.get("tbr") or 0
                sz = f.get("filesize") or f.get("filesize_approx") or 0
                if abr > best_abr:
                    best_abr = int(abr)
                    best_codec = str(f.get("acodec") or "audio").split(".")[0].upper()
                    best_audio_size = sz

        source_label = (
            f"Best Source Audio ({best_abr} kbps {best_codec})"
            if best_abr > 0
            else "Best Available Audio (Highest Source Quality)"
        )

        options: List[AudioFormatOption] = [
            AudioFormatOption(
                bitrate_kbps="source",
                label=source_label,
                codec=best_codec,
                approx_size=best_audio_size if best_audio_size > 0 else None,
                is_source=True,
                is_default=True,
            ),
            AudioFormatOption(
                bitrate_kbps="320",
                label="320 kbps — Studio Master MP3 (Highest Bitrate)",
                codec="mp3",
                is_default=False,
            ),
            AudioFormatOption(
                bitrate_kbps="256",
                label="256 kbps — High Quality MP3",
                codec="mp3",
                is_default=False,
            ),
            AudioFormatOption(
                bitrate_kbps="192",
                label="192 kbps — Standard Quality MP3",
                codec="mp3",
                is_default=False,
            ),
            AudioFormatOption(
                bitrate_kbps="128",
                label="128 kbps — Compact MP3",
                codec="mp3",
                is_default=False,
            ),
            AudioFormatOption(
                bitrate_kbps="96",
                label="96 kbps — Voice / Speech MP3",
                codec="mp3",
                is_default=False,
            ),
        ]

        return options

    @staticmethod
    def build_video_selector(target_height: int, target_fps: Optional[int], has_ffmpeg: bool) -> str:
        """
        Construct optimal yt-dlp format selector string.
        Falls back progressively if exact stream combination is unavailable.
        """
        if not has_ffmpeg:
            if target_height <= 0:
                return "best/b"
            return f"best[height={target_height}]/best[height<={target_height}]/best"

        if target_height <= 0:
            # Best available video + audio stream
            return "bv*+ba/b"

        h = target_height
        fps = int(target_fps or 0)
        if fps > 0:
            return (
                f"bv*[height={h}][fps={fps}]+ba/"
                f"bv*[height={h}]+ba/"
                f"bv*[height<={h}]+ba/"
                f"b[height<={h}]/best"
            )
        else:
            return (
                f"bv*[height={h}]+ba/"
                f"bv*[height<={h}]+ba/"
                f"b[height<={h}]/best"
            )

    @staticmethod
    def build_audio_selector() -> str:
        """Construct optimal audio format selector."""
        return "ba/b"
