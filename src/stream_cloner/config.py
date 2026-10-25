"""Configuration management for Stream Cloner."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from stream_cloner.domain.enums import ThemePreference

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


def get_default_download_dir() -> str:
    """Return user's Desktop or Downloads folder across macOS, Windows, and Linux."""
    if IS_WINDOWS:
        user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        candidates = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(user_profile, "OneDrive", "Desktop"),
            os.path.join(user_profile, "Downloads"),
        ]
        onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        if onedrive:
            candidates.insert(0, os.path.join(onedrive, "Desktop"))
        for c in candidates:
            if os.path.isdir(c):
                return c
        return user_profile
    else:
        desktop = os.path.expanduser("~/Desktop")
        if os.path.isdir(desktop):
            return desktop
        downloads = os.path.expanduser("~/Downloads")
        if os.path.isdir(downloads):
            return downloads
        return os.path.expanduser("~")


def get_app_config_dir() -> Path:
    """Locate or create configuration directory in standard user location."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        config_dir = Path(base) / "StreamCloner"
    elif IS_MACOS:
        config_dir = Path.home() / "Library" / "Application Support" / "StreamCloner"
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        config_dir = (Path(xdg_config) if xdg_config else Path.home() / ".config") / "stream-cloner"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        config_dir = Path.home() / ".stream_cloner"
        config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir


CLIENT_STRATEGIES: List[Optional[List[str]]] = [
    ["default", "android_vr"],
    None,
    ["tv", "android_vr", "web_safari"],
    ["android_vr", "web_embedded", "ios"],
    ["web_safari", "web_embedded", "ios", "android", "-tv_downgraded"],
]


@dataclass
class AppConfig:
    """Application configuration and persistence."""

    theme_preference: ThemePreference = ThemePreference.DARK
    download_dir: str = field(default_factory=get_default_download_dir)
    default_audio_bitrate: str = "320"
    network_timeout_seconds: int = 20
    max_retries: int = 3
    prefer_mp4_container: bool = True
    max_parallel_downloads: int = 2
    config_file_path: Optional[Path] = None

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> AppConfig:
        """Load configuration from disk with safe fallback to defaults."""
        target_path = config_path or (get_app_config_dir() / "settings.json")
        instance = cls(config_file_path=target_path)

        if not target_path.exists():
            return instance

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_theme = data.get("theme_preference", ThemePreference.DARK.value)
            try:
                instance.theme_preference = ThemePreference(raw_theme)
            except ValueError:
                instance.theme_preference = ThemePreference.DARK

            saved_dir = data.get("download_dir")
            if saved_dir and os.path.isdir(saved_dir):
                instance.download_dir = saved_dir

            instance.default_audio_bitrate = str(data.get("default_audio_bitrate", "320"))
            instance.network_timeout_seconds = int(data.get("network_timeout_seconds", 20))
            instance.max_retries = int(data.get("max_retries", 3))
            instance.prefer_mp4_container = bool(data.get("prefer_mp4_container", True))
            max_parallel = int(data.get("max_parallel_downloads", 2))
            instance.max_parallel_downloads = max(1, min(max_parallel, 10))

        except Exception:
            # Fall back to default config if file is corrupted or unreadable
            pass

        return instance

    def save(self) -> None:
        """Persist current configuration to disk."""
        target_path = self.config_file_path or (get_app_config_dir() / "settings.json")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "theme_preference": self.theme_preference.value,
                "download_dir": self.download_dir,
                "default_audio_bitrate": self.default_audio_bitrate,
                "network_timeout_seconds": self.network_timeout_seconds,
                "max_retries": self.max_retries,
                "prefer_mp4_container": self.prefer_mp4_container,
                "max_parallel_downloads": self.max_parallel_downloads,
            }
            tmp_path = target_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            tmp_path.replace(target_path)
        except OSError:
            pass
