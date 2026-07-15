#!/usr/bin/env python3
"""Render simple PNG previews for the generated magnet OBJ/STL files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.font_manager import FontProperties
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from design_constraints import get_in, load_design_constraints, product_constraints
from platform_utils import find_chinese_font, preferred_chinese_font_family

REFERENCES = Path(os.environ.get("SHANYE_REFERENCES_ROOT", BASE / "references"))
OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE / "output"))
FONT_PATH = find_chinese_font()
FONT = FontProperties(fname=str(FONT_PATH)) if FONT_PATH else FontProperties(family=preferred_chinese_font_family())
BASE_HEIGHT = 4.0

CONSTRAINTS = load_design_constraints(BASE)
MAGNET_CONSTRAINTS = product_constraints(CONSTRAINTS, "magnet_3d")
MAGNET_PALETTE = get_in(MAGNET_CONSTRAINTS, ["script_hooks", "product_palette"], {})
SOURCE = CONSTRAINTS.get("source", {})


def color_from_palette(key: str, fallback: str) -> str:
    value = MAGNET_PALETTE.get(key)
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        return value
    return fallback


BASE_MATERIAL = color_from_palette("base_material", "#D7C282")
RELIEF_LOW = color_from_palette("relief_low", "#C8D194")
RELIEF_HIGH = color_from_palette("relief_high", "#F0E2AF")
TEXT_COLOR = color_from_palette("text", "#3D5233")
MUTED_COLOR = color_from_palette("muted_text", "#5A7A6A")
EDGE_COLOR = color_from_palette("edge", BASE_MATERIAL)
PREVIEW_BG = color_from_palette("preview_bg", "#E8DFD3")
TERRAIN_CMAP = LinearSegmentedColormap.from_list(
    "magnet_terrain",
    [BASE_MATERIAL, RELIEF_HIGH, RELIEF_LOW],
)


def route_summary_label() -> str:
    route_path = REFERENCES / "route_data.json"
    content_path = REFERENCES / "content_assets.json"
    content = {}
    if content_path.exists():
        with content_path.open("r", encoding="utf-8") as f:
            content = json.load(f)
    if not route_path.exists():
        route_name = SOURCE.get("route_name") or content.get("route_name") or "路线纪念"
        team_name = SOURCE.get("team_name") or content.get("team_name") or "山野路迹"
        return f"{route_name} · {team_name} · 0.00KM · +0M"
    with route_path.open("r", encoding="utf-8") as f:
        route = json.load(f)
    route_name = SOURCE.get("route_name") or content.get("route_name") or "路线纪念"
    team_name = SOURCE.get("team_name") or content.get("team_name") or "山野路迹"
    distance = route.get("total_distance_km", 0)
    gain = int(round(route.get("elevation_gain", 0)))
    return f"{route_name} · {team_name} · {distance:.2f}KM · +{gain}M"


def face_colors(tri: np.ndarray, show_edges: bool) -> tuple[np.ndarray, str | tuple[float, float, float, float], float]:
    z_avg = tri[:, :, 2].mean(axis=1)
    z_norm = (z_avg - z_avg.min()) / max(float(np.ptp(z_avg)), 1e-6)

    v1 = tri[:, 1] - tri[:, 0]
    v2 = tri[:, 2] - tri[:, 0]
    normals = np.cross(v1, v2)
    normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-9
    light = np.array([-0.35, -0.45, 0.82])
    light /= np.linalg.norm(light)
    shade = 0.72 + 0.28 * np.clip(normals @ light, 0, 1)

    colors = TERRAIN_CMAP(z_norm)
    colors[:, :3] *= shade[:, None]
    colors[:, 3] = 1.0
    edge = EDGE_COLOR if show_edges else (0, 0, 0, 0)
    return colors, edge, 0.015 if show_edges else 0


def visible_preview_faces(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Drop hidden underside faces from the preview to avoid Matplotlib 3D sorting artifacts."""
    tri = vertices[faces]
    v1 = tri[:, 1] - tri[:, 0]
    v2 = tri[:, 2] - tri[:, 0]
    normals = np.cross(v1, v2)
    centroids = tri.mean(axis=1)
    flat_bottom = np.all(tri[:, :, 2] <= 0.02, axis=1)
    downward_under_surface = (normals[:, 2] < -1e-8) & (centroids[:, 2] <= 0.08)
    return faces[~(flat_bottom | downward_under_surface)]


def render_mesh(
    mesh_path: Path,
    output_path: Path,
    title: str,
    *,
    label: bool = True,
    zoom: float = 0.58,
    show_edges: bool = False,
    max_faces: int | None = 16000,
) -> None:
    mesh = trimesh.load_mesh(mesh_path)
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    faces = visible_preview_faces(vertices, faces)

    # Reduce face count for a lightweight preview while keeping silhouette and relief visible.
    if max_faces and len(faces) > max_faces:
        step = max(1, len(faces) // max_faces)
        faces = faces[::step]

    tri = vertices[faces]
    fig = plt.figure(figsize=(8, 8), dpi=220)
    ax = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor(PREVIEW_BG)
    ax.set_facecolor(PREVIEW_BG)

    colors, edgecolor, linewidth = face_colors(tri, show_edges)
    collection = Poly3DCollection(
        tri,
        facecolors=colors,
        edgecolor=edgecolor,
        linewidths=linewidth,
        alpha=1.0,
    )
    ax.add_collection3d(collection)

    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    radius = (bounds[1] - bounds[0]).max() * zoom
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(bounds[0][2], bounds[0][2] + radius * 0.95)
    ax.view_init(elev=42, azim=-48)
    ax.set_box_aspect((1, 1, 0.38))
    ax.set_axis_off()
    if label:
        ax.text2D(
            0.06,
            0.94,
            title,
            transform=ax.transAxes,
            color=TEXT_COLOR,
            fontsize=16,
            fontweight="bold",
            fontproperties=FONT,
        )
        ax.text2D(
            0.06,
            0.89,
            route_summary_label(),
            transform=ax.transAxes,
            color=MUTED_COLOR,
            fontsize=8,
            fontproperties=FONT,
        )
        plt.tight_layout(pad=0)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.02)
    else:
        ax.set_position([0, 0, 1, 1])
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    print(f"Rendered {output_path}")


def main() -> None:
    hexagon_path = OUTPUT / "magnet_3d_hexagon.obj"
    if not hexagon_path.exists():
        raise FileNotFoundError(f"Missing required magnet model: {hexagon_path}")

    render_mesh(hexagon_path, OUTPUT / "magnet_3d_preview.png", "六边形 3D 冰箱贴")
    render_mesh(
        hexagon_path,
        OUTPUT / "magnet_3d_ardot_preview.png",
        "六边形 3D 冰箱贴",
        label=False,
        zoom=0.45,
        show_edges=False,
        max_faces=None,
    )

    circle_path = OUTPUT / "magnet_3d_circle.obj"
    if circle_path.exists():
        render_mesh(circle_path, OUTPUT / "magnet_3d_relief_preview.png", "圆形 3D 冰箱贴")
    else:
        relief_path = OUTPUT / "magnet_3d_relief_preview.png"
        if relief_path.exists():
            relief_path.unlink()
        print("Skipped circle preview: magnet_3d_circle.obj not found")


if __name__ == "__main__":
    main()
