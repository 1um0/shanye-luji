#!/usr/bin/env python3
"""
山野路迹 - 照片路线匹配器
将徒步照片按照 GPS 和时间匹配到路线轨迹点上。

匹配策略:
  1. GPS 匹配（优先）: 有 GPS 的照片，找轨迹上最近点
  2. 时间插值（次选）: 无 GPS 但有时间的照片，通过时间戳找对应轨迹点
  3. 手动指定（兜底）: 完全无数据的照片，标记为需手动分配

用法:
    python photo_matcher.py
    （读取 references/route_data.json 和 references/photos_data.json）
"""

import json
import math
from datetime import datetime, timezone, timedelta

# 上海时区
CST = timezone(timedelta(hours=8))


def haversine(lat1, lon1, lat2, lon2):
    """计算两点间距离（米）"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_datetime_cst(dt_str):
    """解析时间字符串，返回 UTC datetime 对象。
    输入可能是 '2025:11:22 07:41:17'（照片EXIF，本地时间）或 '2025-11-22T05:41:17+00:00'（GPX，UTC）"""
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    # EXIF 格式: "2025:11:22 07:41:17"（假设为本地时间 CST=UTC+8）
    if len(dt_str) == 19 and dt_str[4] == ':' and dt_str[10] == ' ':
        dt_naive = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        dt_cst = dt_naive.replace(tzinfo=CST)
        return dt_cst
    # ISO 格式: "2025-11-21T23:34:08+00:00"
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return None


def find_nearest_by_gps(photo_lat, photo_lon, track_points):
    """GPS 匹配：找轨迹上距离最近的点"""
    best_idx = 0
    best_dist = float('inf')
    for i, pt in enumerate(track_points):
        dist = haversine(photo_lat, photo_lon, pt["lat"], pt["lon"])
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx, best_dist


def find_nearest_by_time(photo_time, track_points):
    """时间匹配：找轨迹上时间最接近的点。
    photo_time 应为 UTC datetime 对象。"""
    if not photo_time:
        return None, None
    best_idx = 0
    best_diff = float('inf')
    for i, pt in enumerate(track_points):
        if not pt.get("time"):
            continue
        pt_time = datetime.fromisoformat(pt["time"])
        diff = abs((pt_time - photo_time).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx, best_diff


def match_photos(route_data, photos_data):
    """执行照片匹配"""
    track_points = route_data["track_points"]

    # 轨迹时间范围
    t0 = datetime.fromisoformat(track_points[0]["time"])
    t1 = datetime.fromisoformat(track_points[-1]["time"])

    results = []
    stats = {
        "gps_matched": 0,
        "time_matched": 0,
        "manual": 0,
        "total": len(photos_data),
    }

    for photo in photos_data:
        entry = {
            "file": photo["file"],
            "filename": photo["filename"],
            "format": photo.get("format", "unknown"),
            "size": photo.get("size"),
            "captured_at": photo.get("captured_at"),
            "has_gps": "gps" in photo,
            "gps": photo.get("gps"),
        }

        photo_time_utc = parse_datetime_cst(photo.get("captured_at"))
        entry["photo_time_utc"] = photo_time_utc.isoformat() if photo_time_utc else None

        matched = False

        # 策略 1: GPS 匹配
        if photo.get("gps") and photo["gps"].get("latitude") is not None:
            idx, dist = find_nearest_by_gps(
                photo["gps"]["latitude"],
                photo["gps"]["longitude"],
                track_points,
            )
            matched_pt = track_points[idx]
            entry.update({
                "match_method": "gps",
                "route_index": idx,
                "match_point": {
                    "lat": matched_pt["lat"],
                    "lon": matched_pt["lon"],
                    "ele": matched_pt["ele"],
                    "time": matched_pt["time"],
                    "cumulative_distance_m": matched_pt["cumulative_distance_m"],
                },
                "match_distance_m": round(dist, 1),
                "match_quality": "excellent" if dist < 20 else ("good" if dist < 50 else "acceptable"),
            })
            # 也计算时间差（如果有时间）
            if photo_time_utc and matched_pt["time"]:
                mt = datetime.fromisoformat(matched_pt["time"])
                entry["match_time_diff_s"] = round(abs((photo_time_utc - mt).total_seconds()), 1)
            stats["gps_matched"] += 1
            matched = True

        # 策略 2: 时间插值匹配
        if not matched and photo_time_utc:
            if photo_time_utc > t1:
                # 照片在徒步结束后拍摄 → 匹配到终点
                idx = len(track_points) - 1
                entry["match_note"] = "拍摄于徒步结束后，默认匹配到终点"
            elif photo_time_utc < t0:
                # 照片在徒步开始前拍摄 → 匹配到起点
                idx = 0
                entry["match_note"] = "拍摄于徒步开始前，默认匹配到起点"
            else:
                idx, diff = find_nearest_by_time(photo_time_utc, track_points)
                entry["match_time_diff_s"] = round(diff, 1) if diff else None

            matched_pt = track_points[idx]
            entry.update({
                "match_method": "time",
                "route_index": idx,
                "match_point": {
                    "lat": matched_pt["lat"],
                    "lon": matched_pt["lon"],
                    "ele": matched_pt["ele"],
                    "time": matched_pt["time"],
                    "cumulative_distance_m": matched_pt["cumulative_distance_m"],
                },
                "match_quality": "estimated",
            })
            stats["time_matched"] += 1
            matched = True

        # 策略 3: 无法自动匹配
        if not matched:
            entry.update({
                "match_method": "manual",
                "match_note": "缺少 GPS 和时间信息，需要手动指定位置",
            })
            stats["manual"] += 1

        results.append(entry)

    return results, stats


def main():
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    references = os.environ.get("SHANYE_REFERENCES_ROOT", os.path.join(base, "references"))

    # 加载数据
    with open(os.path.join(references, "route_data.json")) as f:
        route_data = json.load(f)
    with open(os.path.join(references, "photos_data.json")) as f:
        photos_data = json.load(f)

    # 匹配
    results, stats = match_photos(route_data, photos_data)

    # 输出
    output_path = os.path.join(references, "matched_photos.json")
    with open(output_path, "w") as f:
        json.dump({"stats": stats, "photos": results}, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print(f"匹配完成！")
    print(f"  总数: {stats['total']} 张")
    print(f"  GPS 匹配: {stats['gps_matched']} 张")
    print(f"  时间匹配: {stats['time_matched']} 张")
    print(f"  需手动: {stats['manual']} 张")
    print(f"  输出: {output_path}")

    # 打印每张照片的匹配详情
    print(f"\n--- 匹配详情 ---")
    for i, r in enumerate(results):
        method = r.get("match_method", "?")
        quality = r.get("match_quality", "-")
        note = r.get("match_note", "")
        dist_info = ""
        if "match_distance_m" in r:
            dist_info = f" 偏差{r['match_distance_m']}m"
        time_info = ""
        if "match_time_diff_s" in r and r["match_time_diff_s"] is not None:
            time_info = f" 时差{r['match_time_diff_s']}s"
        note_str = f" [{note}]" if note else ""
        print(f"  [{method:5s}] {r['filename']:30s} | {quality:10s}{dist_info}{time_info}{note_str}")


if __name__ == "__main__":
    main()
