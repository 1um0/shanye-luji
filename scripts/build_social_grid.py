#!/usr/bin/env python3
"""
山野路迹 — 小红书社交组图构建器
基于小红书专家输出的九宫格导演表，为每张图生成不同卡型。

核心能力：
  1. 轨迹图用真实 GPS lat/lon 投影，不再变形
  2. 每张卡片在轨迹图上高亮照片拍摄位置（橙色脉冲圆点）
  3. 从 social_grid.script_hooks.card_plan 读取 archetype/headline/sticker
  4. 封面、路线小票、狼狈现场、山脊大片、最高点、收尾复盘使用不同骨架

用法:
    python build_social_grid.py
"""

import json
import math
import os
import sys
import shutil
from datetime import datetime, timedelta, timezone
from html import escape

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from design_constraints import get_in, list_from_constraints, load_design_constraints, product_constraints
from platform_utils import CSS_FONT_STACK
from render_engine import get_tokens

OUTPUT = os.environ.get("SHANYE_OUTPUT_ROOT", os.path.join(BASE, "output"))
PHOTOS_DIR = os.path.join(OUTPUT, "photos")
os.makedirs(OUTPUT, exist_ok=True)

tokens = get_tokens()
constraints = load_design_constraints(BASE)
social_constraints = product_constraints(constraints, "social_grid")
source_constraints = constraints.get("source", {})

PHOTO_PICKS = []
CAPTIONS = {}

photo_picks_constraint = get_in(social_constraints, ["script_hooks", "photo_picks"], [])
caption_map_constraint = get_in(social_constraints, ["script_hooks", "caption_map"], {})
if not caption_map_constraint:
    caption_map_constraint = {
        item.get("photo"): item.get("caption")
        for item in get_in(social_constraints, ["copy_strategy", "cards"], [])
        if item.get("photo") and item.get("caption")
    }

card_plan_constraint = get_in(social_constraints, ["script_hooks", "card_plan"], [])
if not card_plan_constraint:
    card_plan_constraint = get_in(social_constraints, ["composition", "xhs_grid_plan", "cards"], [])

if card_plan_constraint:
    PHOTO_PICKS = [item["photo"] for item in card_plan_constraint if item.get("photo")]
else:
    PHOTO_PICKS = list_from_constraints(photo_picks_constraint, PHOTO_PICKS)
CAPTIONS = {**CAPTIONS, **caption_map_constraint}
for item in card_plan_constraint:
    if item.get("photo") and item.get("caption"):
        CAPTIONS[item["photo"]] = item["caption"]

DEFAULT_ARCHETYPES = [
    "cover_burst",
    "route_ticket",
    "climb_note",
    "grit_snapshot",
    "grit_snapshot",
    "lookback_split",
    "ridge_frame",
    "summit_proof",
    "finish_receipt",
]

if not card_plan_constraint:
    card_plan_constraint = [
        {
            "photo": photo,
            "caption": CAPTIONS.get(photo, "山野路迹"),
            "archetype": DEFAULT_ARCHETYPES[idx % len(DEFAULT_ARCHETYPES)],
            "headline": CAPTIONS.get(photo, "山野路迹"),
            "subline": "",
            "sticker": f"{idx + 1:02d}",
            "data_focus": "current_point",
            "show_data": idx in (0, len(PHOTO_PICKS) - 1),
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "crop": "center",
        }
        for idx, photo in enumerate(PHOTO_PICKS)
    ]

CARD_PLAN = {item["photo"]: item for item in card_plan_constraint if item.get("photo")}


def select_evenly(items, count):
    if len(items) <= count:
        return items
    result = []
    used = set()
    for i in range(count):
        idx = round(i * (len(items) - 1) / max(count - 1, 1))
        while idx in used and idx + 1 < len(items):
            idx += 1
        used.add(idx)
        result.append(items[idx])
    return result


def route_stats_from_route(route):
    seconds = float(route.get("duration_seconds", 0) or 0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    date_display = ""
    start_time = route.get("start_time")
    if start_time:
        try:
            date_display = datetime.fromisoformat(str(start_time).replace("Z", "+00:00")).astimezone(
                timezone(timedelta(hours=8))
            ).strftime("%Y.%m.%d")
        except Exception:
            date_display = str(start_time)[:10]
    return {
        "distance": f"{float(route.get('total_distance_km', 0) or 0):.2f} km",
        "elevation_gain": f"{int(round(float(route.get('elevation_gain', 0) or 0))):,} m",
        "duration": f"{hours}小时{minutes}分" if hours else f"{minutes}分钟",
        "max_elevation": f"{int(round(float(route.get('max_elevation', 0) or 0))):,} m",
        "date": date_display,
    }


def h(value):
    return escape(str(value), quote=True)


def multiline_text(value):
    return h(value).replace("|", "<br>")


def css_alpha(value, default):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric > 1:
        numeric = numeric / 100
    return max(0, min(1, numeric))


FORBIDDEN_VISIBLE_PHRASES = [
    phrase
    for phrase in get_in(social_constraints, ["script_hooks", "forbidden_visible_phrases"], [])
    if str(phrase).strip()
]
FORBIDDEN_VISIBLE_PHRASES.extend(
    [
        "现场照片和路线数据对得上",
        "现场照片和路线数据对的上",
        "路线数据对得上",
        "此刻在路线上的位置",
        "证明真的上来了",
    ]
)
INTERNAL_ROLE_LABELS = {"路线说明", "节点记录"}


def clean_visible_copy(value, fallback="真实记录"):
    text = str(value or "").strip()
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        if phrase and phrase in text:
            return fallback
    return text or fallback


def clean_role_label(value):
    text = clean_visible_copy(value, "")
    if text in INTERNAL_ROLE_LABELS:
        return ""
    return text


def assert_no_forbidden_html(html, filename):
    blocked = [*FORBIDDEN_VISIBLE_PHRASES, *INTERNAL_ROLE_LABELS]
    hits = [phrase for phrase in blocked if phrase and phrase in html]
    if hits:
        raise SystemExit(f"{filename} contains forbidden visible copy: {', '.join(sorted(set(hits)))}")


def load_data():
    references = os.environ.get("SHANYE_REFERENCES_ROOT", os.path.join(BASE, "references"))
    with open(os.path.join(references, "route_data.json")) as f:
        route = json.load(f)
    with open(os.path.join(references, "matched_photos.json")) as f:
        matched = json.load(f)
    with open(os.path.join(references, "content_assets.json")) as f:
        content = json.load(f)
    return route, matched, content


def project_trail(route):
    """
    将 GPS track_points 投影到平面坐标（米），返回归一化后的点列表。
    使用墨卡托投影：lat → 米，lon → 米。
    """
    pts = route.get("track_points", route.get("route_outline", []))
    if not pts:
        return [], 0, 0

    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    center_lat = (min(lats) + max(lats)) / 2
    LAT_TO_M = 110540.0
    LON_TO_M = 111320.0 * math.cos(math.radians(center_lat))

    coords = []
    for p in pts:
        x = (p["lon"] - min(lons)) * LON_TO_M
        y = (p["lat"] - min(lats)) * LAT_TO_M
        coords.append((x, y, p.get("ele", 0), p.get("cumulative_distance_m", 0)))

    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    x_range = max(xs) - min(xs) or 1
    y_range = max(ys) - min(ys) or 1

    # Normalize to 0-1, preserve aspect ratio
    normalized = []
    for x, y, ele, dist in coords:
        nx = (x - min(xs)) / x_range
        ny = 1.0 - (y - min(ys)) / y_range  # flip Y (north = top)
        normalized.append((nx, ny, ele, dist))

    return normalized, x_range, y_range


def ensure_output_photos(matched):
    if os.path.isdir(PHOTOS_DIR) and any(os.scandir(PHOTOS_DIR)):
        return
    fallback = os.path.join(BASE, "output", "photos")
    if os.path.abspath(fallback) == os.path.abspath(PHOTOS_DIR) or not os.path.isdir(fallback):
        return
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    wanted = {f"{os.path.splitext(item.get('filename', ''))[0]}.jpg" for item in matched.get("photos", [])}
    wanted |= {f"{os.path.splitext(item.get('filename', ''))[0]}.JPG" for item in matched.get("photos", [])}
    for name in wanted:
        source = os.path.join(fallback, name)
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(PHOTOS_DIR, name))


def project_photo_point(photo_match, route):
    """将照片的 match_point lat/lon 投影到与 trail 相同的坐标系"""
    pts = route.get("track_points", route.get("route_outline", []))
    if not pts:
        return (0.5, 0.5)

    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    center_lat = (min(lats) + max(lats)) / 2
    LAT_TO_M = 110540.0
    LON_TO_M = 111320.0 * math.cos(math.radians(center_lat))

    mp = photo_match.get("match_point", {})
    lat = mp.get("lat", center_lat)
    lon = mp.get("lon", min(lons))

    x = (lon - min(lons)) * LON_TO_M
    y = (lat - min(lats)) * LAT_TO_M

    xs = [(p["lon"] - min(lons)) * LON_TO_M for p in pts]
    ys = [(p["lat"] - min(lats)) * LAT_TO_M for p in pts]
    x_range = max(xs) - min(xs) or 1
    y_range = max(ys) - min(ys) or 1

    nx = (x - min(xs)) / x_range
    ny = 1.0 - (y - min(ys)) / y_range
    return (nx, ny)


def build_trail_svg(trail_pts, photo_xy, w=400, h=400):
    """
    生成大尺寸轨迹图 SVG，无背景，低透明度融入照片。
    """
    accent = tokens.hex("accent")

    pad = 30
    pw, ph = w - 2 * pad, h - 2 * pad

    step = max(1, len(trail_pts) // 60)
    sampled = trail_pts[::step]
    if trail_pts[-1] not in sampled:
        sampled.append(trail_pts[-1])

    points_str = " ".join(
        f"{pad + p[0] * pw:.1f},{pad + p[1] * ph:.1f}" for p in sampled
    )

    px = pad + photo_xy[0] * pw
    py = pad + photo_xy[1] * ph

    return f"""<svg class="trail-svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <polyline class="trail-halo" points="{points_str}" fill="none" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
  <polyline class="trail-line" points="{points_str}" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle class="trail-point-halo" cx="{px:.1f}" cy="{py:.1f}" r="13"/>
  <circle class="trail-point" cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{accent}" stroke-width="2"/>
</svg>"""


def data_items_for_card(data_focus, ele_display, dist_display, stats):
    if data_focus in ("none", "hide", ""):
        return []
    if data_focus == "distance_only":
        return [("已走", dist_display)]
    if data_focus == "elevation_only":
        return [("海拔", ele_display)]
    if data_focus == "distance_elevation":
        return [
            ("已走", dist_display),
            ("海拔", ele_display),
        ]
    if data_focus == "route_summary":
        return [
            ("距离", stats.get("distance", "0.00 km")),
            ("爬升", stats.get("elevation_gain", "0 m")),
            ("用时", stats.get("duration", "0分钟")),
        ]
    if data_focus == "max_elevation":
        return [
            ("最高点", stats.get("max_elevation", ele_display)),
            ("此处", ele_display),
            ("已走", dist_display),
        ]
    if data_focus == "finish_summary":
        return [
            ("全程", stats.get("distance", "0.00 km")),
            ("爬升", stats.get("elevation_gain", "0 m")),
            ("用时", stats.get("duration", "0分钟")),
        ]
    return [
        ("已走", dist_display),
        ("海拔", ele_display),
    ]


def build_data_tiles(items):
    if not items:
        return ""
    return "\n".join(
        f'<div class="data-tile"><span>{h(label)}</span><b>{h(value)}</b></div>'
        for label, value in items
    )


def build_card_html(idx, photo_info, trail_pts, photo_xy, stats, total_photos=9):
    """生成单张卡片 HTML，由小红书专家 card_plan 决定卡型。"""

    photo_filename = photo_info["jpg_name"]
    rel_path = os.path.relpath(os.path.join(PHOTOS_DIR, photo_filename), OUTPUT)

    gold = tokens.hex("earth_gold")
    cream = tokens.hex("cream")
    pine = tokens.hex("pine")
    accent = tokens.hex("accent")
    mineral = tokens.hex("mineral")
    visual_treatment = get_in(
        social_constraints,
        ["script_hooks", "visual_treatment"],
        "xhs_native_grid_story",
    )
    palette = get_in(social_constraints, ["script_hooks", "product_palette"], {})
    paper = palette.get("paper", "#fff7e8")
    ink = palette.get("ink", "#161711")
    ticket = palette.get("ticket", "#f8e7c0")
    sticker_red = palette.get("sticker_red", "#f05a3c")
    sticker_blue = palette.get("sticker_blue", "#2f6f8f")
    sticker_yellow = palette.get("sticker_yellow", "#f0c75a")
    route_light = palette.get("route_light", cream)
    route_dark = palette.get("route_dark", ink)
    text_scrim_opacity = css_alpha(
        get_in(social_constraints, ["script_hooks", "text_scrim_opacity"], 0.52),
        0.52,
    )
    data_scrim_opacity = css_alpha(
        get_in(social_constraints, ["script_hooks", "data_scrim_opacity"], 0.44),
        0.44,
    )
    team_watermark_opacity = css_alpha(
        get_in(social_constraints, ["script_hooks", "team_watermark_opacity"], 0.18),
        0.18,
    )
    hide_trail_label = bool(get_in(social_constraints, ["script_hooks", "hide_trail_label"], True))
    remove_photo_borders = bool(get_in(social_constraints, ["script_hooks", "remove_photo_borders"], True))

    plan = photo_info.get("plan", {})
    archetype = plan.get("archetype", "climb_note")
    caption = clean_visible_copy(plan.get("caption") or photo_info["caption"], "这一段路")
    headline = clean_visible_copy(plan.get("headline") or caption, caption)
    subline = clean_visible_copy(plan.get("subline") or "", "")
    sticker = plan.get("sticker") or f"{idx:02d}"
    show_role = bool(plan.get("show_role", False))
    photo_role = clean_role_label(plan.get("photo_role") or "")
    if not photo_role:
        show_role = False
    data_focus = plan.get("data_focus", "current_point")
    show_data = bool(plan.get("show_data", True))
    footer_text = clean_visible_copy(plan.get("footer_text") or "", "")
    crop = plan.get("crop", "center")

    elevation = photo_info["elevation"]
    distance_km = photo_info["distance_km"]
    ele_display = f"{elevation}m" if elevation else "—"
    dist_display = f"{distance_km:.1f}km" if distance_km else "—"

    trail_svg = build_trail_svg(trail_pts, photo_xy, 400, 400)
    data_items = data_items_for_card(data_focus, ele_display, dist_display, stats) if show_data else []
    data_tiles = build_data_tiles(data_items)

    route_name = stats.get("route_name", "路线纪念")
    team_name = stats.get("team_name", source_constraints.get("team_name", "山野路迹"))
    place_name = stats.get("place_name", "徒步路线")
    date_text = stats.get("date", "")
    mood = " / ".join(source_constraints.get("mood", ["真实记录"]))
    safe_rel_path = h(rel_path)
    route_meta = " · ".join(item for item in [route_name, date_text] if item)
    place_meta = place_name
    map_label_html = "" if hide_trail_label else '<div class="map-label"></div>'
    role_html = f'<div class="role">{h(photo_role)}</div>' if show_role and photo_role else ""
    subline_html = f"<p>{h(subline)}</p>" if subline else ""
    data_strip_html = f'<div class="data-strip">{data_tiles}</div>' if data_tiles else ""
    brandline_html = (
        f'<div class="brandline"><span class="team-name">{h(team_name)}</span><span>{h(footer_text)}</span></div>'
        if footer_text
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1080">
<title>山野路迹 · {idx:02d}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  width: 1080px; height: 1080px;
  font-family: {CSS_FONT_STACK};
  overflow: hidden; position: relative;
  background: {paper};
  color: {ink};
  --ink: {ink};
  --paper: {paper};
  --paper-2: {ticket};
  --pine: {pine};
  --mineral: {mineral};
  --gold: {sticker_yellow};
  --cream: {route_light};
  --accent: {sticker_red};
  --red: {sticker_red};
  --blue: {sticker_blue};
  --route-dark: {route_dark};
  --text-scrim: {text_scrim_opacity:.3f};
  --data-scrim: {data_scrim_opacity:.3f};
  --team-watermark-opacity: {team_watermark_opacity:.3f};
  --team-watermark-dark-opacity: {team_watermark_opacity * 0.72:.3f};
  --photo-border-width: {"0px" if remove_photo_borders else "18px"};
  --shadow: 0 28px 70px rgba(26, 21, 12, 0.26);
}}

body::before {{
  content: '';
  position: absolute; inset: 0;
  background:
    linear-gradient(rgba(21,23,17,0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(21,23,17,0.04) 1px, transparent 1px);
  background-size: 42px 42px;
  z-index: 0;
}}

body::after {{
  content: '';
  position: absolute; inset: 22px;
  border: 0;
  pointer-events: none;
  z-index: 10;
}}

.photo-layer {{
  position: absolute;
  background-image: url("{safe_rel_path}");
  background-position: {h(crop)};
  background-size: cover;
  box-shadow: var(--shadow);
  z-index: 1;
}}
.photo-layer::after {{
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0.18) 100%);
}}

.headline-card {{
  position: absolute;
  z-index: 7;
  background: rgba(255, 250, 240, var(--text-scrim));
  color: var(--ink);
  box-shadow: 0 18px 42px rgba(27, 20, 10, 0.12);
  backdrop-filter: blur(8px);
  padding: 34px 36px;
}}
.role {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 19px;
  font-weight: 900;
  color: var(--red);
  margin-bottom: 12px;
}}
.role::before {{
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--red);
}}
.headline-card h1 {{
  font-size: 74px;
  line-height: 0.98;
  letter-spacing: 0;
  font-weight: 950;
  text-wrap: balance;
  overflow-wrap: anywhere;
}}
.headline-card p {{
  margin-top: 18px;
  font-size: 28px;
  line-height: 1.35;
  font-weight: 700;
  color: rgba(21, 23, 17, 0.72);
  text-wrap: pretty;
}}

.caption-sticker {{
  position: absolute;
  z-index: 8;
  background: color-mix(in srgb, var(--accent) 82%, transparent);
  color: white;
  border-radius: 999px;
  padding: 16px 26px;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 950;
  box-shadow: 0 15px 28px rgba(217, 75, 43, 0.28);
}}
.stamp {{
  position: absolute;
  z-index: 8;
  display: grid;
  place-items: center;
  min-width: 116px;
  min-height: 72px;
  padding: 14px 20px;
  color: var(--red);
                  border: 3px solid var(--red);
  background: rgba(255, 250, 240, var(--text-scrim));
  transform: rotate(-8deg);
  font-size: 23px;
  font-weight: 950;
  line-height: 1;
  text-align: center;
}}

.data-strip {{
  position: absolute;
  z-index: 8;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}}
.data-tile {{
  background: rgba(255, 250, 240, var(--data-scrim));
  color: var(--ink);
  padding: 13px 17px 14px;
  min-width: 118px;
  box-shadow: 0 10px 22px rgba(27, 20, 10, 0.08);
  backdrop-filter: blur(7px);
}}
.data-tile span {{
  display: block;
  color: rgba(21, 23, 17, 0.58);
  font-size: 15px;
  font-weight: 800;
}}
.data-tile b {{
  display: block;
  margin-top: 3px;
  font-size: 30px;
  line-height: 1;
  color: var(--pine);
}}

.map-chip {{
  position: absolute;
  z-index: 8;
  width: 236px;
  height: 258px;
  padding: 0;
  background: transparent;
  color: var(--trail-text, var(--cream));
  box-shadow: none;
  filter: drop-shadow(0 8px 16px rgba(0,0,0,0.28));
  pointer-events: none;
}}
.map-chip svg {{
  width: 100%;
  height: 100%;
  overflow: visible;
}}
.map-label {{
  display: none;
}}
.trail-svg {{
  --trail-line: rgba(245,240,232,0.92);
  --trail-halo: rgba(15,18,14,0.72);
  --trail-point-stroke: rgba(245,240,232,0.96);
}}
.trail-on-light .trail-svg {{
  --trail-line: color-mix(in srgb, var(--route-dark) 92%, transparent);
  --trail-halo: rgba(255,250,240,0.78);
  --trail-point-stroke: rgba(255,250,240,0.96);
}}
.trail-line {{
  stroke: var(--trail-line);
}}
.trail-halo {{
  stroke: var(--trail-halo);
  opacity: 0.92;
}}
.trail-point-halo {{
  fill: var(--trail-halo);
  opacity: 0.8;
}}
.trail-point {{
  stroke: var(--trail-point-stroke);
}}

.top-meta, .brandline {{
  position: absolute;
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: rgba(21, 23, 17, 0.54);
  font-size: 18px;
  font-weight: 850;
}}
.top-meta {{
  top: 42px;
  left: 48px;
  right: 48px;
  text-shadow: 0 1px 12px rgba(255,250,240,0.42);
}}
.top-meta .route-meta {{
  max-width: 760px;
  overflow-wrap: anywhere;
}}
.top-meta .place-meta {{
  font-weight: 750;
  opacity: 0.72;
}}
.brandline {{
  left: 48px;
  right: 48px;
  bottom: 36px;
  justify-content: flex-end;
  color: rgba(21, 23, 17, 0.58);
}}
.brandline .team-name {{
  display: none;
}}
.team-watermark {{
  position: absolute;
  z-index: 6;
  right: 48px;
  bottom: 44px;
  max-width: 820px;
  font-size: 86px;
  line-height: 0.9;
  font-weight: 950;
  color: rgba(255, 250, 240, var(--team-watermark-opacity));
  text-shadow: 0 2px 16px rgba(0,0,0,0.18);
  pointer-events: none;
  text-align: right;
  mix-blend-mode: soft-light;
  overflow-wrap: anywhere;
}}
.route_ticket .team-watermark,
.lookback_split .team-watermark,
.ridge_frame .team-watermark,
.finish_receipt .team-watermark {{
  color: rgba(21, 23, 17, var(--team-watermark-dark-opacity));
  text-shadow: 0 2px 14px rgba(255,250,240,0.2);
}}
.page-num {{
  color: rgba(21, 23, 17, 0.42);
  font-size: 18px;
  font-weight: 950;
}}
.cover_burst .page-num,
.grit_snapshot .page-num,
.summit_proof .page-num {{
  color: rgba(255, 250, 240, 0.56);
}}

.cover_burst {{
  background: #1f3d2d;
}}
.cover_burst .photo-layer {{
  inset: 0;
}}
.cover_burst .photo-layer::after {{
  background: linear-gradient(180deg, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0.25) 54%, rgba(0,0,0,0.46) 100%);
}}
.cover_burst .headline-card {{
  left: 56px;
  right: 330px;
  bottom: 88px;
  background: rgba(255, 250, 240, var(--text-scrim));
}}
.cover_burst .headline-card h1 {{
  font-size: 72px;
  line-height: 1.02;
}}
.cover_burst .stamp {{
  top: 92px;
  right: 76px;
}}
.cover_burst .caption-sticker {{
  right: 72px;
  bottom: 312px;
}}
.cover_burst .data-strip {{
  left: 92px;
  top: 92px;
}}
.cover_burst .map-chip {{
  right: 54px;
  bottom: 66px;
  width: 216px;
  height: 238px;
  transform: rotate(3deg);
}}
.cover_burst .map-chip svg {{
  height: 100%;
}}
.cover_burst .top-meta, .cover_burst .brandline {{
  color: rgba(255, 250, 240, 0.72);
}}

.route_ticket .photo-layer {{
  top: 88px;
  right: 62px;
  width: 530px;
  height: 720px;
  border: var(--photo-border-width) solid var(--paper-2);
  transform: rotate(2deg);
}}
.route_ticket .headline-card {{
  left: 56px;
  top: 118px;
  width: 430px;
  min-height: 612px;
  border: 0;
}}
.route_ticket .headline-card h1 {{
  font-size: 76px;
}}
.route_ticket .data-strip {{
  left: 84px;
  bottom: 128px;
  width: 450px;
}}
.route_ticket .map-chip {{
  right: 96px;
  bottom: 88px;
  transform: rotate(-2deg);
}}
.route_ticket .stamp {{
  right: 430px;
  top: 706px;
}}
.route_ticket .caption-sticker {{
  right: 112px;
  top: 676px;
  background: var(--pine);
}}

.climb_note .photo-layer {{
  left: 62px;
  right: 62px;
  top: 64px;
  height: 640px;
  border-radius: 0;
}}
.climb_note .headline-card {{
  left: 92px;
  right: 92px;
  bottom: 104px;
}}
.climb_note .headline-card h1 {{
  font-size: 66px;
}}
.climb_note .data-strip {{
  left: 128px;
  bottom: 338px;
}}
.climb_note .map-chip {{
  right: 92px;
  top: 94px;
  transform: rotate(2deg);
}}
.climb_note .stamp {{
  left: 96px;
  top: 92px;
}}
.climb_note .caption-sticker {{
  right: 108px;
  bottom: 70px;
}}

.grit_snapshot {{
  background: #211b14;
}}
.grit_snapshot .photo-layer {{
  inset: 0;
  filter: saturate(1.08) contrast(1.05);
}}
.grit_snapshot .photo-layer::after {{
  background:
    linear-gradient(90deg, rgba(33, 27, 20, 0.58) 0%, rgba(33, 27, 20, 0.12) 60%),
    linear-gradient(180deg, rgba(0,0,0,0.01) 0%, rgba(0,0,0,0.32) 100%);
}}
.grit_snapshot .headline-card {{
  left: 48px;
  top: 96px;
  width: 460px;
  background: transparent;
  color: var(--paper-2);
  box-shadow: none;
  padding: 0;
}}
.grit_snapshot .headline-card h1 {{
  font-size: 82px;
  color: var(--paper-2);
}}
.grit_snapshot .headline-card p, .grit_snapshot .role {{
  color: rgba(255, 250, 240, 0.82);
}}
.grit_snapshot .role::before {{
  background: var(--accent);
}}
.grit_snapshot .data-strip {{
  left: 54px;
  bottom: 88px;
}}
.grit_snapshot .map-chip {{
  right: 70px;
  bottom: 76px;
  transform: rotate(-3deg);
}}
.grit_snapshot .stamp {{
  right: 80px;
  top: 86px;
  background: var(--accent);
  color: white;
  border-color: white;
}}
.grit_snapshot .caption-sticker {{
  left: 54px;
  top: 540px;
}}
.grit_snapshot .top-meta, .grit_snapshot .brandline {{
  color: rgba(255, 250, 240, 0.72);
}}

.lookback_split .photo-layer {{
  left: 48px;
  top: 72px;
  bottom: 80px;
  width: 590px;
  border: var(--photo-border-width) solid var(--paper-2);
  transform: rotate(-1.5deg);
}}
.lookback_split .headline-card {{
  right: 56px;
  top: 132px;
  width: 385px;
  min-height: 478px;
  background: rgba(44, 100, 112, 0.68);
  color: var(--paper-2);
}}
.lookback_split .headline-card h1 {{
  font-size: 62px;
  color: var(--paper-2);
}}
.lookback_split .headline-card p, .lookback_split .role {{
  color: rgba(255, 250, 240, 0.84);
}}
.lookback_split .role::before {{
  background: var(--paper-2);
}}
.lookback_split .data-strip {{
  right: 70px;
  bottom: 132px;
  width: 380px;
}}
.lookback_split .map-chip {{
  left: 96px;
  bottom: 116px;
}}
.lookback_split .stamp {{
  right: 118px;
  top: 648px;
}}
.lookback_split .caption-sticker {{
  left: 96px;
  top: 104px;
  background: var(--blue);
}}

.ridge_frame {{
  background: #e8dfd3;
}}
.ridge_frame .photo-layer {{
  inset: 42px;
  border: var(--photo-border-width) solid var(--paper-2);
}}
.ridge_frame .photo-layer::after {{
  background: linear-gradient(180deg, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0.28) 100%);
}}
.ridge_frame .headline-card {{
  left: 82px;
  bottom: 98px;
  width: 560px;
  background: rgba(255, 250, 240, var(--text-scrim));
}}
.ridge_frame .headline-card h1 {{
  font-size: 70px;
}}
.ridge_frame .map-chip {{
  right: 92px;
  top: 96px;
  transform: rotate(2deg);
}}
.ridge_frame .data-strip {{
  right: 96px;
  bottom: 112px;
  width: 330px;
}}
.ridge_frame .stamp {{
  left: 104px;
  top: 100px;
}}
.ridge_frame .caption-sticker {{
  right: 110px;
  top: 392px;
  background: var(--pine);
}}

.summit_proof {{
  background: #19251c;
}}
.summit_proof .photo-layer {{
  inset: 0;
}}
.summit_proof .photo-layer::after {{
  background:
    linear-gradient(180deg, rgba(15, 26, 18, 0.01) 0%, rgba(15, 26, 18, 0.48) 100%),
    linear-gradient(90deg, rgba(15, 26, 18, 0.54) 0%, rgba(15, 26, 18, 0.08) 72%);
}}
.summit_proof .headline-card {{
  left: 58px;
  top: 116px;
  width: 538px;
  background: transparent;
  color: var(--paper-2);
  box-shadow: none;
  padding: 0;
}}
.summit_proof .headline-card h1 {{
  font-size: 152px;
  color: var(--paper-2);
  line-height: 0.84;
}}
.summit_proof .headline-card p, .summit_proof .role {{
  color: rgba(255, 250, 240, 0.84);
}}
.summit_proof .role::before {{
  background: var(--accent);
}}
.summit_proof .data-strip {{
  left: 66px;
  bottom: 96px;
}}
.summit_proof .map-chip {{
  right: 70px;
  bottom: 84px;
}}
.summit_proof .stamp {{
  right: 88px;
  top: 96px;
  background: rgba(255, 250, 240, var(--text-scrim));
}}
.summit_proof .caption-sticker {{
  left: 62px;
  top: 500px;
}}
.summit_proof .top-meta, .summit_proof .brandline {{
  color: rgba(255, 250, 240, 0.72);
}}

.finish_receipt .photo-layer {{
  inset: 0;
  filter: saturate(0.95);
}}
.finish_receipt .photo-layer::after {{
  background: rgba(246, 240, 223, 0.64);
}}
.finish_receipt .headline-card {{
  left: 172px;
  right: 172px;
  top: 150px;
  bottom: 136px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  border: 0;
}}
.finish_receipt .headline-card h1 {{
  font-size: 86px;
}}
.finish_receipt .data-strip {{
  left: 226px;
  right: 226px;
  bottom: 188px;
  justify-content: center;
}}
.finish_receipt .map-chip {{
  left: 64px;
  bottom: 72px;
  transform: rotate(-2deg);
}}
.finish_receipt .stamp {{
  right: 122px;
  top: 106px;
}}
.finish_receipt .caption-sticker {{
  left: 50%;
  transform: translateX(-50%) rotate(-2deg);
  bottom: 98px;
  background: var(--pine);
}}
</style>
</head>
<body class="{h(archetype)}">
<div class="photo-layer"></div>
<div class="team-watermark">{h(team_name)}</div>
<div class="top-meta">
  <span class="route-meta">{h(route_meta)}</span>
  <span class="place-meta">{h(place_meta)}</span>
  <span class="page-num">{idx:02d}/{total_photos:02d}</span>
</div>
<section class="headline-card">
  {role_html}
  <h1>{multiline_text(headline)}</h1>
  {subline_html}
</section>
<div class="caption-sticker">{h(caption)}</div>
<div class="stamp">{h(sticker)}</div>
{data_strip_html}
<div class="map-chip">
  {map_label_html}
  {trail_svg}
</div>
{brandline_html}
<div style="display:none">{h(visual_treatment)}</div>
<script>
(function(){{
  const chip = document.querySelector('.map-chip');
  if (!chip) return;
  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.src = "{safe_rel_path}";
  img.onload = function(){{
    try {{
      const canvas = document.createElement('canvas');
      const size = 48;
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d', {{ willReadFrequently: true }});
      const rect = chip.getBoundingClientRect();
      const cx = Math.max(0, Math.min(1, (rect.left + rect.width / 2) / 1080));
      const cy = Math.max(0, Math.min(1, (rect.top + rect.height / 2) / 1080));
      const sw = Math.max(24, img.naturalWidth * 0.24);
      const sh = Math.max(24, img.naturalHeight * 0.24);
      const sx = Math.max(0, Math.min(img.naturalWidth - sw, img.naturalWidth * cx - sw / 2));
      const sy = Math.max(0, Math.min(img.naturalHeight - sh, img.naturalHeight * cy - sh / 2));
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, size, size);
      const data = ctx.getImageData(0, 0, size, size).data;
      let total = 0;
      for (let i = 0; i < data.length; i += 4) {{
        total += 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      }}
      const avg = total / (data.length / 4);
      chip.classList.toggle('trail-on-light', avg > 138);
      chip.style.setProperty('--trail-text', avg > 138 ? 'rgba(21,23,17,0.84)' : 'rgba(255,250,240,0.9)');
      chip.style.setProperty('--trail-shadow', avg > 138 ? 'rgba(255,250,240,0.72)' : 'rgba(0,0,0,0.78)');
    }} catch (err) {{
      chip.classList.remove('trail-on-light');
    }}
  }};
}})();
</script>

</body>
</html>"""


def build_grid_preview(card_files, content, stats):
    """3×3 网格预览页"""
    gold = tokens.hex("earth_gold")
    pine = tokens.hex("pine")
    mineral = tokens.hex("mineral")

    items = ""
    for f in card_files:
        items += f'<div class="grid-item"><iframe src="{f}" frameborder="0" scrolling="no"></iframe></div>\n'

    route_name = content.get("route_name", source_constraints.get("route_name", "路线纪念"))
    place_name = source_constraints.get("place_name", content.get("place_name", "徒步路线"))
    team_name = source_constraints.get("team_name", content.get("team_name", "山野路迹"))
    hashtags = get_in(social_constraints, ["copy_strategy", "hashtags"], ["#徒步", "#户外记录"])
    hashtags_text = " ".join(hashtags)
    cover_hook = get_in(social_constraints, ["composition", "cover_hook"], "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>山野路迹 · 社交组图预览</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background: #f6f0df;
  font-family: {CSS_FONT_STACK};
  color: #151711;
}}
body::before {{
  content: ''; position: fixed; inset: 0; pointer-events: none;
  background:
    linear-gradient(rgba(21,23,17,0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(21,23,17,0.04) 1px, transparent 1px);
  background-size: 48px 48px;
}}
.header {{
  max-width: 3252px; margin: 0 auto;
  padding: 44px 20px 18px;
  display: flex; align-items: flex-end; justify-content: space-between;
  border-bottom: 2px solid rgba(21,23,17,0.16);
}}
.header h1 {{
  font-size: 42px; font-weight: 900;
  color: #151711;
  letter-spacing: 0;
}}
.header p {{
  max-width: 720px;
  font-size: 15px; color: rgba(21,23,17,0.68);
  margin-top: 8px; letter-spacing: 0; text-align: right;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(3, 540px);
  gap: 12px;
  max-width: 1664px;
  margin: 0 auto;
  padding: 20px;
}}
.grid-item {{
  position: relative;
  width: 540px;
  height: 540px;
  overflow: hidden;
}}
.grid-item iframe {{
  position: absolute; top: 0; left: 0;
  width: 1080px; height: 1080px;
  border: none;
  transform-origin: top left;
  transform: scale(0.5);
}}
.footer {{
  text-align: center; padding: 20px;
  font-size: 12px; color: rgba(21,23,17,0.55); letter-spacing: 0;
}}
</style>
</head>
<body>
<div class="header">
  <h1>{place_name} · {route_name}</h1>
  <p>{cover_hook or f'{stats["distance"]} · {stats["elevation_gain"]}爬升 · {stats["duration"]}'}</p>
</div>
<div class="grid">{items}</div>
<div class="footer">{team_name} · 小红书社交组图 · {hashtags_text}</div>
</body>
</html>"""


def main():
    global PHOTO_PICKS, CARD_PLAN, CAPTIONS

    route, matched, content = load_data()
    ensure_output_photos(matched)
    stats = {
        **route_stats_from_route(route),
        **content.get("stats_display", {}),
        "route_name": source_constraints.get("route_name", content.get("route_name", "路线纪念")),
        "team_name": source_constraints.get("team_name", content.get("team_name", "山野路迹")),
        "place_name": source_constraints.get("place_name", content.get("place_name", "徒步路线")),
    }

    # Project trail to normalized coordinates
    trail_pts, x_range, y_range = project_trail(route)
    print("山野路迹 · 小红书社交组图")
    print(f"  设计约束：{get_in(social_constraints, ['composition', 'sequence_logic'], 'route_timeline')} / {len(PHOTO_PICKS)} 张")
    print(f"  轨迹投影：{len(trail_pts)} 点，X范围={x_range:.0f}m Y范围={y_range:.0f}m")
    print()

    # Build photo lookup
    photo_map = {}
    for p in matched["photos"]:
        name = os.path.splitext(p["filename"])[0]
        for ext in [".jpg", ".JPG"]:
            jpg_name = f"{name}{ext}"
            if os.path.exists(os.path.join(PHOTOS_DIR, jpg_name)):
                photo_map[name] = {**p, "jpg_name": jpg_name}
                break

    if not PHOTO_PICKS:
        ordered_names = [
            os.path.splitext(p["filename"])[0]
            for p in sorted(
                matched.get("photos", []),
                key=lambda item: item.get("match_point", {}).get("cumulative_distance_m", 0),
            )
            if os.path.splitext(p.get("filename", ""))[0] in photo_map
        ]
        PHOTO_PICKS = select_evenly(ordered_names, 9)
        if not card_plan_constraint:
            generated_plan = []
            for idx, photo in enumerate(PHOTO_PICKS):
                archetype = DEFAULT_ARCHETYPES[idx % len(DEFAULT_ARCHETYPES)]
                caption = CAPTIONS.get(photo) or ("起点" if idx == 0 else "终点" if idx == len(PHOTO_PICKS) - 1 else f"途中 {idx + 1}")
                generated_plan.append(
                    {
                        "photo": photo,
                        "caption": caption,
                        "archetype": archetype,
                        "headline": caption,
                        "subline": "",
                        "sticker": f"{idx + 1:02d}",
                        "data_focus": "route_summary" if idx == 0 else "finish_summary" if idx == len(PHOTO_PICKS) - 1 else "current_point",
                        "show_data": idx in (0, len(PHOTO_PICKS) - 1),
                        "show_role": False,
                        "photo_role": "",
                        "footer_text": "",
                        "crop": "center",
                    }
                )
            CARD_PLAN = {item["photo"]: item for item in generated_plan}
            CAPTIONS.update({item["photo"]: item["caption"] for item in generated_plan})

    files = []
    for idx, photo_name in enumerate(PHOTO_PICKS, 1):
        photo_info = photo_map.get(photo_name)
        if not photo_info:
            print(f"  ⚠ 跳过 {photo_name}：未找到照片")
            continue

        # Get photo data
        caption = CAPTIONS.get(photo_name, photo_info.get("custom_title", "山野路迹"))
        mp = photo_info.get("match_point", {})
        elevation = int(mp.get("ele", 0))
        distance_m = mp.get("cumulative_distance_m", 0)
        distance_km = distance_m / 1000.0 if distance_m else 0

        # Project photo position onto trail coordinate system
        photo_xy = project_photo_point(photo_info, route)

        photo_data = {
            "jpg_name": photo_info["jpg_name"],
            "caption": caption,
            "elevation": elevation,
            "distance_km": distance_km,
            "plan": CARD_PLAN.get(photo_name, {}),
        }

        html = build_card_html(idx, photo_data, trail_pts, photo_xy, stats)
        filename = f"social_card_{idx:02d}.html"
        assert_no_forbidden_html(html, filename)
        path = os.path.join(OUTPUT, filename)
        with open(path, "w") as f:
            f.write(html)
        files.append(filename)
        print(f"  ✓ {filename} — {caption} ({elevation}m, {distance_km:.1f}km) pos=({photo_xy[0]:.2f},{photo_xy[1]:.2f})")

    # Grid preview
    grid_html = build_grid_preview(files, content, stats)
    grid_path = os.path.join(OUTPUT, "social_grid_preview.html")
    with open(grid_path, "w") as f:
        f.write(grid_html)
    print(f"\n  ✓ social_grid_preview.html — 3×3 预览页")
    print(f"\n共生成 {len(files)} 张卡片")


if __name__ == "__main__":
    main()
