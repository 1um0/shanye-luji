#!/usr/bin/env python3
"""Check runtime dependencies for the 山野路迹 skill."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from platform_utils import CSS_FONT_STACK, find_chinese_font, find_chrome


MODULE_GROUPS = {
    "image": [
        ("PIL", "Pillow"),
        ("pillow_heif", "pillow-heif"),
    ],
    "magnet": [
        ("numpy", "numpy"),
        ("trimesh", "trimesh"),
        ("shapely", "shapely"),
        ("matplotlib", "matplotlib"),
        ("mapbox_earcut", "mapbox-earcut"),
    ],
}


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def collect(groups: list[str]) -> dict:
    selected = []
    for group in groups:
        selected.extend(MODULE_GROUPS[group])
    missing = [(module, package) for module, package in selected if not module_exists(module)]
    chrome = find_chrome()
    font = find_chinese_font()
    return {
        "python": sys.executable,
        "base": str(BASE),
        "groups": groups,
        "missing_modules": [{"module": m, "package": p} for m, p in missing],
        "chrome": str(chrome) if chrome else None,
        "chinese_font": str(font) if font else None,
        "css_font_stack": CSS_FONT_STACK,
        "requirements": str(BASE / "requirements.txt"),
    }


def print_report(report: dict) -> None:
    print("山野路迹运行环境检查")
    print(f"  Python: {report['python']}")
    if report["missing_modules"]:
        packages = " ".join(item["package"] for item in report["missing_modules"])
        print("  缺少 Python 包:")
        for item in report["missing_modules"]:
            print(f"    - {item['package']} (import {item['module']})")
        print()
        print("  推荐安装:")
        print(f"    \"{report['python']}\" -m pip install -r \"{report['requirements']}\"")
        print(f"  或只装缺失包:")
        print(f"    \"{report['python']}\" -m pip install {packages}")
    else:
        print("  Python 包: OK")

    print(f"  Chrome: {report['chrome'] or '未找到'}")
    print(f"  中文字体: {report['chinese_font'] or '未找到实体字体文件，将使用系统字体族回退'}")
    print(f"  CSS 字体栈: {report['css_font_stack']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--groups",
        default="image,magnet",
        help="comma-separated dependency groups: image,magnet",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="exit 1 when modules are missing")
    args = parser.parse_args()

    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    unknown = [g for g in groups if g not in MODULE_GROUPS]
    if unknown:
        raise SystemExit(f"Unknown dependency group(s): {', '.join(unknown)}")

    report = collect(groups)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    if args.strict and report["missing_modules"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

