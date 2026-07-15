#!/usr/bin/env python3
"""Cross-platform helpers for 山野路迹 scripts."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent


CHINESE_FONT_FAMILIES = [
    "Microsoft YaHei",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "Source Han Sans SC",
    "Hiragino Sans GB",
    "SimHei",
    "Arial Unicode MS",
    "sans-serif",
]


CSS_FONT_STACK = ", ".join(f'"{name}"' if " " in name else name for name in CHINESE_FONT_FAMILIES)


def candidate_chrome_paths() -> list[Path]:
    """Return common Chrome/Chromium executable paths for macOS, Windows and Linux."""
    paths: list[Path] = []
    for env_name in ("CHROME", "CHROME_PATH", "GOOGLE_CHROME_SHIM"):
        value = os.environ.get(env_name)
        if value:
            paths.append(Path(value))

    system = platform.system().lower()
    if system == "windows":
        for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(env_name)
            if root:
                paths.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
        paths.append(Path("C:/Program Files/Google/Chrome/Application/chrome.exe"))
        paths.append(Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"))
    elif system == "darwin":
        paths.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
        paths.append(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
            found = shutil.which(name)
            if found:
                paths.append(Path(found))

    return paths


def find_chrome() -> Path | None:
    for path in candidate_chrome_paths():
        if path.exists():
            return path
    return None


def candidate_chinese_font_paths() -> list[Path]:
    """Return common CJK font files. Prefer Microsoft YaHei on Windows."""
    paths: list[Path] = []
    windir = os.environ.get("WINDIR", "C:/Windows")
    paths.extend(
        [
            Path(windir) / "Fonts" / "msyh.ttc",
            Path(windir) / "Fonts" / "msyh.ttf",
            Path(windir) / "Fonts" / "msyhbd.ttc",
            Path(windir) / "Fonts" / "simhei.ttf",
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            Path("/System/Library/Fonts/STHeiti Light.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        ]
    )
    extra = os.environ.get("SHANYE_CHINESE_FONT")
    if extra:
        paths.insert(0, Path(extra))
    return paths


def find_chinese_font() -> Path | None:
    for path in candidate_chinese_font_paths():
        if path.exists():
            return path
    return None


def preferred_chinese_font_family() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "Microsoft YaHei"
    if system == "darwin":
        return "PingFang SC"
    return "Noto Sans CJK SC"

