#!/usr/bin/env python3
"""
山野路迹 — 3D 打印冰箱贴模型生成器
修复：复用 3D 小报的 WGS84 + SRTM 地形网格；文字曲线轮廓正确扁平化后挤出。

用法:
    python build_magnet_3d.py --shape circle
    python build_magnet_3d.py --shape hexagon
"""

import json
import math
import os
import sys
import argparse
import base64
import struct
import io
import zipfile
import urllib.request
from datetime import datetime, timezone, timedelta
from shutil import copyfile

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from design_constraints import get_in, load_design_constraints, product_constraints
from platform_utils import find_chinese_font, preferred_chinese_font_family

REFERENCES = os.environ.get("SHANYE_REFERENCES_ROOT", os.path.join(BASE, "references"))
OUTPUT = os.environ.get("SHANYE_OUTPUT_ROOT", os.path.join(BASE, "output"))
os.makedirs(OUTPUT, exist_ok=True)
CONSTRAINTS = load_design_constraints(BASE)
MAGNET_CONSTRAINTS = product_constraints(CONSTRAINTS, "magnet_3d")
SOURCE_CONSTRAINTS = CONSTRAINTS.get("source", {})

# ---- 物理尺寸 (mm) ----
BASE_DIAMETER = 80.0
BASE_HEIGHT = 4.0
RIM_WIDTH = 9.0
TERRAIN_DIAMETER = BASE_DIAMETER - 2 * RIM_WIDTH  # 62mm
TERRAIN_MAX_HEIGHT = 16.0


def mm_hook(path, default, min_value, max_value):
    try:
        value = float(get_in(MAGNET_CONSTRAINTS, ["script_hooks", path], default))
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


TRAIL_TUBE_RADIUS = mm_hook("trail_tube_radius_mm", 0.38, 0.25, 0.8)
TEXT_ENGRAVE_DEPTH = mm_hook("text_engrave_depth_mm", 0.85, 0.35, 1.4)
TEXT_BOLD_OFFSET = mm_hook("text_bold_offset_mm", 0.12, 0.0, 0.25)
TEXT_ROUTE_MAX_HEIGHT = mm_hook("text_route_height_mm", 3.6, 2.4, 4.4)
TEXT_FIELD_MAX_HEIGHT = mm_hook("text_field_height_mm", 3.05, 2.2, 3.8)
TERRAIN_INSET = 2.0
TERRAIN_RADIAL_SEGMENTS = 58
TERRAIN_ANGLE_SEGMENTS = 168
ROUTE_FIT_RATIO = 0.74
HGT_ROWS = 3601
SHOULDER_HEIGHT = 2.2
SHOULDER_WIDTH = 4.0
SHOULDER_SEGMENTS = 10
EDGE_FADE_FRACTION = 0.18
LABEL_INSET = 6.5
BASE_CUTOUT_RADIUS = TERRAIN_DIAMETER / 2 - TERRAIN_INSET + SHOULDER_WIDTH


def load_data():
    srtm_path = os.path.join(REFERENCES, "srtm_elevation_wgs84.json")
    srtm = {}
    if os.path.exists(srtm_path):
        with open(srtm_path, encoding="utf-8") as f:
            srtm = json.load(f)
    with open(os.path.join(REFERENCES, "route_data.json"), encoding="utf-8") as f:
        route = json.load(f)
    with open(os.path.join(REFERENCES, "content_assets.json"), encoding="utf-8") as f:
        content = json.load(f)
    build_data_path = os.path.join(OUTPUT, "build_data.json")
    build_data = {}
    if os.path.exists(build_data_path):
        with open(build_data_path, encoding="utf-8") as f:
            build_data = json.load(f)
    return srtm, route, content, build_data


class PosterTerrain:
    """复用 3D 小报的地形坐标框架：world X=0..10, Z=0..8。"""

    def __init__(self, build_data):
        self.grid_size = build_data["grid_size"]
        self.elev_min = build_data["elev_min"]
        self.elev_max = build_data["elev_max"]
        self.tube_pts = build_data["tube_pts"]

        raw = base64.b64decode(build_data["grid_b64"])
        self.grid = struct.unpack(f"<{len(raw) // 2}H", raw)

        half_diag_world = math.sqrt(5.0 ** 2 + 4.0 ** 2)
        terrain_radius = TERRAIN_DIAMETER / 2 - TERRAIN_INSET
        self.scale = terrain_radius / half_diag_world
        self.half_w = 5.0 * self.scale
        self.half_h = 4.0 * self.scale

    def sample_elevation(self, wx, wz):
        col = round(wx / 10.0 * (self.grid_size - 1))
        row = round(wz / 8.0 * (self.grid_size - 1))
        col = max(0, min(self.grid_size - 1, col))
        row = max(0, min(self.grid_size - 1, row))
        return self.grid[row * self.grid_size + col]

    def height_mm(self, wx, wz):
        e = self.sample_elevation(wx, wz)
        if e <= 0 or self.elev_max <= self.elev_min:
            return 0.2
        return (e - self.elev_min) / (self.elev_max - self.elev_min) * TERRAIN_MAX_HEIGHT

    def world_to_mm(self, wx, wz):
        # 小报里 Z=0 是北侧；实体模型里让北侧朝 +Y，方便和地图直觉一致。
        x = (wx - 5.0) * self.scale
        y = (4.0 - wz) * self.scale
        return x, y

    def mm_to_world(self, x, y):
        wx = x / self.scale + 5.0
        wz = 4.0 - y / self.scale
        return wx, wz


# ================================================================
# 与 3D 小报同源的 WGS84 + SRTM HGT 采样
# ================================================================

PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323


def _transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320.0 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lat, lon):
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlon = (dlon * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lat - dlat, lon - dlon


def download_srtm_hgt(tile_name):
    cache_dir = os.environ.get("SHANYE_SRTM_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "shanye-luji", "srtm"))
    os.makedirs(cache_dir, exist_ok=True)
    hgt_path = os.path.join(cache_dir, f"{tile_name}.hgt")
    if os.path.exists(hgt_path):
        return hgt_path

    urls = [
        f"https://step.esa.int/auxdata/dem/SRTMGL1/{tile_name}.SRTMGL1.hgt.zip",
        f"https://srtm.kurviger.de/SRTM1/{tile_name}.hgt.zip",
    ]
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LearnBuddy/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                data = resp.read()
            if data[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    hgt_name = next((n for n in zf.namelist() if n.endswith(".hgt")), zf.namelist()[0])
                    data = zf.read(hgt_name)
            with open(hgt_path, "wb") as f:
                f.write(data)
            return hgt_path
        except Exception:
            continue
    raise RuntimeError(f"Could not download SRTM tile {tile_name}")


class HGTSampler:
    def __init__(self, tile_paths):
        self.tile_paths = tile_paths

    def sample(self, lat, lon):
        tile_lat = int(math.floor(lat))
        tile_lon = int(math.floor(lon))
        tile_name = f"N{tile_lat:02d}E{tile_lon:03d}"
        hgt_path = self.tile_paths.get(tile_name)
        if not hgt_path:
            hgt_path = next(iter(self.tile_paths.values()))
            tile_lat = int(os.path.basename(hgt_path)[1:3])
            tile_lon = int(os.path.basename(hgt_path)[4:7])

        row = int((tile_lat + 1 - lat) * (HGT_ROWS - 1))
        col = int((lon - tile_lon) * (HGT_ROWS - 1))
        row = max(0, min(HGT_ROWS - 1, row))
        col = max(0, min(HGT_ROWS - 1, col))
        with open(hgt_path, "rb") as f:
            f.seek((row * HGT_ROWS + col) * 2)
            val = struct.unpack(">h", f.read(2))[0]
        return max(0, val)


def make_hgt_sampler(points):
    """Create an HGT sampler covering all given lat/lon points."""
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    tile_names = set()
    for lat_base in range(int(math.floor(min(lats))), int(math.floor(max(lats))) + 1):
        for lon_base in range(int(math.floor(min(lons))), int(math.floor(max(lons))) + 1):
            tile_names.add(f"N{lat_base:02d}E{lon_base:03d}")
    return HGTSampler({name: download_srtm_hgt(name) for name in sorted(tile_names)})


def choose_coordinate_points(raw_pts):
    """
    GPX is normally WGS84, but some Chinese app exports may be GCJ-02.
    Compare route elevations against SRTM in both modes and pick the better fit.
    """
    raw_points = [
        {
            "lat": p["lat"],
            "lon": p["lon"],
            "ele": p.get("ele"),
            "dist": p.get("cumulative_distance_m", 0),
        }
        for p in raw_pts
    ]
    converted_points = []
    for p in raw_pts:
        lat, lon = gcj02_to_wgs84(p["lat"], p["lon"])
        converted_points.append(
            {
                "lat": lat,
                "lon": lon,
                "ele": p.get("ele"),
                "dist": p.get("cumulative_distance_m", 0),
            }
        )

    def score(points):
        sampler = make_hgt_sampler(points)
        step = max(1, len(points) // 400)
        errors = []
        gpx_vals = []
        srtm_vals = []
        for p in points[::step]:
            if p.get("ele") is None:
                continue
            srtm_ele = sampler.sample(p["lat"], p["lon"])
            errors.append(abs(float(p["ele"]) - srtm_ele))
            gpx_vals.append(float(p["ele"]))
            srtm_vals.append(float(srtm_ele))
        mae = float(np.mean(errors)) if errors else float("inf")
        if len(gpx_vals) > 2 and np.std(gpx_vals) > 0 and np.std(srtm_vals) > 0:
            corr = float(np.corrcoef(gpx_vals, srtm_vals)[0, 1])
        else:
            corr = 0.0
        return mae, corr, sampler

    raw_mae, raw_corr, raw_sampler = score(raw_points)
    converted_mae, converted_corr, converted_sampler = score(converted_points)

    # Prefer raw WGS84 unless conversion is clearly better. Standard GPX files are WGS84.
    converted_is_better = converted_mae + 10 < raw_mae and converted_corr >= raw_corr - 0.05
    if converted_is_better:
        return "gcj02_to_wgs84", converted_points, converted_sampler, {
            "raw_mae": raw_mae,
            "raw_corr": raw_corr,
            "converted_mae": converted_mae,
            "converted_corr": converted_corr,
        }

    return "wgs84_raw", raw_points, raw_sampler, {
        "raw_mae": raw_mae,
        "raw_corr": raw_corr,
        "converted_mae": converted_mae,
        "converted_corr": converted_corr,
    }


class ShapeTerrain:
    """按路线外扩采大一圈地形，再按圆形或六边形轮廓裁成实体浮雕。"""

    def __init__(self, route):
        raw_pts = route.get("track_points", [])
        self.coord_mode, self.points, initial_sampler, self.coord_diagnostics = choose_coordinate_points(raw_pts)

        self.center_lat = sum(p["lat"] for p in self.points) / len(self.points)
        self.center_lon = sum(p["lon"] for p in self.points) / len(self.points)
        cos_lat = math.cos(math.radians(self.center_lat))
        xs = [(p["lon"] - self.center_lon) * 111000 * cos_lat for p in self.points]
        ys = [(p["lat"] - self.center_lat) * 111000 for p in self.points]
        max_r_m = max(math.hypot(x, y) for x, y in zip(xs, ys))

        self.terrain_radius = TERRAIN_DIAMETER / 2 - TERRAIN_INSET
        self.meters_per_mm = max_r_m / (self.terrain_radius * ROUTE_FIT_RATIO)
        self.cos_lat = cos_lat

        terrain_m = self.terrain_radius * self.meters_per_mm
        lat_delta = terrain_m / 111000
        lon_delta = terrain_m / (111000 * cos_lat)
        lon_min = self.center_lon - lon_delta
        lon_max = self.center_lon + lon_delta
        lat_min = self.center_lat - lat_delta
        lat_max = self.center_lat + lat_delta

        tile_points = [{"lat": lat, "lon": lon} for lat in [lat_min, lat_max] for lon in [lon_min, lon_max]]
        self.hgt = make_hgt_sampler(tile_points)

        route_elev = [self.hgt.sample(p["lat"], p["lon"]) for p in self.points]
        self.elev_min = min(route_elev)
        self.elev_max = max(route_elev)
        self.elev_range = max(1, self.elev_max - self.elev_min)

    def mm_to_latlon(self, x, y):
        dlon_m = x * self.meters_per_mm
        dlat_m = y * self.meters_per_mm
        lat = self.center_lat + dlat_m / 111000
        lon = self.center_lon + dlon_m / (111000 * self.cos_lat)
        return lat, lon

    def latlon_to_mm(self, lat, lon):
        x = ((lon - self.center_lon) * 111000 * self.cos_lat) / self.meters_per_mm
        y = ((lat - self.center_lat) * 111000) / self.meters_per_mm
        return x, y

    def height_mm_at_xy(self, x, y):
        lat, lon = self.mm_to_latlon(x, y)
        e = self.hgt.sample(lat, lon)
        h = (e - self.elev_min) / self.elev_range
        return max(0, min(1, h)) * TERRAIN_MAX_HEIGHT

    def height_mm_at_latlon(self, lat, lon):
        e = self.hgt.sample(lat, lon)
        h = (e - self.elev_min) / self.elev_range
        return max(0, min(1, h)) * TERRAIN_MAX_HEIGHT


# ================================================================
# SRTM 双线性插值
# ================================================================

class SRTMSampler:
    """从 SRTM grid 双线性插值获取任意 lat/lon 的高程"""
    def __init__(self, srtm):
        self.grid_size = srtm["grid"]["size"]
        self.elev = srtm["grid"]["elevation"]
        self.bounds = srtm["bounds"]
        self.lat_min = srtm["bounds"]["lat_min"]
        self.lat_max = srtm["bounds"]["lat_max"]
        self.lon_min = srtm["bounds"]["lon_min"]
        self.lon_max = srtm["bounds"]["lon_max"]
        self.ele_min = srtm["stats"]["min"]
        self.ele_max = srtm["stats"]["max"]

    def sample(self, lat, lon):
        """双线性插值获取高程。lat/lon 超出范围时 clamp。"""
        lat = max(self.lat_min, min(self.lat_max, lat))
        lon = max(self.lon_min, min(self.lon_max, lon))
        # row: 0 = lat_max (北), grid_size-1 = lat_min (南)
        row = (self.lat_max - lat) / (self.lat_max - self.lat_min) * (self.grid_size - 1)
        col = (lon - self.lon_min) / (self.lon_max - self.lon_min) * (self.grid_size - 1)
        r0 = int(math.floor(row))
        c0 = int(math.floor(col))
        r1 = min(r0 + 1, self.grid_size - 1)
        c1 = min(c0 + 1, self.grid_size - 1)
        r0 = max(0, min(r0, self.grid_size - 1))
        c0 = max(0, min(c0, self.grid_size - 1))
        dr = row - r0
        dc = col - c0
        e00 = self.elev[r0][c0]
        e01 = self.elev[r0][c1]
        e10 = self.elev[r1][c0]
        e11 = self.elev[r1][c1]
        return e00 * (1 - dr) * (1 - dc) + e01 * (1 - dr) * dc + e10 * dr * (1 - dc) + e11 * dr * dc


def hex_radius_at_angle(angle, circumradius):
    """六边形在指定极角上的边界半径。"""
    vertices = [
        (circumradius * math.cos(math.pi / 3 * i + math.pi / 6),
         circumradius * math.sin(math.pi / 3 * i + math.pi / 6))
        for i in range(6)
    ]
    dx, dy = math.cos(angle), math.sin(angle)
    best = circumradius
    for i in range(6):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % 6]
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        t = (x1 * ey - y1 * ex) / den
        u = (x1 * dy - y1 * dx) / den
        if t > 0 and -1e-6 <= u <= 1 + 1e-6:
            best = min(best, t)
    return best


def shape_radius_at_angle(shape, angle, circumradius):
    if shape == "hexagon":
        return hex_radius_at_angle(angle, circumradius)
    return circumradius


# ================================================================
# 底座
# ================================================================

def build_base_mesh(shape="circle", segments=128, height=BASE_HEIGHT):
    """
    Build the base as a rim with a recessed center pocket.

    The center top face is intentionally removed so the terrain relief's
    bottom cap closes the pocket instead of occupying the same volume as a
    solid base slab.
    """
    outer_radius = BASE_DIAMETER / 2
    inner_radius = BASE_CUTOUT_RADIUS
    n = TERRAIN_ANGLE_SEGMENTS if shape == "hexagon" else max(segments, TERRAIN_ANGLE_SEGMENTS)
    angles = [2 * math.pi * i / n for i in range(n)]

    verts = [[0, 0, 0]]
    inner_bot = []
    outer_bot = []
    inner_top = []
    outer_top = []

    for a in angles:
        r = shape_radius_at_angle(shape, a, inner_radius)
        verts.append([r * math.cos(a), r * math.sin(a), 0])
        inner_bot.append(len(verts) - 1)
    for a in angles:
        r = shape_radius_at_angle(shape, a, outer_radius)
        verts.append([r * math.cos(a), r * math.sin(a), 0])
        outer_bot.append(len(verts) - 1)
    for a in angles:
        r = shape_radius_at_angle(shape, a, inner_radius)
        verts.append([r * math.cos(a), r * math.sin(a), height])
        inner_top.append(len(verts) - 1)
    for a in angles:
        r = shape_radius_at_angle(shape, a, outer_radius)
        verts.append([r * math.cos(a), r * math.sin(a), height])
        outer_top.append(len(verts) - 1)

    faces = []
    center = 0
    for i in range(n):
        j = (i + 1) % n
        # Bottom cap, including the area below the recessed relief.
        faces.append([center, inner_bot[j], inner_bot[i]])
        faces.append([inner_bot[i], inner_bot[j], outer_bot[i]])
        faces.append([outer_bot[i], inner_bot[j], outer_bot[j]])

        # Outer side wall.
        faces.append([outer_bot[i], outer_bot[j], outer_top[i]])
        faces.append([outer_top[i], outer_bot[j], outer_top[j]])

        # Inner recessed wall. The terrain bottom cap closes this pocket at z=BASE_HEIGHT.
        faces.append([inner_bot[i], inner_top[i], inner_bot[j]])
        faces.append([inner_bot[j], inner_top[i], inner_top[j]])

        # Top rim only: no central top face under the terrain.
        faces.append([inner_top[i], outer_top[i], inner_top[j]])
        faces.append([inner_top[j], outer_top[i], outer_top[j]])

    return np.array(verts), np.array(faces)


# ================================================================
# 地形 — 极坐标网格 + SRTM 双线性插值 + 边缘封闭
# ================================================================


def build_terrain_mesh(route, shape="circle"):
    """
    先按路线外扩采一整块真实 WGS84/SRTM 地形，再按圆形/六边形轮廓裁切。
    """
    terrain = ShapeTerrain(route)
    terrain_radius = terrain.terrain_radius
    relief_radius = terrain_radius + SHOULDER_WIDTH
    verts = []
    top = []
    bot = []

    center_h = terrain.height_mm_at_xy(0, 0)
    verts.append([0, 0, BASE_HEIGHT + center_h])
    center_top = len(verts) - 1
    verts.append([0, 0, BASE_HEIGHT])
    center_bot = len(verts) - 1

    for ai in range(TERRAIN_ANGLE_SEGMENTS):
        angle = 2 * math.pi * ai / TERRAIN_ANGLE_SEGMENTS
        edge_radius = (
            hex_radius_at_angle(angle, relief_radius)
            if shape == "hexagon"
            else relief_radius
        )
        core_edge_radius = (
            hex_radius_at_angle(angle, terrain_radius)
            if shape == "hexagon"
            else terrain_radius
        )
        row = [center_top]
        bot_row = [center_bot]
        for ri in range(1, TERRAIN_RADIAL_SEGMENTS + 1):
            r = edge_radius * ri / TERRAIN_RADIAL_SEGMENTS
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            terrain_h = terrain.height_mm_at_xy(x, y)
            if r > core_edge_radius:
                shoulder_t = (r - core_edge_radius) / max(0.001, edge_radius - core_edge_radius)
                # Smoothly settle the terrain into a raised shoulder instead of a vertical cliff.
                smooth = shoulder_t * shoulder_t * (3 - 2 * shoulder_t)
                terrain_h = terrain_h * (1 - smooth) + 0.25 * smooth
            z = BASE_HEIGHT + terrain_h
            verts.append([x, y, z])
            row.append(len(verts) - 1)
            verts.append([x, y, BASE_HEIGHT])
            bot_row.append(len(verts) - 1)
        top.append(row)
        bot.append(bot_row)

    faces = []
    for ai in range(TERRAIN_ANGLE_SEGMENTS):
        ni = (ai + 1) % TERRAIN_ANGLE_SEGMENTS
        for ri in range(TERRAIN_RADIAL_SEGMENTS):
            if ri == 0:
                faces.append([center_top, top[ai][1], top[ni][1]])
                faces.append([center_bot, bot[ni][1], bot[ai][1]])
            else:
                a = top[ai][ri]
                b = top[ai][ri + 1]
                c = top[ni][ri + 1]
                d = top[ni][ri]
                faces.append([a, b, d])
                faces.append([b, c, d])

                ab = bot[ai][ri]
                bb = bot[ai][ri + 1]
                cb = bot[ni][ri + 1]
                db = bot[ni][ri]
                faces.append([ab, db, bb])
                faces.append([bb, db, cb])

    # 外圈侧墙。
    edge = TERRAIN_RADIAL_SEGMENTS
    for ai in range(TERRAIN_ANGLE_SEGMENTS):
        ni = (ai + 1) % TERRAIN_ANGLE_SEGMENTS
        a = top[ai][edge]
        b = top[ni][edge]
        ab = bot[ai][edge]
        bb = bot[ni][edge]
        faces.append([a, ab, b])
        faces.append([b, ab, bb])

    return np.array(verts), np.array(faces)


def build_shoulder_mesh(shape="circle"):
    """浮雕边缘过渡护坡：从山体边缘平顺落到底座表面。"""
    terrain_radius = TERRAIN_DIAMETER / 2 - TERRAIN_INSET
    verts = []
    faces = []
    rings = []

    for ri in range(SHOULDER_SEGMENTS + 1):
        t = ri / SHOULDER_SEGMENTS
        smooth = t * t * (3 - 2 * t)
        circum = terrain_radius + SHOULDER_WIDTH * t
        z_top = BASE_HEIGHT + SHOULDER_HEIGHT * (1 - smooth) + 0.25 * smooth
        top_row = []
        bot_row = []
        for ai in range(TERRAIN_ANGLE_SEGMENTS):
            angle = 2 * math.pi * ai / TERRAIN_ANGLE_SEGMENTS
            r = hex_radius_at_angle(angle, circum) if shape == "hexagon" else circum
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            verts.append([x, y, z_top])
            top_row.append(len(verts) - 1)
            verts.append([x, y, BASE_HEIGHT])
            bot_row.append(len(verts) - 1)
        rings.append((top_row, bot_row))

    for ri in range(SHOULDER_SEGMENTS):
        top0, bot0 = rings[ri]
        top1, bot1 = rings[ri + 1]
        for ai in range(TERRAIN_ANGLE_SEGMENTS):
            ni = (ai + 1) % TERRAIN_ANGLE_SEGMENTS
            faces.append([top0[ai], top0[ni], top1[ai]])
            faces.append([top0[ni], top1[ni], top1[ai]])
            faces.append([bot0[ai], bot1[ai], bot0[ni]])
            faces.append([bot0[ni], bot1[ai], bot1[ni]])

    # Inner and outer side walls.
    for ring_idx in [0, SHOULDER_SEGMENTS]:
        top, bot = rings[ring_idx]
        for ai in range(TERRAIN_ANGLE_SEGMENTS):
            ni = (ai + 1) % TERRAIN_ANGLE_SEGMENTS
            faces.append([top[ai], bot[ai], top[ni]])
            faces.append([top[ni], bot[ai], bot[ni]])

    return np.array(verts), np.array(faces)


# ================================================================
# 轨迹管道
# ================================================================

def build_trail_tube(route):
    import trimesh
    terrain = ShapeTerrain(route)
    pts = terrain.points
    if not pts:
        return np.array([]), np.array([])

    path_3d = []
    step = max(1, len(pts) // 260)
    sampled = pts[::step]
    if sampled[-1] != pts[-1]:
        sampled.append(pts[-1])
    for p in sampled:
        x, y = terrain.latlon_to_mm(p["lat"], p["lon"])
        z = BASE_HEIGHT + terrain.height_mm_at_latlon(p["lat"], p["lon"]) + TRAIL_TUBE_RADIUS
        path_3d.append([x, y, z])

    if len(path_3d) < 2:
        return np.array([]), np.array([])

    path_3d = np.array(path_3d)
    meshes = []
    for i in range(len(path_3d) - 1):
        p0 = path_3d[i]
        p1 = path_3d[i + 1]
        length = np.linalg.norm(p1 - p0)
        if length < 0.01:
            continue
        cyl = trimesh.creation.cylinder(
            radius=TRAIL_TUBE_RADIUS, height=length,
            segment=np.array([p0, p1]), sections=12,
        )
        meshes.append(cyl)
    for p in path_3d[1:-1]:
        sphere = trimesh.creation.icosphere(radius=TRAIL_TUBE_RADIUS, subdivisions=1)
        sphere.apply_translation(p)
        meshes.append(sphere)
    if not meshes:
        return np.array([]), np.array([])
    combined = trimesh.util.concatenate(meshes)
    return combined.vertices, combined.faces


# ================================================================
# 边缘凹刻文字 — 中文字体 + GPX 真实数据
# ================================================================

def build_engraved_text_top_layer(route, content, shape="hexagon"):
    """
    Build the top portion of the base rim with text-shaped holes.

    This is a robust printable substitute for 3D boolean subtraction: the
    rim's upper layer is generated from a 2D polygon difference, then extruded
    from the engraving floor up to BASE_HEIGHT. The lower base layer remains
    intact, so the letters read as recessed cuts instead of raised glyphs.
    """
    try:
        import mapbox_earcut  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "中文凹刻文字需要 mapbox-earcut 才能把字体轮廓三角化。"
            "请运行: python -m pip install mapbox-earcut"
        ) from exc

    from trimesh.creation import extrude_polygon
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    # ---- 从 GPX 真实数据提取文字 ----
    route_name = SOURCE_CONSTRAINTS.get("route_name", content.get("route_name", ""))
    team_name = SOURCE_CONSTRAINTS.get("team_name", content.get("team_name", "山野路迹"))
    dist_km = route.get("total_distance_km", 0)
    elev_gain = int(route.get("elevation_gain", 0))
    max_elev = int(route.get("max_elevation", 0))

    start_time = route.get("start_time", "")
    try:
        dt = datetime.fromisoformat(start_time).astimezone(timezone(timedelta(hours=8)))
        date_str = dt.strftime("%Y.%m.%d")
    except Exception:
        date_str = ""

    dur_seconds = route.get("duration_seconds", 0)
    dur_h = int(dur_seconds // 3600)
    dur_m = int((dur_seconds % 3600) // 60)

    label_values = {
        "route_name": route_name,
        "team_name": team_name,
        "date": date_str,
        "distance": f"{dist_km:.2f} KM",
        "elevation_gain": f"+{elev_gain} M",
        "duration": f"{dur_h}H{dur_m:02d}M",
        "max_elevation": f"MAX {max_elev}M",
        "duration_max_elevation": f"{dur_h}H{dur_m:02d}M MAX{max_elev}M",
    }
    label_keys = get_in(
        MAGNET_CONSTRAINTS,
        ["copy_strategy", "edge_labels"],
        ["route_name", "team_name", "date", "distance", "elevation_gain", "duration_max_elevation"],
    )
    labels = [label_values.get(key, str(key)) for key in label_keys][:6]
    while len(labels) < 6:
        labels.append("")

    font_path = find_chinese_font()
    if font_path:
        font_prop = FontProperties(fname=str(font_path))
        print(f"    字体: {font_path}")
    else:
        family = preferred_chinese_font_family()
        font_prop = FontProperties(family=family)
        print(f"    字体: {family} (family fallback)")

    def text_polygons(text, char_size):
        """TextPath 的中文轮廓包含二次曲线，先扁平化再转 Polygon。"""
        tp = TextPath((0, 0), text, size=char_size, prop=font_prop)
        paths = tp.to_polygons(closed_only=True)
        raw_polys = []
        for poly in paths:
            if len(poly) < 3:
                continue
            try:
                p = Polygon(poly)
                if not p.is_valid:
                    p = p.buffer(0)
                if p.is_empty:
                    continue
                if hasattr(p, "geoms"):
                    raw_polys.extend([g for g in p.geoms if g.area > 0.0005])
                elif p.area > 0.0005:
                    raw_polys.append(p)
            except Exception:
                continue

        # TextPath returns counters such as "0" holes as separate closed paths.
        # Rebuild a filled glyph polygon so engraved Latin/numeric text stays legible.
        geoms = []
        consumed = set()
        ordered = sorted(enumerate(raw_polys), key=lambda item: item[1].area, reverse=True)
        for idx, outer in ordered:
            if idx in consumed:
                continue
            holes = []
            for hole_idx, hole in ordered:
                if hole_idx == idx or hole_idx in consumed:
                    continue
                if outer.contains(hole.representative_point()):
                    holes.append(list(hole.exterior.coords))
                    consumed.add(hole_idx)
            rebuilt = Polygon(list(outer.exterior.coords), holes)
            if not rebuilt.is_valid:
                rebuilt = rebuilt.buffer(0)
            if not rebuilt.is_empty:
                if hasattr(rebuilt, "geoms"):
                    geoms.extend([g for g in rebuilt.geoms if g.area > 0.0005])
                elif rebuilt.area > 0.0005:
                    geoms.append(rebuilt)
        return geoms

    def render_label(text, center, angle, max_width, max_height):
        geoms = text_polygons(text, char_size)
        if not geoms:
            return []

        minx = min(g.bounds[0] for g in geoms)
        maxx = max(g.bounds[2] for g in geoms)
        miny = min(g.bounds[1] for g in geoms)
        maxy = max(g.bounds[3] for g in geoms)
        width = max(maxx - minx, 1e-6)
        height = max(maxy - miny, 1e-6)
        scale_factor = min(max_width / width, max_height / height)
        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2
        ca = math.cos(angle)
        sa = math.sin(angle)

        placed = []
        for g in geoms:
            coords = []
            for x, y in list(g.exterior.coords):
                x0 = (x - cx) * scale_factor
                y0 = (y - cy) * scale_factor
                coords.append((
                    center[0] + x0 * ca - y0 * sa,
                    center[1] + x0 * sa + y0 * ca,
                ))
            p = Polygon(coords)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty:
                if hasattr(p, "geoms"):
                    placed.extend([part for part in p.geoms if part.area > 0.0005])
                elif p.area > 0.0005:
                    placed.append(p)
        if TEXT_BOLD_OFFSET > 0:
            placed = [
                g.buffer(TEXT_BOLD_OFFSET, join_style=2, mitre_limit=2.0)
                for g in placed
                if not g.is_empty
            ]
        return placed

    def upright_angle(angle):
        while angle <= -math.pi:
            angle += 2 * math.pi
        while angle > math.pi:
            angle -= 2 * math.pi
        if angle > math.pi / 2:
            angle -= math.pi
        if angle < -math.pi / 2:
            angle += math.pi
        return angle

    outer_radius = BASE_DIAMETER / 2
    inner_radius = BASE_CUTOUT_RADIUS
    engraving_floor = max(0.2, BASE_HEIGHT - TEXT_ENGRAVE_DEPTH)
    char_size = 3.0
    letter_geoms = []
    counts = []

    if shape == "hexagon":
        outer_poly_points = [
            (
                outer_radius * math.cos(math.pi / 3 * i + math.pi / 6),
                outer_radius * math.sin(math.pi / 3 * i + math.pi / 6),
            )
            for i in range(6)
        ]
        inner_poly_points = [
            (
                inner_radius * math.cos(math.pi / 3 * i + math.pi / 6),
                inner_radius * math.sin(math.pi / 3 * i + math.pi / 6),
            )
            for i in range(6)
        ][::-1]
        rim_polygon = Polygon(outer_poly_points, [inner_poly_points])
    else:
        circle_resolution = 160
        outer_poly_points = [
            (
                outer_radius * math.cos(2 * math.pi * i / circle_resolution),
                outer_radius * math.sin(2 * math.pi * i / circle_resolution),
            )
            for i in range(circle_resolution)
        ]
        inner_poly_points = [
            (
                inner_radius * math.cos(2 * math.pi * i / circle_resolution),
                inner_radius * math.sin(2 * math.pi * i / circle_resolution),
            )
            for i in range(circle_resolution)
        ][::-1]
        rim_polygon = Polygon(outer_poly_points, [inner_poly_points])

    char_size = 3.0
    if shape == "hexagon":
        outer_r = BASE_DIAMETER / 2 - 1.6
        vertices = [
            (outer_r * math.cos(math.pi / 3 * i + math.pi / 6),
             outer_r * math.sin(math.pi / 3 * i + math.pi / 6))
            for i in range(6)
        ]
        # Put the route name on the most visible upper edge, then continue clockwise.
        edge_order = [0, 1, 2, 3, 4, 5]
        for label, edge_i in zip(labels, edge_order):
            p0 = vertices[edge_i]
            p1 = vertices[(edge_i + 1) % 6]
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            r = math.hypot(mid[0], mid[1]) or 1
            # Keep text on the outer rim, outside the relief cutout.
            inset = 1.55
            center = (mid[0] - mid[0] / r * inset, mid[1] - mid[1] / r * inset)
            angle = upright_angle(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
            max_width = math.dist(p0, p1) - 8.0
            max_height = TEXT_ROUTE_MAX_HEIGHT if label == route_name else TEXT_FIELD_MAX_HEIGHT
            geoms = render_label(label, center, angle, max_width, max_height)
            letter_geoms.extend(geoms)
            counts.append((label, len(geoms)))
    else:
        label_radius = BASE_DIAMETER / 2 - 5.0
        for i, label in enumerate(labels):
            theta = math.pi / 2 - i * (2 * math.pi / len(labels))
            center = (label_radius * math.cos(theta), label_radius * math.sin(theta))
            angle = upright_angle(theta - math.pi / 2)
            geoms = render_label(label, center, angle, 24.0, TEXT_FIELD_MAX_HEIGHT)
            letter_geoms.extend(geoms)
            counts.append((label, len(geoms)))

    print(
        "    凹刻信息: "
        + " | ".join(f"{label}:{count}" for label, count in counts)
        + f" | 深度 {TEXT_ENGRAVE_DEPTH:.2f}mm | 字重 +{TEXT_BOLD_OFFSET:.2f}mm"
    )

    if not letter_geoms:
        return np.array([]), np.array([])

    letters = unary_union(letter_geoms)
    if letters.is_empty:
        return np.array([]), np.array([])

    rim_with_recesses = rim_polygon.difference(letters)
    if rim_with_recesses.is_empty:
        return np.array([]), np.array([])

    meshes = []
    geoms = list(rim_with_recesses.geoms) if hasattr(rim_with_recesses, "geoms") else [rim_with_recesses]
    for geom in geoms:
        if geom.is_empty or geom.area < 0.01:
            continue
        try:
            mesh = extrude_polygon(geom, height=TEXT_ENGRAVE_DEPTH)
        except Exception:
            continue
        mesh.vertices[:, 2] += engraving_floor
        meshes.append(mesh)

    if not meshes:
        return np.array([]), np.array([])

    import trimesh
    combined = trimesh.util.concatenate(meshes)
    return combined.vertices, combined.faces


# ================================================================
# 合并 + 导出
# ================================================================

def merge_meshes(*meshes):
    import trimesh
    all_meshes = []
    for verts, faces in meshes:
        if len(verts) == 0:
            continue
        all_meshes.append(trimesh.Trimesh(vertices=verts, faces=faces))
    if not all_meshes:
        return None
    return trimesh.util.concatenate(all_meshes)


def export_with_timestamp(mesh, shape, timestamp=None):
    timestamp_enabled = get_in(MAGNET_CONSTRAINTS, ["script_hooks", "timestamp_exports"], True)
    stl_path = os.path.join(OUTPUT, f"magnet_3d_{shape}.stl")
    obj_path = os.path.join(OUTPUT, f"magnet_3d_{shape}.obj")
    mesh.export(stl_path)
    mesh.export(obj_path)

    timestamp_paths = []
    if timestamp_enabled:
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        ts_stl = os.path.join(OUTPUT, f"magnet_3d_{shape}_{ts}.stl")
        ts_obj = os.path.join(OUTPUT, f"magnet_3d_{shape}_{ts}.obj")
        copyfile(stl_path, ts_stl)
        copyfile(obj_path, ts_obj)
        with open(os.path.join(OUTPUT, "magnet_3d_latest_timestamp.txt"), "w", encoding="utf-8") as f:
            f.write(ts)
        timestamp_paths = [ts_stl, ts_obj]

    return stl_path, obj_path, timestamp_paths


def main():
    parser = argparse.ArgumentParser(description="3D 打印冰箱贴模型生成")
    parser.add_argument("--shape", choices=["circle", "hexagon"], default="circle")
    parser.add_argument("--no-text", action="store_true")
    parser.add_argument("--timestamp", default=os.environ.get("MAGNET_BUILD_TIMESTAMP"))
    args = parser.parse_args()

    srtm, route, content, build_data = load_data()

    print("山野路迹 · 3D 打印冰箱贴")
    print(f"  形状: {args.shape}")
    print(f"  底座: {BASE_DIAMETER}mm × {BASE_HEIGHT}mm")
    print(f"  地形: 3D小报同源 WGS84/SRTM，按 {args.shape} 外轮廓裁切")
    print(f"  设计约束: {get_in(MAGNET_CONSTRAINTS, ['composition', 'base_structure'], 'outer_rim_with_center_recess')} / {get_in(MAGNET_CONSTRAINTS, ['composition', 'text_zone'], 'outer_rim')}")
    print()

    # 1. 底座
    print("  构建 底座...", end=" ")
    base_v, base_f = build_base_mesh(shape=args.shape, height=max(0.2, BASE_HEIGHT - TEXT_ENGRAVE_DEPTH))
    print(f"{len(base_v)} 顶点, {len(base_f)} 面")

    # 2. 地形（复用 3D 小报 SRTM 网格 + 坐标框架）
    print("  构建 地形...", end=" ")
    terrain_v, terrain_f = build_terrain_mesh(route, shape=args.shape)
    print(f"{len(terrain_v)} 顶点, {len(terrain_f)} 面")

    # 3. 轨迹管道
    print("  构建 轨迹...", end=" ")
    trail_v, trail_f = build_trail_tube(route)
    if len(trail_v) > 0:
        print(f"{len(trail_v)} 顶点, {len(trail_f)} 面")
    else:
        print("跳过")

    # 4. 文字（凹刻信息铭牌）
    if not args.no_text:
        print("  构建 凹刻文字...", end=" ")
        text_v, text_f = build_engraved_text_top_layer(route, content, shape=args.shape)
        if len(text_v) > 0:
            print(f"{len(text_v)} 顶点, {len(text_f)} 面")
        else:
            print("跳过")
    else:
        text_v, text_f = np.array([]), np.array([])

    # 5. 合并
    print("  合并...", end=" ")
    combined = merge_meshes(
        (base_v, base_f), (terrain_v, terrain_f),
        (trail_v, trail_f), (text_v, text_f),
    )
    if combined is None:
        print("失败")
        sys.exit(1)
    print(f"{len(combined.vertices)} 顶点, {len(combined.faces)} 面")

    # 6. 导出
    stl_path, obj_path, timestamp_paths = export_with_timestamp(combined, args.shape, args.timestamp)
    print(f"\n  ✓ {stl_path} ({os.path.getsize(stl_path) / 1024:.0f} KB)")
    print(f"  ✓ {obj_path} ({os.path.getsize(obj_path) / 1024:.0f} KB)")
    for path in timestamp_paths:
        print(f"  ✓ {path} ({os.path.getsize(path) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
