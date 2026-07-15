#!/usr/bin/env python3
"""
Build trail poster: paper-cut contour 3D scene — self-contained.

All data processing is internal; the script no longer parses an older HTML build.

Pipeline:
  1. GCJ-02 → WGS-84 coordinate conversion
  2. SRTM1 30m elevation grid (200×200)
  3. Unified 3D coordinate mapping
  4. GPX speed extraction for trail coloring
  5. Photo marker cleaning + distance dedup
  6. Generate final HTML (Three.js 3D scene)
  7. Output build_data.json for downstream scripts
"""
import json as _json
import math
import base64 as _b64
import struct as _struct
import urllib.request
import io
import zipfile
import os
import re as _re
import shutil as _shutil
import subprocess as _subprocess
import tempfile as _tempfile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.parent
REFERENCES = Path(os.environ.get("SHANYE_REFERENCES_ROOT", BASE_DIR / "references"))
OUTPUT = Path(os.environ.get("SHANYE_OUTPUT_ROOT", BASE_DIR / "output"))
sys.path.insert(0, str(BASE_DIR / "scripts"))
from design_constraints import get_in, load_design_constraints, product_constraints
from platform_utils import CSS_FONT_STACK
from render_engine import get_tokens

_tokens = get_tokens()
_constraints = load_design_constraints(BASE_DIR)
_poster_constraints = product_constraints(_constraints, "poster_3d")
_source_constraints = _constraints.get("source", {})
_poster_palette = get_in(_poster_constraints, ["script_hooks", "product_palette"], {})
POSTER_STYLE = get_in(
    _poster_constraints,
    ["script_hooks", "style_variant"],
    get_in(_poster_constraints, ["script_hooks", "visual_treatment"], "terrain_control_console"),
)
POSTER_TEXTURE_LEVEL = get_in(_poster_constraints, ["script_hooks", "texture_level"], "medium")
POSTER_DATA_DENSITY = get_in(_poster_constraints, ["script_hooks", "data_density"], "medium")
POSTER_IS_EXPEDITION = POSTER_STYLE == "expedition_dashboard"


def _hex_color(value, fallback):
    if isinstance(value, str) and _re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()):
        return value.strip()
    return fallback


def _rgb_tuple(value):
    h = value.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgba_from_hex(value, alpha):
    r, g, b = _rgb_tuple(value)
    return f"rgba({r},{g},{b},{alpha})"


def _js_rgb_array(value):
    return "[" + ",".join(f"{channel / 255:.4f}" for channel in _rgb_tuple(value)) + "]"


POSTER_BACKGROUND = _hex_color(_poster_palette.get("background"), "#10120f")
POSTER_PANEL = _hex_color(_poster_palette.get("panel"), _tokens.hex("cream"))
POSTER_PANEL_INK = _hex_color(_poster_palette.get("panel_ink"), "#181a14")
POSTER_TERRAIN_LOW = _hex_color(_poster_palette.get("terrain_low"), "#3d5233")
POSTER_TERRAIN_HIGH = _hex_color(_poster_palette.get("terrain_high"), "#d6bd76")
POSTER_TERRAIN_EDGE = _hex_color(_poster_palette.get("terrain_edge"), "#b99e7a")
POSTER_TERRAIN_SIDE = _hex_color(_poster_palette.get("terrain_side"), "#63482e")
POSTER_ACCENT = _hex_color(_poster_palette.get("accent"), _tokens.hex("accent"))
POSTER_GOLD = _hex_color(_poster_palette.get("route_line_gold"), _tokens.hex("gold"))
POSTER_TERRAIN_LOW_JS = _js_rgb_array(POSTER_TERRAIN_LOW)
POSTER_TERRAIN_HIGH_JS = _js_rgb_array(POSTER_TERRAIN_HIGH)
POSTER_TERRAIN_EDGE_JS = _js_rgb_array(POSTER_TERRAIN_EDGE)
POSTER_TERRAIN_SIDE_JS = _js_rgb_array(POSTER_TERRAIN_SIDE)
POSTER_BODY_CLASS = "style-expedition-dashboard" if POSTER_IS_EXPEDITION else "style-terrain-control-console"
POSTER_PANEL_LABEL = "EXPEDITION DASHBOARD" if POSTER_IS_EXPEDITION else "TERRAIN CONTROL"
POSTER_HINT_TEXT = "拖拽旋转 · 滚轮缩放 · 点击证据点" if POSTER_IS_EXPEDITION else "拖拽旋转 · 滚轮缩放 · 点击标记查看"
POSTER_SECTION_PHOTO_LABEL = "现场证据"
POSTER_SECTION_STORY_LABEL = "行动记录" if POSTER_IS_EXPEDITION else "路线记录"
POSTER_FOOTER_LABEL = "HARD ROUTE LOG" if POSTER_IS_EXPEDITION else "徒步纪念"
POSTER_GRID_SIZE = "38px 38px" if POSTER_IS_EXPEDITION else "54px 54px"
POSTER_INFO_BORDER = "12px solid " + POSTER_GOLD if POSTER_IS_EXPEDITION else "8px solid " + POSTER_GOLD
POSTER_PANEL_WIDTH = "clamp(370px, 34vw, 520px)" if POSTER_IS_EXPEDITION else "clamp(340px, 32vw, 470px)"

# ============================================================
# GCJ-02 ↔ WGS-84 Conversion
# ============================================================
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

def gcj02_to_wgs84(lat, lon, precision=6):
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlon = (dlon * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return round(lat - dlat, precision), round(lon - dlon, precision)


# ============================================================
# Step 1: Load and convert GPX data (GCJ-02 → WGS-84)
# ============================================================
print("=" * 60)
print("Step 1: GCJ-02 → WGS-84 conversion")

with open(REFERENCES / "route_data.json", "r") as f:
    route_data = _json.load(f)
with open(REFERENCES / "content_assets.json", "r", encoding="utf-8") as f:
    content_assets = _json.load(f)

dist_display = f"{route_data.get('total_distance_km', 0):.2f}"
gain_display = f"{int(route_data.get('elevation_gain', 0)):,}"
gain_plain = f"{int(route_data.get('elevation_gain', 0))}"
max_elev_display = f"{int(route_data.get('max_elevation', 0))}"
duration_seconds = route_data.get("duration_seconds", 0)
duration_compact = f"{int(duration_seconds // 3600)}h{int((duration_seconds % 3600) // 60):02d}m"
route_name_display = get_in(
    _poster_constraints,
    ["copy_strategy", "title"],
    _source_constraints.get("route_name", content_assets.get("route_name", "山野路迹")),
)
route_place_display = get_in(
    _poster_constraints,
    ["copy_strategy", "place_label"],
    _source_constraints.get("place_name", content_assets.get("place_name", "徒步路线")),
)
team_name_display = get_in(
    _poster_constraints,
    ["copy_strategy", "team_label"],
    _source_constraints.get("team_name", content_assets.get("team_name", "山野路迹")),
)
story_text_display = get_in(
    _poster_constraints,
    ["copy_strategy", "story_quote"],
    content_assets.get("hike_story", "").strip() or "真实记录",
)


def _image_data_url(path):
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    data = path.read_bytes()
    return f"data:{mime};base64,{_b64.b64encode(data).decode('ascii')}"


def _photo_texture_data_url(photo_rel, max_px=180):
    """Embed small marker thumbnails so WebGL textures work from file:// URLs."""
    photo_path = OUTPUT / photo_rel
    if not photo_path.exists():
        return None

    try:
        from PIL import Image

        with Image.open(photo_path) as img:
            img = img.convert("RGB")
            img.thumbnail((max_px, max_px))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=72, optimize=True)
            return f"data:image/jpeg;base64,{_b64.b64encode(buf.getvalue()).decode('ascii')}"
    except Exception:
        pass

    sips = _shutil.which("sips")
    if sips:
        try:
            with _tempfile.TemporaryDirectory() as tmp:
                thumb_path = Path(tmp) / f"{photo_path.stem}_thumb.jpg"
                cmd = [
                    sips,
                    "-Z",
                    str(max_px),
                    "-s",
                    "format",
                    "jpeg",
                    "-s",
                    "formatOptions",
                    "70",
                    str(photo_path),
                    "--out",
                    str(thumb_path),
                ]
                _subprocess.run(cmd, check=True, capture_output=True)
                if thumb_path.exists() and thumb_path.stat().st_size > 0:
                    return _image_data_url(thumb_path)
        except Exception:
            pass

    return _image_data_url(photo_path)

# Convert all track points
track_points = route_data["track_points"]
wgs84_points = []
for p in track_points:
    wgs_lat, wgs_lon = gcj02_to_wgs84(p["lat"], p["lon"])
    wgs84_points.append({
        "lat": wgs_lat, "lon": wgs_lon,
        "ele": p["ele"], "time": p.get("time"),
        "cumulative_distance_m": p.get("cumulative_distance_m", 0)
    })

# WGS84 route bounds
wgs_lats = [p["lat"] for p in wgs84_points]
wgs_lons = [p["lon"] for p in wgs84_points]
ROUTE_LAT_MIN = min(wgs_lats)
ROUTE_LAT_MAX = max(wgs_lats)
ROUTE_LON_MIN = min(wgs_lons)
ROUTE_LON_MAX = max(wgs_lons)

print(f"  Route WGS-84 bounds: lat [{ROUTE_LAT_MIN:.6f}, {ROUTE_LAT_MAX:.6f}]")
print(f"                       lon [{ROUTE_LON_MIN:.6f}, {ROUTE_LON_MAX:.6f}]")

# Convert photo markers
with open(REFERENCES / "photo_markers_3d.json", "r") as f:
    old_markers = _json.load(f)

wgs84_markers = []
for m in old_markers:
    wgs_lat, wgs_lon = gcj02_to_wgs84(m["lat"], m["lon"])
    wgs84_markers.append({
        "lat": wgs_lat, "lon": wgs_lon,
        "ele": m["ele"], "title": m["title"], "photo": m["photo"]
    })
print(f"  Converted {len(wgs84_markers)} photo markers")

# ============================================================
# Step 2: SRTM1 30m elevation grid
# ============================================================
print("=" * 60)
print("Step 2: SRTM1 elevation grid (200×200)")

GRID_SIZE = 200

TERRAIN_PAD_RATIO = float(get_in(_poster_constraints, ["script_hooks", "terrain_pad_ratio"], 0.28))
lat_pad = (ROUTE_LAT_MAX - ROUTE_LAT_MIN) * TERRAIN_PAD_RATIO
lon_pad = (ROUTE_LON_MAX - ROUTE_LON_MIN) * TERRAIN_PAD_RATIO
WGS_LAT_MIN = ROUTE_LAT_MIN - lat_pad
WGS_LAT_MAX = ROUTE_LAT_MAX + lat_pad
WGS_LON_MIN = ROUTE_LON_MIN - lon_pad
WGS_LON_MAX = ROUTE_LON_MAX + lon_pad
srtm_lat_min = WGS_LAT_MIN
srtm_lat_max = WGS_LAT_MAX
srtm_lon_min = WGS_LON_MIN
srtm_lon_max = WGS_LON_MAX

print(f"  Terrain expanded bounds (+{TERRAIN_PAD_RATIO:.0%}): lat [{WGS_LAT_MIN:.6f}, {WGS_LAT_MAX:.6f}]")
print(f"                                        lon [{WGS_LON_MIN:.6f}, {WGS_LON_MAX:.6f}]")

tile_names = []
for lat_base in range(int(math.floor(srtm_lat_min)), int(math.floor(srtm_lat_max)) + 1):
    for lon_base in range(int(math.floor(srtm_lon_min)), int(math.floor(srtm_lon_max)) + 1):
        tile_names.append(f"N{lat_base:02d}E{lon_base:03d}")
print(f"  SRTM tiles needed: {tile_names}")


def download_srtm_hgt(tile_name):
    cache_dir = Path(os.environ.get("SHANYE_SRTM_CACHE", Path.home() / ".cache" / "shanye-luji" / "srtm"))
    cache_dir.mkdir(exist_ok=True)
    hgt_path = cache_dir / f"{tile_name}.hgt"
    if hgt_path.exists():
        print(f"  Using cached {tile_name}.hgt ({hgt_path.stat().st_size} bytes)")
        return hgt_path

    urls = [
        f"https://step.esa.int/auxdata/dem/SRTMGL1/{tile_name}.SRTMGL1.hgt.zip",
        f"https://srtm.kurviger.de/SRTM1/{tile_name}.hgt.zip",
    ]

    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE

    for url in urls:
        try:
            print(f"  Trying: {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "LearnBuddy/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=_ctx) as resp:
                data = resp.read()
            if data[:2] == b'PK':
                print(f"  Extracting ZIP ({len(data)} bytes)")
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    names = zf.namelist()
                    hgt_name = next((n for n in names if n.endswith('.hgt')), names[0])
                    hgt_data = zf.read(hgt_name)
                with open(hgt_path, 'wb') as f:
                    f.write(hgt_data)
            else:
                with open(hgt_path, 'wb') as f:
                    f.write(data)
            print(f"  Saved {tile_name}.hgt ({hgt_path.stat().st_size} bytes)")
            return hgt_path
        except Exception as e:
            print(f"  Failed: {e}")
            continue
    raise RuntimeError(f"Could not download SRTM tile {tile_name}")


def read_srtm_elevation_from_tile(hgt_path, lat, lon, tile_lat, tile_lon, rows=3601):
    row = int((tile_lat + 1 - lat) * (rows - 1))
    col = int((lon - tile_lon) * (rows - 1))
    row = max(0, min(rows - 1, row))
    col = max(0, min(rows - 1, col))
    with open(hgt_path, 'rb') as f:
        f.seek((row * rows + col) * 2)
        val = _struct.unpack('>h', f.read(2))[0]
    return max(0, val)


def read_srtm_elevation(tile_map, lat, lon):
    tile_lon_base = int(math.floor(lon))
    tile_lat_base = int(math.floor(lat))
    tile_lat_sign = 'N' if tile_lat_base >= 0 else 'S'
    tile_lon_sign = 'E' if tile_lon_base >= 0 else 'W'
    tile_name = f"{tile_lat_sign}{abs(tile_lat_base):02d}{tile_lon_sign}{abs(tile_lon_base):03d}"
    if tile_name in tile_map:
        return read_srtm_elevation_from_tile(tile_map[tile_name], lat, lon, tile_lat_base, tile_lon_base)
    else:
        hgt_path = list(tile_map.values())[0]
        rows = 3601
        tile_lat_base = int(tile_name[1:3]) if tile_name[0] == 'N' else -int(tile_name[1:3])
        tile_lon_base = int(tile_name[4:7]) if tile_name[3] == 'E' else -int(tile_name[4:7])
        return read_srtm_elevation_from_tile(hgt_path, lat, lon, tile_lat_base, tile_lon_base)


# Download tiles
hgt_tiles = {}
for tile_name in tile_names:
    hgt_tiles[tile_name] = download_srtm_hgt(tile_name)

# Build elevation grid
print(f"  Building {GRID_SIZE}×{GRID_SIZE} elevation grid...")
elevation_grid = []
for row in range(GRID_SIZE):
    row_data = []
    lat = WGS_LAT_MAX - row * (WGS_LAT_MAX - WGS_LAT_MIN) / (GRID_SIZE - 1)
    for col in range(GRID_SIZE):
        lon = WGS_LON_MIN + col * (WGS_LON_MAX - WGS_LON_MIN) / (GRID_SIZE - 1)
        row_data.append(read_srtm_elevation(hgt_tiles, lat, lon))
    elevation_grid.append(row_data)

flat_grid = [v for row in elevation_grid for v in row]
ELEV_MIN = min(v for v in flat_grid if v > 0)
ELEV_MAX = max(flat_grid)
print(f"  Elevation range: {ELEV_MIN}m - {ELEV_MAX}m")

# Encode grid as base64 (uint16 little-endian)
grid_bytes = _struct.pack(f'<{GRID_SIZE*GRID_SIZE}H', *flat_grid)
GRID_B64 = _b64.b64encode(grid_bytes).decode('ascii')

# Save WGS84 elevation JSON (for reference)
srtm_out = {
    "bounds": {"lat_min": WGS_LAT_MIN, "lat_max": WGS_LAT_MAX,
               "lon_min": WGS_LON_MIN, "lon_max": WGS_LON_MAX},
    "grid": {"size": GRID_SIZE, "elevation": elevation_grid},
    "stats": {"min": ELEV_MIN, "max": ELEV_MAX}
}
REFERENCES.mkdir(parents=True, exist_ok=True)
with open(REFERENCES / "srtm_elevation_wgs84.json", "w") as f:
    _json.dump(srtm_out, f, ensure_ascii=False)

# ============================================================
# Step 3: Build unified 3D coordinates
# ============================================================
print("=" * 60)
print("Step 3: Unified coordinate mapping")

lat_range = WGS_LAT_MAX - WGS_LAT_MIN
lon_range = WGS_LON_MAX - WGS_LON_MIN

# TUBE_PTS from WGS84 track points
TUBE_PTS = []
for p in wgs84_points:
    wx = (p["lon"] - WGS_LON_MIN) / lon_range * 10.0
    wz = (WGS_LAT_MAX - p["lat"]) / lat_range * 8.0
    wy = p["ele"]
    TUBE_PTS.append([round(wx, 6), round(wy, 1), round(wz, 6)])

# PHOTO_MARKERS from WGS84 markers
PHOTO_MARKERS_RAW = []
for m in wgs84_markers:
    wx = (m["lon"] - WGS_LON_MIN) / lon_range * 10.0
    wz = (WGS_LAT_MAX - m["lat"]) / lat_range * 8.0
    wy = m["ele"]
    PHOTO_MARKERS_RAW.append({
        "x": round(wx, 3), "y": round(wy, 1), "z": round(wz, 3),
        "ele": m["ele"], "title": m["title"], "photo": m["photo"],
        "lat": m["lat"], "lon": m["lon"],
    })

print(f"  TUBE_PTS: {len(TUBE_PTS)} points")
print(f"  PHOTO_MARKERS: {len(PHOTO_MARKERS_RAW)}")

# ============================================================
# Step 4: Extract GPX speed data
# ============================================================
print("=" * 60)
print("Step 4: GPX speed extraction")

def _parse_iso_time(value):
    if not value:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


speeds = [float(p.get("speed")) for p in track_points if p.get("speed") is not None]
if len(speeds) < len(track_points) * 0.5:
    estimated = [0.0]
    for prev, cur in zip(track_points, track_points[1:]):
        t0 = _parse_iso_time(prev.get("time"))
        t1 = _parse_iso_time(cur.get("time"))
        dt = (t1 - t0).total_seconds() if t0 and t1 else 0
        dd = float(cur.get("cumulative_distance_m", 0)) - float(prev.get("cumulative_distance_m", 0))
        estimated.append(max(0.0, dd / dt) if dt > 0 else 0.0)
    speeds = estimated
SPEEDS = speeds
if speeds:
    print(f"  Speeds: {len(speeds)} points, range [{min(speeds):.2f}-{max(speeds):.2f}] m/s")
else:
    print("  Speeds: unavailable")

# ============================================================
# Step 5: Clean & dedup photo markers
# ============================================================
print("=" * 60)
print("Step 5: Photo marker cleaning + SRTM elevation")

# Decode SRTM grid for SRTM elevation lookups
b = _b64.b64decode(GRID_B64)
grid_flat = list(_struct.unpack(f'<{len(b)//2}H', b))


def srtm_elev_py(wx, wz):
    gs = GRID_SIZE
    col = max(0, min(gs - 1, round(wx / 10 * (gs - 1))))
    row = max(0, min(gs - 1, round(wz / 8 * (gs - 1))))
    idx = row * gs + col
    e = grid_flat[idx]
    return e if e > 0 else None


# Clean titles
for m in PHOTO_MARKERS_RAW:
    t = m.get("title", "")
    if _re.match(r'合照\d+', t):
        m["title"] = f"途中{int(t[2:]):02d}"

# Distance-based dedup
def world_dist(a, b):
    return ((a["x"] - b["x"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5


deduped = []
seen_photos = set()
for m in PHOTO_MARKERS_RAW:
    if m["photo"] in seen_photos:
        continue
    is_dup = False
    for d in deduped:
        if world_dist(m, d) < 0.15:
            is_dup = True
            break
    if not is_dup:
        se = srtm_elev_py(m["x"], m["z"])
        if se is not None:
            m["srtm_ele"] = se
            m["ele"] = se
        deduped.append(m)
        seen_photos.add(m["photo"])

PHOTO_MARKERS = deduped
for m in PHOTO_MARKERS:
    thumb = _photo_texture_data_url(m.get("photo", ""))
    if thumb:
        m["thumb"] = thumb
print(f"  Photo markers: {len(PHOTO_MARKERS_RAW)} → {len(PHOTO_MARKERS)} after cleaning")

# ============================================================
# Step 6: Output build_data.json for downstream scripts
# ============================================================
print("=" * 60)
print("Step 6: Output build_data.json")

build_data = {
    "grid_size": GRID_SIZE,
    "elev_min": ELEV_MIN,
    "elev_max": ELEV_MAX,
    "grid_b64": GRID_B64,
    "tube_pts": TUBE_PTS,
    "speeds": SPEEDS,
    "photo_markers": PHOTO_MARKERS,
    "terrain_pad_ratio": TERRAIN_PAD_RATIO,
    "gps_bounds": {
        "lat_min": ROUTE_LAT_MIN, "lat_max": ROUTE_LAT_MAX,
        "lon_min": ROUTE_LON_MIN, "lon_max": ROUTE_LON_MAX,
    },
    "terrain_bounds": {
        "lat_min": WGS_LAT_MIN, "lat_max": WGS_LAT_MAX,
        "lon_min": WGS_LON_MIN, "lon_max": WGS_LON_MAX,
    }
}

output_dir = OUTPUT
output_dir.mkdir(parents=True, exist_ok=True)
with open(output_dir / "build_data.json", "w", encoding="utf-8") as f:
    _json.dump(build_data, f, ensure_ascii=False, indent=2)
print(f"  Written build_data.json ({len(_json.dumps(build_data))} chars)")

# ============================================================
# Step 7: Serialize JS data
# ============================================================
TUBE_PTS_JS = _json.dumps(TUBE_PTS)
PHOTO_MARKERS_JS = _json.dumps(PHOTO_MARKERS, ensure_ascii=False)
SPEEDS_JS = "[" + ",".join(f"{s:.4f}" for s in SPEEDS) + "]"

# ============================================================
# Step 8: Generate HTML (Paper-Cut Contour Aesthetic)
# ============================================================
print("=" * 60)
print("Step 8: Generate 3D Poster HTML")

HTML = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>山野路迹 · {route_name_display}</title>
<style>
/* ===== Trail Poster Design System (powered by render_engine.DesignTokens) ===== */
:root {{
  --paper: {POSTER_PANEL};
  --paper-warm: {_tokens.hex("warm_sand")};
  --paper-dark: {_tokens.hex("warm_sand")};
  --pine-light: {_tokens.hex("pine_light")};
  --pine: {_tokens.hex("pine")};
  --pine-dark: {_tokens.hex("pine_dark")};
  --mineral: {_tokens.hex("mineral")};
  --mineral-dark: {_tokens.hex("mineral_dark")};
  --earth: {_tokens.hex("earth_gold")};
  --earth-light: {_tokens.hex("earth_light")};
  --sand: {_tokens.hex("warm_sand")};
  --text-primary: {_tokens.hex("text_primary")};
  --text-secondary: {_tokens.hex("text_secondary")};
  --text-muted: {_tokens.hex("text_muted")};
  --text-inverse: {_tokens.hex("text_inverse")};
  --gold: {POSTER_GOLD};
  --gold-light: {_tokens.hex("gold_light")};
  --divider: {_tokens.hex("divider")};
  --poster-bg: {POSTER_BACKGROUND};
  --poster-panel-ink: {POSTER_PANEL_INK};
  --poster-accent: {POSTER_ACCENT};
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
  background: var(--poster-bg);
  color: var(--text-primary);
  font-family: {CSS_FONT_STACK};
  height: 100dvh; display: flex; overflow: hidden;
  -webkit-font-smoothing: antialiased;
}}

/* ===== 3D Viewer ===== */
.viewer-panel {{
  flex: 1; position: relative; cursor: grab; min-width: 0;
  background:
    linear-gradient({_rgba_from_hex(POSTER_PANEL, 0.035)} 1px, transparent 1px),
    linear-gradient(90deg, {_rgba_from_hex(POSTER_PANEL, 0.035)} 1px, transparent 1px),
    var(--poster-bg);
  background-size: {POSTER_GRID_SIZE};
}}
.style-expedition-dashboard .viewer-panel::before {{
  content: ''; position: absolute; inset: 0; pointer-events: none; z-index: 1;
  background:
    radial-gradient(circle at 12% 18%, {_rgba_from_hex(POSTER_GOLD, 0.14)}, transparent 28%),
    linear-gradient(135deg, transparent 0 48%, {_rgba_from_hex(POSTER_ACCENT, 0.08)} 49% 51%, transparent 52% 100%);
  mix-blend-mode: screen;
}}
.style-expedition-dashboard .viewer-panel::after {{
  content: ''; position: absolute; inset: 24px; pointer-events: none; z-index: 2;
  border: 1px dashed {_rgba_from_hex(POSTER_GOLD, 0.42)};
}}
.style-expedition-dashboard {{
  display: block;
}}
.style-expedition-dashboard .viewer-panel {{
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100dvh;
  flex: none;
}}
.style-expedition-dashboard .viewer-hint {{
  bottom: 30px;
  left: 50%;
  background: {_rgba_from_hex(POSTER_PANEL, 0.78)};
  color: {POSTER_PANEL_INK};
  z-index: 30;
}}
.viewer-panel:active {{ cursor: grabbing; }}
.viewer-panel canvas {{ display: block; }}

.viewer-hint {{
  position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
  color: var(--text-muted); font-size: 11px; pointer-events: none;
  transition: opacity 0.6s; letter-spacing: 1.5px; z-index: 5;
  background: rgba(245,240,232,0.9); padding: 6px 16px;
  border-radius: 0; backdrop-filter: none;
}}

.viewer-title {{
  position: absolute; top: 20px; left: 24px;
  font-size: 13px; font-weight: 900; color: rgba(245,240,232,0.72);
  letter-spacing: 1px; pointer-events: none; z-index: 5;
  writing-mode: horizontal-tb; text-orientation: mixed;
}}
.style-expedition-dashboard .viewer-title {{
  top: 30px; left: 34px;
  padding: 8px 12px;
  border: 1px solid {_rgba_from_hex(POSTER_GOLD, 0.42)};
  color: {POSTER_GOLD};
  background: {_rgba_from_hex(POSTER_BACKGROUND, 0.54)};
}}
.style-expedition-dashboard .photo-hint {{
  z-index: 40;
}}

.photo-hint {{
  position: absolute; background: {_tokens.rgba("text_primary",0.92)}; color: var(--text-inverse);
  padding: 6px 14px; border-radius: 6px; font-size: 12px;
  white-space: nowrap; pointer-events: none; opacity: 0;
  transition: opacity 0.15s; z-index: 10;
  font-family: {CSS_FONT_STACK};
}}
.photo-hint.visible {{ opacity: 1; }}

/* ===== Lightbox ===== */
.lightbox {{
  position: fixed; inset: 0; background: {_tokens.rgba("dark",0.95)}; z-index: 100;
  display: none; align-items: center; justify-content: center;
  flex-direction: column; cursor: pointer;
}}
.lightbox.active {{ display: flex; }}
.lightbox img {{
  max-width: 85vw; max-height: 70vh; border-radius: 2px;
  box-shadow: 0 2px 30px rgba(0,0,0,0.3);
  border: 8px solid {_tokens.hex("cream")};
}}
.lightbox .lb-info {{
  color: {_tokens.hex("text_muted")}; font-size: 13px; margin-top: 16px; text-align: center;
  font-family: {CSS_FONT_STACK};
}}
.lightbox .lb-close {{
  position: absolute; top: 24px; right: 32px;
  color: {_tokens.hex("earth_gold")}; font-size: 32px; cursor: pointer;
  font-weight: 300; line-height: 1;
}}

/* ===== Right Info Panel ===== */
.info-panel {{
  width: {POSTER_PANEL_WIDTH};
  background: {POSTER_PANEL};
  border-left: {POSTER_INFO_BORDER};
  overflow-y: auto; overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: {_tokens.hex("divider")} transparent;
  display: flex; flex-direction: column;
}}
.info-panel::-webkit-scrollbar {{ width: 4px; }}
.info-panel::-webkit-scrollbar-thumb {{ background: {_tokens.hex("divider")}; border-radius: 2px; }}

/* Panel Header */
.panel-header {{
  padding: 34px 30px 24px;
  border-bottom: 2px solid var(--poster-panel-ink);
  position: relative;
}}
.panel-header::after {{
  content: '{POSTER_PANEL_LABEL}';
  position: absolute; top: 14px; right: 30px;
  height: auto; background: transparent;
  font-size: 10px; color: {_tokens.hex("mineral")};
  letter-spacing: 1px; font-weight: 900;
}}
.panel-header .route-name {{
  font-size: 42px; font-weight: 900; color: var(--poster-panel-ink);
  letter-spacing: 0; line-height: 1.05;
}}
.style-expedition-dashboard .panel-header {{
  padding-top: 46px;
  background:
    repeating-linear-gradient(90deg, {_rgba_from_hex(POSTER_PANEL_INK, 0.06)} 0 18px, transparent 18px 32px),
    {POSTER_PANEL};
}}
.style-expedition-dashboard .info-panel {{
  position: fixed;
  left: 34px;
  right: 34px;
  bottom: 34px;
  width: auto;
  height: 258px;
  z-index: 20;
  display: grid;
  grid-template-columns: 320px 320px 1fr 300px;
  overflow: hidden;
  border-left: 0;
  border-top: 10px solid {POSTER_GOLD};
  border-right: 1px solid {_rgba_from_hex(POSTER_GOLD, 0.45)};
  border-bottom: 1px solid {_rgba_from_hex(POSTER_GOLD, 0.45)};
  background:
    linear-gradient(90deg, {_rgba_from_hex(POSTER_PANEL, 0.96)}, {_rgba_from_hex(POSTER_PANEL, 0.88)}),
    repeating-linear-gradient(90deg, {_rgba_from_hex(POSTER_PANEL_INK, 0.06)} 0 20px, transparent 20px 36px);
  box-shadow: 0 22px 70px rgba(0,0,0,.38);
}}
.style-expedition-dashboard .panel-header {{
  grid-column: 1;
  grid-row: 1;
  padding: 42px 24px 18px;
  border-bottom: 0;
  border-right: 2px solid {POSTER_PANEL_INK};
  min-width: 0;
}}
.style-expedition-dashboard .panel-header .route-name {{
  font-size: 46px;
  text-shadow: 6px 6px 0 {_rgba_from_hex(POSTER_GOLD, 0.14)};
}}
.style-expedition-dashboard .panel-header::before {{
  content: 'HARD ROUTE LOG';
  position: absolute; left: 30px; top: 18px;
  font-size: 10px; font-weight: 900; letter-spacing: 2px;
  color: {POSTER_ACCENT};
}}
.style-expedition-dashboard .panel-header::after {{ display: none; }}
.style-expedition-dashboard .panel-header .route-sub {{
  margin-top: 10px;
}}
.style-expedition-dashboard .panel-header .route-meta {{
  font-size: 11px;
}}
.style-expedition-dashboard .elevation-section {{
  grid-column: 2;
  grid-row: 1;
  padding: 24px;
  border-bottom: 0;
  border-right: 2px solid {POSTER_PANEL_INK};
  display: flex;
  align-items: center;
}}
.style-expedition-dashboard .elevation-section canvas {{
  height: 170px;
}}
.style-expedition-dashboard .stats-section {{
  grid-column: 3;
  grid-row: 1;
  padding: 0;
  border-bottom: 0;
  grid-template-columns: repeat(4, 1fr);
}}
.style-expedition-dashboard .photo-section {{
  grid-column: 4;
  grid-row: 1;
  padding: 18px;
  border-bottom: 0;
  border-left: 2px solid {POSTER_PANEL_INK};
  overflow: hidden;
}}
.style-expedition-dashboard .photo-grid {{
  grid-template-columns: repeat(3, 1fr);
  gap: 5px;
}}
.style-expedition-dashboard .photo-card:nth-child(n+7) {{
  display: none;
}}
.style-expedition-dashboard .story-section {{
  display: none;
}}
.style-expedition-dashboard .panel-footer {{
  position: fixed;
  right: 42px;
  top: 38px;
  z-index: 30;
  padding: 8px 12px;
  border: 1px solid {_rgba_from_hex(POSTER_GOLD, 0.42)};
  background: {_rgba_from_hex(POSTER_BACKGROUND, 0.58)};
  color: {POSTER_GOLD};
}}
.panel-header .route-sub {{
  font-size: 14px; color: var(--poster-accent);
  margin-top: 14px; letter-spacing: 0;
  font-weight: 900;
}}
.panel-header .route-meta {{
  font-size: 12px; color: {_tokens.hex("mineral")};
  margin-top: 6px; opacity: 1;
  font-weight: 800;
}}

/* Elevation Profile */
.elevation-section {{
  padding: 18px 30px;
  border-bottom: 2px solid var(--poster-panel-ink);
}}
.elevation-section canvas {{
  width: 100%; height: 80px; display: block;
  border-radius: 2px;
}}

/* Stats Grid */
.stats-section {{
  display: grid; grid-template-columns: 1fr 1fr;
  padding: 0 30px;
  border-bottom: 2px solid var(--poster-panel-ink);
  gap: 0;
}}
.stat-card {{
  text-align: left; padding: 18px 12px;
  background: transparent;
  border-radius: 0;
  border: 0;
  border-right: 1px solid {_rgba_from_hex(POSTER_PANEL_INK, 0.24)};
  border-bottom: 1px solid {_rgba_from_hex(POSTER_PANEL_INK, 0.24)};
}}
.stat-card:nth-child(2n) {{ border-right: 0; }}
.stat-card:nth-child(n+3) {{ border-bottom: 0; }}
.stat-card .stat-value {{
  font-size: 30px; font-weight: 900;
  color: var(--poster-panel-ink); letter-spacing: 0;
  font-variant-numeric: tabular-nums;
}}
.style-expedition-dashboard .stat-card {{
  background: {_rgba_from_hex(POSTER_GOLD, 0.07)};
}}
.style-expedition-dashboard .stat-card .stat-value {{
  font-size: 38px;
}}
.style-expedition-dashboard .stat-card .stat-label {{
  font-size: 11px;
}}
.stat-card .stat-value.accent {{ color: var(--gold); }}
.stat-card .stat-value.climb {{ color: var(--poster-accent); }}
.stat-card .stat-label {{
  font-size: 10px; color: {_tokens.hex("mineral")};
  margin-top: 4px; letter-spacing: 0;
  text-transform: none; font-weight: 900;
}}

/* Photo Strip */
.photo-section {{
  padding: 20px 30px;
  border-bottom: 2px solid var(--poster-panel-ink);
}}
.photo-section .section-label {{
  font-size: 12px; color: var(--poster-panel-ink);
  letter-spacing: 1px; margin-bottom: 12px;
  text-transform: none; font-weight: 900;
}}
.photo-grid {{
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}}
.photo-card {{
  aspect-ratio: 1; position: relative; cursor: pointer;
  transition: transform 0.2s ease;
  border-radius: 0; overflow: hidden;
}}
.photo-card:hover {{ transform: scale(1.05); z-index: 2; }}
.photo-card img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
}}
.photo-card::after {{
  content: ''; position: absolute; inset: 0;
  border: 2px solid {_rgba_from_hex(POSTER_GOLD, 0.75)};
  pointer-events: none;
}}
.photo-card .elevation-tag {{
  position: absolute; bottom: 4px; right: 4px;
  background: {_tokens.rgba("text_primary",0.75)}; color: {_tokens.hex("cream")};
  font-size: 9px; padding: 2px 5px; border-radius: 2px;
  font-family: {CSS_FONT_STACK};
  pointer-events: none;
}}

/* Story Section */
.story-section {{
  padding: 22px 30px;
  border-bottom: 2px solid var(--poster-panel-ink);
  flex: 1;
}}
.story-section .section-label {{
  font-size: 12px; color: var(--poster-panel-ink);
  letter-spacing: 1px; margin-bottom: 12px;
  text-transform: none; font-weight: 900;
}}
.story-text {{
  font-size: 13px; line-height: 1.85; color: var(--poster-panel-ink);
}}
.story-text .highlight {{
  color: var(--pine-dark); font-weight: 600;
}}
.story-quote {{
  margin-top: 14px; padding: 12px 16px;
  border: 1px solid {_rgba_from_hex(POSTER_PANEL_INK, 0.28)};
  background: {_rgba_from_hex(POSTER_GOLD, 0.12)};
  font-style: normal; color: var(--poster-panel-ink);
  font-size: 13px; line-height: 1.8;
}}
.style-expedition-dashboard .story-quote {{
  border: 2px dashed {_rgba_from_hex(POSTER_ACCENT, 0.44)};
  background: {_rgba_from_hex(POSTER_ACCENT, 0.09)};
  font-weight: 800;
}}

/* Panel Footer */
.panel-footer {{
  padding: 14px 28px;
  font-size: 10px; color: {_tokens.hex("mineral")};
  text-align: center; letter-spacing: 1px;
  border-top: 0;
  opacity: 1; font-weight: 800;
}}

/* ===== Responsive ===== */
@media (max-width: 900px) {{
  .info-panel {{ width: clamp(260px, 34vw, 340px); }}
  .panel-header {{ padding: 20px 20px 16px; }}
  .panel-header .route-name {{ font-size: 22px; }}
  .stats-section {{ padding: 12px 20px; gap: 8px; }}
  .photo-section, .story-section {{ padding: 12px 20px; }}
  .photo-grid {{ grid-template-columns: repeat(3, 1fr); }}
}}
@media (max-width: 640px) {{
  body {{ flex-direction: column; }}
  .viewer-panel {{ flex: none; height: 52dvh; }}
  .info-panel {{ width: 100%; max-height: 48dvh; border-left: none; border-top: 1px solid var(--divider); }}
  .panel-header .route-name {{ font-size: 20px; }}
  .photo-grid {{ grid-template-columns: repeat(4, 1fr); }}
  .stats-section {{ grid-template-columns: repeat(4, 1fr); }}
  .stat-card {{ padding: 8px 4px; }}
  .stat-card .stat-value {{ font-size: 16px; }}
}}
</style>
</head>
<body class="{POSTER_BODY_CLASS}">

<div class="viewer-panel" id="viewer">
  <div class="viewer-title">{route_place_display} · {route_name_display}</div>
  <div class="viewer-hint" id="hint">{POSTER_HINT_TEXT}</div>
  <div class="photo-hint" id="photoHint"></div>
</div>

<div class="lightbox" id="lightbox">
  <div class="lb-close">&times;</div>
  <img id="lbImg" src="" alt="">
  <div class="lb-info" id="lbInfo"></div>
</div>

<div class="info-panel">
  <div class="panel-header">
    <div class="route-name">{route_name_display}</div>
    <div class="route-sub">2025年11月22日</div>
    <div class="route-meta">{team_name_display} · SRTM1 真实地形 · WGS84 坐标</div>
  </div>

  <div class="elevation-section">
    <canvas id="elevationProfile"></canvas>
  </div>

  <div class="stats-section">
    <div class="stat-card">
      <div class="stat-value">{dist_display}</div>
      <div class="stat-label">总里程 km</div>
    </div>
    <div class="stat-card">
      <div class="stat-value climb">{gain_display}</div>
      <div class="stat-label">累计爬升 m</div>
    </div>
    <div class="stat-card">
      <div class="stat-value accent">{max_elev_display}</div>
      <div class="stat-label">最高海拔 m</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{duration_compact}</div>
      <div class="stat-label">总用时</div>
    </div>
  </div>

  <div class="photo-section">
    <div class="section-label">{POSTER_SECTION_PHOTO_LABEL}</div>
    <div class="photo-grid" id="photoGrid"></div>
  </div>

  <div class="story-section">
    <div class="section-label">{POSTER_SECTION_STORY_LABEL}</div>
    <div class="story-text">
      全程 <span class="highlight">{dist_display} 公里</span>，累计爬升 {gain_plain} 米，最高点 {max_elev_display} 米。
    </div>
    <div class="story-quote">
      "{story_text_display}"
    </div>
  </div>

  <div class="panel-footer">{team_name_display} · 山野路迹 · {POSTER_FOOTER_LABEL}</div>
</div>

<script type="importmap">
{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

// === Embedded Data (WGS84 coordinates, internally generated) ===
const GRID_SIZE={GRID_SIZE},ELEV_MIN={ELEV_MIN},ELEV_MAX={ELEV_MAX};
const TERRAIN_GRID_B64="{GRID_B64}";
const TUBE_PTS={TUBE_PTS_JS};
const SPEEDS={SPEEDS_JS};
const PHOTO_MARKERS={PHOTO_MARKERS_JS};

const GPS_LAT_MIN={ROUTE_LAT_MIN},GPS_LAT_MAX={ROUTE_LAT_MAX};
const GPS_LON_MIN={ROUTE_LON_MIN},GPS_LON_MAX={ROUTE_LON_MAX};
const TERRAIN_LAT_MIN={WGS_LAT_MIN},TERRAIN_LAT_MAX={WGS_LAT_MAX};
const TERRAIN_LON_MIN={WGS_LON_MIN},TERRAIN_LON_MAX={WGS_LON_MAX};

// === Decode SRTM Grid ===
function decodeGrid(){{
  const b=atob(TERRAIN_GRID_B64),u=new Uint8Array(b.length);
  for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);
  const v=new DataView(u.buffer),d=new Uint16Array(GRID_SIZE*GRID_SIZE);
  for(let i=0;i<d.length;i++)d[i]=v.getUint16(i*2,!0);
  return d;
}}
const terrainData=decodeGrid();

function sampleTerrain(wx,wz){{
  const gx=Math.max(0,Math.min(1,wx/10))*(GRID_SIZE-1);
  const gz=Math.max(0,Math.min(1,wz/8))*(GRID_SIZE-1);
  const c0=Math.floor(gx),r0=Math.floor(gz);
  const c1=Math.min(c0+1,GRID_SIZE-1),r1=Math.min(r0+1,GRID_SIZE-1);
  const tx=gx-c0,tz=gz-r0;
  const e00=terrainData[r0*GRID_SIZE+c0];
  const e01=terrainData[r0*GRID_SIZE+c1];
  const e10=terrainData[r1*GRID_SIZE+c0];
  const e11=terrainData[r1*GRID_SIZE+c1];
  const e0=e00*(1-tx)+e01*tx;
  const e1=e10*(1-tx)+e11*tx;
  const e=e0*(1-tz)+e1*tz;
  return e>0&&ELEV_MAX>ELEV_MIN?(e-ELEV_MIN)/(ELEV_MAX-ELEV_MIN)*5:0.02;
}}

// === Distance-based dedup (safety net, Python already cleaned) ===
function markerDist(a,b){{return Math.sqrt((a.x-b.x)**2+(a.z-b.z)**2);}}
const um=[];
const seenPhotos=new Set();
PHOTO_MARKERS.forEach(m=>{{
  if(seenPhotos.has(m.photo))return;
  const tooClose=um.some(d=>markerDist(m,d)<0.12);
  if(!tooClose){{um.push(m);seenPhotos.add(m.photo);}}
}});

// === DOM Refs ===
const viewer=document.getElementById('viewer');
const hint=document.getElementById('hint');
const photoHint=document.getElementById('photoHint');
const lb=document.getElementById('lightbox');
const lbImg=document.getElementById('lbImg');
const lbInfo=document.getElementById('lbInfo');

// ================================================================
// Trail poster scene: paper-cut contour aesthetic with natural lighting
// ================================================================

const renderer=new THREE.WebGLRenderer({{antialias:!0,alpha:!0}});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.setSize(viewer.clientWidth,viewer.clientHeight);
renderer.shadowMap.enabled=!0;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.1;
viewer.appendChild(renderer.domElement);

const scene=new THREE.Scene();
scene.background=new THREE.Color('{POSTER_BACKGROUND}');
scene.fog=new THREE.Fog('{POSTER_BACKGROUND}',13,34);

const camera=new THREE.PerspectiveCamera(50,viewer.clientWidth/viewer.clientHeight,.5,50);
camera.position.set(8,8,12);
camera.lookAt(5,1.5,4);

const controls=new OrbitControls(camera,renderer.domElement);
controls.target.set(5,1.5,4);
controls.enableDamping=!0;
controls.dampingFactor=.08;
controls.minDistance=3;
controls.maxDistance=22;
controls.maxPolarAngle=Math.PI*.65;
controls.autoRotate=!0;
controls.autoRotateSpeed=.25;
controls.update();

let ui=!1;
const sa=()=>{{if(!ui){{controls.autoRotate=!1;ui=!0;hint.style.opacity='0'}}}};
renderer.domElement.addEventListener('pointerdown',sa);
renderer.domElement.addEventListener('wheel',sa);

// Lighting: natural sunlight
const hemi=new THREE.HemisphereLight('#c9dff0','#b8a080',1.8);
scene.add(hemi);
const sun=new THREE.DirectionalLight('#fff5e8',5.5);
sun.position.set(14,10,2);
sun.castShadow=!0;
sun.shadow.mapSize.set(2048,2048);
sun.shadow.camera.near=.5;sun.shadow.camera.far=40;
sun.shadow.camera.left=-12;sun.shadow.camera.right=12;
sun.shadow.camera.top=12;sun.shadow.camera.bottom=-4;
sun.shadow.bias=-5e-5;
scene.add(sun);
const fill=new THREE.DirectionalLight('#e8dcc8',1.8);
fill.position.set(-4,3,10);
scene.add(fill);
const rim=new THREE.DirectionalLight('#e0d0c0',1.2);
rim.position.set(-2,2,-3);
scene.add(rim);

// Terrain mesh: expanded sampling + sealed relief slab
const TERRAIN_WIDTH=10,TERRAIN_DEPTH=8;
const TERRAIN_EDGE_BAND=.20;
const TERRAIN_EDGE_HEIGHT=.12;
const TERRAIN_BOTTOM_Y=-.34;

function clamp01(v){{return Math.max(0,Math.min(1,v));}}
function smootherStep(t){{
  t=clamp01(t);
  return t*t*t*(t*(t*6-15)+10);
}}
function terrainFade(wx,wz){{
  const ux=clamp01(wx/TERRAIN_WIDTH),uz=clamp01(wz/TERRAIN_DEPTH);
  const edge=Math.min(ux,1-ux,uz,1-uz);
  return smootherStep(edge/TERRAIN_EDGE_BAND);
}}
function terrainSurfaceHeight(wx,wz){{
  const raw=sampleTerrain(wx,wz);
  const fade=terrainFade(wx,wz);
  return TERRAIN_EDGE_HEIGHT+(raw-TERRAIN_EDGE_HEIGHT)*fade;
}}
function terrainColor(rawHeight,fade){{
  const t=clamp01(rawHeight/5);
  const low={POSTER_TERRAIN_LOW_JS};
  const high={POSTER_TERRAIN_HIGH_JS};
  const edge={POSTER_TERRAIN_EDGE_JS};
  const r=low[0]*(1-t)+high[0]*t;
  const g=low[1]*(1-t)+high[1]*t;
  const b=low[2]*(1-t)+high[2]*t;
  const [er,eg,eb]=edge;
  const m=.35+.65*fade;
  return [er*(1-m)+r*m,eg*(1-m)+g*m,eb*(1-m)+b*m];
}}

function buildTerrainTopGeometry(){{
  const verts=[],cols=[],idx=[];
  for(let row=0;row<GRID_SIZE;row++){{
    const wz=row/(GRID_SIZE-1)*TERRAIN_DEPTH;
    for(let col=0;col<GRID_SIZE;col++){{
      const wx=col/(GRID_SIZE-1)*TERRAIN_WIDTH;
      const raw=sampleTerrain(wx,wz);
      const fade=terrainFade(wx,wz);
      const y=terrainSurfaceHeight(wx,wz);
      const [r,g,b]=terrainColor(raw,fade);
      verts.push(wx,y,wz);
      cols.push(r,g,b);
    }}
  }}
  for(let row=0;row<GRID_SIZE-1;row++){{
    for(let col=0;col<GRID_SIZE-1;col++){{
      const a=row*GRID_SIZE+col,b=a+1,d=(row+1)*GRID_SIZE+col,c=d+1;
      idx.push(a,d,b,b,d,c);
    }}
  }}
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));
  geo.setAttribute('color',new THREE.Float32BufferAttribute(cols,3));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  return geo;
}}

function buildTerrainSideGeometry(){{
  const verts=[],cols=[],idx=[];
  const baseColor={POSTER_TERRAIN_SIDE_JS};
  function addVertex(x,y,z,color){{verts.push(x,y,z);cols.push(color[0],color[1],color[2]);}}
  function edgePoint(wx,wz){{
    const raw=sampleTerrain(wx,wz),fade=terrainFade(wx,wz);
    return {{x:wx,y:terrainSurfaceHeight(wx,wz),z:wz,color:terrainColor(raw,fade)}};
  }}
  function addQuad(p0,p1){{
    const i=verts.length/3;
    addVertex(p0.x,p0.y,p0.z,p0.color);
    addVertex(p1.x,p1.y,p1.z,p1.color);
    addVertex(p0.x,TERRAIN_BOTTOM_Y,p0.z,baseColor);
    addVertex(p1.x,TERRAIN_BOTTOM_Y,p1.z,baseColor);
    idx.push(i,i+2,i+1,i+1,i+2,i+3);
  }}
  for(let col=0;col<GRID_SIZE-1;col++){{
    const x0=col/(GRID_SIZE-1)*TERRAIN_WIDTH,x1=(col+1)/(GRID_SIZE-1)*TERRAIN_WIDTH;
    addQuad(edgePoint(x0,0),edgePoint(x1,0));
    addQuad(edgePoint(x1,TERRAIN_DEPTH),edgePoint(x0,TERRAIN_DEPTH));
  }}
  for(let row=0;row<GRID_SIZE-1;row++){{
    const z0=row/(GRID_SIZE-1)*TERRAIN_DEPTH,z1=(row+1)/(GRID_SIZE-1)*TERRAIN_DEPTH;
    addQuad(edgePoint(TERRAIN_WIDTH,z0),edgePoint(TERRAIN_WIDTH,z1));
    addQuad(edgePoint(0,z1),edgePoint(0,z0));
  }}
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));
  geo.setAttribute('color',new THREE.Float32BufferAttribute(cols,3));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  return geo;
}}

function buildTerrainBottomGeometry(){{
  const verts=[
    0,TERRAIN_BOTTOM_Y,0,
    TERRAIN_WIDTH,TERRAIN_BOTTOM_Y,0,
    TERRAIN_WIDTH,TERRAIN_BOTTOM_Y,TERRAIN_DEPTH,
    0,TERRAIN_BOTTOM_Y,TERRAIN_DEPTH,
  ];
  const cols=[
    ...{POSTER_TERRAIN_SIDE_JS},...{POSTER_TERRAIN_SIDE_JS},...{POSTER_TERRAIN_SIDE_JS},...{POSTER_TERRAIN_SIDE_JS},
  ];
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));
  geo.setAttribute('color',new THREE.Float32BufferAttribute(cols,3));
  geo.setIndex([0,1,2,0,2,3]);
  geo.computeVertexNormals();
  return geo;
}}

const terrainAssembly=new THREE.Group();
const tMesh=new THREE.Mesh(buildTerrainTopGeometry(),new THREE.MeshStandardMaterial({{
  vertexColors:!0,roughness:.62,metalness:.02,side:THREE.DoubleSide
}}));
tMesh.receiveShadow=tMesh.castShadow=!0;
terrainAssembly.add(tMesh);

const sideMat=new THREE.MeshStandardMaterial({{
  vertexColors:!0,roughness:.72,metalness:.01,side:THREE.DoubleSide
}});
const sideMesh=new THREE.Mesh(buildTerrainSideGeometry(),sideMat);
sideMesh.receiveShadow=sideMesh.castShadow=!0;
terrainAssembly.add(sideMesh);

const bottomMesh=new THREE.Mesh(buildTerrainBottomGeometry(),sideMat);
bottomMesh.receiveShadow=!0;
terrainAssembly.add(bottomMesh);
scene.add(terrainAssembly);

// Ground shadow plane
const bGeo=new THREE.PlaneGeometry(11.6,9.6);
bGeo.rotateX(-Math.PI/2);
const bMesh=new THREE.Mesh(bGeo,new THREE.MeshStandardMaterial({{
  color:'{POSTER_BACKGROUND}',roughness:.9,metalness:.02
}}));
bMesh.position.set(5,TERRAIN_BOTTOM_Y-.05,4);
bMesh.receiveShadow=!0;
scene.add(bMesh);

// Smooth tube trail with GPX speed-based color gradient
function speedColor(speed){{
  const t=Math.min(1,Math.max(0,speed/4.0));
  let r,g,b;
  if(t<.2){{const s=t/.2;r=.15+s*.25;g=.35+s*.30;b=.22-s*.05;}}
  else if(t<.45){{const s=(t-.2)/.25;r=.40+s*.35;g=.65-s*.08;b=.17-s*.05;}}
  else if(t<.7){{const s=(t-.45)/.25;r=.75+s*.22;g=.57-s*.32;b=.12-s*.05;}}
  else{{const s=(t-.7)/.3;r=.97;g=.25-s*.10;b=.07-s*.02;}}
  return [r,g,b];
}}

function createSmoothTrail(points3D,speeds){{
  const step=Math.max(1,Math.floor(points3D.length/400));
  const ctrlPts=[],ctrlSpeeds=[];
  for(let i=0;i<points3D.length;i+=step){{
    const p=points3D[i];
    const ty=sampleTerrain(p[0],p[2]);
    ctrlPts.push(new THREE.Vector3(p[0],ty+.08,p[2]));
    ctrlSpeeds.push(speeds[Math.min(i,speeds.length-1)]);
  }}
  const lastP=points3D[points3D.length-1];
  ctrlPts.push(new THREE.Vector3(lastP[0],sampleTerrain(lastP[0],lastP[2])+.08,lastP[2]));
  ctrlSpeeds.push(speeds[speeds.length-1]);
  const curve=new THREE.CatmullRomCurve3(ctrlPts,!1,'catmullrom',.5);
  const tubularSegments=ctrlPts.length*2;
  const radius=.06,radialSegments=6;
  const geo=new THREE.TubeGeometry(curve,tubularSegments,radius,radialSegments,!1);
  const vertsPerRing=radialSegments+1;
  const cols=new Float32Array(geo.attributes.position.count*3);
  for(let ring=0;ring<=tubularSegments;ring++){{
    const t=ring/tubularSegments;
    const idx=t*(ctrlSpeeds.length-1);
    const i0=Math.floor(idx),i1=Math.min(i0+1,ctrlSpeeds.length-1);
    const frac=idx-i0;
    const speed=ctrlSpeeds[i0]*(1-frac)+ctrlSpeeds[i1]*frac;
    const [r,g,b]=speedColor(speed);
    for(let v=0;v<vertsPerRing;v++){{
      const vi=(ring*vertsPerRing+v)*3;
      cols[vi]=r;cols[vi+1]=g;cols[vi+2]=b;
    }}
  }}
  geo.setAttribute('color',new THREE.BufferAttribute(cols,3));
  const mat=new THREE.MeshStandardMaterial({{
    vertexColors:!0,roughness:.32,metalness:.05,
    emissive:'{POSTER_TERRAIN_LOW}',emissiveIntensity:.12
  }});
  const mesh=new THREE.Mesh(geo,mat);
  mesh.renderOrder=1;
  mesh.receiveShadow=mesh.castShadow=!0;
  return mesh;
}}

const trailMesh=createSmoothTrail(TUBE_PTS,SPEEDS);
scene.add(trailMesh);

// Glow Tube
function createTrailGlow(points3D){{
  const step=Math.max(1,Math.floor(points3D.length/300));
  const ctrlPts=[];
  for(let i=0;i<points3D.length;i+=step){{
    const p=points3D[i];
    const ty=sampleTerrain(p[0],p[2]);
    ctrlPts.push(new THREE.Vector3(p[0],ty+.05,p[2]));
  }}
  const lastP=points3D[points3D.length-1];
  ctrlPts.push(new THREE.Vector3(lastP[0],sampleTerrain(lastP[0],lastP[2])+.05,lastP[2]));
  const curve=new THREE.CatmullRomCurve3(ctrlPts,!1,'catmullrom',.5);
  const geo=new THREE.TubeGeometry(curve,ctrlPts.length*2,.18,6,!1);
  const mat=new THREE.MeshBasicMaterial({{
    color:'{POSTER_GOLD}',transparent:!0,opacity:.11,depthTest:!0,depthWrite:!1
  }});
  const mesh=new THREE.Mesh(geo,mat);
  mesh.renderOrder=0;
  return mesh;
}}
scene.add(createTrailGlow(TUBE_PTS));

// Shadow Trail
const spts=TUBE_PTS.map(p=>new THREE.Vector3(p[0],.01,p[2]));
const sc=new THREE.CatmullRomCurve3(spts,!1,'catmullrom',.5);
const sGeo=new THREE.TubeGeometry(sc,150,.03,4,!1);
scene.add(new THREE.Mesh(sGeo,new THREE.MeshBasicMaterial({{
  color:'#000',transparent:!0,opacity:.08,depthWrite:!1
}})));

// Photo markers with frame effect
const textureLoader=new THREE.TextureLoader();
const markerMeshes=[];

function createMarkerDot(innerColor,outerColor,size){{
  const c=document.createElement('canvas');
  c.width=c.height=size;
  const ctx=c.getContext('2d');
  const cx=size/2,cy=size/2;
  const grad=ctx.createRadialGradient(cx,cy,0,cx,cy,size/2);
  grad.addColorStop(0,outerColor);
  grad.addColorStop(1,'transparent');
  ctx.fillStyle=grad;
  ctx.fillRect(0,0,size,size);
  ctx.beginPath();ctx.arc(cx,cy,size*.2,0,Math.PI*2);
  ctx.fillStyle=innerColor;ctx.fill();
  const tex=new THREE.CanvasTexture(c);tex.needsUpdate=!0;
  return tex;
}}

function createFrameTexture(frameColor,bgColor,innerW,innerH,totalW,totalH){{
  const c=document.createElement('canvas');
  c.width=totalW;c.height=totalH;
  const ctx=c.getContext('2d');
  ctx.fillStyle=frameColor;
  ctx.fillRect(0,0,totalW,totalH);
  const ox=(totalW-innerW)/2,oy=(totalH-innerH)/2;
  ctx.clearRect(ox-2,oy-2,innerW+4,innerH+4);
  ctx.strokeStyle=bgColor;
  ctx.lineWidth=4;
  ctx.strokeRect(ox,oy,innerW,innerH);
  ctx.fillStyle=frameColor;
  ctx.fillRect(0,totalH*.78,totalW,totalH*.22);
  ctx.strokeStyle='rgba(0,0,0,0.08)';
  ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(ox,oy-1);ctx.lineTo(ox+innerW,oy-1);
  ctx.stroke();
  const tex=new THREE.CanvasTexture(c);tex.needsUpdate=!0;
  return tex;
}}

const markerDotTex=createMarkerDot('{POSTER_GOLD}','{_rgba_from_hex(POSTER_GOLD, 0.6)}',64);

um.forEach(m=>{{
  const ty=sampleTerrain(m.x,m.z);
  const py=ty+.08;

  const discGeo=new THREE.PlaneGeometry(.22,.22);
  const discMat=new THREE.MeshBasicMaterial({{map:markerDotTex,transparent:!0,depthTest:!0,depthWrite:!1}});
  const disc=new THREE.Mesh(discGeo,discMat);
  disc.rotation.x=-Math.PI/2;
  disc.position.set(m.x,py,m.z);
  disc.renderOrder=2;
  disc.userData={{marker:m,type:'marker'}};
  scene.add(disc);
  markerMeshes.push(disc);

  const frameTex=createFrameTexture('{_tokens.hex("cream")}','{_tokens.hex("warm_sand")}',44,36,56,56);
  const frameMat=new THREE.SpriteMaterial({{
    map:frameTex,transparent:!0,depthTest:!0,depthWrite:!1,opacity:.95
  }});
  const frameSprite=new THREE.Sprite(frameMat);
  frameSprite.position.set(m.x,py+.56,m.z);
  frameSprite.scale.set(.42,.42,1);
  frameSprite.renderOrder=6;
  scene.add(frameSprite);
  markerMeshes.push(frameSprite);

  const spriteMat=new THREE.SpriteMaterial({{
    map:markerDotTex,transparent:!0,opacity:.8,depthTest:!0,depthWrite:!1
  }});
  const sprite=new THREE.Sprite(spriteMat);
  sprite.position.set(m.x,py+.565,m.z);
  sprite.scale.set(.27,.27,1);
  sprite.userData={{marker:m,type:'photo-sprite'}};
  sprite.renderOrder=7;
  scene.add(sprite);
  markerMeshes.push(sprite);

  textureLoader.load(
    m.thumb||m.photo,
    tex=>{{
      tex.colorSpace=THREE.SRGBColorSpace;
      sprite.material=new THREE.SpriteMaterial({{
        map:tex,transparent:!1,depthTest:!0,depthWrite:!1
      }});
      sprite.scale.set(.27,.27,1);
      sprite.renderOrder=7;
      sprite.material.needsUpdate=!0;
    }},
    undefined,err=>{{console.warn('Photo marker texture failed',m.photo,err);}}
  );
}});

// Field-dossier treatment: no decorative cloud particles on the dark survey table.

// Raycaster Interaction
const rc=new THREE.Raycaster();
const ms=new THREE.Vector2();
let hm=null;

viewer.addEventListener('pointermove',e=>{{
  ms.x=(e.clientX/viewer.clientWidth)*2-1;
  ms.y=-(e.clientY/viewer.clientHeight)*2+1;
  rc.setFromCamera(ms,camera);
  const is=rc.intersectObjects(markerMeshes);
  if(is.length>0){{
    const o=is[0].object;
    if((o.userData.type==='marker'||o.userData.type==='photo-sprite')&&o.userData.marker!==hm){{
      hm=o.userData.marker;
      const m=o.userData.marker;
      const se=Math.round(ELEV_MIN+sampleTerrain(m.x,m.z)/5*(ELEV_MAX-ELEV_MIN));
      photoHint.textContent=`${{m.title}} · ${{se}}m`;
      photoHint.style.left=(e.clientX+16)+'px';
      photoHint.style.top=(e.clientY-12)+'px';
      photoHint.classList.add('visible');
    }}
  }}else{{
    hm=null;photoHint.classList.remove('visible');
  }}
}});

viewer.addEventListener('click',e=>{{
  ms.x=(e.clientX/viewer.clientWidth)*2-1;
  ms.y=-(e.clientY/viewer.clientHeight)*2+1;
  rc.setFromCamera(ms,camera);
  const is=rc.intersectObjects(markerMeshes);
  if(is.length>0){{
    const ud=is[0].object.userData;
    if(ud.type==='marker'||ud.type==='photo-sprite'){{
      const m=ud.marker;
      const se=Math.round(ELEV_MIN+sampleTerrain(m.x,m.z)/5*(ELEV_MAX-ELEV_MIN));
      m.ele=se;
      lbImg.src=m.photo;
      lbInfo.innerHTML=`<strong>${{m.title}}</strong><br>${{se}}m · SRTM`;
      lb.classList.add('active');
      e.stopPropagation();
    }}
  }}
}});
lb.addEventListener('click',()=>lb.classList.remove('active'));

// Right Panel Photo Grid
const pg=document.getElementById('photoGrid');
um.forEach((m,i)=>{{
  const card=document.createElement('div');
  card.className='photo-card';
  const img=document.createElement('img');
  img.src=m.photo;img.alt=m.title;img.loading='lazy';
  const tag=document.createElement('div');
  tag.className='elevation-tag';
  const se=Math.round(ELEV_MIN+sampleTerrain(m.x,m.z)/5*(ELEV_MAX-ELEV_MIN));
  tag.textContent=`${{se}}m`;
  card.appendChild(img);card.appendChild(tag);
  card.addEventListener('click',()=>{{
    lbImg.src=m.photo;
    lbInfo.innerHTML=`<strong>${{m.title}}</strong><br>${{se}}m · SRTM`;
    lb.classList.add('active');
  }});
  pg.appendChild(card);
}});

// Elevation Profile Chart
function drawElevationProfile(){{
  const canvas=document.getElementById('elevationProfile');
  if(!canvas)return;
  const rect=canvas.parentElement.getBoundingClientRect();
  const W=rect.width-56;
  const H=80;
  const dpr=Math.min(window.devicePixelRatio,2);
  canvas.width=W*dpr;canvas.height=H*dpr;
  canvas.style.width=W+'px';canvas.style.height=H+'px';
  const ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);

  const step=Math.max(1,Math.floor(TUBE_PTS.length/200));
  const pts=[];
  for(let i=0;i<TUBE_PTS.length;i+=step)pts.push(TUBE_PTS[i]);
  if(pts[pts.length-1]!==TUBE_PTS[TUBE_PTS.length-1])pts.push(TUBE_PTS[TUBE_PTS.length-1]);

  const elevMin=Math.min(...pts.map(p=>p[1]));
  const elevMax=Math.max(...pts.map(p=>p[1]));
  const range=elevMax-elevMin||1;

  ctx.fillStyle='rgba(255,255,255,0.4)';
  ctx.fillRect(0,0,W,H);

  ctx.beginPath();
  const x0=0,y0=H-((pts[0][1]-elevMin)/range)*H;
  ctx.moveTo(x0,H);ctx.lineTo(x0,y0);
  pts.forEach((p,i)=>{{
    const x=(i/(pts.length-1))*W;
    const y=H-((p[1]-elevMin)/range)*H;
    ctx.lineTo(x,y);
  }});
  const lastX=W,lastY=H-((pts[pts.length-1][1]-elevMin)/range)*H;
  ctx.lineTo(lastX,H);ctx.closePath();
  const grad=ctx.createLinearGradient(0,0,0,H);
  grad.addColorStop(0,'{_rgba_from_hex(POSTER_TERRAIN_LOW, 0.3)}');
  grad.addColorStop(1,'{_rgba_from_hex(POSTER_GOLD, 0.1)}');
  ctx.fillStyle=grad;ctx.fill();

  ctx.beginPath();
  ctx.moveTo(x0,y0);
  pts.forEach((p,i)=>{{
    ctx.lineTo((i/(pts.length-1))*W,H-((p[1]-elevMin)/range)*H);
  }});
  ctx.strokeStyle='{POSTER_TERRAIN_LOW}';ctx.lineWidth=1.5;ctx.stroke();

  ctx.fillStyle='{_tokens.hex("text_muted")}';ctx.font='9px {CSS_FONT_STACK}';
  ctx.fillText(elevMin+'m',2,H-4);
  ctx.fillText(elevMax+'m',W-28,H-4);
  ctx.fillText('高程剖面',W/2-18,10);
}}
setTimeout(drawElevationProfile,200);
window.addEventListener('resize',()=>setTimeout(drawElevationProfile,300));

// Animation
const clock=new THREE.Clock();
function animate(){{
  requestAnimationFrame(animate);
  const dt=Math.min(clock.getDelta(),.1);
  controls.update();
  renderer.render(scene,camera);
}}
animate();

// Keyboard Controls
window.addEventListener('keydown',e=>{{
  switch(e.key.toLowerCase()){{
    case'r':camera.position.set(8,8,12);controls.target.set(5,1.5,4);break;
    case't':camera.position.set(5,12,4);controls.target.set(5,1.5,4);break;
    case'f':camera.position.set(5,3,15);controls.target.set(5,1.5,4);break;
  }}
  controls.update();
}});

function onResize(){{
  const w=viewer.clientWidth,h=viewer.clientHeight;
  camera.aspect=w/Math.max(h,1);
  camera.updateProjectionMatrix();
  renderer.setSize(w,h);
}}
window.addEventListener('resize',onResize);
window.addEventListener('orientationchange',()=>setTimeout(onResize,200));

console.log('Trail poster: paper-cut contour aesthetic + natural lighting (self-contained build)');
</script>
</body>
</html>'''

# Write output
output_path = OUTPUT / "trail_poster.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"  Written {len(HTML)} bytes to {output_path}")
print("=" * 60)
print("BUILD TRAIL POSTER COMPLETE (self-contained)")
print(f"  GCJ-02 → WGS-84: ✓")
print(f"  SRTM grid: {GRID_SIZE}×{GRID_SIZE}, {ELEV_MIN}-{ELEV_MAX}m")
print(f"  TUBE_PTS: {len(TUBE_PTS)}, Markers: {len(PHOTO_MARKERS)}")
print(f"  build_data.json: ✓")
print(f"  Output: {output_path}")
