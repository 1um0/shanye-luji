#!/usr/bin/env python3
"""Run the full 山野路迹 generation pipeline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
REFERENCES = Path(os.environ.get("SHANYE_REFERENCES_ROOT", BASE / "references")).resolve()
OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE / "output")).resolve()
sys.path.insert(0, str(BASE / "scripts"))

from platform_utils import find_chrome


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("\n$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=BASE, check=True, env=env)


def python_cmd(preferred: str | None = None) -> str:
    if preferred and Path(preferred).expanduser().exists():
        return str(Path(preferred).expanduser())
    return sys.executable or "python3"


def existing_python(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser())
    return None


def bundled_python_candidates() -> list[str]:
    """Return common local virtualenv Python paths on Windows, macOS and Linux."""
    return [
        str(BASE / ".venv" / "Scripts" / "python.exe"),
        str(BASE / ".venv" / "bin" / "python"),
        str(BASE / "venv" / "Scripts" / "python.exe"),
        str(BASE / "venv" / "bin" / "python"),
        str(Path.home() / ".venvs" / "shanye-luji" / "Scripts" / "python.exe"),
        str(Path.home() / ".venvs" / "shanye-luji" / "bin" / "python"),
        "/tmp/shanluji-venv/bin/python",
        "/tmp/magnet3d-venv/bin/python",
    ]


def magnet_python_candidates() -> list[str]:
    return [
        str(BASE / ".venv" / "Scripts" / "python.exe"),
        str(BASE / ".venv" / "bin" / "python"),
        str(BASE / "venv" / "Scripts" / "python.exe"),
        str(BASE / "venv" / "bin" / "python"),
        str(Path.home() / ".venvs" / "shanye-luji" / "Scripts" / "python.exe"),
        str(Path.home() / ".venvs" / "shanye-luji" / "bin" / "python"),
        "/tmp/magnet3d-venv/bin/python",
    ]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(BASE))
    except ValueError:
        return str(path)


def ensure_route_data(gpx_path: str | None, py: str) -> None:
    route_path = REFERENCES / "route_data.json"
    if not gpx_path:
        if route_path.exists():
            print(f"Using existing {display_path(route_path)}")
            return
        raise SystemExit("Missing GPX path and references/route_data.json does not exist")

    result = subprocess.run(
        [py, "scripts/gpx_parser.py", gpx_path, "--json"],
        cwd=BASE,
        check=True,
        capture_output=True,
        text=True,
    )
    write_json(route_path, json.loads(result.stdout))
    print(f"Wrote {display_path(route_path)}")


def ensure_photo_data(image_dir: str | None, py: str) -> None:
    photos_path = REFERENCES / "photos_data.json"
    if not image_dir:
        if photos_path.exists():
            print(f"Using existing {display_path(photos_path)}")
            return
        raise SystemExit("Missing image directory and references/photos_data.json does not exist")

    result = subprocess.run(
        [py, "scripts/photo_reader.py", image_dir, "--json"],
        cwd=BASE,
        check=True,
        capture_output=True,
        text=True,
    )
    write_json(photos_path, json.loads(result.stdout))
    print(f"Wrote {display_path(photos_path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references-root", help="case-specific references directory")
    parser.add_argument("--output-root", help="case-specific output directory")
    parser.add_argument("--gpx", help="source GPX file; omit to reuse references/route_data.json")
    parser.add_argument("--images", help="source image directory; omit to reuse references/photos_data.json and output/photos")
    parser.add_argument("--expert-pack-root", help="optional local TT expert pack root")
    parser.add_argument("--route-name", help="route name printed on keepsakes")
    parser.add_argument("--route-subtitle", help="optional route subtitle")
    parser.add_argument("--place-name", help="place or activity name")
    parser.add_argument("--team-name", help="team or organization name")
    parser.add_argument("--slogan", help="optional slogan")
    parser.add_argument("--mood", help="comma-separated mood keywords")
    parser.add_argument("--xhs-style", help="Xiaohongshu copy style")
    parser.add_argument("--hashtags", help="comma-separated hashtags")
    parser.add_argument("--forbidden", help="comma-separated photo/person/content restrictions")
    parser.add_argument("--hike-story", help="user-confirmed hike story")
    parser.add_argument("--post-hike-review", help="user-confirmed personal/team reflection")
    parser.add_argument("--shape", default="hexagon", choices=["hexagon", "circle"], help="magnet shape")
    parser.add_argument("--skip-magnet", action="store_true", help="skip STL/OBJ generation")
    parser.add_argument("--skip-screenshots", action="store_true", help="skip Chrome screenshot export")
    parser.add_argument("--keep-old-output", action="store_true", help="do not delete regenerable output files first")
    parser.add_argument("--python", help="Python executable for normal scripts")
    parser.add_argument("--image-python", help="Python executable with Pillow/pillow-heif")
    parser.add_argument("--magnet-python", help="Python executable with trimesh/numpy/shapely/matplotlib")
    parser.add_argument("--chrome", help="Chrome executable path for screenshots")
    parser.add_argument("--skip-env-check", action="store_true", help="do not check Python dependency groups first")
    args = parser.parse_args()

    global REFERENCES, OUTPUT
    if args.references_root:
        REFERENCES = Path(args.references_root).expanduser().resolve()
    if args.output_root:
        OUTPUT = Path(args.output_root).expanduser().resolve()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    REFERENCES.mkdir(parents=True, exist_ok=True)
    pipeline_env = os.environ.copy()
    pipeline_env["SHANYE_REFERENCES_ROOT"] = str(REFERENCES)
    pipeline_env["SHANYE_OUTPUT_ROOT"] = str(OUTPUT)
    normal_py = python_cmd(args.python)
    image_py = python_cmd(args.image_python or existing_python(bundled_python_candidates()))
    magnet_py = python_cmd(args.magnet_python or existing_python(magnet_python_candidates()))

    if not args.skip_env_check:
        run([image_py, "scripts/check_environment.py", "--groups", "image", "--strict"], env=pipeline_env)
        if not args.skip_magnet:
            run([magnet_py, "scripts/check_environment.py", "--groups", "magnet", "--strict"], env=pipeline_env)

    if not args.keep_old_output:
        patterns = [
            "trail_poster.html",
            "trail_poster.png",
            "trail_postcard.html",
            "trail_postcard.png",
            "trail_wechat.html",
            "trail_wechat.png",
            "social_card_*.html",
            "social_card_*.png",
            "social_grid_preview.html",
            "social_grid_preview.png",
            "magnet_3d_preview.png",
            "magnet_3d_ardot_preview.png",
            "magnet_3d_relief_preview.png",
            "design_constraints.json",
            "expert_constraints_trace.json",
            "ardot_editable_plan.json",
            "ardot_manifest.json",
        ]
        if not args.skip_magnet:
            patterns.extend(["magnet_3d_*.stl", "magnet_3d_*.obj", "magnet_3d_latest_timestamp.txt"])
        for pattern in patterns:
            for path in OUTPUT.glob(pattern):
                if path.is_file():
                    path.unlink()

    ensure_route_data(args.gpx, normal_py)
    ensure_photo_data(args.images, image_py)
    content_cmd = [normal_py, "scripts/prepare_content_assets.py"]
    for attr, flag in [
        ("route_name", "--route-name"),
        ("route_subtitle", "--route-subtitle"),
        ("place_name", "--place-name"),
        ("team_name", "--team-name"),
        ("slogan", "--slogan"),
        ("mood", "--mood"),
        ("xhs_style", "--xhs-style"),
        ("hashtags", "--hashtags"),
        ("forbidden", "--forbidden"),
        ("hike_story", "--hike-story"),
        ("post_hike_review", "--post-hike-review"),
    ]:
        value = getattr(args, attr)
        if value is not None:
            content_cmd.extend([flag, value])
    run(content_cmd, env=pipeline_env)

    if args.images:
        run([image_py, "scripts/convert_photos.py"], env=pipeline_env)
    elif not any((OUTPUT / "photos").glob("*")):
        raise SystemExit("output/photos is empty; pass --images so photos can be converted/copied")

    if args.expert_pack_root:
        pipeline_env["SHANYE_EXPERT_PACK_ROOT"] = args.expert_pack_root
    run([normal_py, "scripts/photo_matcher.py"], env=pipeline_env)
    run([normal_py, "scripts/generate_design_constraints_from_experts.py"], env=pipeline_env)
    run([normal_py, "scripts/validate_design_constraints.py"], env=pipeline_env)
    run([normal_py, "scripts/build_photo_markers.py"], env=pipeline_env)
    run([normal_py, "scripts/build_trail_poster.py"], env=pipeline_env)
    run([normal_py, "scripts/build_postcard.py"], env=pipeline_env)
    run([normal_py, "scripts/build_social_grid.py"], env=pipeline_env)
    run([normal_py, "scripts/build_wechat_article.py"], env=pipeline_env)

    if not args.skip_magnet:
        run([magnet_py, "scripts/build_magnet_3d.py", "--shape", args.shape], env=pipeline_env)
        run([normal_py, "scripts/validate_magnet_outputs.py", "--shape", args.shape], env=pipeline_env)
        run([magnet_py, "scripts/render_magnet_preview.py"], env=pipeline_env)

    if not args.skip_screenshots:
        chrome = Path(args.chrome) if args.chrome else find_chrome()
        if chrome and chrome.exists():
            run([normal_py, "scripts/screenshot_all.py", "--chrome", str(chrome)], env=pipeline_env)
        else:
            print("Skipped screenshots: Google Chrome not found. Pass --chrome to specify chrome.exe")

    run([normal_py, "scripts/html_to_ardot_plan.py", "--output-root", str(OUTPUT), "--json"], env=pipeline_env)
    run(
        [
            normal_py,
            "scripts/ardot_manifest.py",
            "--output-root",
            str(OUTPUT),
            "--references-root",
            str(REFERENCES),
            "--json",
        ],
        env=pipeline_env,
    )
    shutil.rmtree(BASE / "scripts" / "__pycache__", ignore_errors=True)
    print("\nGeneration complete. See output/ and output/ardot_manifest.json")


if __name__ == "__main__":
    main()
