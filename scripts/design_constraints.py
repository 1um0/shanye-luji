#!/usr/bin/env python3
"""Load TT expert design constraints for generation scripts."""

from __future__ import annotations

import copy
import os
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_design_constraints(base_dir: str | Path | None = None) -> dict[str, Any]:
    """Load template defaults, then overlay output/design_constraints.json."""
    base = Path(base_dir) if base_dir else BASE_DIR
    references_root = Path(os.environ.get("SHANYE_REFERENCES_ROOT", base / "references"))
    output_root = Path(os.environ.get("SHANYE_OUTPUT_ROOT", base / "output"))
    if not references_root.exists() and (base / "shanye-luji" / "references").exists():
        references_root = base / "shanye-luji" / "references"
    template = _read_json(references_root / "design_constraints_template.json")
    project = _read_json(output_root / "design_constraints.json")
    return _deep_merge(template, project)


def product_constraints(
    constraints: dict[str, Any],
    product_key: str,
) -> dict[str, Any]:
    return constraints.get("products", {}).get(product_key, {})


def get_in(data: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def source_value(
    constraints: dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    return constraints.get("source", {}).get(key, default)


def list_from_constraints(value: Any, fallback: list[Any]) -> list[Any]:
    if isinstance(value, list) and value:
        return value
    return fallback
