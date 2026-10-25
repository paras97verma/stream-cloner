"""Filesystem utilities and safe path management."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from stream_cloner.domain.exceptions import FilesystemError
from stream_cloner.infrastructure.logging import get_logger

logger = get_logger("filesystem")

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


def sanitize_filename(name: str, max_length: int = 160) -> str:
    """Sanitize filename by stripping illegal characters and preserving Unicode."""
    if not name:
        return "stream_media"

    # Remove illegal filename characters across Windows/macOS/Linux
    cleaned = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "_", name).strip()
    # Normalize excessive spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip(". ")
    if not cleaned:
        cleaned = "stream_media"

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")

    return cleaned


def sanitize_folder_name(name: str, max_length: int = 120) -> str:
    """Sanitize folder name for playlist storage."""
    if not name or not name.strip():
        return "Stream_Playlist"
    cleaned = sanitize_filename(name, max_length=max_length)
    if not cleaned or cleaned == "stream_media":
        return "Stream_Playlist"
    return cleaned


def get_unique_path(target_path: str) -> str:
    """If target file already exists, return unique name with incrementing counter."""
    if not os.path.exists(target_path):
        return target_path

    p = Path(target_path)
    stem = p.stem
    ext = p.suffix
    parent = p.parent

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){ext}"
        if not candidate.exists():
            return str(candidate)
        counter += 1


def ensure_directory(path: str | Path) -> Path:
    """Safely create directory tree if it does not already exist."""
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except OSError as e:
        logger.error(f"Failed to create directory {path}: {e}")
        raise FilesystemError(f"Cannot create directory: {path}") from e


def get_file_manager_name() -> str:
    """Return OS-appropriate file manager name ('Finder' on macOS, 'Explorer' on Windows, 'Files' on Linux)."""
    if IS_MACOS:
        return "Finder"
    if IS_WINDOWS:
        return "Explorer"
    return "Files"


def reveal_in_file_manager(path: str | Path) -> bool:
    """
    Open containing folder or highlight file in native desktop file manager.
    Expands ~ and environment variables, creates directory if needed, and returns True on success.
    """
    if not path:
        return False

    raw_path = str(path).strip()
    if not raw_path:
        return False

    try:
        expanded = os.path.expanduser(os.path.expandvars(raw_path))
        target = Path(expanded).resolve()

        if not target.exists():
            parent = target.parent
            if parent.exists():
                target = parent
            else:
                try:
                    target.mkdir(parents=True, exist_ok=True)
                except Exception:
                    try:
                        parent.mkdir(parents=True, exist_ok=True)
                        target = parent
                    except Exception:
                        logger.warning(f"Target path does not exist and cannot be created: {raw_path}")
                        return False

        if IS_MACOS:
            open_bin = shutil.which("open") or "/usr/bin/open"
            if target.is_file():
                subprocess.Popen([open_bin, "-R", str(target)])
            else:
                subprocess.Popen([open_bin, str(target)])
            return True

        elif IS_WINDOWS:
            win_path = str(target).replace("/", "\\")
            if target.is_file():
                subprocess.Popen(f'explorer.exe /select,"{win_path}"', shell=True)
            else:
                try:
                    os.startfile(win_path)  # type: ignore[attr-defined]
                except Exception:
                    subprocess.Popen(f'explorer.exe "{win_path}"', shell=True)
            return True

        else:
            xdg_bin = shutil.which("xdg-open") or "/usr/bin/xdg-open"
            folder = str(target if target.is_dir() else target.parent)
            subprocess.Popen([xdg_bin, folder])
            return True

    except Exception as exc:
        logger.warning(f"Could not open file manager for {path}: {exc}")
        return False
