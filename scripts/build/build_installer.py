#!/usr/bin/env python3
"""
Stream Cloner - Standalone Installer Builder (.dmg for macOS, .exe for Windows)
Usage:
    python3 scripts/build/build_installer.py

Features:
1. Generates an Apple-inspired glassmorphic app icon (assets/icon.icns / assets/icon.ico) using Pillow.
2. Locates standalone ffmpeg and deno binaries to bundle inside the installer.
3. Runs PyInstaller to compile app.py into:
   - macOS: dist/Stream Cloner.app + dist/Stream-Cloner-macOS.dmg
   - Windows: dist/Stream-Cloner-Windows.exe
   - Linux: dist/Stream-Cloner-Linux
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure UTF-8 output encoding for Windows CLI / CI runners
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform.startswith("win")
# Project root is two levels up from scripts/build/
ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
ASSETS_DIR = ROOT_DIR / "assets"
DIST_DIR = ROOT_DIR / "dist"
BUILD_WORK_DIR = ROOT_DIR / "build"


def generate_app_icons() -> Path:
    """
    Generate an Apple-inspired glassmorphic app icon in pure Python using Pillow.
    Returns path to .icns (macOS), .ico (Windows), or .png.
    """
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Gradient squircle
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = 24
    rect = [margin, margin, size - margin, size - margin]
    mask_draw.rounded_rectangle(rect, radius=116, fill=255)

    # Gradient from blue (37, 99, 235) to purple (124, 58, 237)
    grad = Image.new("RGBA", (size, size))
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2.0 * size)
            r = int(37 * (1 - t) + 124 * t)
            g = int(99 * (1 - t) + 58 * t)
            b = int(235 * (1 - t) + 237 * t)
            grad.putpixel((x, y), (r, g, b, 255))

    img.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    # Subtle inner highlight border
    draw.rounded_rectangle(rect, radius=116, outline=(255, 255, 255, 70), width=4)

    # 1. Source Stream Screen (Top Left)
    s_rect = [80, 80, 320, 260]
    draw.rounded_rectangle(s_rect, radius=36, fill=(255, 255, 255, 45), outline=(255, 255, 255, 180), width=4)
    # Media Play Glyph
    play_pts = [(175, 135), (175, 205), (245, 170)]
    draw.polygon(play_pts, fill=(255, 255, 255, 240))

    # 2. Cloned Output Screen (Bottom Right - Overlapping)
    c_rect = [180, 180, 440, 440]
    draw.rounded_rectangle(c_rect, radius=48, fill=(11, 15, 25, 235), outline=(96, 165, 250, 255), width=6)

    # Download Arrow in Cloned Screen
    cx, cy = 310, 290
    draw.rectangle([cx - 12, cy - 50, cx + 12, cy + 15], fill=(56, 189, 248, 255))
    head_pts = [(cx - 45, cy + 10), (cx + 45, cy + 10), (cx, cy + 55)]
    draw.polygon(head_pts, fill=(56, 189, 248, 255))
    draw.rounded_rectangle([cx - 55, cy + 80, cx + 55, cy + 96], radius=8, fill=(167, 139, 250, 255))

    png_path = ASSETS_DIR / "icon.png"
    img.save(png_path, format="PNG")

    if IS_WINDOWS:
        ico_path = ASSETS_DIR / "icon.ico"
        img.save(
            ico_path,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
        return ico_path

    if IS_MACOS:
        icns_path = ASSETS_DIR / "icon.icns"
        try:
            img.save(icns_path, format="ICNS")
            if icns_path.exists():
                return icns_path
        except Exception:
            pass

        # Fallback using iconutil
        iconset_dir = ASSETS_DIR / "StreamCloner.iconset"
        iconset_dir.mkdir(parents=True, exist_ok=True)
        for sz in (16, 32, 128, 256, 512):
            resized = img.resize((sz, sz), Image.Resampling.LANCZOS)
            resized.save(iconset_dir / f"icon_{sz}x{sz}.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)], check=False)
        if icns_path.exists():
            return icns_path

    return png_path


def find_external_binary(name: str) -> str | None:
    """Locate ffmpeg or deno in virtualenv, PATH, or standard paths."""
    exe_name = f"{name}.exe" if IS_WINDOWS else name
    venv_dir = Path(sys.executable).resolve().parent
    candidate = venv_dir / exe_name
    if candidate.is_file():
        return str(candidate)

    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
            if ff and os.path.isfile(ff):
                return ff
        except Exception:
            pass

    found = shutil.which(name)
    if found:
        return found

    if IS_MACOS:
        for p in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", os.path.expanduser(f"~/.deno/bin/{name}")):
            if os.path.isfile(p):
                return p
    return None


def build_macos_dmg(app_bundle_path: Path, dmg_output_path: Path) -> None:
    """Package Stream Cloner.app into a distributable .dmg disk image with an Applications symlink."""
    print(f"[*] Packaging {app_bundle_path.name} into {dmg_output_path.name} ...")
    if dmg_output_path.exists():
        dmg_output_path.unlink()

    # Ad-hoc codesign the .app bundle
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    with tempfile.TemporaryDirectory(prefix="stream_cloner_dmg_") as staging_str:
        staging_dir = Path(staging_str)
        staged_app = staging_dir / app_bundle_path.name
        shutil.copytree(app_bundle_path, staged_app, symlinks=True)

        apps_link = staging_dir / "Applications"
        os.symlink("/Applications", apps_link)

        cmd = [
            "hdiutil",
            "create",
            "-volname",
            "Stream Cloner Installer",
            "-srcfolder",
            str(staging_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_output_path),
        ]
        subprocess.run(cmd, check=True)

    print(f"[OK] Created macOS DMG installer: {dmg_output_path}")


def main() -> None:
    print("=================================================================")
    print("  Stream Cloner - Standalone Installer Builder (.dmg / .exe)")
    print("=================================================================")

    icon_path = generate_app_icons()
    print(f"[OK] Generated application icon: {icon_path}")

    sep = ";" if IS_WINDOWS else ":"
    add_binaries: list[str] = []

    # Bundle FFmpeg
    ffmpeg_bin = find_external_binary("ffmpeg")
    if ffmpeg_bin:
        target_name = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
        BUILD_WORK_DIR.mkdir(parents=True, exist_ok=True)
        staged_ff = BUILD_WORK_DIR / target_name
        shutil.copy2(ffmpeg_bin, staged_ff)
        add_binaries.extend(["--add-binary", f"{staged_ff}{sep}."])
        print(f"[OK] Bundling FFmpeg binary: {ffmpeg_bin}")
    else:
        print("[!] Warning: Standalone FFmpeg binary not found to bundle.")

    # Bundle Deno
    deno_bin = find_external_binary("deno")
    if deno_bin:
        target_deno = "deno.exe" if IS_WINDOWS else "deno"
        BUILD_WORK_DIR.mkdir(parents=True, exist_ok=True)
        staged_deno = BUILD_WORK_DIR / target_deno
        shutil.copy2(deno_bin, staged_deno)
        add_binaries.extend(["--add-binary", f"{staged_deno}{sep}."])
        print(f"[OK] Bundling Deno runtime: {deno_bin}")
    else:
        print("[!] Warning: Standalone Deno runtime not found to bundle.")

    # Ensure frontend is built
    web_dist = SRC_DIR / "stream_cloner" / "web" / "dist"
    if not (web_dist / "index.html").exists():
        print("[*] Compiling frontend assets before packaging...")
        npm_bin = shutil.which("npm") or ("npm.cmd" if IS_WINDOWS else "npm")
        subprocess.run([npm_bin, "run", "build"], cwd=str(ROOT_DIR / "frontend"), check=True, shell=IS_WINDOWS)

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--paths",
        str(SRC_DIR),
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "certifi",
        "--collect-all",
        "darkdetect",
        "--collect-all",
        "stream_cloner",
        "--collect-all",
        "webview",
        "--collect-all",
        "bottle",
        "--add-data",
        f"{web_dist}{sep}stream_cloner/web/dist",
        "--hidden-import",
        "requests",
        "--hidden-import",
        "PIL",
    ]

    try:
        import yt_dlp_ejs  # noqa: F401
        pyinstaller_cmd.extend(["--collect-all", "yt_dlp_ejs"])
    except ImportError:
        pass

    try:
        import pythonnet  # noqa: F401
        pyinstaller_cmd.extend([
            "--collect-all", "pythonnet",
            "--collect-all", "clr_loader",
            "--hidden-import", "clr",
            "--hidden-import", "clr_loader",
            "--hidden-import", "pythonnet",
        ])
    except ImportError:
        pass

    if icon_path.exists():
        pyinstaller_cmd.extend(["--icon", str(icon_path)])

    pyinstaller_cmd.extend(add_binaries)

    if IS_MACOS:
        pyinstaller_cmd.extend([
            "--name",
            "Stream Cloner",
            "--osx-bundle-identifier",
            "com.streamcloner.app",
            str(ROOT_DIR / "app.py"),
        ])
        print("[*] Running PyInstaller to build macOS .app bundle...")
        subprocess.run(pyinstaller_cmd, check=True)

        app_bundle = DIST_DIR / "Stream Cloner.app"
        dmg_path = DIST_DIR / "Stream-Cloner-macOS.dmg"
        if app_bundle.exists():
            build_macos_dmg(app_bundle, dmg_path)
            version_str = os.environ.get("STREAM_CLONER_VERSION")
            if not version_str:
                try:
                    sys.path.insert(0, str(SRC_DIR))
                    import stream_cloner
                    version_str = getattr(stream_cloner, "__version__", None)
                except Exception:
                    pass
            if version_str:
                ver_dmg = DIST_DIR / f"Stream-Cloner-v{version_str}-macOS.dmg"
                shutil.copy2(dmg_path, ver_dmg)
                print(f"  SUCCESS! Versioned DMG    : {ver_dmg}")
            print("=================================================================")
            print(f"  SUCCESS! macOS App Bundle : {app_bundle}")
            print(f"  SUCCESS! macOS DMG File   : {dmg_path}")
            print("=================================================================")
        else:
            raise RuntimeError("Expected Stream Cloner.app was not created in dist/.")

    elif IS_WINDOWS:
        pyinstaller_cmd.extend([
            "--onefile",
            "--name",
            "Stream-Cloner-Windows",
            str(ROOT_DIR / "app.py"),
        ])
        print("[*] Running PyInstaller to build standalone Windows .exe ...")
        subprocess.run(pyinstaller_cmd, check=True)

        exe_path = DIST_DIR / "Stream-Cloner-Windows.exe"
        version_str = os.environ.get("STREAM_CLONER_VERSION")
        if not version_str:
            try:
                sys.path.insert(0, str(SRC_DIR))
                import stream_cloner
                version_str = getattr(stream_cloner, "__version__", None)
            except Exception:
                pass
        if version_str:
            ver_exe = DIST_DIR / f"Stream-Cloner-v{version_str}-Windows.exe"
            shutil.copy2(exe_path, ver_exe)
            print(f"  SUCCESS! Versioned EXE    : {ver_exe}")
        print("=================================================================")
        print(f"  SUCCESS! Standalone Windows EXE: {exe_path}")
        print("=================================================================")

    else:
        pyinstaller_cmd.extend([
            "--onefile",
            "--name",
            "Stream-Cloner-Linux",
            str(ROOT_DIR / "app.py"),
        ])
        subprocess.run(pyinstaller_cmd, check=True)
        print(f"[OK] Built standalone binary in {DIST_DIR}")



if __name__ == "__main__":
    main()
