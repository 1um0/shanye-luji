#!/usr/bin/env python3
"""批量转换 HEIC 照片为 JPG，输出到 output/photos/ 目录"""

import json
import os
import shutil
import sys
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCES = os.environ.get("SHANYE_REFERENCES_ROOT", os.path.join(BASE, "references"))
OUTPUT = os.environ.get("SHANYE_OUTPUT_ROOT", os.path.join(BASE, "output"))
OUTPUT_DIR = os.path.join(OUTPUT, "photos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(os.path.join(REFERENCES, "photos_data.json")) as f:
    photos = json.load(f)

converted = 0
skipped = 0

for photo in photos:
    src = photo["file"]
    name = os.path.splitext(photo["filename"])[0]
    
    if photo.get("format") == "JPEG":
        # 直接复制 JPG
        dst = os.path.join(OUTPUT_DIR, photo["filename"])
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            skipped += 1
        continue
    
    # HEIC → JPG
    dst = os.path.join(OUTPUT_DIR, f"{name}.jpg")
    if os.path.exists(dst):
        skipped += 1
        continue
    
    try:
        img = Image.open(src)
        # 缩放到最大 2000px 宽/高，控制文件大小
        w, h = img.size
        max_dim = 2000
        if w > max_dim or h > max_dim:
            ratio = min(max_dim / w, max_dim / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        img.save(dst, "JPEG", quality=85)
        converted += 1
        print(f"  ✓ {photo['filename']} → {name}.jpg ({img.size[0]}×{img.size[1]})")
    except Exception as e:
        print(f"  ✗ {photo['filename']}: {e}")

print(f"\n转换完成: {converted} 张 HEIC→JPG, {skipped} 张 JPG 已复制")
