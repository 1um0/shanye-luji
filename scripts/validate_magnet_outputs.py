#!/usr/bin/env python3
"""Lightweight checks for generated magnet STL/OBJ outputs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE / "output"))
BASE_HEIGHT = 4.0


def read_obj_vertices(path: Path) -> list[tuple[float, float, float]]:
    vertices = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("v "):
                continue
            parts = line.split()
            if len(parts) >= 4:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return vertices


def validate(shape: str) -> list[str]:
    errors = []
    stl = OUTPUT / f"magnet_3d_{shape}.stl"
    obj = OUTPUT / f"magnet_3d_{shape}.obj"
    ts_file = OUTPUT / "magnet_3d_latest_timestamp.txt"
    for path in (stl, obj):
        if not path.exists():
            errors.append(f"缺少 {path.name}")
        elif path.stat().st_size < 1024:
            errors.append(f"{path.name} 文件过小，可能导出失败")

    if not obj.exists():
        return errors

    vertices = read_obj_vertices(obj)
    if not vertices:
        errors.append(f"{obj.name} 没有顶点")
        return errors

    zs = [v[2] for v in vertices]
    if min(zs) > 0.05:
        errors.append("模型没有 z=0 底面，底座可能未生成")
    if not any(abs(z - BASE_HEIGHT) < 0.05 for z in zs):
        errors.append("模型没有 BASE_HEIGHT 顶面顶点，底座外圈可能缺失")
    if max(zs) <= BASE_HEIGHT + 1.0:
        errors.append("模型最高点过低，中心地形浮雕可能缺失")

    if ts_file.exists():
        ts = ts_file.read_text(encoding="utf-8").strip()
        for ext in ("stl", "obj"):
            ts_path = OUTPUT / f"magnet_3d_{shape}_{ts}.{ext}"
            if not ts_path.exists():
                errors.append(f"缺少时间戳模型 {ts_path.name}")
    else:
        errors.append("缺少 magnet_3d_latest_timestamp.txt")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shape", default="hexagon", choices=["hexagon", "circle"])
    args = parser.parse_args()

    errors = validate(args.shape)
    if errors:
        print("冰箱贴模型验收失败:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)
    print(f"冰箱贴模型验收通过: magnet_3d_{args.shape}.stl / .obj")


if __name__ == "__main__":
    main()
