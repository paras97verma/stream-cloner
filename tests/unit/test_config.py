"""Unit tests for configuration persistence and validation."""

from pathlib import Path

from stream_cloner.config import AppConfig, get_app_config_dir, get_default_download_dir
from stream_cloner.domain.enums import ThemePreference


def test_default_config():
    config = AppConfig()
    assert config.theme_preference == ThemePreference.DARK
    assert config.network_timeout_seconds == 20
    assert config.default_audio_bitrate == "320"
    assert config.max_retries == 3
    assert config.prefer_mp4_container is True
    assert config.max_parallel_downloads == 2
    assert isinstance(config.download_dir, str)
    assert len(config.download_dir) > 0


def test_save_and_load_config(temp_dir: Path):
    cfg_file = temp_dir / "custom_settings.json"
    cfg = AppConfig(
        theme_preference=ThemePreference.DARK,
        download_dir=str(temp_dir),
        default_audio_bitrate="256",
        network_timeout_seconds=30,
        max_parallel_downloads=4,
        config_file_path=cfg_file,
    )
    cfg.save()

    assert cfg_file.exists()

    loaded = AppConfig.load(cfg_file)
    assert loaded.theme_preference == ThemePreference.DARK
    assert loaded.download_dir == str(temp_dir)
    assert loaded.default_audio_bitrate == "256"
    assert loaded.network_timeout_seconds == 30
    assert loaded.max_parallel_downloads == 4


def test_corrupt_config_fallback(temp_dir: Path):
    cfg_file = temp_dir / "corrupted.json"
    cfg_file.write_text("{this is not valid json}", encoding="utf-8")

    loaded = AppConfig.load(cfg_file)
    assert loaded.theme_preference == ThemePreference.DARK
    assert loaded.default_audio_bitrate == "320"
    assert loaded.max_parallel_downloads == 2
