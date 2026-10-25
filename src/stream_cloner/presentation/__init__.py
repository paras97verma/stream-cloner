"""Presentation layer exports for Stream Cloner."""

from stream_cloner.presentation.api import BridgeAPI
from stream_cloner.presentation.web_window import launch_app, start_local_server

__all__ = [
    "BridgeAPI",
    "launch_app",
    "start_local_server",
]
