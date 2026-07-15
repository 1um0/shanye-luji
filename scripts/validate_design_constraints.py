#!/usr/bin/env python3
"""Validate the machine-readable TT expert constraints before rendering."""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from design_constraints import get_in, load_design_constraints, product_constraints


REQUIRED_PRODUCTS = [
    "poster_3d",
    "magnet_3d",
    "postcard",
    "wechat_article",
    "social_grid",
    "ardot_board",
]

REQUIRED_ROLES = ["ui", "xiaohongshu", "ardot", "web"]
FORBIDDEN_SOCIAL_COPY = [
    "现场照片和路线数据对得上",
    "现场照片和路线数据对的上",
    "路线数据对得上",
    "此刻在路线上的位置",
    "证明真的上来了",
]
INTERNAL_SOCIAL_LABELS = {"路线说明", "节点记录"}


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped.startswith("［")
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _contains_forbidden(value: object, phrases: list[str]) -> list[str]:
    text = str(value or "")
    return [phrase for phrase in phrases if phrase and phrase in text]


def main() -> int:
    constraints = load_design_constraints(BASE_DIR)
    errors: list[str] = []

    if not constraints.get("version"):
        errors.append("missing version")

    expert_pack = constraints.get("expert_pack", {})
    if expert_pack.get("status") != "generated_from_local_expert_pack":
        errors.append("expert_pack.status must be generated_from_local_expert_pack")

    trace_ids_by_role: dict[str, set[str]] = {}
    for role in REQUIRED_ROLES:
        role_pack = get_in(expert_pack, ["roles", role], {})
        if _is_empty(role_pack.get("package_id")):
            errors.append(f"expert_pack.roles.{role}.package_id is missing")
        files = role_pack.get("files", [])
        if not isinstance(files, list) or not files:
            errors.append(f"expert_pack.roles.{role}.files is missing")
            trace_ids_by_role[role] = set()
            continue
        trace_ids = set()
        for idx, item in enumerate(files):
            if _is_empty(item.get("trace_id")):
                errors.append(f"expert_pack.roles.{role}.files[{idx}].trace_id is missing")
            else:
                trace_ids.add(str(item["trace_id"]))
            if _is_empty(item.get("file")):
                errors.append(f"expert_pack.roles.{role}.files[{idx}].file is missing")
            if _is_empty(item.get("sha256")):
                errors.append(f"expert_pack.roles.{role}.files[{idx}].sha256 is missing")
        trace_ids_by_role[role] = trace_ids

    expert_trace = constraints.get("expert_trace", {})
    for role in REQUIRED_ROLES:
        evidence = get_in(expert_trace, ["roles", role, "evidence"], [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"expert_trace.roles.{role}.evidence is missing")

    for key in ["route_name", "place_name", "team_name"]:
        value = get_in(constraints, ["source", key])
        if not value or str(value).startswith("［"):
            errors.append(f"source.{key} is empty or still a placeholder")

    global_palette = get_in(constraints, ["global", "palette_strategy"], {})
    if not isinstance(global_palette, dict) or not global_palette:
        errors.append("global.palette_strategy is missing")
    else:
        if _is_empty(global_palette.get("brand_anchor")):
            errors.append("global.palette_strategy.brand_anchor is missing")
        if global_palette.get("avoid_monotone") is not True:
            errors.append("global.palette_strategy.avoid_monotone must be true")

    for product_key in REQUIRED_PRODUCTS:
        product = product_constraints(constraints, product_key)
        if not product:
            errors.append(f"products.{product_key} is missing")
            continue
        for field in ["composition", "visual_differentiators", "copy_strategy", "script_hooks"]:
            if field not in product:
                errors.append(f"products.{product_key}.{field} is missing")

        expert_inputs = product.get("expert_inputs", {})
        if not isinstance(expert_inputs, dict):
            errors.append(f"products.{product_key}.expert_inputs must be an object")
            expert_inputs = {}
        for role in REQUIRED_ROLES:
            role_input = expert_inputs.get(role, {})
            if not isinstance(role_input, dict):
                errors.append(f"products.{product_key}.expert_inputs.{role} must include source metadata")
                continue
            if _is_empty(role_input.get("summary")):
                errors.append(f"products.{product_key}.expert_inputs.{role}.summary is missing")
            source = role_input.get("source", {})
            if not isinstance(source, dict):
                errors.append(f"products.{product_key}.expert_inputs.{role}.source is missing")
                continue
            if _is_empty(source.get("package_id")):
                errors.append(f"products.{product_key}.expert_inputs.{role}.source.package_id is missing")
            if _is_empty(source.get("files")):
                errors.append(f"products.{product_key}.expert_inputs.{role}.source.files is missing")
            trace_ids = source.get("trace_ids", [])
            if not isinstance(trace_ids, list) or not trace_ids:
                errors.append(f"products.{product_key}.expert_inputs.{role}.source.trace_ids is missing")
            else:
                unknown = set(str(item) for item in trace_ids) - trace_ids_by_role.get(role, set())
                if unknown:
                    errors.append(
                        f"products.{product_key}.expert_inputs.{role}.source.trace_ids has unknown ids: "
                        + ", ".join(sorted(unknown))
                    )

        treatment = get_in(product, ["composition", "visual_treatment"])
        if _is_empty(treatment):
            errors.append(f"products.{product_key}.composition.visual_treatment is missing")
        style_variant = get_in(product, ["composition", "style_variant"])
        if product_key in {"poster_3d", "postcard"} and _is_empty(style_variant):
            errors.append(f"products.{product_key}.composition.style_variant is missing")
        palette_strategy = get_in(product, ["composition", "palette_strategy"], {})
        if not isinstance(palette_strategy, dict) or not palette_strategy:
            errors.append(f"products.{product_key}.composition.palette_strategy is missing")
        else:
            if _is_empty(palette_strategy.get("brand_anchor")):
                errors.append(f"products.{product_key}.composition.palette_strategy.brand_anchor is missing")
            if _is_empty(palette_strategy.get("product_palette")):
                errors.append(f"products.{product_key}.composition.palette_strategy.product_palette is missing")
            if _is_empty(palette_strategy.get("rationale")):
                errors.append(f"products.{product_key}.composition.palette_strategy.rationale is missing")
        product_palette = get_in(product, ["script_hooks", "product_palette"], {})
        if product_key != "ardot_board" and (not isinstance(product_palette, dict) or not product_palette):
            errors.append(f"products.{product_key}.script_hooks.product_palette is missing")
        treatment_source = get_in(product, ["composition", "visual_treatment_source"], {})
        if not isinstance(treatment_source, dict):
            errors.append(f"products.{product_key}.composition.visual_treatment_source must be an object")
        else:
            if _is_empty(treatment_source.get("rationale")):
                errors.append(f"products.{product_key}.composition.visual_treatment_source.rationale is missing")
            source_list = treatment_source.get("source", [])
            if not isinstance(source_list, list) or not source_list:
                errors.append(f"products.{product_key}.composition.visual_treatment_source.source is missing")
            else:
                roles = {item.get("role") for item in source_list if isinstance(item, dict)}
                missing_roles = set(REQUIRED_ROLES) - roles
                if missing_roles:
                    errors.append(
                        f"products.{product_key}.composition.visual_treatment_source.source missing role(s): "
                        + ", ".join(sorted(missing_roles))
                    )

        script_treatment = get_in(product, ["script_hooks", "visual_treatment"])
        if _is_empty(script_treatment):
            errors.append(f"products.{product_key}.script_hooks.visual_treatment is missing")
        script_variant = get_in(product, ["script_hooks", "style_variant"])
        if product_key in {"poster_3d", "postcard"}:
            if _is_empty(script_variant):
                errors.append(f"products.{product_key}.script_hooks.style_variant is missing")
            elif not _is_empty(style_variant) and str(script_variant) != str(style_variant):
                errors.append(
                    f"products.{product_key}.script_hooks.style_variant must match composition.style_variant"
                )

    social_cards = get_in(constraints, ["products", "social_grid", "copy_strategy", "cards"], [])
    social_picks = get_in(constraints, ["products", "social_grid", "script_hooks", "photo_picks"], [])
    if social_cards and social_picks and len(social_cards) != len(social_picks):
        errors.append("social_grid cards and photo_picks counts differ")
    xhs_plan = get_in(constraints, ["products", "social_grid", "composition", "xhs_grid_plan"], {})
    if not isinstance(xhs_plan, dict) or not xhs_plan:
        errors.append("social_grid.composition.xhs_grid_plan is missing")
    else:
        if _is_empty(xhs_plan.get("strategy")):
            errors.append("social_grid.composition.xhs_grid_plan.strategy is missing")
        if _is_empty(xhs_plan.get("native_visual_cues")):
            errors.append("social_grid.composition.xhs_grid_plan.native_visual_cues is missing")
        plan_cards = xhs_plan.get("cards", [])
        script_plan_cards = get_in(constraints, ["products", "social_grid", "script_hooks", "card_plan"], [])
        if not isinstance(plan_cards, list) or len(plan_cards) != 9:
            errors.append("social_grid.composition.xhs_grid_plan.cards must contain 9 cards")
        if not isinstance(script_plan_cards, list) or len(script_plan_cards) != 9:
            errors.append("social_grid.script_hooks.card_plan must contain 9 cards")
        for idx, card in enumerate(plan_cards if isinstance(plan_cards, list) else [], 1):
            for field in ["photo", "caption", "archetype", "headline", "subline", "sticker", "data_focus"]:
                if _is_empty(card.get(field)):
                    errors.append(f"social_grid.composition.xhs_grid_plan.cards[{idx}].{field} is missing")
            for field in ["caption", "headline", "subline", "sticker", "photo_role", "footer_text"]:
                hits = _contains_forbidden(card.get(field), FORBIDDEN_SOCIAL_COPY)
                if hits:
                    errors.append(
                        f"social_grid.composition.xhs_grid_plan.cards[{idx}].{field} contains forbidden copy: "
                        + ", ".join(hits)
                    )
            if card.get("photo_role") in INTERNAL_SOCIAL_LABELS:
                errors.append(
                    f"social_grid.composition.xhs_grid_plan.cards[{idx}].photo_role is an internal label: "
                    f"{card.get('photo_role')}"
                )
            if card.get("show_role") is True and _is_empty(card.get("photo_role")):
                errors.append(f"social_grid.composition.xhs_grid_plan.cards[{idx}] show_role=true without photo_role")
        archetypes = {
            card.get("archetype")
            for card in plan_cards
            if isinstance(card, dict) and not _is_empty(card.get("archetype"))
        }
        if len(archetypes) < 5:
            errors.append("social_grid.xhs_grid_plan must use at least 5 distinct card archetypes")
        sublines = [
            str(card.get("subline", "")).strip()
            for card in plan_cards
            if isinstance(card, dict) and str(card.get("subline", "")).strip()
        ]
        repeated = sorted({line for line in sublines if sublines.count(line) > 1})
        if repeated:
            errors.append("social_grid.xhs_grid_plan contains repeated subline(s): " + ", ".join(repeated))

        for idx, card in enumerate(script_plan_cards if isinstance(script_plan_cards, list) else [], 1):
            for field in ["caption", "headline", "subline", "sticker", "photo_role", "footer_text"]:
                hits = _contains_forbidden(card.get(field), FORBIDDEN_SOCIAL_COPY)
                if hits:
                    errors.append(
                        f"social_grid.script_hooks.card_plan[{idx}].{field} contains forbidden copy: "
                        + ", ".join(hits)
                    )
            if card.get("photo_role") in INTERNAL_SOCIAL_LABELS:
                errors.append(
                    f"social_grid.script_hooks.card_plan[{idx}].photo_role is an internal label: {card.get('photo_role')}"
                )

    magnet_hooks = get_in(constraints, ["products", "magnet_3d", "script_hooks"], {})
    if magnet_hooks.get("base_cutout") is not True:
        errors.append("magnet_3d.script_hooks.base_cutout must be true")
    if magnet_hooks.get("text_outside_relief") is not True:
        errors.append("magnet_3d.script_hooks.text_outside_relief must be true")

    if errors:
        print("Design constraints invalid:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Design constraints OK")
    for product_key in REQUIRED_PRODUCTS:
        product = product_constraints(constraints, product_key)
        diffs = product.get("visual_differentiators", [])
        print(f"  - {product_key}: {len(diffs)} visual differentiator(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
