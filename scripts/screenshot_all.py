#!/usr/bin/env python3
"""Capture all generated HTML outputs with Chrome, cross-platform."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from platform_utils import find_chrome

OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE / "output"))


CAPTURES = [
    ("trail_postcard.html", "trail_postcard.png", "1280,880", 3000, "明信片"),
    ("trail_wechat.html", "trail_wechat.png", "1080,8500", 5000, "公众号"),
    *[
        (f"social_card_{i:02d}.html", f"social_card_{i:02d}.png", "1080,1080", 2000, f"社交组图 {i:02d}")
        for i in range(1, 10)
    ],
    ("trail_poster.html", "trail_poster.png", "1400,1000", 12000, "3D小报"),
]


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def capture(chrome: Path, html_name: str, png_name: str, window_size: str, budget: int, timeout: int = 180) -> bool:
    html = OUTPUT / html_name
    if not html.exists():
        print(f"  - skip {html_name}: HTML 不存在")
        return False
    png = OUTPUT / png_name
    cmd = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--disable-gpu-sandbox",
        "--hide-scrollbars",
        "--use-gl=angle",
        "--use-angle=swiftshader",
        f"--window-size={window_size}",
        f"--screenshot={png}",
        f"--virtual-time-budget={budget}",
        file_url(html),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    size = png.stat().st_size / 1024 if png.exists() else 0
    print(f"  ✓ {png_name}: {size:.0f} KB")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", help="Chrome executable path")
    args = parser.parse_args()

    chrome = Path(args.chrome) if args.chrome else find_chrome()
    if not chrome or not chrome.exists():
        raise SystemExit(
            "未找到 Chrome。可安装 Google Chrome，或传入 --chrome \"C:/Program Files/Google/Chrome/Application/chrome.exe\""
        )

    print(f"=== 截图开始: {chrome} ===")
    for html_name, png_name, window_size, budget, _label in CAPTURES:
        capture(chrome, html_name, png_name, window_size, budget)
    print("=== 截图完成 ===")


if __name__ == "__main__":
    main()
