#!/usr/bin/env python3
"""Build a manifest for assembling 山野路迹 deliverables in Ardot."""

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import struct


BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "output"
REFERENCES = BASE / "references"


def load_json(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt_duration(seconds):
    seconds = float(seconds or 0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h{minutes:02d}m"


def fmt_date(start_time):
    if not start_time:
        return ""
    try:
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        return dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y.%m.%d")
    except ValueError:
        return start_time[:10]


def rel(path):
    return str(path.relative_to(BASE))


def existing(path):
    return rel(path) if path.exists() else None


def first_existing(*paths):
    for path in paths:
        found = existing(path)
        if found:
            return found
    return None


def png_size(path):
    """Return (width, height) for a PNG without third-party dependencies."""
    if not path.exists():
        return None
    with path.open("rb") as f:
        header = f.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def asset_info(path):
    found = existing(path)
    if not found:
        return None
    size = png_size(path)
    item = {"path": found}
    if size:
        item["width"], item["height"] = size
    return item


def compact(items):
    return [item for item in items if item]


def latest_timestamp_models():
    stamp_path = OUTPUT / "magnet_3d_latest_timestamp.txt"
    if not stamp_path.exists():
        return []
    stamp = stamp_path.read_text(encoding="utf-8").strip()
    if not stamp:
        return []
    return [
        existing(OUTPUT / f"magnet_3d_hexagon_{stamp}.stl"),
        existing(OUTPUT / f"magnet_3d_hexagon_{stamp}.obj"),
    ]


def default_output_root(base):
    direct = base / "output"
    if direct.exists():
        return direct
    nested = base / "shanye-luji" / "output"
    if nested.exists():
        return nested
    return direct


def default_references_root(base):
    direct = base / "references"
    if direct.exists():
        return direct
    nested = base / "shanye-luji" / "references"
    if nested.exists():
        return nested
    return direct


def build_manifest():
    route = load_json(REFERENCES / "route_data.json")
    content = load_json(REFERENCES / "content_assets.json")
    route_name = content.get("route_name") or route.get("route_name") or "［路线名称］"
    distance = float(route.get("total_distance_km", 0) or 0)
    gain = int(round(float(route.get("elevation_gain", 0) or 0)))
    min_elev = int(round(float(route.get("min_elevation", 0) or 0)))
    max_elev = int(round(float(route.get("max_elevation", 0) or 0)))
    duration = fmt_duration(route.get("duration_seconds", 0))
    date = fmt_date(route.get("start_time", ""))

    assets = {
        "poster": existing(OUTPUT / "trail_poster.png"),
        "postcard": existing(OUTPUT / "trail_postcard.png"),
        "magnet_preview": first_existing(
            OUTPUT / "magnet_3d_ardot_preview.png",
            OUTPUT / "magnet_3d_preview.png",
            OUTPUT / "magnet_3d_relief_preview.png",
        ),
        "magnet_relief_preview": existing(OUTPUT / "magnet_3d_relief_preview.png"),
        "wechat_preview": first_existing(
            OUTPUT / "trail_wechat_ardot_preview.png",
            OUTPUT / "trail_wechat.png",
        ),
        "social_grid_preview": existing(OUTPUT / "social_grid_preview.png"),
        "social_cards": compact(
            [existing(OUTPUT / f"social_card_{i:02d}.png") for i in range(1, 10)]
        ),
    }
    model_files = [
        existing(OUTPUT / "magnet_3d_hexagon.stl"),
        existing(OUTPUT / "magnet_3d_hexagon.obj"),
        *latest_timestamp_models(),
    ]
    final_assets = {
        "poster": asset_info(OUTPUT / "trail_poster.png"),
        "postcard": asset_info(OUTPUT / "trail_postcard.png"),
        "wechat": asset_info(OUTPUT / "trail_wechat.png"),
        "magnet_preview": asset_info(OUTPUT / Path(assets["magnet_preview"]).name)
        if assets["magnet_preview"]
        else None,
        "social_cards": compact(
            [asset_info(OUTPUT / f"social_card_{i:02d}.png") for i in range(1, 10)]
        ),
    }

    editable_boards = compact(
        [
            {
                "key": "social_grid",
                "title": "小红书九宫格",
                "mode": "native_editable_rebuild",
                "layout": {"type": "grid", "columns": 3, "rows": 3, "gap": 0},
                "reference_cards": final_assets["social_cards"],
                "board": {"width": 3240, "height": 3240, "fill": "#FFFFFF"},
                "visible_explanatory_text": False,
                "editable_nodes_required": True,
                "allow_full_card_png_as_primary": False,
            }
            if final_assets["social_cards"]
            else None,
            {
                "key": "trail_poster",
                "title": "3D小报网页端",
                "mode": "hybrid_editable_with_reference",
                "reference_image": final_assets["poster"],
                "board": {
                    "width": (final_assets["poster"] or {}).get("width", 1400),
                    "height": (final_assets["poster"] or {}).get("height", 1000),
                    "fill": "#FFFFFF",
                },
                "visible_explanatory_text": False,
                "editable_nodes_required": ["title", "metrics", "photo_grid", "data_panel"],
            }
            if final_assets["poster"]
            else None,
            {
                "key": "trail_postcard",
                "title": "路线明信片",
                "mode": "native_editable_rebuild",
                "reference_image": final_assets["postcard"],
                "board": {
                    "width": (final_assets["postcard"] or {}).get("width", 1280),
                    "height": (final_assets["postcard"] or {}).get("height", 880),
                    "fill": "#FFFFFF",
                },
                "visible_explanatory_text": False,
                "editable_nodes_required": True,
            }
            if final_assets["postcard"]
            else None,
            {
                "key": "wechat_article",
                "title": "公众号长图",
                "mode": "native_editable_rebuild",
                "reference_image": final_assets["wechat"],
                "board": {
                    "width": (final_assets["wechat"] or {}).get("width", 1080),
                    "height": (final_assets["wechat"] or {}).get("height", 8500),
                    "fill": "#FFFFFF",
                },
                "visible_explanatory_text": False,
                "editable_nodes_required": True,
            }
            if final_assets["wechat"]
            else None,
            {
                "key": "magnet_preview",
                "title": "3D冰箱贴渲染预览",
                "mode": "hybrid_editable_with_reference",
                "reference_image": final_assets["magnet_preview"],
                "source_model": compact(
                    [
                        existing(OUTPUT / "magnet_3d_hexagon.stl"),
                        existing(OUTPUT / "magnet_3d_hexagon.obj"),
                    ]
                ),
                "board": {
                    "width": (final_assets["magnet_preview"] or {}).get("width", 1760),
                    "height": (final_assets["magnet_preview"] or {}).get("height", 1760),
                    "fill": "#FFFFFF",
                },
                "visible_explanatory_text": False,
                "editable_nodes_required": ["title", "specs", "model_file_names"],
            }
            if final_assets["magnet_preview"]
            else None,
        ]
    )

    flat_boards = [
        {
            "key": "trail_poster",
            "title": "01 3D 小报网页端",
            "image": assets["poster"],
            "source_html": existing(OUTPUT / "trail_poster.html"),
            "board": {"width": 1700, "height": 1280, "fill": "#F2EBDD"},
            "caption": "展示扩展地形采样、边缘封口过渡、照片节点和路线数据。",
            "image_fit": "contain",
        },
        {
            "key": "trail_postcard",
            "title": "02 路线明信片",
            "image": assets["postcard"],
            "source_html": existing(OUTPUT / "trail_postcard.html"),
            "board": {"width": 1600, "height": 1180, "fill": "#F6F1E7"},
            "caption": "保留照片气质，让路线轨迹以低干扰方式融入画面。",
            "image_fit": "contain",
        },
        {
            "key": "social_grid",
            "title": "03 小红书九宫格",
            "image": assets["social_grid_preview"],
            "images": assets["social_cards"],
            "source_html": existing(OUTPUT / "social_grid_preview.html"),
            "board": {"width": 1700, "height": 1900, "fill": "#F5EEE3"},
            "caption": "九张卡按专家导演表分工展示，避免同模板、同文案重复。",
            "layout": "3x3",
            "image_fit": "contain",
        },
        {
            "key": "wechat_article",
            "title": "04 公众号长图预览",
            "image": assets["wechat_preview"],
            "source_html": existing(OUTPUT / "trail_wechat.html"),
            "board": {"width": 1100, "height": 1900, "fill": "#EFE8DD"},
            "caption": "作品板只放长图预览；完整长图和 HTML 在文件清单中交付。",
            "image_fit": "fit-width",
        },
        {
            "key": "magnet_preview",
            "title": "05 3D 冰箱贴渲染预览",
            "image": assets["magnet_preview"],
            "source_model": compact(
                [
                    existing(OUTPUT / "magnet_3d_hexagon.stl"),
                    existing(OUTPUT / "magnet_3d_hexagon.obj"),
                ]
            ),
            "board": {"width": 1260, "height": 1450, "fill": "#F1E8DA"},
            "caption": "Ardot 展示渲染预览；STL/OBJ 作为文件交付，不能当作图片填充。",
            "image_fit": "contain",
        },
    ]
    flat_boards = [
        board for board in flat_boards if board.get("image") or board.get("images")
    ]

    return {
        "title": f"山野路迹 · {route_name}",
        "route_name": route_name,
        "date": date,
        "metrics": {
            "distance_km": round(distance, 2),
            "elevation_gain_m": gain,
            "min_elevation_m": min_elev,
            "max_elevation_m": max_elev,
            "duration": duration,
        },
        "summary_line": (
            f"{date} / {distance:.2f} KM / 爬升 {gain:,} M / "
            f"最高 {max_elev:,} M / {duration}"
        ),
        "elevation_note": (
            f"累计爬升按最高点减最低点计算：{max_elev}m - {min_elev}m = {gain}m。"
        ),
        "assets": assets,
        "model_files": [p for p in model_files if p],
        "ardot": {
            "default_mode": "native_editable_rebuild",
            "final_page_name": "山野路迹文创可编辑重建",
            "final_boards": editable_boards,
            "final_rules": {
                "visible_explanatory_text": False,
                "editable_nodes_required": True,
                "png_reference_only": True,
                "allow_full_card_png_as_primary": False,
                "notes": [
                    "Final Ardot page should contain editable deliverables only, without visible labels or explanations.",
                    "PNG outputs are references for visual QA and must not replace editable text/frame/SVG layers.",
                ],
            },
            "page_name": "山野路迹文创产物总览",
            "board_name": "山野路迹文创产物总览",
            "recommended_board": {"width": 1800, "height": 2600, "fill": "#EDE6DA"},
            "flat_page_name": "山野路迹文创平面成果",
            "flat_boards": flat_boards,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="",
        help="project root used for relative paths; defaults to the skill directory",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help="generated output directory; defaults to <project-root>/output",
    )
    parser.add_argument(
        "--references-root",
        default="",
        help="references directory; defaults to <project-root>/references",
    )
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    parser.add_argument(
        "--out",
        default="",
        help="manifest output path",
    )
    args = parser.parse_args()

    global BASE, OUTPUT, REFERENCES
    if args.project_root:
        BASE = Path(args.project_root).resolve()
    elif args.output_root:
        BASE = Path(args.output_root).resolve().parent
    if args.output_root:
        OUTPUT = Path(args.output_root).resolve()
    else:
        OUTPUT = default_output_root(BASE)
    if args.references_root:
        REFERENCES = Path(args.references_root).resolve()
    else:
        REFERENCES = default_references_root(BASE)

    manifest = build_manifest()
    out = Path(args.out) if args.out else OUTPUT / "ardot_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
