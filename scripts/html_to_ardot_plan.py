#!/usr/bin/env python3
"""Extract editable Ardot rebuild data from generated HTML deliverables.

This script intentionally does not call Ardot. It creates a deterministic plan
that an Ardot-capable agent can turn into native frames, text, vectors, and
image fills. PNG outputs are recorded as reference previews only.
"""

import argparse
import json
import re
import struct
from html import unescape
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = BASE / "output"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def first(pattern: str, text: str, default: str = "", flags: int = re.S) -> str:
    match = re.search(pattern, text, flags)
    return unescape(match.group(1)).strip() if match else default


def image_ref_to_abs(output_root: Path, ref: str) -> str:
    if not ref:
        return ""
    path = Path(ref)
    if path.is_absolute():
        return str(path)
    direct = output_root / path
    if direct.exists():
        return str(direct.resolve())
    # Some HTML stores a lowercase extension while copied source kept uppercase.
    if path.suffix:
        parent = output_root / path.parent
        if parent.exists():
            wanted = path.name.lower()
            for candidate in parent.iterdir():
                if candidate.name.lower() == wanted:
                    return str(candidate.resolve())
    return str(direct.resolve())


def png_size(path: Path):
    if not path.exists():
        return None
    with path.open("rb") as f:
        header = f.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def pixel_reference(output_root: Path, filename: str):
    path = output_root / filename
    if not path.exists():
        return None
    item = {"png": str(path.resolve())}
    size = png_size(path)
    if size:
        item["width"], item["height"] = size
    return item


def extract_data_tiles(html: str):
    tiles = []
    for label, value in re.findall(
        r'<div class="data-tile"><span>(.*?)</span><b>(.*?)</b></div>',
        html,
        flags=re.S,
    ):
        tiles.append({"label": clean_html(label), "value": clean_html(value)})
    return tiles


def extract_social_cards(output_root: Path):
    cards = []
    for i in range(1, 10):
        path = output_root / f"social_card_{i:02d}.html"
        html = read_text(path)
        if not html:
            continue
        body_class = first(r'<body class="([^"]+)"', html)
        photo = first(r'background-image:\s*url\(["\']?([^"\')]+)', html)
        svg = first(r'(<svg class="trail-svg"[\s\S]*?</svg>)', html)
        cards.append(
            {
                "key": f"social_card_{i:02d}",
                "title": f"小红书卡片 {i:02d}",
                "html": str(path.resolve()),
                "pixel_reference": pixel_reference(output_root, f"social_card_{i:02d}.png"),
                "canvas": {"width": 1080, "height": 1080},
                "body_class": body_class,
                "photo": image_ref_to_abs(output_root, photo),
                "route_meta": clean_html(first(r'<span class="route-meta">(.*?)</span>', html)),
                "place_meta": clean_html(first(r'<span class="place-meta">(.*?)</span>', html)),
                "page_num": clean_html(first(r'<span class="page-num">(.*?)</span>', html)),
                "headline": clean_html(first(r"<h1>(.*?)</h1>", html)),
                "subline": clean_html(first(r"<p>(.*?)</p>", html)),
                "caption": clean_html(first(r'<div class="caption-sticker">(.*?)</div>', html)),
                "stamp": clean_html(first(r'<div class="stamp">(.*?)</div>', html)),
                "data_tiles": extract_data_tiles(html),
                "trail_svg": svg,
                "editable": [
                    "background frame + image fill",
                    "route/place/page text",
                    "headline/subline text",
                    "caption and stamp text",
                    "data tiles",
                    "trail SVG as vector",
                    "team watermark text",
                ],
                "lossy_css": [
                    "CSS filters, blend modes, backdrop blur, and gradients are approximated.",
                    "Photo crop uses image fill; exact CSS object-position may need manual adjustment.",
                ],
            }
        )
    return cards


def extract_postcard(output_root: Path):
    path = output_root / "trail_postcard.html"
    html = read_text(path)
    if not html:
        return None
    photo = first(r"background:url\('([^']+)'\)", html)
    trail_data = first(r"const TRAIL_MAP=(\[[\s\S]*?\]);", html)
    profile_data = first(r"const PROFILE=(\[[\s\S]*?\]);", html)
    return {
        "key": "trail_postcard",
        "title": "路线明信片",
        "html": str(path.resolve()),
        "pixel_reference": pixel_reference(output_root, "trail_postcard.png"),
        "canvas": {"width": 1200, "height": 800},
        "photo": image_ref_to_abs(output_root, photo),
        "front_text": {
            "team": clean_html(first(r'<div class="org-name">[\s\S]*?</div>\s*(.*?)\s*</div>', html)),
            "date": clean_html(first(r'<div class="date-main">(.*?)</div>', html)),
            "place": clean_html(first(r'<div class="title-tag">(.*?)</div>', html)),
            "route": clean_html(first(r'<div class="title-main">(.*?)</div>', html)),
            "archive": clean_html(first(r'<div class="title-en">(.*?)</div>', html)),
        },
        "stats": [
            {"value": clean_html(v), "label": clean_html(l)}
            for v, l in re.findall(
                r'<span class="val">(.*?)</span><span class="lbl">(.*?)</span>',
                html,
                flags=re.S,
            )
        ],
        "route_data_js": trail_data,
        "profile_data_js": profile_data,
        "editable": [
            "front/back frames",
            "photo frame as image fill",
            "all visible text",
            "stats grid",
            "route and elevation redrawn from JS data as vector when needed",
        ],
        "non_native": ["canvas route/elevation need vector reconstruction from JS data"],
    }


def extract_wechat(output_root: Path):
    path = output_root / "trail_wechat.html"
    html = read_text(path)
    if not html:
        return None
    photos = []
    for img, cap in re.findall(
        r'<div class="photo-frame">\s*<img src="([^"]+)"[^>]*>\s*</div>\s*<p class="photo-caption">(.*?)</p>',
        html,
        flags=re.S,
    ):
        photos.append({"image": image_ref_to_abs(output_root, img), "caption": clean_html(cap)})
    stats = []
    for icon, value, label in re.findall(
        r'<div class="stat-card">\s*<div class="icon">(.*?)</div>\s*<div class="value">(.*?)</div>\s*<div class="label">(.*?)</div>',
        html,
        flags=re.S,
    ):
        stats.append({"icon": clean_html(icon), "value": clean_html(value), "label": clean_html(label)})
    return {
        "key": "wechat_article",
        "title": "公众号长图",
        "html": str(path.resolve()),
        "pixel_reference": pixel_reference(output_root, "trail_wechat.png"),
        "canvas": {"width": 1080, "height": 8500},
        "hero_image": image_ref_to_abs(output_root, first(r'<div class="hero">\s*<img src="([^"]+)"', html)),
        "hero_title": clean_html(first(r'<div class="hero-title">(.*?)</div>', html)),
        "hero_sub": clean_html(first(r'<div class="hero-sub">(.*?)</div>', html)),
        "hero_dossier": clean_html(first(r'<div class="hero-dossier">(.*?)</div>', html)),
        "intro_meta": clean_html(first(r'<p class="intro-meta">(.*?)</p>', html)),
        "intro_quote": clean_html(first(r'<p class="intro-quote">(.*?)</p>', html)),
        "story": [clean_html(p) for p in re.findall(r'<p class="story-p">(.*?)</p>', html, flags=re.S)],
        "stats": stats,
        "photos": photos,
        "elevation_svg": first(r'(<svg viewBox="0 0 960 220"[\s\S]*?</svg>)', html),
        "editable": [
            "hero image frame",
            "title/subtitle/dossier text",
            "intro and story text",
            "stats cards",
            "photo blocks",
            "elevation SVG as vector",
        ],
        "lossy_css": ["long article should be sectioned into editable frames to avoid one oversized node"],
    }


def extract_poster(output_root: Path):
    path = output_root / "trail_poster.html"
    html = read_text(path)
    if not html:
        return None
    return {
        "key": "trail_poster",
        "title": "3D 小报网页端",
        "html": str(path.resolve()),
        "pixel_reference": pixel_reference(output_root, "trail_poster.png"),
        "conversion_mode": "hybrid",
        "editable": [
            "right-side data panel text",
            "photo grid and captions",
            "elevation profile redrawn from source data when available",
        ],
        "reference_only": [
            "Three.js/WebGL terrain viewport cannot become native Ardot 3D geometry from HTML",
            "use screenshot or model preview as locked visual reference",
        ],
    }


def build_plan(output_root: Path):
    products = []
    for item in (
        extract_postcard(output_root),
        extract_wechat(output_root),
        extract_poster(output_root),
    ):
        if item:
            products.append(item)
    social_cards = extract_social_cards(output_root)
    if social_cards:
        products.append(
            {
                "key": "social_grid",
                "title": "小红书九宫格",
                "html": str((output_root / "social_grid_preview.html").resolve()),
                "cards": social_cards,
                "editable_layout": {
                    "mode": "native_editable_rebuild",
                    "visible_explanatory_text": False,
                    "columns": 3,
                    "rows": 3,
                    "gap": 0,
                    "card_width": 1080,
                    "card_height": 1080,
                    "board_width": 3240,
                    "board_height": 3240,
                },
                "conversion_mode": "native-editable",
            }
        )
    return {
        "schema": "shanye-luji.ardot-editable-plan.v1",
        "source_output": str(output_root.resolve()),
        "principle": (
            "Use native_editable_rebuild as the default Ardot delivery. Rebuild flat "
            "products with text/frame/image-fill/SVG nodes. PNG screenshots are "
            "reference previews only and must not replace editable layers."
        ),
        "final_delivery": {
            "mode": "native_editable_rebuild",
            "visible_explanatory_text": False,
            "editable_nodes_required": True,
            "png_reference_only": True,
            "allow_full_card_png_as_primary": False,
        },
        "reference_delivery": {
            "mode": "pixel_reference_preview",
            "lossy_by_default": False,
            "not_primary_delivery": True,
        },
        "conversion_rules": {
            "text": "create Ardot text nodes",
            "image": "create frame/rectangle and apply image fill",
            "svg": "insert as SVG frame/vector when supported",
            "div_background": "create colored frame; approximate gradients and blur",
            "canvas": "redraw from embedded JS/source data where possible; otherwise mark as reference-only",
            "webgl_or_3d": "not natively editable in Ardot; keep preview/model file plus editable metadata layer",
        },
        "products": products,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT), help="generated output directory")
    parser.add_argument("--out", default="", help="plan output path")
    parser.add_argument("--json", action="store_true", help="print plan to stdout")
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    plan = build_plan(output_root)
    out = Path(args.out).resolve() if args.out else output_root / "ardot_editable_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
