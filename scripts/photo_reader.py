#!/usr/bin/env python3
"""
山野路迹 - 照片信息读取器
读取 JPG / HEIC / PNG 照片的 EXIF 信息（时间、GPS、设备），
支持将 HEIC 转换为 JPG。

用法:
    python photo_reader.py <image_dir>
    python photo_reader.py <image_dir> --json
    python photo_reader.py <image_dir> --convert   # 同时转换 HEIC 为 JPG
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS

# HEIC 支持（需要 pillow-heif）
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False


SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp'}


def _convert_gps_to_decimal(gps_value, gps_ref):
    """将 EXIF GPS 坐标转换为十进制度数"""
    if not gps_value:
        return None
    degrees, minutes, seconds = gps_value
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if gps_ref in ('S', 'W'):
        decimal = -decimal
    return round(decimal, 6)


def read_exif(filepath):
    """读取单张照片的 EXIF 信息"""
    try:
        img = Image.open(filepath)
        exif = img.getexif()
        info = {
            "file": filepath,
            "filename": os.path.basename(filepath),
            "format": img.format,
            "size": list(img.size),
        }

        # 基础 EXIF
        for tag_id, value in exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name in ('DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
                            'Make', 'Model', 'Software', 'ImageDescription'):
                info[tag_name] = str(value)

        # GPS 信息
        gps_info = exif.get_ifd(0x8825)
        if gps_info:
            lat_value = gps_info.get(2)  # GPSLatitude
            lat_ref = gps_info.get(1)    # GPSLatitudeRef
            lon_value = gps_info.get(4)  # GPSLongitude
            lon_ref = gps_info.get(3)    # GPSLongitudeRef
            alt_value = gps_info.get(6)  # GPSAltitude

            if lat_value and lon_value:
                info["gps"] = {
                    "latitude": _convert_gps_to_decimal(lat_value, lat_ref),
                    "longitude": _convert_gps_to_decimal(lon_value, lon_ref),
                    "altitude": round(float(alt_value), 1) if alt_value else None,
                }

        # 拍摄时间（优先 DateTimeOriginal）
        dt_str = info.get('DateTimeOriginal') or info.get('DateTime') or info.get('DateTimeDigitized')
        if dt_str:
            info['captured_at'] = dt_str

        return info
    except Exception as e:
        return {"file": filepath, "filename": os.path.basename(filepath), "error": str(e)}


def read_directory(directory, convert_heic=False):
    """读取目录下所有照片的 EXIF 信息"""
    results = []
    supported_files = []

    for f in sorted(os.listdir(directory)):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_FORMATS:
            supported_files.append(os.path.join(directory, f))

    for filepath in supported_files:
        info = read_exif(filepath)
        results.append(info)

        # HEIC -> JPG 转换
        if convert_heic and info.get("format") in ("HEIF", "HEIC") and "error" not in info:
            jpg_path = _convert_heic_to_jpg(filepath)
            if jpg_path:
                info["converted_to"] = jpg_path

    return results


def _convert_heic_to_jpg(heic_path):
    """Convert HEIC to JPG using Pillow/pillow-heif; fall back to macOS sips when available."""
    jpg_path = os.path.splitext(heic_path)[0] + "_converted.jpg"
    try:
        img = Image.open(heic_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=88)
        return jpg_path
    except Exception:
        pass

    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", heic_path, "--out", jpg_path],
            capture_output=True, check=True, timeout=30
        )
        return jpg_path
    except Exception:
        return None


def match_to_route(photos, route_points):
    """将照片与路线轨迹点进行时间匹配"""
    for photo in photos:
        if "captured_at" not in photo or "error" in photo:
            photo["matched_point"] = None
            continue

        photo_time = photo["captured_at"]
        best_point = None
        best_diff = float("inf")

        for pt in route_points:
            if not pt.get("time"):
                continue
            pt_time = pt["time"]
            # 简单的时间差比较
            try:
                t1 = datetime.fromisoformat(photo_time.replace(" ", "T"))
                t2 = datetime.fromisoformat(pt_time.replace("Z", "+00:00") if "Z" in pt_time else pt_time)
                diff = abs((t1 - t2.replace(tzinfo=None)).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_point = pt
            except Exception:
                continue

        if best_point and best_diff < 300:  # 5 分钟以内
            photo["matched_point"] = {
                "lat": best_point["lat"],
                "lon": best_point["lon"],
                "ele": best_point.get("ele"),
                "time_diff_seconds": round(best_diff, 1),
            }

    return photos


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python photo_reader.py <image_dir> [--json] [--convert]")
        sys.exit(1)

    directory = sys.argv[1]
    use_json = "--json" in sys.argv
    do_convert = "--convert" in sys.argv

    if not HEIC_SUPPORT:
        print("⚠ 警告: pillow-heif 未安装，HEIC 文件将无法读取 EXIF", file=sys.stderr)

    photos = read_directory(directory, convert_heic=do_convert)

    if use_json:
        print(json.dumps(photos, ensure_ascii=False, indent=2))
    else:
        print(f"\n===== 照片信息读取结果（共 {len(photos)} 张）=====\n")
        for p in photos:
            if "error" in p:
                print(f"  ✗ {p['filename']}: 读取失败 - {p['error']}")
            else:
                gps_str = ""
                if p.get("gps"):
                    g = p["gps"]
                    gps_str = f" GPS({g['latitude']}, {g['longitude']})"
                print(f"  ✓ {p['filename']}: {p.get('format')} {p['size'][0]}x{p['size'][1]}"
                      f" {p.get('captured_at', '无时间')}{gps_str}")
