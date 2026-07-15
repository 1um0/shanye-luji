#!/usr/bin/env python3
"""Prepare reusable content_assets.json from route facts and user-provided copy."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent.parent
REFERENCES = Path(os.environ.get("SHANYE_REFERENCES_ROOT", BASE / "references"))


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def split_list(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("，", ",").replace("、", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def local_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone(timedelta(hours=8))
        )
    except Exception:
        return None


def duration_display(seconds: float | int | None) -> str:
    seconds = float(seconds or 0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours:
        return f"{hours}小时{minutes}分"
    return f"{minutes}分钟"


def stats_display(route: dict[str, Any]) -> dict[str, str]:
    distance = float(route.get("total_distance_km", 0) or 0)
    gain = int(round(float(route.get("elevation_gain", route.get("elevation_range", 0)) or 0)))
    max_elev = int(round(float(route.get("max_elevation", 0) or 0)))
    duration = duration_display(route.get("duration_seconds", 0))
    start = local_dt(route.get("start_time"))
    end = local_dt(route.get("end_time"))
    speed = float(route.get("avg_speed_kmh", 0) or 0)
    return {
        "distance": f"{distance:.2f} km",
        "elevation_gain": f"{gain:,} m",
        "max_elevation": f"{max_elev:,} m",
        "duration": duration,
        "start_time": start.strftime("%H:%M") if start else "",
        "end_time": end.strftime("%H:%M") if end else "",
        "avg_speed": f"{speed:.2f} km/h" if speed else "",
        "peaks": "",
        "weather": "",
        "temperature": "",
    }


def default_hashtags(route_name: str, place_name: str, team_name: str) -> list[str]:
    tags = []
    for value in [place_name, route_name, "徒步", team_name, "户外记录"]:
        value = str(value).strip().replace(" ", "")
        if value and value not in {"无", "none", "None"}:
            tag = value if value.startswith("#") else f"#{value}"
            if tag not in tags:
                tags.append(tag)
    return tags[:8]


def build_assets(args: argparse.Namespace) -> dict[str, Any]:
    route = read_json(REFERENCES / "route_data.json", {})
    existing = read_json(REFERENCES / "content_assets.json", {})

    route_name = (
        args.route_name
        or existing.get("route_name")
        or existing.get("trail_title")
        or Path(str(route.get("file", "路线纪念"))).stem
        or "路线纪念"
    )
    place_name = args.place_name or existing.get("place_name") or existing.get("activity_name") or "徒步路线"
    team_name = args.team_name or existing.get("team_name") or "山野路迹"
    route_subtitle = args.route_subtitle or existing.get("route_subtitle", "")
    slogan = args.slogan if args.slogan is not None else existing.get("slogan", "")
    mood = split_list(args.mood) or existing.get("mood") or ["真实记录"]
    if isinstance(mood, str):
        mood = split_list(mood) or [mood]
    hashtags = split_list(args.hashtags) or existing.get("hashtags") or default_hashtags(route_name, place_name, team_name)
    xhs_style = args.xhs_style or existing.get("xhs_style") or "真实记录"
    forbidden = split_list(args.forbidden) or existing.get("forbidden_content") or []

    stats = stats_display(route)
    date = local_dt(route.get("start_time"))
    date_text = date.strftime("%Y年%m月%d日") if date else "这一天"
    date_short = date.strftime("%Y.%m.%d") if date else ""
    distance = stats["distance"].replace(" km", "公里")
    gain = stats["elevation_gain"].replace(" m", "米")
    max_elev = stats["max_elevation"].replace(" m", "米")
    duration = stats["duration"]
    mood_text = "、".join(mood)

    # Detect stale cached text: if route identity changed, regenerate auto-fields
    old_route = existing.get("route_name")
    old_place = existing.get("place_name")
    old_mood = "、".join(existing.get("mood") or [])
    route_changed = bool(old_route and old_route != route_name)
    place_changed = bool(old_place and old_place != place_name)
    mood_changed = bool(old_mood and old_mood != mood_text)
    stale = route_changed or place_changed or mood_changed

    trail_summary = args.trail_summary or (
        existing.get("trail_summary") if not stale else None
    ) or (
        f"{date_text}，{team_name}在{place_name}完成{route_name}，"
        f"全程{distance}，用时{duration}，海拔跨度{gain}，最高点{max_elev}。"
        f"整体情绪是{mood_text}。"
    )
    hike_story = args.hike_story or (
        existing.get("hike_story") if not stale else None
    ) or (
        f"这是一段关于{route_name}的真实记录。"
        f"{date_text}的山路、照片和脚步一起留下了{mood_text}。"
    )
    post_hike_review = args.post_hike_review or (
        existing.get("post_hike_review") if not stale else None
    ) or mood_text
    companion_message = args.companion_message or existing.get("companion_message", "")
    postcard_text = args.postcard_text or (
        existing.get("postcard_text") if not stale else None
    ) or (
        f"走完{route_name}，把{mood_text}留在路上。\n"
        f"——{team_name} · {place_name}" + (f" · {date_short}" if date_short else "")
    )
    social_copy = args.social_copy or (
        existing.get("social_copy") if not stale else None
    ) or (
        f"{route_name}{xhs_style}。\n\n"
        f"{stats['distance']}，{duration}，最高{stats['max_elevation']}。{mood_text}。\n\n"
        + " ".join(hashtags)
    )
    magnet_text = args.magnet_text or (
        existing.get("magnet_text") if not stale else None
    ) or route_name

    return {
        "generated_at": datetime.now().date().isoformat(),
        "route_name": route_name,
        "route_subtitle": route_subtitle,
        "place_name": place_name,
        "activity_name": place_name,
        "team_name": team_name,
        "slogan": slogan,
        "mood": mood,
        "xhs_style": xhs_style,
        "hashtags": hashtags,
        "forbidden_content": forbidden,
        "trail_title": route_name,
        "trail_summary": trail_summary,
        "hike_story": hike_story,
        "companion_message": companion_message,
        "postcard_text": postcard_text,
        "social_copy": social_copy,
        "magnet_text": args.magnet_text or existing.get("magnet_text") or route_name,
        "post_hike_review": post_hike_review,
        "photo_highlights": existing.get("photo_highlights", []),
        "stats_display": stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-name")
    parser.add_argument("--route-subtitle")
    parser.add_argument("--place-name")
    parser.add_argument("--team-name")
    parser.add_argument("--slogan")
    parser.add_argument("--mood", help="comma-separated mood keywords")
    parser.add_argument("--xhs-style")
    parser.add_argument("--hashtags", help="comma-separated hashtags")
    parser.add_argument("--forbidden", help="comma-separated content that must not be shown")
    parser.add_argument("--trail-summary")
    parser.add_argument("--hike-story")
    parser.add_argument("--post-hike-review")
    parser.add_argument("--companion-message")
    parser.add_argument("--postcard-text")
    parser.add_argument("--social-copy")
    parser.add_argument("--magnet-text")
    args = parser.parse_args()

    assets = build_assets(args)
    output = REFERENCES / "content_assets.json"
    write_json(output, assets)
    try:
        display_path = output.relative_to(BASE)
    except ValueError:
        display_path = output
    print(f"Wrote {display_path}")


if __name__ == "__main__":
    main()
