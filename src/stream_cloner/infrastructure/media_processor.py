"""Media processing and external tool resolution (FFmpeg, FFprobe, Deno, Node)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from stream_cloner.domain.exceptions import DependencyNotFoundError
from stream_cloner.infrastructure.logging import get_logger

logger = get_logger("media_processor")

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
VENV_BIN = os.path.dirname(os.path.abspath(sys.executable))


def resolve_ffmpeg_executable() -> Optional[str]:
    """Locate ffmpeg / ffmpeg.exe in bundle, virtualenv, PATH, Homebrew, or imageio-ffmpeg."""
    exe_name = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"

    # 1. Bundled in PyInstaller frozen package
    bundled = os.path.join(BUNDLE_DIR, exe_name)
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled

    # 2. Virtual environment bin/Scripts directory
    venv_candidate = os.path.join(VENV_BIN, exe_name)
    if os.path.isfile(venv_candidate) and os.access(venv_candidate, os.X_OK):
        return venv_candidate

    # 3. System PATH
    system_candidate = shutil.which("ffmpeg")
    if system_candidate:
        return system_candidate

    # 4. Standard macOS Homebrew / Unix locations
    if not IS_WINDOWS:
        for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

    # 5. imageio-ffmpeg fallback package
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass

    return None


def resolve_ffprobe_executable() -> Optional[str]:
    """Locate ffprobe / ffprobe.exe if present."""
    probe_name = "ffprobe.exe" if IS_WINDOWS else "ffprobe"
    bundled = os.path.join(BUNDLE_DIR, probe_name)
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled

    venv_candidate = os.path.join(VENV_BIN, probe_name)
    if os.path.isfile(venv_candidate) and os.access(venv_candidate, os.X_OK):
        return venv_candidate

    sys_probe = shutil.which("ffprobe")
    if sys_probe:
        return sys_probe

    if not IS_WINDOWS:
        for candidate in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

    return None


def has_ffprobe() -> bool:
    """Return True if ffprobe executable is found."""
    return resolve_ffprobe_executable() is not None


def resolve_js_runtimes() -> Dict[str, Dict[str, Any]]:
    """Locate Deno or Node runtime so yt-dlp can unlock ultra-high-resolution streams."""
    runtimes: Dict[str, Dict[str, Any]] = {}
    deno_name = "deno.exe" if IS_WINDOWS else "deno"

    deno_candidates = [
        os.path.join(BUNDLE_DIR, deno_name),
        os.path.join(VENV_BIN, deno_name),
        shutil.which("deno") or "",
        os.path.expanduser(f"~/.deno/bin/{deno_name}"),
    ]
    if not IS_WINDOWS:
        deno_candidates.extend(["/opt/homebrew/bin/deno", "/usr/local/bin/deno"])

    for c in deno_candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            runtimes["deno"] = {"path": c}
            break

    node_candidates = [shutil.which("node") or ""]
    if not IS_WINDOWS:
        node_candidates.extend(["/opt/homebrew/bin/node", "/usr/local/bin/node"])
    else:
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        node_candidates.append(os.path.join(prog_files, "nodejs", "node.exe"))

    for c in node_candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            runtimes["node"] = {"path": c}
            break

    return runtimes


def convert_audio_with_ffmpeg(
    input_file: str,
    output_file: str,
    bitrate_kbps: str = "320",
    ffmpeg_exe: Optional[str] = None,
) -> str:
    """
    Transcode an input audio or video file to MP3 using FFmpeg with safe argument arrays.
    """
    exe = ffmpeg_exe or resolve_ffmpeg_executable()
    if not exe:
        raise DependencyNotFoundError("FFmpeg is required for audio encoding but was not found.")

    cmd = [
        exe,
        "-y",
        "-i",
        input_file,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        f"{bitrate_kbps}k",
        "-ar",
        "44100",
        output_file,
    ]

    logger.info(f"Running audio conversion: {' '.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")
        logger.error(f"FFmpeg conversion failed: {err}")
        raise RuntimeError(f"FFmpeg failed to convert audio: {err[:200]}")

    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        raise RuntimeError("FFmpeg conversion completed but output file is missing or empty.")

    return output_file
