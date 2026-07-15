#!/usr/bin/env python3
"""Generate design_constraints.json from local TT expert packs.

The script intentionally stores package IDs and relative file paths only. It
does not write the user's absolute expert-pack path into generated artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
REFERENCES = Path(os.environ.get("SHANYE_REFERENCES_ROOT", BASE_DIR / "references"))
OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE_DIR / "output"))
import sys

sys.path.insert(0, str(BASE_DIR / "scripts"))
from platform_utils import CSS_FONT_STACK, preferred_chinese_font_family

ROLE_KEYS = ["ui", "xiaohongshu", "ardot", "web"]
FORBIDDEN_VISIBLE_PHRASES = [
    "现场照片和路线数据对得上",
    "现场照片和路线数据对的上",
    "路线数据对得上",
    "此刻在路线上的位置",
    "证明真的上来了",
]
INTERNAL_ROLE_LABELS = {"路线说明", "节点记录"}


ROLE_DEFS = {
    "ui": {
        "display_name": "UI 设计师",
        "markers": ["UI设计师", "design-experience"],
        "files": [
            "agents/ui-ux-designer.md",
            "agents/accessibility-specialist.md",
        ],
        "keywords": [
            "visual hierarchy",
            "design systems",
            "accessibility",
            "responsive",
            "brand identity",
            "usability",
        ],
    },
    "xiaohongshu": {
        "display_name": "小红书运营专家",
        "markers": ["小红书", "xiaohongshu"],
        "files": [
            "agents/xiaohongshu-operations-expert.md",
            "skills/xiaohongshu/SKILL.md",
            "skills/humanizer/SKILL.md",
            "skills/anti-distill/SKILL.md",
        ],
        "keywords": [
            "aesthetic consistency",
            "authentic storytelling",
            "shareable",
            "lifestyle",
            "hashtags",
            "community",
        ],
    },
    "ardot": {
        "display_name": "Ardot 设计专家",
        "markers": ["Ardot", "ardot"],
        "files": [
            "rules/design-rules.md",
            "rules/style-guide.md",
            "rules/style-guide-tags.md",
            "skills/ardot-design-assistant/SKILL.md",
        ],
        "keywords": [
            "validate",
            "capture_layout",
            "capture_screenshot",
            "meaningful name",
            "flexbox",
            "batch_edit",
        ],
    },
    "web": {
        "display_name": "现代 Web 开发专家",
        "markers": ["现代Web", "modern-webapp"],
        "files": [
            "rules/instruction.md",
            "skills/ui-ux-pro-max/SKILL.md",
            "skills/modern-web-app/SKILL.md",
        ],
        "keywords": [
            "design system",
            "responsive",
            "testing",
            "html-tailwind",
            "accessibility",
            "performance",
        ],
    },
}


PRODUCT_SOURCE_ROLES = {
    "poster_3d": ["ui", "xiaohongshu", "ardot", "web"],
    "magnet_3d": ["ui", "xiaohongshu", "ardot", "web"],
    "postcard": ["ui", "xiaohongshu", "ardot", "web"],
    "wechat_article": ["ui", "xiaohongshu", "ardot", "web"],
    "social_grid": ["ui", "xiaohongshu", "ardot", "web"],
    "ardot_board": ["ui", "xiaohongshu", "ardot", "web"],
}


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def discover_expert_root(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_root = os.environ.get("SHANYE_EXPERT_PACK_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    # The distributable skill ships with a complete expert pack under assets/expert.
    candidates.append(BASE_DIR / "assets" / "expert")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    searched = ", ".join(str(c) for c in candidates) if candidates else "(none)"
    raise FileNotFoundError(
        "No expert pack root found. The bundled pack should be at "
        f"{BASE_DIR / 'assets' / 'expert'}. Provide --expert-pack-root or set "
        f"SHANYE_EXPERT_PACK_ROOT to use another pack. Searched: {searched}"
    )


def find_package(root: Path, markers: list[str]) -> Path:
    marker_l = [m.lower() for m in markers]
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        name = child.name.lower()
        if any(marker in name for marker in marker_l):
            return child
    raise FileNotFoundError(f"Could not find expert package matching {markers}")


def select_excerpt(text: str, keywords: list[str], max_chars: int = 220) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lower_keywords = [k.lower() for k in keywords]
    for line in lines:
        low = line.lower()
        if any(k in low for k in lower_keywords):
            return line[:max_chars]
    return (lines[0] if lines else "")[:max_chars]


def load_expert_sources(root: Path) -> dict[str, Any]:
    roles: dict[str, Any] = {}
    for role, role_def in ROLE_DEFS.items():
        package_dir = find_package(root, role_def["markers"])
        files = []
        for rel in role_def["files"]:
            path = package_dir / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            trace_id = f"{role}:{rel}"
            files.append(
                {
                    "trace_id": trace_id,
                    "package_id": package_dir.name,
                    "file": rel,
                    "sha256": sha256_text(text),
                    "excerpt": select_excerpt(text, role_def["keywords"]),
                }
            )
        if not files:
            raise FileNotFoundError(f"No readable source files found for {role}")
        roles[role] = {
            "role": role,
            "display_name": role_def["display_name"],
            "package_id": package_dir.name,
            "files": files,
        }
    return roles


def source_refs(roles: dict[str, Any], role_names: list[str]) -> list[dict[str, Any]]:
    refs = []
    for role in role_names:
        role_data = roles[role]
        refs.append(
            {
                "role": role,
                "display_name": role_data["display_name"],
                "package_id": role_data["package_id"],
                "trace_ids": [item["trace_id"] for item in role_data["files"]],
            }
        )
    return refs


def expert_inputs_for_product(
    product_key: str,
    roles: dict[str, Any],
    summaries: dict[str, str],
) -> dict[str, Any]:
    result = {}
    for role in PRODUCT_SOURCE_ROLES[product_key]:
        role_data = roles[role]
        result[role] = {
            "summary": summaries[role],
            "source": {
                "package_id": role_data["package_id"],
                "trace_ids": [item["trace_id"] for item in role_data["files"]],
                "files": [item["file"] for item in role_data["files"]],
            },
        }
    return result


def local_date(route: dict[str, Any]) -> str:
    start_time = route.get("start_time", "")
    try:
        dt = datetime.fromisoformat(start_time).astimezone(timezone(timedelta(hours=8)))
        return dt.strftime("%Y.%m.%d")
    except Exception:
        return ""


def duration_compact(route: dict[str, Any]) -> str:
    seconds = float(route.get("duration_seconds", 0))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}H{minutes:02d}M"


def display_duration(route: dict[str, Any]) -> str:
    seconds = float(route.get("duration_seconds", 0))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours:
        return f"{hours}小时{minutes}分"
    return f"{minutes}分钟"


def split_hashtags(content: dict[str, Any], route_name: str, place_name: str, team_name: str) -> list[str]:
    raw = content.get("hashtags") or []
    if isinstance(raw, str):
        raw = raw.replace("，", ",").replace("、", ",").split(",")
    tags: list[str] = []
    for item in [*raw, place_name, route_name, "徒步", team_name, "户外记录"]:
        value = str(item).strip().replace(" ", "")
        if not value or value.lower() in {"none", "无"}:
            continue
        tag = value if value.startswith("#") else f"#{value}"
        if tag not in tags:
            tags.append(tag)
    return tags[:8]


def photo_stem(item: dict[str, Any]) -> str:
    return Path(str(item.get("filename", ""))).stem


def jpeg_name(item: dict[str, Any]) -> str:
    return f"{photo_stem(item)}.jpg"


def clean_visible_copy(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        if phrase and phrase in text:
            return fallback
    return text or fallback


def clean_role_label(value: Any) -> str:
    text = clean_visible_copy(value, "")
    if text in INTERNAL_ROLE_LABELS:
        return ""
    return text


def sanitize_social_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_subline: dict[str, int] = {}
    sanitized = []
    for idx, card in enumerate(cards):
        item = dict(card)
        fallback_caption = f"现场 {idx + 1:02d}"
        item["caption"] = clean_visible_copy(item.get("caption"), fallback_caption)
        item["headline"] = clean_visible_copy(item.get("headline"), item["caption"])
        item["subline"] = clean_visible_copy(item.get("subline"), "")
        item["photo_role"] = clean_role_label(item.get("photo_role"))
        item["show_role"] = bool(item.get("show_role", False) and item["photo_role"])
        item["footer_text"] = clean_visible_copy(item.get("footer_text"), "")
        if item["subline"]:
            seen_subline[item["subline"]] = seen_subline.get(item["subline"], 0) + 1
            if seen_subline[item["subline"]] > 1:
                item["subline"] = ""
        sanitized.append(item)
    return sanitized


def sorted_matched_photos() -> list[dict[str, Any]]:
    matched = read_json(REFERENCES / "matched_photos.json", {})
    photos = [
        item for item in matched.get("photos", [])
        if item.get("filename") and item.get("match_point") and item.get("match_method") != "manual"
    ]
    photos.sort(key=lambda item: item.get("match_point", {}).get("cumulative_distance_m", 0))
    return photos


def style_profile_from_mood(mood: list[Any]) -> dict[str, Any]:
    """Select product style variants from user mood and keep them script-readable."""
    mood_text = " ".join(str(item).lower() for item in mood)
    if any(word in mood_text for word in ["硬核", "狼狈", "强度", "虐", "hard", "grit"]):
        return {
            "family": "gritty_expedition_archive",
            "poster_variant": "expedition_dashboard",
            "postcard_variant": "film_ticket",
            "texture_level": "high",
            "data_density": "high",
            "layout_energy": "angular",
            "rationale": "用户情绪偏硬核和狼狈，视觉应更像行动档案、胶片票根和粗粝路书，而不是安静治愈模板。",
        }
    if any(word in mood_text for word in ["轻松", "治愈", "舒服", "松弛", "relax", "healing"]):
        return {
            "family": "soft_photo_journal",
            "poster_variant": "photo_journal_terrain",
            "postcard_variant": "field_note",
            "texture_level": "medium",
            "data_density": "medium",
            "layout_energy": "open",
            "rationale": "用户情绪偏轻松治愈，视觉应增加照片呼吸感、手账感和温和纸本质地。",
        }
    if any(word in mood_text for word in ["孤独", "壮阔", "史诗", "辽阔", "epic", "solitary"]):
        return {
            "family": "museum_topographic_case",
            "poster_variant": "museum_terrain_case",
            "postcard_variant": "museum_specimen",
            "texture_level": "medium",
            "data_density": "low",
            "layout_energy": "monumental",
            "rationale": "用户情绪偏壮阔和纪念，视觉应像地形馆藏和标本卡，减少噪声，放大路线仪式感。",
        }
    return {
        "family": "field_dossier",
        "poster_variant": "terrain_control_console",
        "postcard_variant": "trail_permit_pass",
        "texture_level": "medium",
        "data_density": "medium",
        "layout_energy": "balanced",
        "rationale": "未出现强风格情绪，使用稳定的山野档案风作为默认骨架。",
    }


def pick_photo_samples(photos: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if not photos:
        return []
    if len(photos) <= count:
        return photos
    picks = []
    used: set[int] = set()
    for i in range(count):
        idx = round(i * (len(photos) - 1) / max(count - 1, 1))
        while idx in used and idx + 1 < len(photos):
            idx += 1
        while idx in used and idx - 1 >= 0:
            idx -= 1
        used.add(idx)
        picks.append(photos[idx])
    return picks


def nearest_photo_to_highest(photos: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not photos:
        return None
    return max(photos, key=lambda item: item.get("match_point", {}).get("ele", 0) or 0)


def build_social_cards(
    photos: list[dict[str, Any]],
    *,
    route_name: str,
    team_name: str,
    place_name: str,
    mood_text: str,
    dist_km: float,
    duration: str,
    max_elev: int,
) -> list[dict[str, Any]]:
    samples = pick_photo_samples(photos, 9)
    card_scripts = [
        {
            "archetype": "cover_burst",
            "headline": f"{route_name}|真实记录",
            "subline": "不是攻略，是现场",
            "caption_template": "开走",
            "sticker": "开走",
            "data_focus": "route_summary",
            "show_data": True,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "封面只讲路线与完成感，快速建立收藏入口。",
        },
        {
            "archetype": "route_ticket",
            "headline": "路线小票",
            "subline": "先把这张票收好",
            "caption_template": "开始进山",
            "sticker": "START",
            "data_focus": "distance_only",
            "show_data": True,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "用票据感解释起步，不重复全局信息。",
        },
        {
            "archetype": "climb_note",
            "headline": "路况开始|不客气",
            "subline": "脚下变碎，节奏也变慢",
            "caption_template": "别急，先稳住",
            "sticker": "01",
            "data_focus": "none",
            "show_data": False,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "第三张从数据说明转向现场体感。",
        },
        {
            "archetype": "grit_snapshot",
            "headline": "过程开始|上强度",
            "subline": "山风很好，腿不太同意",
            "caption_template": "{km:.1f}km，已经不好装轻松",
            "sticker": "HARD MODE",
            "data_focus": "distance_elevation",
            "show_data": False,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "用一句真实吐槽承接用户给的硬核和狼狈。",
        },
        {
            "archetype": "grit_snapshot",
            "headline": "继续往前",
            "subline": "狼狈归狼狈，风景没输",
            "caption_template": "喘气时刻",
            "sticker": "KEEP GOING",
            "data_focus": "elevation_only",
            "show_data": True,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "第五张减少文字，把海拔作为情绪锚点。",
        },
        {
            "archetype": "lookback_split",
            "headline": "回头看|刚走过的线",
            "subline": "原来刚才那段这么长",
            "caption_template": "回望来路",
            "sticker": "LOOK BACK",
            "data_focus": "distance_only",
            "show_data": True,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "第六张把轨迹和照片建立关系，但不说教。",
        },
        {
            "archetype": "ridge_frame",
            "headline": "路上的|开阔时刻",
            "subline": "这一眼，值得停一下",
            "caption_template": "山脊亮了一下",
            "sticker": "RIDGE",
            "data_focus": "none",
            "show_data": False,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "第七张给照片呼吸，避免信息持续堆叠。",
        },
        {
            "archetype": "summit_proof",
            "headline": "{ele}m",
            "subline": "风大，腿酸，但人到了",
            "caption_template": "最高点附近",
            "sticker": "TOP POINT",
            "data_focus": "max_elevation",
            "show_data": False,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "最高点用大数字表达，不再加证明式说明。",
        },
        {
            "archetype": "finish_receipt",
            "headline": "硬核、狼狈|但开心",
            "subline": f"{team_name} / {place_name}",
            "caption_template": "收队复盘",
            "sticker": "DONE",
            "data_focus": "finish_summary",
            "show_data": True,
            "show_role": False,
            "photo_role": "",
            "footer_text": "",
            "layout_note": "最后一张集中承载情绪关键词，其他卡不重复。",
        },
    ]
    cards: list[dict[str, Any]] = []
    for idx, item in enumerate(samples):
        script = card_scripts[min(idx, len(card_scripts) - 1)]
        stem = photo_stem(item)
        mp = item.get("match_point", {})
        km = float(mp.get("cumulative_distance_m", 0) or 0) / 1000
        ele = int(round(float(mp.get("ele", 0) or 0)))
        caption = script["caption_template"].format(km=km, ele=ele, route_name=route_name)
        headline = script["headline"].format(km=km, ele=ele, route_name=route_name)
        subline = script["subline"].format(km=km, ele=ele, route_name=route_name)
        cards.append(
            {
                "photo": stem,
                "caption": caption,
                "archetype": script["archetype"],
                "headline": headline,
                "subline": subline,
                "sticker": script["sticker"],
                "data_focus": script["data_focus"],
                "show_data": script["show_data"],
                "show_role": script["show_role"],
                "photo_role": script["photo_role"],
                "footer_text": script["footer_text"],
                "layout_note": script["layout_note"],
                "crop": "center",
            }
        )
    return sanitize_social_cards(cards)


def build_constraints(roles: dict[str, Any], root_name: str = "expert-pack-root") -> dict[str, Any]:
    route = read_json(REFERENCES / "route_data.json", {})
    content = read_json(REFERENCES / "content_assets.json", {})

    route_name = content.get("route_name") or content.get("trail_title") or Path(str(route.get("file", "路线纪念"))).stem or "路线纪念"
    place_name = content.get("place_name") or content.get("activity_name") or "徒步路线"
    team_name = content.get("team_name") or "山野路迹"
    mood = content.get("mood") or ["真实记录"]
    if isinstance(mood, str):
        mood = [mood]
    mood_text = "、".join(str(item) for item in mood if str(item).strip()) or "真实记录"
    style_profile = style_profile_from_mood(mood)
    date_str = local_date(route)
    dist_km = float(route.get("total_distance_km", 0))
    gain_m = int(route.get("elevation_gain", route.get("elevation_range", 0)))
    max_elev = int(route.get("max_elevation", 0))
    duration = duration_compact(route)
    duration_text = display_duration(route)
    hashtags = split_hashtags(content, route_name, place_name, team_name)
    matched_photos = sorted_matched_photos()
    social_cards = build_social_cards(
        matched_photos,
        route_name=route_name,
        team_name=team_name,
        place_name=place_name,
        mood_text=mood_text,
        dist_km=dist_km,
        duration=duration,
        max_elev=max_elev,
    )
    story_photos = [
        {"filename": jpeg_name(item), "caption": card["caption"]}
        for item, card in zip(pick_photo_samples(matched_photos, 6), social_cards[:6])
    ]
    hero_photo = nearest_photo_to_highest(matched_photos)
    hero_photo_name = jpeg_name(hero_photo) if hero_photo else "highest_elevation_photo"

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    common_style_sources = source_refs(roles, ["ui", "xiaohongshu", "web"])
    ardot_sources = source_refs(roles, ["ardot", "ui", "web"])

    constraints: dict[str, Any] = {
        "version": "1.1",
        "generated_at": generated_at,
        "generated_by": "local TT expert packs -> generate_design_constraints_from_experts.py",
        "expert_pack": {
            "status": "generated_from_local_expert_pack",
            "root_name": root_name,
            "roles": {
                role: {
                    "display_name": data["display_name"],
                    "package_id": data["package_id"],
                    "files": [
                        {
                            "trace_id": item["trace_id"],
                            "file": item["file"],
                            "sha256": item["sha256"],
                        }
                        for item in data["files"]
                    ],
                }
                for role, data in roles.items()
            },
        },
        "source": {
            "route_name": route_name,
            "place_name": place_name,
            "team_name": team_name,
            "mood": mood,
            "slogan": "",
            "data_policy": {
                "elevation_gain": "max_elevation_minus_min_elevation",
                "use_only_gpx_exif_srtm_facts": True,
            },
        },
        "global": {
            "visual_family": "山野档案 × 纸雕地形纪念物",
            "keywords": ["真实记录", *mood[:3], "可收藏"],
            "palette_strategy": {
                "brand_anchor": ["route_line", "team_signature"],
                "photo_adaptive_color": True,
                "avoid_monotone": True,
                "default_brand_tokens": {
                    "pine": "#6d8b5e",
                    "mineral": "#5a7a6a",
                    "earth_gold": "#c4a87a",
                    "accent": "#e07b3c",
                    "warm_sand": "#e8dfd3",
                    "cream": "#f5f0e8",
                    "dark": "#1a1a1a",
                },
            },
            "typography": {
                "zh": preferred_chinese_font_family(),
                "zh_stack": CSS_FONT_STACK,
                "latin": "Inter",
                "policy": "use platform_utils.py; Windows prefers Microsoft YaHei, macOS prefers PingFang/Hiragino, Linux prefers Noto/Source Han",
            },
            "style_tokens": {
                "art_direction": "field_dossier",
                "surface_strategy": "dark_field_board_with_cream_evidence_panels",
                "shape_language": ["斜切裁片", "测绘边框", "路线证据条", "低圆角信息铭牌"],
                "texture_language": ["实拍照片压暗", "等高线细纹", "档案编号", "户外通行证"],
                "style_profile": style_profile,
                "source": common_style_sources,
            },
            "avoid": [
                "网页截图感",
                "过度文艺化",
                "把专家意见只写成说明",
                "冰箱贴文字压到山体浮雕上",
                "社交组图每张都堆同一组全局数据",
            ],
        },
        "products": {},
    }

    summaries = {
        "ui": "以设计系统、信息层级、可访问性和跨品类一致性为优先，把文创设计成可识别的山野档案系统。",
        "xiaohongshu": "以真实记录、可收藏、可分享为核心，九宫格采用现场感叙事和统一审美，避免营销腔。",
        "ardot": "把每个产物作为独立作品板对象，明确命名、布局、验证和交付路径，便于 Ardot 中单独构建。",
        "web": "把专家意图转译为可参数化的 HTML/CSS/Canvas/Three.js/STL 约束，先设计系统后脚本实现。",
    }

    def visual_source(roles_for_product: list[str], rationale: str) -> dict[str, Any]:
        return {"rationale": rationale, "source": source_refs(roles, roles_for_product)}

    constraints["products"]["poster_3d"] = {
        "expert_inputs": expert_inputs_for_product("poster_3d", roles, summaries),
        "composition": {
            "layout": "terrain_viewer_left_data_panel_right",
            "style_variant": style_profile["poster_variant"],
            "terrain_crop": "expanded_context_with_soft_edge",
            "panel_density": "high_density_expedition" if style_profile["data_density"] == "high" else "compact_archive",
            "palette_strategy": {
                "brand_anchor": ["route_line_gold", "team_signature_pine"],
                "product_palette": {
                    "background": "#15100c" if style_profile["poster_variant"] == "expedition_dashboard" else "#10120f",
                    "panel": "#efe3cc" if style_profile["poster_variant"] == "expedition_dashboard" else "#f1eadc",
                    "panel_ink": "#21160f" if style_profile["poster_variant"] == "expedition_dashboard" else "#181a14",
                    "terrain_low": "#4b4d34" if style_profile["poster_variant"] == "expedition_dashboard" else "#3d5233",
                    "terrain_high": "#e3b55d" if style_profile["poster_variant"] == "expedition_dashboard" else "#d6bd76",
                    "terrain_edge": "#a97042" if style_profile["poster_variant"] == "expedition_dashboard" else "#b99e7a",
                    "terrain_side": "#563728" if style_profile["poster_variant"] == "expedition_dashboard" else "#63482e",
                    "route_line_gold": "#f0a33a" if style_profile["poster_variant"] == "expedition_dashboard" else "#c49a45",
                    "accent": "#d9472e" if style_profile["poster_variant"] == "expedition_dashboard" else "#e07b3c",
                },
                "rationale": f"3D 小报采用 {style_profile['poster_variant']}：{style_profile['rationale']}",
            },
            "visual_treatment": style_profile["poster_variant"],
            "visual_treatment_source": visual_source(
                ["ui", "xiaohongshu", "ardot", "web"],
                "UI 专家要求信息层级和设计系统一致；小红书专家要求首屏具备真实记录的分享感；Web 专家要求可实现、可截图；Ardot 专家要求产物作为作品板主视觉源可被验证。",
            ),
        },
        "visual_differentiators": [
            "暗色测绘台上的纸雕地形模型",
            "右侧控制台式路线档案面板",
            "照片标记作为地形上的证据点",
        ],
        "copy_strategy": {
            "title": route_name,
            "place_label": place_name,
            "team_label": team_name,
            "story_quote": content.get("hike_story", mood_text),
        },
        "script_hooks": {
            "style_variant": style_profile["poster_variant"],
            "texture_level": style_profile["texture_level"],
            "data_density": style_profile["data_density"],
            "layout_energy": style_profile["layout_energy"],
            "terrain_pad_ratio": 0.32 if style_profile["poster_variant"] == "expedition_dashboard" else 0.28,
            "show_photo_strip": True,
            "product_palette": {
                "background": "#15100c" if style_profile["poster_variant"] == "expedition_dashboard" else "#10120f",
                "panel": "#efe3cc" if style_profile["poster_variant"] == "expedition_dashboard" else "#f1eadc",
                "panel_ink": "#21160f" if style_profile["poster_variant"] == "expedition_dashboard" else "#181a14",
                "terrain_low": "#4b4d34" if style_profile["poster_variant"] == "expedition_dashboard" else "#3d5233",
                "terrain_high": "#e3b55d" if style_profile["poster_variant"] == "expedition_dashboard" else "#d6bd76",
                "terrain_edge": "#a97042" if style_profile["poster_variant"] == "expedition_dashboard" else "#b99e7a",
                "terrain_side": "#563728" if style_profile["poster_variant"] == "expedition_dashboard" else "#63482e",
                "route_line_gold": "#f0a33a" if style_profile["poster_variant"] == "expedition_dashboard" else "#c49a45",
                "accent": "#d9472e" if style_profile["poster_variant"] == "expedition_dashboard" else "#e07b3c",
            },
            "visual_treatment": style_profile["poster_variant"],
        },
        "acceptance_checks": [
            "暗色背景无云粒子脏斑",
            "右侧控制台不遮挡地形主体",
            "路线数据均来自 GPX 或 SRTM",
        ],
    }

    constraints["products"]["magnet_3d"] = {
        "expert_inputs": expert_inputs_for_product("magnet_3d", roles, summaries),
        "composition": {
            "primary_shape": "hexagon",
            "base_structure": "outer_rim_with_center_recess",
            "relief_boundary": "inside_cutout",
            "text_zone": "outer_rim",
            "palette_strategy": {
                "brand_anchor": ["engraved_route_text"],
                "product_palette": {
                    "base_material": "#d9c48a",
                    "relief_low": "#c8d194",
                    "relief_high": "#f0e2af",
                    "edge": "#c0a66f",
                    "preview_bg": "#e8dfd3",
                    "trail": "#e07b3c",
                    "text": "#3d5233",
                    "muted_text": "#5a7a6a",
                },
                "rationale": "冰箱贴以 3D 打印材质色为主，不套网页配色；颜色只影响预览和 Ardot 呈现。",
            },
            "visual_treatment": "printed_terrain_badge",
            "visual_treatment_source": visual_source(
                ["ui", "xiaohongshu", "ardot", "web"],
                "UI 专家定义徽章式收藏物；小红书专家强调可拍照传播；Web/STL 专家把它约束为可打印几何结构；Ardot 专家要求预览与文件清单可展示。",
            ),
        },
        "visual_differentiators": [
            "六边形户外徽章轮廓",
            "中心山体浮雕使用外扩地形后裁切",
            "底座肩部抬高，避免山体边缘生硬断开",
            "外圈文字采用加粗凹刻信息铭牌，适配 FDM/光固化打印",
            "轨迹管道细化为贴地细线，避免压住山体纹理",
        ],
        "copy_strategy": {
            "edge_labels": [
                "route_name",
                "team_name",
                "date",
                "distance",
                "elevation_gain",
                "duration_max_elevation",
            ]
        },
        "script_hooks": {
            "coordinate_mode": "auto",
            "base_cutout": True,
            "text_outside_relief": True,
            "text_mode": "engraved_recess",
            "text_engrave_depth_mm": 0.85,
            "text_bold_offset_mm": 0.12,
            "text_route_height_mm": 3.6,
            "text_field_height_mm": 3.05,
            "trail_tube_radius_mm": 0.38,
            "timestamp_exports": True,
            "relief_edge_transition": "raised_base_shoulder",
            "product_palette": {
                "base_material": "#d9c48a",
                "relief_low": "#c8d194",
                "relief_high": "#f0e2af",
                "edge": "#c0a66f",
                "preview_bg": "#e8dfd3",
                "trail": "#e07b3c",
                "text": "#3d5233",
                "muted_text": "#5a7a6a",
            },
            "visual_treatment": "printed_terrain_badge",
        },
        "acceptance_checks": [
            "中心浮雕不与底座实体顶面重叠",
            "文字全部位于中心浮雕边界外，且以凹刻方式进入底座",
            "轨迹线不粗于 0.8mm 直径，不喧宾夺主",
            "常规 STL/OBJ 和时间戳 STL/OBJ 同时存在",
        ],
    }

    constraints["products"]["postcard"] = {
        "expert_inputs": expert_inputs_for_product("postcard", roles, summaries),
        "composition": {
            "front": "trail_permit_pass_with_photo_cut",
            "back": "field_log_postcard",
            "style_variant": style_profile["postcard_variant"],
            "palette_strategy": {
                "brand_anchor": ["gold_route_data"],
                "product_palette": {
                    "front_bg": "#17110d" if style_profile["postcard_variant"] == "film_ticket" else "#0f1117",
                    "front_text": "#fff4dd" if style_profile["postcard_variant"] == "film_ticket" else "#f5f0e8",
                    "stamp": "#f0a33a" if style_profile["postcard_variant"] == "film_ticket" else "#d6a84f",
                    "back_bg": "#efe1c8" if style_profile["postcard_variant"] == "film_ticket" else "#f4efe4",
                    "back_ink": "#2b1d13" if style_profile["postcard_variant"] == "film_ticket" else "#273128",
                    "route_line_light": "#fff1cb" if style_profile["postcard_variant"] == "film_ticket" else "#fff8e5",
                    "route_line_dark": "#21160f" if style_profile["postcard_variant"] == "film_ticket" else "#171b14",
                },
                "rationale": f"明信片采用 {style_profile['postcard_variant']}：{style_profile['rationale']}",
            },
            "visual_treatment": style_profile["postcard_variant"],
            "visual_treatment_source": visual_source(
                ["ui", "xiaohongshu", "ardot", "web"],
                "UI 专家要求标题/数据/照片分层；小红书专家要求实拍图能被分享；Web 专家要求模板参数化；Ardot 专家要求正反两面可独立展示。",
            ),
        },
        "visual_differentiators": [
            "正面像一张山野通行证而不是普通照片明信片",
            "照片被切成斜切证件照，左侧为路线许可信息区",
            "轨迹图透明叠在照片上, 按照片亮度自动切换浅色/深色线",
            "背面像行后记录单，海拔剖面和留言区有明确分区",
        ],
        "copy_strategy": {
            "title_tag": place_name,
            "title_main": route_name,
            "title_en": f"{route_name} ARCHIVE".upper(),
            "back_story": content.get(
                "hike_story",
                f"这是一段关于{route_name}的真实记录。全程{dist_km:.2f}公里，用时{duration_text}，整体情绪是{mood_text}。",
            ),
        },
        "script_hooks": {
            "hero_photo": "highest_elevation_photo",
            "style_variant": style_profile["postcard_variant"],
            "texture_level": style_profile["texture_level"],
            "data_density": style_profile["data_density"],
            "layout_energy": style_profile["layout_energy"],
            "trail_overlay_background": "transparent",
            "trail_color_mode": "adaptive_photo_luminance",
            "product_palette": {
                "front_bg": "#17110d" if style_profile["postcard_variant"] == "film_ticket" else "#0f1117",
                "front_text": "#fff4dd" if style_profile["postcard_variant"] == "film_ticket" else "#f5f0e8",
                "stamp": "#f0a33a" if style_profile["postcard_variant"] == "film_ticket" else "#d6a84f",
                "back_bg": "#efe1c8" if style_profile["postcard_variant"] == "film_ticket" else "#f4efe4",
                "back_ink": "#2b1d13" if style_profile["postcard_variant"] == "film_ticket" else "#273128",
                "route_line_light": "#fff1cb" if style_profile["postcard_variant"] == "film_ticket" else "#fff8e5",
                "route_line_dark": "#21160f" if style_profile["postcard_variant"] == "film_ticket" else "#171b14",
            },
            "visual_treatment": style_profile["postcard_variant"],
        },
        "acceptance_checks": [
            "正面标题不遮挡照片主体",
            "背面故事不编造用户未提供内容",
        ],
    }

    constraints["products"]["wechat_article"] = {
        "expert_inputs": expert_inputs_for_product("wechat_article", roles, summaries),
        "composition": {
            "sequence": ["hero", "intro", "stats", "story", "photos", "profile", "review", "footer"],
            "hero_photo": hero_photo_name,
            "palette_strategy": {
                "brand_anchor": ["profile_line_gold"],
                "product_palette": {
                    "page_bg": "#f2eadb",
                    "paper": "#fffaf0",
                    "ink": "#1f241d",
                    "muted": "#6f765e",
                    "rule": "#b49a66",
                    "alert": "#b65f3a",
                },
                "rationale": "公众号像纸本文档和行后复盘，避免和 3D 小报同一暗色控制台。",
            },
            "visual_treatment": "field_dossier_article",
            "visual_treatment_source": visual_source(
                ["ui", "xiaohongshu", "ardot", "web"],
                "小红书专家要求真实记录和现场感；UI 专家把长图改为档案阅读节奏；Web 专家负责稳定截图；Ardot 专家确保可放入作品板。",
            ),
        },
        "visual_differentiators": [
            "封面像一份徒步复盘档案，照片被压成现场证据",
            "数据区是测绘记录表，不再是圆角卡片",
            "照片段落采用交错的现场记录版式",
        ],
        "copy_strategy": {
            "intro_meta": f"{date_str} · {team_name} · {place_name}",
            "intro_quote_source": "trail_summary",
            "review_source": "post_hike_review",
            "hashtags": hashtags,
        },
        "script_hooks": {
            "visual_treatment": "field_dossier_article",
            "product_palette": {
                "page_bg": "#f2eadb",
                "paper": "#fffaf0",
                "ink": "#1f241d",
                "muted": "#6f765e",
                "rule": "#b49a66",
                "alert": "#b65f3a",
            },
            "photo_sequence": story_photos,
        },
        "acceptance_checks": [
            "章节顺序按复盘阅读路径展开",
            "hashtags 与用户要求一致或为中性户外标签",
        ],
    }

    xhs_grid_plan = {
        "strategy": "九宫格按小红书浏览节奏拆成封面钩子、路线解释、过程冲突、山脊大片、最高点时刻和终点复盘。",
        "source": source_refs(roles, ["xiaohongshu"]),
        "grid_rhythm": [
            "第 1 张必须在 1 秒内说明路线和情绪",
            "第 2 张解释路线数据, 降低陌生用户理解成本",
            "第 3-5 张制造真实过程和狼狈感",
            "第 6-8 张放大山脊、回望和最高点的收藏感",
            "第 9 张用完成感和团队署名收尾",
        ],
        "native_visual_cues": [
            "手机相册感满幅照片裁切",
            "路线小票",
            "轻量手账贴纸",
            "无照片边框",
            "半透明文字叠层",
            "团队名低透明水印",
            "手写短句",
            "少量真实数据, 不堆全局指标",
        ],
        "avoid": [
            "九张图同一暗色档案模板",
            "每张都用同样的信息栏",
            "把社交卡做成网页后台截图",
            "出现现场照片和路线数据对得上这类数据证明式文案",
            "轨迹图显示说明性标题",
            "照片外加相纸白边或厚边框",
            "团队名作为抢眼主标题",
            "营销腔标题",
        ],
        "cards": social_cards,
    }

    constraints["products"]["social_grid"] = {
        "expert_inputs": expert_inputs_for_product("social_grid", roles, summaries),
        "composition": {
            "grid_count": 9,
            "cover_hook": f"{route_name}九宫格：{dist_km:.2f}km / {duration}",
            "sequence_logic": "route_timeline",
            "palette_strategy": {
                "brand_anchor": ["small_team_signature"],
                "product_palette": {
                    "paper": "#fff7e8",
                    "ink": "#161711",
                    "ticket": "#f8e7c0",
                    "sticker_red": "#f05a3c",
                    "sticker_blue": "#2f6f8f",
                    "sticker_yellow": "#f0c75a",
                    "route_light": "#fff8e5",
                    "route_dark": "#171b14",
                },
                "rationale": "小红书组图要像照片手账和路线小票，允许更鲜明贴纸色，不能套暗色档案模板。",
            },
            "visual_treatment": "xhs_native_grid_story",
            "xhs_grid_plan": xhs_grid_plan,
            "visual_treatment_source": visual_source(
                ["ui", "xiaohongshu", "ardot", "web"],
                "小红书专家把九宫格拆成封面、路线解释、过程冲突、山脊大片、最高点时刻和终点复盘；UI 专家提供信息层级；Ardot 专家要求每张卡能作为独立作品对象展示；Web 专家把卡型导演表脚本化。",
            ),
        },
        "visual_differentiators": [
            "九张图使用不同卡型, 不再套同一个暗色档案模板",
            "封面、路线小票、狼狈现场、山脊大片、最高点时刻和收尾复盘各自承担传播任务",
            "轨迹图无深色背景块, 使用照片亮度自适应双描边路线",
            "轨迹浮层不显示说明性标题, 只留下路线和当前位置",
            "文字信息使用轻透明叠层, 照片不加边框, 团队名以水印融入画面",
            "标题像真实记录和手账标注, 不像旅游攻略",
        ],
        "copy_strategy": {
            "tone": "真实记录",
            "hashtags": hashtags,
            "cards": social_cards,
        },
        "script_hooks": {
            "visual_treatment": "xhs_native_grid_story",
            "trail_overlay_background": "transparent",
            "trail_color_mode": "adaptive_photo_luminance",
            "hide_trail_label": True,
            "remove_photo_borders": True,
            "text_scrim_opacity": 0.52,
            "data_scrim_opacity": 0.44,
            "team_watermark_opacity": 0.18,
            "metadata_integration": "small_inline_overlay_with_watermark_team",
            "forbidden_visible_phrases": [
                "现场照片和路线数据对得上",
                "路线数据对得上",
                "此刻在路线上的位置",
                "证明真的上来了",
            ],
            "product_palette": {
                "paper": "#fff7e8",
                "ink": "#161711",
                "ticket": "#f8e7c0",
                "sticker_red": "#f05a3c",
                "sticker_blue": "#2f6f8f",
                "sticker_yellow": "#f0c75a",
                "route_light": "#fff8e5",
                "route_dark": "#171b14",
            },
            "photo_picks": [card["photo"] for card in social_cards],
            "caption_map": {card["photo"]: card["caption"] for card in social_cards},
            "card_plan": social_cards,
        },
        "acceptance_checks": [
            "九张图顺序来自约束文件",
            "每张 caption 来自约束文件",
            "每张 archetype 来自小红书九宫格导演表",
            "不出现数据证明式文案或轨迹说明标题",
            "照片不加厚边框, 信息层为轻透明叠加",
            "团队名以低透明水印呈现, 不抢主视觉",
            "底部只显示当前位置数据",
        ],
    }

    constraints["products"]["ardot_board"] = {
        "expert_inputs": expert_inputs_for_product("ardot_board", roles, summaries),
        "composition": {
            "storyline": "input_to_expert_constraints_to_outputs",
            "separate_product_frames": True,
            "palette_strategy": {
                "brand_anchor": ["board_title", "route_metrics"],
                "product_palette": {
                    "board_bg": "#ede6da",
                    "frame_bg": "#fffaf0",
                    "ink": "#1f241d",
                    "accent": "#b49a66",
                },
                "rationale": "Ardot 作品板作为策展层保持克制纸本底色，突出各产物自己的风格差异。",
            },
            "visual_treatment": "expert_trace_product_board",
            "visual_treatment_source": visual_source(
                ["ui", "xiaohongshu", "ardot", "web"],
                "Ardot 专家要求节点命名、flex 布局、分批构建与截图验证；UI/Web 专家要求作品板呈现从专家约束到产物的因果链；小红书专家补充传播视角下的可读叙事。",
            ),
        },
        "visual_differentiators": [
            "展示专家约束如何影响每个产物",
            "每个产品有单独画板和交付文件清单",
        ],
        "copy_strategy": {
            "board_title": "山野路迹文创产物总览",
            "section_labels": ["路线事实", "专家约束", "文创产物", "迭代记录"],
        },
        "script_hooks": {"use_manifest": True, "visual_treatment": "expert_trace_product_board"},
        "acceptance_checks": [
            "每个产品单独画板",
            "冰箱贴清单包含时间戳 STL/OBJ",
            "TT 协同日志和设计约束可追溯",
        ],
    }

    constraints["expert_trace"] = {
        "roles": {
            role: {
                "package_id": data["package_id"],
                "evidence": [
                    {
                        "trace_id": item["trace_id"],
                        "file": item["file"],
                        "excerpt": item["excerpt"],
                    }
                    for item in data["files"]
                ],
            }
            for role, data in roles.items()
        },
        "decision_summary": [
            "UI 专家包提供设计系统、层级、可访问性和跨端一致性依据。",
            "小红书专家包提供真实记录、审美一致、可分享和话题策略依据。",
            "Ardot 专家包提供作品板构建、节点命名、布局验证和交付验证依据。",
            "现代 Web 专家包提供设计系统先行、响应式、截图和可参数化实现依据。",
        ],
    }

    return constraints


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate design constraints from local expert packs")
    parser.add_argument("--expert-pack-root", help="Directory containing local expert packages")
    parser.add_argument(
        "--output",
        default=str(OUTPUT / "design_constraints.json"),
        help="Output design_constraints.json path",
    )
    parser.add_argument(
        "--trace-output",
        default=str(OUTPUT / "expert_constraints_trace.json"),
        help="Output trace JSON path",
    )
    args = parser.parse_args()

    root = discover_expert_root(args.expert_pack_root)
    roles = load_expert_sources(root)
    constraints = build_constraints(roles, root.name)
    write_json(Path(args.output), constraints)
    write_json(
        Path(args.trace_output),
        {
            "generated_at": constraints["generated_at"],
            "expert_pack": constraints["expert_pack"],
            "expert_trace": constraints["expert_trace"],
            "products": {
                key: {
                    "visual_treatment": value["composition"].get("visual_treatment"),
                    "visual_treatment_source": value["composition"].get("visual_treatment_source"),
                    "expert_inputs": value.get("expert_inputs"),
                }
                for key, value in constraints["products"].items()
            },
        },
    )

    print("Generated design constraints from local expert packs")
    print(f"  root_name: {root.name}")
    for role in ROLE_KEYS:
        role_data = roles[role]
        print(f"  {role}: {role_data['package_id']} ({len(role_data['files'])} source file(s))")
    print(f"  output: {Path(args.output)}")
    print(f"  trace: {Path(args.trace_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
