#!/usr/bin/env python3
"""Build 3D poster photo markers from fresh matched_photos.json."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


BASE = Path(__file__).parent.parent
REFERENCES = Path(os.environ.get("SHANYE_REFERENCES_ROOT", BASE / "references"))
OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE / "output"))
sys.path.insert(0, str(BASE / "scripts"))
from design_constraints import get_in, load_design_constraints, product_constraints


def caption_map_from_constraints() -> dict[str, str]:
    constraints = load_design_constraints(BASE)
    social = product_constraints(constraints, "social_grid")
    cards = get_in(social, ["script_hooks", "card_plan"], []) or get_in(
        social, ["composition", "xhs_grid_plan", "cards"], []
    )
    return {
        str(item["photo"]): str(item["caption"])
        for item in cards
        if item.get("photo") and item.get("caption")
    }


def fallback_caption(item: dict, index: int, total: int) -> str:
    match_point = item.get("match_point") or {}
    ele = int(round(float(match_point.get("ele", 0) or 0)))
    if index == 0:
        return "起点"
    if index == total - 1:
        return "终点"
    if ele:
        return f"途中 {ele}m"
    return "途中"


def main() -> None:
    matched = json.loads((REFERENCES / "matched_photos.json").read_text(encoding="utf-8"))
    caption_map = caption_map_from_constraints()
    photo_items = [
        item for item in matched.get("photos", [])
        if item.get("match_method") != "manual" and item.get("match_point")
    ]
    markers = []
    for index, item in enumerate(photo_items):
        match_point = item.get("match_point")
        stem = Path(item["filename"]).stem
        jpg_name = f"{stem}.jpg"
        if not (OUTPUT / "photos" / jpg_name).exists():
            jpg_name = item["filename"]
        markers.append(
            {
                "lat": match_point["lat"],
                "lon": match_point["lon"],
                "ele": match_point.get("ele", 0),
                "title": caption_map.get(stem, fallback_caption(item, index, len(photo_items))),
                "photo": f"photos/{jpg_name}",
                "distance_km": round(match_point.get("cumulative_distance_m", 0) / 1000, 2),
                "match_method": item.get("match_method"),
            }
        )

    output = REFERENCES / "photo_markers_3d.json"
    output.write_text(json.dumps(markers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(markers)} markers to {output}")


if __name__ == "__main__":
    main()
