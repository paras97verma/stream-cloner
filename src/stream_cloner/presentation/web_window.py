"""Standalone desktop window launcher for Vue.js frontend powered by pywebview."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from stream_cloner.config import AppConfig
from stream_cloner.infrastructure.logging import get_logger
from stream_cloner.presentation.api import BridgeAPI

logger = get_logger("web_window")

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


def find_free_port() -> int:
    """Locate an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def resolve_web_dist_dir() -> Path:
    """Find the built Vue.js production dist directory."""
    # 1. Bundled inside PyInstaller _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        meipass_dist = Path(sys._MEIPASS) / "stream_cloner" / "web" / "dist"
        if meipass_dist.exists():
            return meipass_dist

    # 2. Inside src/stream_cloner/web/dist
    pkg_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if pkg_dist.exists() and (pkg_dist / "index.html").exists():
        return pkg_dist

    # 3. Inside frontend/dist
    root_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    if root_dist.exists() and (root_dist / "index.html").exists():
        return root_dist

    # Fallback to pkg_dist
    return pkg_dist


def start_local_server(dist_dir: Path, port: int, api: BridgeAPI):
    """Start lightweight local Bottle server to serve static assets and handle REST requests."""
    import json
    import bottle
    from bottle import HTTPResponse, static_file

    app = bottle.Bottle()

    @app.hook("after_request")
    def enable_cors():
        bottle.response.headers["Access-Control-Allow-Origin"] = "*"
        bottle.response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        bottle.response.headers["Access-Control-Allow-Headers"] = "Content-Type"

    @app.route("/<:re:.*>", method="OPTIONS")
    def options_handler():
        return {}

    # Static file serving
    @app.route("/")
    def serve_index():
        return static_file("index.html", root=str(dist_dir))

    @app.route("/assets/<filename:path>")
    def serve_assets(filename):
        return static_file(filename, root=str(dist_dir / "assets"))

    @app.route("/<filename:path>")
    def serve_files(filename):
        if (dist_dir / filename).exists():
            return static_file(filename, root=str(dist_dir))
        return static_file("index.html", root=str(dist_dir))

    # REST API endpoints mirroring BridgeAPI for dual-mode support
    @app.route("/api/state", method=["GET", "POST"])
    def api_state():
        return api.get_initial_state()

    @app.route("/api/theme", method="POST")
    def api_theme():
        data = bottle.request.json or {}
        return {"success": api.set_theme(data.get("theme", "system"))}

    @app.route("/api/parallel", method="POST")
    def api_parallel():
        data = bottle.request.json or {}
        return {"success": api.set_max_parallel(data.get("max_parallel", 2))}

    @app.route("/api/discover", method="POST")
    def api_discover():
        data = bottle.request.json or {}
        return api.discover_media(data.get("url", ""), data.get("fetch_playlist", False))

    @app.route("/api/download", method="POST")
    def api_download():
        data = bottle.request.json or {}
        return api.start_download(data)

    @app.route("/api/cancel", method="POST")
    def api_cancel():
        return {"success": api.cancel_download()}

    @app.route("/api/choose_directory", method="POST")
    def api_choose_dir():
        return api.choose_directory()

    @app.route("/api/open_folder", method="POST")
    def api_open_folder():
        data = bottle.request.json or {}
        return {"success": api.open_folder(data.get("path"))}

    @app.route("/api/open_url", method="POST")
    def api_open_url():
        data = bottle.request.json or {}
        return {"success": api.open_url(data.get("url", ""))}

    @app.route("/api/history", method=["GET", "POST"])
    def api_history():
        return {"items": api.get_history()}

    @app.route("/api/history/delete", method="POST")
    def api_delete_history():
        data = bottle.request.json or {}
        return {"items": api.delete_history_item(data.get("id", ""))}

    @app.route("/api/history/clear", method="POST")
    def api_clear_history():
        return {"success": api.clear_history()}

    server_thread = threading.Thread(
        target=lambda: bottle.run(app, host="127.0.0.1", port=port, quiet=True),
        daemon=True,
    )
    server_thread.start()
    return server_thread


def launch_app(
    config: Optional[AppConfig] = None,
    headless_browser: bool = False,
) -> int:
    """Launch the Stream Cloner standalone desktop application."""
    dist_dir = resolve_web_dist_dir()
    if not dist_dir.exists() or not (dist_dir / "index.html").exists():
        logger.error(f"Frontend dist not found at {dist_dir}. Please run 'npm run build' in frontend/ first.")
        print(f"\n[!] Frontend assets not built yet. Building frontend now...")
        frontend_dir = Path(__file__).resolve().parent.parent.parent.parent / "frontend"
        if frontend_dir.exists():
            import subprocess
            subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)
            dist_dir = resolve_web_dist_dir()

    api = BridgeAPI(config=config)
    port = find_free_port()
    start_local_server(dist_dir, port, api)

    app_url = f"http://127.0.0.1:{port}"
    logger.info(f"Stream Cloner web engine running at {app_url}")

    if headless_browser:
        webbrowser.open(app_url)
        print(f"Stream Cloner running in browser at {app_url}. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    try:
        import webview

        os_tag = "macOS" if IS_MACOS else ("Windows" if IS_WINDOWS else "Desktop")
        window = webview.create_window(
            title=f"Stream Cloner — {os_tag} YouTube 4K/8K/12K & Playlist Studio",
            url=app_url,
            js_api=api,
            width=960,
            height=820,
            min_size=(480, 600),
            background_color="#0B0F19",
            easy_drag=False,
        )
        api.set_window(window)
        webview.start(debug=False)
        return 0

    except Exception as exc:
        logger.warning(f"Native pywebview window failed ({exc}). Opening in standard web browser...")
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0
