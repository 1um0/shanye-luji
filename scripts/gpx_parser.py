#!/usr/bin/env python3
"""
山野路迹 - GPX 轨迹解析器
解析 GPX 文件，提取路线核心数据。

用法:
    python gpx_parser.py <gpx_file_path>
    python gpx_parser.py <gpx_file_path> --json   # 输出 JSON 格式
"""

import sys
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

try:
    import gpxpy
except ImportError:
    gpxpy = None


def haversine(lat1, lon1, lat2, lon2):
    """计算两点间距离（米），使用 Haversine 公式"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_time(value):
    if not value:
        return None
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _iso_time(value):
    dt = _parse_time(value)
    if dt:
        return dt.isoformat()
    return value


def _parse_with_gpxpy(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                speed = getattr(pt, "speed", None)
                points.append({
                    "lat": pt.latitude,
                    "lon": pt.longitude,
                    "ele": pt.elevation,
                    "time": pt.time.isoformat() if pt.time else None,
                    "speed": speed,
                })
    return points


def _parse_with_elementtree(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()

    def local_name(tag):
        return tag.rsplit("}", 1)[-1]

    points = []
    for trkpt in root.iter():
        if local_name(trkpt.tag) != "trkpt":
            continue
        lat = trkpt.attrib.get("lat")
        lon = trkpt.attrib.get("lon")
        if lat is None or lon is None:
            continue
        data = {"lat": float(lat), "lon": float(lon), "ele": None, "time": None, "speed": None}
        for child in trkpt:
            name = local_name(child.tag)
            text = (child.text or "").strip()
            if name == "ele" and text:
                data["ele"] = float(text)
            elif name == "time" and text:
                data["time"] = _iso_time(text)
            elif name == "speed" and text:
                data["speed"] = float(text)
        points.append(data)
    return points


def parse_gpx(filepath):
    """解析 GPX 文件，返回路线数据资产包。无 gpxpy 时使用标准库兜底。"""

    result = {
        "file": filepath,
        "parsed_at": datetime.now().isoformat(),
    }

    if gpxpy is not None:
        all_points = _parse_with_gpxpy(filepath)
    else:
        all_points = _parse_with_elementtree(filepath)

    if not all_points:
        return {"error": "未找到轨迹点"}

    # 基础统计
    result["total_points"] = len(all_points)

    # 时间范围
    times = [pt["time"] for pt in all_points if pt["time"]]
    if times:
        result["start_time"] = times[0]
        result["end_time"] = times[-1]
        start_dt = datetime.fromisoformat(times[0])
        end_dt = datetime.fromisoformat(times[-1])
        duration_seconds = (end_dt - start_dt).total_seconds()
        result["duration_seconds"] = duration_seconds
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        result["duration_display"] = f"{hours}小时{minutes}分钟"

    # 距离计算（逐点累加）
    total_distance = 0
    max_speed = 0
    elevations = [pt["ele"] for pt in all_points if pt["ele"] is not None]
    speeds = [pt["speed"] for pt in all_points if pt["speed"] is not None]

    for i in range(1, len(all_points)):
        d = haversine(
            all_points[i-1]["lat"], all_points[i-1]["lon"],
            all_points[i]["lat"], all_points[i]["lon"]
        )
        total_distance += d

    result["total_distance_m"] = round(total_distance, 1)
    result["total_distance_km"] = round(total_distance / 1000, 2)

    # 海拔统计
    if elevations:
        result["min_elevation"] = round(min(elevations), 1)
        result["max_elevation"] = round(max(elevations), 1)
        result["elevation_range"] = round(max(elevations) - min(elevations), 1)

        # 展示口径：累计爬升按最高点 - 最低点计算，避免逐点海拔抖动放大。
        total_loss = 0
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i-1]
            if diff < 0:
                total_loss += abs(diff)
        result["elevation_gain"] = result["elevation_range"]
        result["elevation_loss"] = round(total_loss, 1)

    # 速度统计
    if speeds:
        result["avg_speed_ms"] = round(sum(speeds) / len(speeds), 3)
        result["avg_speed_kmh"] = round(sum(speeds) / len(speeds) * 3.6, 2)
        result["max_speed_ms"] = round(max(speeds), 3)
        result["max_speed_kmh"] = round(max(speeds) * 3.6, 2)

    # 起终点
    result["start_point"] = {"lat": all_points[0]["lat"], "lon": all_points[0]["lon"]}
    result["end_point"] = {"lat": all_points[-1]["lat"], "lon": all_points[-1]["lon"]}

    # 海拔最高点和最低点
    if elevations:
        max_idx = elevations.index(max(elevations))
        min_idx = elevations.index(min(elevations))
        result["highest_point"] = {
            "lat": all_points[max_idx]["lat"],
            "lon": all_points[max_idx]["lon"],
            "ele": max(elevations),
            "time": all_points[max_idx].get("time"),
        }
        result["lowest_point"] = {
            "lat": all_points[min_idx]["lat"],
            "lon": all_points[min_idx]["lon"],
            "ele": min(elevations),
            "time": all_points[min_idx].get("time"),
        }

    # 全量轨迹点（含时间和累计距离，用于照片匹配）
    cumulative_dist = 0
    track_points = []
    for i, pt in enumerate(all_points):
        if i > 0:
            cumulative_dist += haversine(
                all_points[i-1]["lat"], all_points[i-1]["lon"],
                pt["lat"], pt["lon"]
            )
        track_points.append({
            "lat": pt["lat"],
            "lon": pt["lon"],
            "ele": pt["ele"],
            "time": pt.get("time"),
            "speed": pt.get("speed"),
            "cumulative_distance_m": round(cumulative_dist, 1),
        })
    result["track_points"] = track_points

    # 路线轮廓（简化后的经纬度序列，用于 3D 和 SVG 绘制）
    # 每隔 N 个点采样一个，控制数据量
    sample_interval = max(1, len(all_points) // 300)
    result["route_outline"] = [
        {"lat": pt["lat"], "lon": pt["lon"], "ele": pt["ele"], "speed": pt.get("speed")}
        for pt in all_points[::sample_interval]
    ]

    # 海拔剖面数据
    result["elevation_profile"] = [
        {"index": i, "distance_km": round(i * total_distance / len(all_points) / 1000, 2), "ele": pt["ele"]}
        for i, pt in enumerate(all_points[::sample_interval])
    ]

    # 关键路段分析：找最陡爬升段
    steepest = {"gain": 0, "distance": 0, "start_idx": 0, "end_idx": 0}
    window = 10  # 滑动窗口大小（点数）
    for i in range(len(all_points) - window):
        segment_gain = 0
        segment_dist = 0
        for j in range(i, i + window):
            if all_points[j]["ele"] is not None and all_points[j+1]["ele"] is not None:
                diff = all_points[j+1]["ele"] - all_points[j]["ele"]
                if diff > 0:
                    segment_gain += diff
            segment_dist += haversine(
                all_points[j]["lat"], all_points[j]["lon"],
                all_points[j+1]["lat"], all_points[j+1]["lon"]
            )
        if segment_dist > 0:
            gradient = segment_gain / segment_dist
            if gradient > steepest.get("gradient", 0):
                steepest = {
                    "gain": round(segment_gain, 1),
                    "distance": round(segment_dist, 1),
                    "gradient_pct": round(gradient * 100, 1),
                    "start_idx": i,
                    "end_idx": i + window,
                    "start_point": {"lat": all_points[i]["lat"], "lon": all_points[i]["lon"]},
                    "end_point": {"lat": all_points[i+window]["lat"], "lon": all_points[i+window]["lon"]},
                }
    result["steepest_section"] = steepest

    # 路线中心点
    lats = [pt["lat"] for pt in all_points]
    lons = [pt["lon"] for pt in all_points]
    result["center_point"] = {
        "lat": round((min(lats) + max(lats)) / 2, 6),
        "lon": round((min(lons) + max(lons)) / 2, 6),
    }
    result["bounds"] = {
        "min_lat": round(min(lats), 6),
        "max_lat": round(max(lats), 6),
        "min_lon": round(min(lons), 6),
        "max_lon": round(max(lons), 6),
    }

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python gpx_parser.py <gpx_file> [--json]")
        sys.exit(1)

    filepath = sys.argv[1]
    use_json = "--json" in sys.argv

    data = parse_gpx(filepath)

    if use_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"\n===== 路线数据解析结果 =====")
        print(f"轨迹点数: {data.get('total_points')}")
        print(f"总距离: {data.get('total_distance_km')} km")
        print(f"总爬升: {data.get('elevation_gain')} m")
        print(f"总下降: {data.get('elevation_loss')} m")
        print(f"最高海拔: {data.get('max_elevation')} m")
        print(f"最低海拔: {data.get('min_elevation')} m")
        print(f"累计用时: {data.get('duration_display')}")
        print(f"平均速度: {data.get('avg_speed_kmh')} km/h")
        print(f"起点: ({data['start_point']['lat']}, {data['start_point']['lon']})")
        print(f"终点: ({data['end_point']['lat']}, {data['end_point']['lon']})")
        if 'steepest_section' in data:
            s = data['steepest_section']
            print(f"最陡爬升段: 坡度 {s.get('gradient_pct', 0)}%, 爬升 {s.get('gain', 0)}m / {s.get('distance', 0)}m")
