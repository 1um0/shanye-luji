#!/usr/bin/env python3
"""
山野路迹 — 公众号推送文章构建器
东方极简 + 纪实摄影，诧寂 × 新自然主义。
1080px 宽，单栏流式，大留白，卡片式数据，故事叙事。

用法:
    python build_wechat_article.py
"""

import json
import os
import sys
import textwrap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from design_constraints import get_in, list_from_constraints, load_design_constraints, product_constraints
from platform_utils import CSS_FONT_STACK
from render_engine import get_tokens

REFERENCES = os.environ.get("SHANYE_REFERENCES_ROOT", os.path.join(BASE, "references"))
OUTPUT = os.environ.get("SHANYE_OUTPUT_ROOT", os.path.join(BASE, "output"))
PHOTOS_DIR = os.path.join(OUTPUT, "photos")
os.makedirs(OUTPUT, exist_ok=True)

tokens = get_tokens()
constraints = load_design_constraints(BASE)
wechat_constraints = product_constraints(constraints, "wechat_article")
source_constraints = constraints.get("source", {})

story_photo_constraints = [
    (item["filename"], item["caption"])
    for item in get_in(wechat_constraints, ["script_hooks", "photo_sequence"], [])
    if item.get("filename") and item.get("caption")
]
STORY_PHOTOS = list_from_constraints(story_photo_constraints, [])


def select_existing_photos(count=6):
    photos = []
    photo_dir = os.path.join(PHOTOS_DIR)
    if not os.path.isdir(photo_dir):
        return photos
    for name in sorted(os.listdir(photo_dir)):
        if name.lower().endswith((".jpg", ".jpeg", ".png")):
            photos.append(name)
    if len(photos) <= count:
        selected = photos
    else:
        selected = [photos[round(i * (len(photos) - 1) / max(count - 1, 1))] for i in range(count)]
    return [(name, f"现场记录 {idx + 1}") for idx, name in enumerate(selected)]


def route_stats_from_route(route):
    seconds = float(route.get("duration_seconds", 0) or 0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return {
        "distance": f"{float(route.get('total_distance_km', 0) or 0):.2f} km",
        "elevation_gain": f"{int(round(float(route.get('elevation_gain', 0) or 0))):,} m",
        "duration": f"{hours}小时{minutes}分" if hours else f"{minutes}分钟",
        "max_elevation": f"{int(round(float(route.get('max_elevation', 0) or 0))):,} m",
    }


def load_data():
    with open(os.path.join(REFERENCES, "route_data.json")) as f:
        route = json.load(f)
    with open(os.path.join(REFERENCES, "content_assets.json")) as f:
        content = json.load(f)
    return route, content


def elevation_svg(route):
    """生成海拔剖面 SVG"""
    profile = route.get("elevation_profile", [])
    if not profile:
        return ""
    pts = [[p["distance_km"], p["ele"]] for p in profile]
    w, h = 960, 220
    pad_t, pad_b, pad_l, pad_r = 10, 30, 50, 40
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    d_max = pts[-1][0]
    e_min = min(p[1] for p in pts)
    e_max = max(p[1] for p in pts)
    e_range = e_max - e_min or 1

    palette = get_in(wechat_constraints, ["script_hooks", "product_palette"], {})
    gold = palette.get("rule", tokens.hex("earth_gold"))
    pine = palette.get("muted", tokens.hex("pine"))
    pine_light = palette.get("muted", tokens.hex("pine_light"))

    # Fill path
    fill_d = f"M{pad_l},{pad_t + ph}"
    for p in pts:
        x = pad_l + (p[0] / d_max) * pw
        y = pad_t + (1 - (p[1] - e_min) / e_range) * ph
        fill_d += f" L{x:.1f},{y:.1f}"
    fill_d += f" L{pad_l + pw},{pad_t + ph} Z"

    # Line path
    line_d = ""
    for i, p in enumerate(pts):
        x = pad_l + (p[0] / d_max) * pw
        y = pad_t + (1 - (p[1] - e_min) / e_range) * ph
        line_d += f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f} "

    # Labels
    labels = f'<text x="{pad_l}" y="{pad_t + ph + 18}" font-size="11" fill="{pine_light}" font-family="sans-serif">0km</text>'
    labels += f'<text x="{pad_l + pw - 30}" y="{pad_t + ph + 18}" font-size="11" fill="{pine_light}" font-family="sans-serif" text-anchor="end">{d_max:.1f}km</text>'
    labels += f'<text x="{pad_l - 8}" y="{pad_t + 12}" font-size="11" fill="{pine_light}" font-family="sans-serif" text-anchor="end">{e_max:.0f}m</text>'
    labels += f'<text x="{pad_l - 8}" y="{pad_t + ph}" font-size="11" fill="{pine_light}" font-family="sans-serif" text-anchor="end">{e_min:.0f}m</text>'

    return f"""<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="elevGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{pine}" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="{pine}" stop-opacity="0.05"/>
    </linearGradient>
  </defs>
  <path d="{fill_d}" fill="url(#elevGrad)"/>
  <path d="{line_d}" fill="none" stroke="{gold}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  {labels}
</svg>"""


def build_html(route, content):
    stats = {**route_stats_from_route(route), **content.get("stats_display", {})}
    route_name = source_constraints.get("route_name", content.get("route_name", "路线纪念"))
    team_name = source_constraints.get("team_name", content.get("team_name", "山野路迹"))
    place_name = source_constraints.get("place_name", content.get("place_name", "徒步路线"))
    palette = get_in(wechat_constraints, ["script_hooks", "product_palette"], {})
    gold = palette.get("rule", tokens.hex("earth_gold"))
    pine = palette.get("muted", tokens.hex("pine"))
    cream = palette.get("paper", tokens.hex("cream"))
    mineral = palette.get("muted", tokens.hex("mineral"))
    warm_sand = palette.get("page_bg", tokens.hex("warm_sand"))
    accent = palette.get("alert", tokens.hex("accent"))
    dark = palette.get("ink", tokens.hex("dark"))
    text_primary = palette.get("ink", tokens.hex("text_primary"))
    visual_treatment = get_in(
        wechat_constraints,
        ["script_hooks", "visual_treatment"],
        "field_dossier_article",
    )

    # Hero photo
    photo_sequence = STORY_PHOTOS or select_existing_photos()
    hero_photo_name = get_in(wechat_constraints, ["composition", "hero_photo"], "")
    if hero_photo_name == "highest_elevation_photo" or not hero_photo_name:
        hero_photo_name = photo_sequence[0][0] if photo_sequence else ""
    hero_photo = os.path.relpath(os.path.join(PHOTOS_DIR, hero_photo_name), OUTPUT)
    intro_meta = get_in(
        wechat_constraints,
        ["copy_strategy", "intro_meta"],
        f"{team_name} · {place_name}",
    )
    hashtags = get_in(
        wechat_constraints,
        ["copy_strategy", "hashtags"],
        content.get("hashtags", ["#徒步", "#户外记录"]),
    )
    hashtags_html = "<br>\n    ".join(" ".join(hashtags[i:i + 3]) for i in range(0, len(hashtags), 3))
    intro_meta_html = intro_meta.replace(team_name, f"<span>{team_name}</span>")

    # Story photos HTML
    photo_sections = ""
    for filename, caption in photo_sequence:
        path = os.path.relpath(os.path.join(PHOTOS_DIR, filename), OUTPUT)
        photo_sections += f"""
    <div class="photo-block">
      <div class="photo-frame">
        <img src="{path}" alt="{caption}">
      </div>
      <p class="photo-caption">{caption}</p>
    </div>"""

    # Elevation chart
    elev_svg = elevation_svg(route)

    # Story text - format paragraphs
    story = content.get("hike_story", content.get("trail_summary", "这是一段真实路线记录。"))
    paragraphs = story.strip().split("\n\n")
    story_html = ""
    for p in paragraphs:
        p = p.strip()
        if p:
            story_html += f'<p class="story-p">{p}</p>\n'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>山野路迹 · {route_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  width: 1080px;
  font-family: {CSS_FONT_STACK};
  background: {warm_sand};
  color: {text_primary};
  line-height: 1.8;
}}
body::before {{
  content: ''; position: fixed; inset: 0; pointer-events: none;
  background:
    linear-gradient(rgba(31,36,29,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(31,36,29,0.035) 1px, transparent 1px);
  background-size: 54px 54px;
}}

/* ---- 封面头图 ---- */
.hero {{
  width: 100%; height: 760px;
  position: relative; overflow: hidden;
  background: {dark};
}}
.hero img {{
  position: absolute; right: 60px; top: 70px;
  width: 620px; height: 560px; object-fit: cover;
  display: block;
  clip-path: polygon(10% 0, 100% 0, 90% 100%, 0 100%);
  filter: saturate(0.9) contrast(1.08);
}}
.hero-overlay {{
  position: absolute; inset: 0;
  background:
    linear-gradient(90deg, color-mix(in srgb, {dark} 100%, transparent) 0%, color-mix(in srgb, {dark} 88%, transparent) 38%, color-mix(in srgb, {dark} 12%, transparent) 100%);
  pointer-events: none;
}}
.hero-title-wrap {{
  position: absolute; top: 92px; left: 82px; width: 440px;
}}
.hero-title {{
  font-size: 86px; font-weight: 900; color: {gold};
  letter-spacing: 0; line-height: 1.02;
  text-wrap: balance;
}}
.hero-sub {{
  font-size: 16px; color: rgba(245,240,232,0.72);
  margin-top: 24px; letter-spacing: 0; font-weight: 700;
}}
.hero-dossier {{
  position: absolute; left: 82px; bottom: 78px;
  width: 430px; border: 1px solid color-mix(in srgb, {gold} 48%, transparent);
  padding: 20px 22px;
  color: rgba(245,240,232,0.76);
  font-size: 14px; line-height: 1.8;
}}
.hero-dossier strong {{ color: {gold}; font-weight: 900; }}
.hero-stamp {{
  position: absolute; right: 82px; top: 54px;
  color: rgba(245,240,232,0.34);
  font-size: 12px; letter-spacing: 3px;
}}

/* ---- 引导语区 ---- */
.intro {{
  padding: 74px 96px 48px;
  background: {cream};
  color: {text_primary};
}}
.intro-meta {{
  font-size: 15px; color: {mineral};
  letter-spacing: 0;
  margin-bottom: 22px;
  font-weight: 800;
}}
.intro-meta span {{ color: {gold}; }}
.intro-quote {{
  font-size: 28px; color: {text_primary};
  line-height: 1.55; letter-spacing: 0;
  max-width: 820px; margin: 0;
  font-weight: 800;
}}

/* ---- 数据卡片区 ---- */
.stats-section {{
  padding: 54px 80px;
  background: {cream};
}}
.stats-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border-top: 2px solid {text_primary};
  border-bottom: 2px solid {text_primary};
}}
.stat-card {{
  background: transparent;
  border-radius: 0;
  padding: 24px 18px;
  text-align: left;
  border-right: 1px solid color-mix(in srgb, {text_primary} 28%, transparent);
}}
.stat-card:last-child {{ border-right: 0; }}
.stat-card .icon {{
  font-size: 12px; margin-bottom: 16px;
  color: {accent};
  font-weight: 900;
}}
.stat-card .value {{
  font-size: 34px; font-weight: 900;
  color: {text_primary};
  letter-spacing: 0;
}}
.stat-card .label {{
  font-size: 13px; color: {mineral};
  margin-top: 6px; letter-spacing: 0;
  font-weight: 800;
}}

/* ---- 正文故事 ---- */
.story-section {{
  padding: 72px 140px 64px;
  background: {dark};
}}
.story-p {{
  font-size: 19px; line-height: 2.05;
  color: rgba(245,240,232,0.86);
  margin-bottom: 28px;
  text-align: justify;
  letter-spacing: 0;
}}
.story-p:first-letter {{
  font-size: 42px; font-weight: 900;
  color: {gold};
}}

/* ---- Section divider ---- */
.section-divider {{
  display: none;
}}
.section-divider .line {{
  flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, {gold}50, transparent);
}}
.section-divider .dot {{
  width: 8px; height: 8px;
  background: {gold};
  border-radius: 50%;
  opacity: 0.6;
}}

/* ---- 照片区 ---- */
.photo-blocks {{
  padding: 38px 80px 60px;
  background: {dark};
}}
.photo-block {{
  margin-bottom: 52px;
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 24px;
  align-items: end;
}}
.photo-block:nth-child(even) {{
  grid-template-columns: 220px 1fr;
}}
.photo-block:nth-child(even) .photo-frame {{ grid-column: 2; }}
.photo-block:nth-child(even) .photo-caption {{ grid-column: 1; grid-row: 1; text-align: right; }}
.photo-frame {{
  border-radius: 0; overflow: hidden;
  border: 1px solid color-mix(in srgb, {gold} 55%, transparent);
  box-shadow: 0 20px 56px rgba(0,0,0,0.34);
}}
.photo-frame img {{
  width: 100%; display: block;
}}
.photo-caption {{
  font-size: 24px; color: {gold};
  text-align: left; margin-top: 0;
  letter-spacing: 0; font-style: normal;
  font-weight: 900; line-height: 1.2;
}}

/* ---- 海拔剖面 ---- */
.elevation-section {{
  padding: 58px 80px 68px;
  background: {cream};
}}
.elevation-title {{
  font-size: 20px; font-weight: 900;
  color: {text_primary};
  text-align: left; letter-spacing: 0;
  margin-bottom: 30px;
}}
.elevation-chart {{
  background: transparent;
  border-radius: 0; padding: 30px 20px 20px;
  border: 1px solid color-mix(in srgb, {text_primary} 28%, transparent);
  text-align: center;
}}
.elevation-chart svg {{
  max-width: 100%;
}}

/* ---- 路线复盘 ---- */
.companion-section {{
  margin: 0;
  padding: 64px 120px;
  background: {dark};
  border-radius: 0;
  border-top: 1px solid color-mix(in srgb, {gold} 48%, transparent);
  text-align: left;
  position: relative;
}}
.companion-section::before {{
  content: 'AFTER ACTION';
  position: absolute; top: 28px; left: 120px;
  font-size: 12px; color: rgba(245,240,232,0.42);
  letter-spacing: 2px; font-family: inherit; line-height: 1;
}}
.companion-text {{
  font-size: 30px; color: {gold};
  font-style: normal; letter-spacing: 0;
  line-height: 1.6; font-weight: 900;
}}

/* ---- 页脚 ---- */
.footer {{
  padding: 60px 120px 80px;
  text-align: center;
  background: {cream};
}}
.footer-hashtags {{
  font-size: 16px; color: {pine};
  letter-spacing: 2px; line-height: 2.4;
}}
.footer-divider {{
  width: 60px; height: 2px;
  background: {gold};
  margin: 30px auto;
  opacity: 0.5;
}}
.footer-logo {{
  font-size: 14px; color: {mineral};
  letter-spacing: 4px;
}}
</style>
</head>
<body>

<!-- 封面头图 -->
<div class="hero">
  <img src="{hero_photo}" alt="{route_name}最高点">
  <div class="hero-overlay"></div>
  <div class="hero-stamp">{visual_treatment}</div>
  <div class="hero-title-wrap">
    <div class="hero-title">{route_name}</div>
    <div class="hero-sub">{intro_meta}</div>
  </div>
  <div class="hero-dossier">
    <strong>FIELD DOSSIER</strong><br>
    路线：{route_name}<br>
    情绪：{' / '.join(source_constraints.get('mood', ['真实记录']))}<br>
    数据源：GPX / EXIF / SRTM
  </div>
</div>

<!-- 引导语 -->
<div class="intro">
  <p class="intro-meta">
    {intro_meta_html}
  </p>
  <p class="intro-quote">
    {content.get("trail_summary", story)}
  </p>
</div>

<!-- 数据卡片 -->
<div class="stats-section">
  <div class="stats-grid">
    <div class="stat-card">
      <div class="icon">KM</div>
      <div class="value">{stats["distance"]}</div>
      <div class="label">总 距 离</div>
    </div>
    <div class="stat-card">
      <div class="icon">UP</div>
      <div class="value">{stats["elevation_gain"]}</div>
      <div class="label">累 计 爬 升</div>
    </div>
    <div class="stat-card">
      <div class="icon">HR</div>
      <div class="value">{stats["duration"]}</div>
      <div class="label">总 用 时</div>
    </div>
    <div class="stat-card">
      <div class="icon">TOP</div>
      <div class="value">{stats["max_elevation"]}</div>
      <div class="label">最高海拔</div>
    </div>
  </div>
</div>

<!-- Section divider -->
<div class="section-divider">
  <span class="line"></span><span class="dot"></span><span class="line"></span>
</div>

<!-- 正文故事 -->
<div class="story-section">
{story_html}
</div>

<!-- Section divider -->
<div class="section-divider">
  <span class="line"></span><span class="dot"></span><span class="line"></span>
</div>

<!-- 照片配图 -->
<div class="photo-blocks">
{photo_sections}
</div>

<!-- 海拔剖面 -->
<div class="elevation-section">
  <div class="elevation-title">▎海拔剖面 · {route_name}</div>
  <div class="elevation-chart">
    {elev_svg}
  </div>
</div>

<!-- 路线复盘 -->
<div class="companion-section">
  <p class="companion-text">{content.get("post_hike_review", "真实记录")}</p>
</div>

<!-- 页脚 -->
<div class="footer">
  <p class="footer-hashtags">
    {hashtags_html}
  </p>
  <div class="footer-divider"></div>
  <p class="footer-logo">{team_name} · 山野路迹 · 记录每一步</p>
</div>

</body>
</html>"""
    return html


def main():
    route, content = load_data()
    html = build_html(route, content)
    path = os.path.join(OUTPUT, "trail_wechat.html")
    with open(path, "w") as f:
        f.write(html)
    print(f"山野路迹 · 公众号推送")
    print(f"  ✓ trail_wechat.html ({len(html):,} bytes)")
    print(f"  配色：{tokens.hex('pine')} / {tokens.hex('earth_gold')} / {tokens.hex('cream')}")
    print(f"  结构：封面头图 → 引导语 → 数据卡片 → 故事正文 → 配图×6 → 海拔剖面 → 路线复盘 → 页脚")


if __name__ == "__main__":
    main()
