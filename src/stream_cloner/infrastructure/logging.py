"""Structured logging infrastructure for Stream Cloner."""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

LOGGER_NAME = "stream_cloner"


def setup_logger(level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Configure and return the root logger for Stream Cloner."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Stream handler (console)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # Optional file handler
        if log_file:
            try:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except OSError:
                pass

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Retrieve child or root logger."""
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)
