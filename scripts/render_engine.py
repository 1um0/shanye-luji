#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
山野路迹 — 统一渲染引擎
模仿 design_system.py 的配置驱动架构，为所有构建脚本提供统一的设计令牌、
Canvas 构建器和 HTML 输出格式化器。

三大核心问题解决：
  1. 颜色硬编码 → DesignTokens 统一管理配色
  2. 模板与逻辑混杂 → TemplateRegistry 分离模板定义
  3. 无设计系统意识 → 所有脚本引用同一来源

用法:
    from scripts.render_engine import DesignTokens, CanvasBuilder, HTMLFormatter

架构:
    DesignTokens ──→ CanvasBuilder ──→ HTMLFormatter
                    (Canvas 2D 绘制)     (HTML + CSS 变量)
"""

import json
import math
from dataclasses import dataclass, field
from typing import Optional

from platform_utils import CSS_FONT_STACK

# ================================================================
# 配置：统一配色系统
# ================================================================
# 单一数据源，所有颜色定义在此一处。修改此处即可影响所有构建脚本。

COLOR_TOKENS_CONFIG = {
    "pine":       {"hex": "#6d8b5e", "wu_xing": "木", "role": "primary_green"},
    "pine_light": {"hex": "#b5c8a3", "wu_xing": "木", "role": "light_green"},
    "pine_dark":  {"hex": "#3d5233", "wu_xing": "木", "role": "dark_green"},
    "pine_pale":  {"hex": "#d0dfc8", "wu_xing": "木", "role": "pale_green"},
    "mineral":    {"hex": "#5a7a6a", "wu_xing": "木", "role": "secondary_green"},
    "mineral_dark":{"hex": "#2d4438","wu_xing": "木", "role": "deep_green"},
    "earth_gold": {"hex": "#c4a87a", "wu_xing": "土", "role": "accent_warm"},
    "earth_light":{"hex": "#e0d0b8", "wu_xing": "土", "role": "light_warm"},
    "accent":     {"hex": "#e07b3c", "wu_xing": "火", "role": "accent_hot"},
    "warm_sand":  {"hex": "#e8dfd3", "wu_xing": "土", "role": "background"},
    "cream":      {"hex": "#f5f0e8", "wu_xing": "金", "role": "paper_base"},
    "dark":       {"hex": "#1a1a1a", "wu_xing": "水", "role": "foreground"},
    "gold":       {"hex": "#c49a45", "wu_xing": "土", "role": "premium_accent"},
    "gold_light": {"hex": "#e0c87a", "wu_xing": "土", "role": "light_accent"},
    # Semantic aliases
    "text_primary":   {"hex": "#3d3a33", "wu_xing": "土", "role": "body_text"},
    "text_secondary": {"hex": "#7a7568", "wu_xing": "土", "role": "secondary_text"},
    "text_muted":     {"hex": "#a09888", "wu_xing": "土", "role": "muted_text"},
    "text_inverse":   {"hex": "#f9f5ed", "wu_xing": "金", "role": "inverse_text"},
    "divider":        {"hex": "#e0d8c8", "wu_xing": "土", "role": "divider_line"},
    # Marker / gradient colors
    "marker_stop":    {"hex": "#1d6b2e", "wu_xing": "木", "role": "trail_stop"},
    "marker_walk":    {"hex": "#4a9c3f", "wu_xing": "木", "role": "trail_walk"},
    "marker_fast":    {"hex": "#b8a030", "wu_xing": "土", "role": "trail_fast"},
    "marker_run":     {"hex": "#e07b3c", "wu_xing": "火", "role": "trail_run"},
    "marker_sprint":  {"hex": "#d44a2a", "wu_xing": "火", "role": "trail_sprint"},
}

TYPOGRAPHY_TOKENS_CONFIG = {
    "h0": {"size": 88, "weight": 900, "letter_spacing": 18},
    "h1": {"size": 56, "weight": 900, "letter_spacing": 8},
    "h2": {"size": 24, "weight": 700, "letter_spacing": 6},
    "h3": {"size": 18, "weight": 600, "letter_spacing": 4},
    "body": {"size": 14, "weight": 400, "letter_spacing": 1},
    "caption": {"size": 10, "weight": 400, "letter_spacing": 2},
    "font_family": CSS_FONT_STACK,
}

SPACING_TOKENS_CONFIG = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "xxl": 48,
    "xxxl": 64,
}


# ================================================================
# DesignTokens — 不可变设计令牌容器
# ================================================================

@dataclass(frozen=True)
class DesignTokens:
    """统一设计令牌。创建后不可变，所有构建脚本共享同一实例。"""

    colors: dict = field(default_factory=dict)
    typography: dict = field(default_factory=dict)
    spacing: dict = field(default_factory=dict)

    def hex(self, token_name: str) -> str:
        """获取颜色 hex 值。e.g. tokens.hex('pine') → '#6d8b5e'"""
        return self.colors.get(token_name, {}).get("hex", "#000000")

    def rgba(self, token_name: str, alpha: float = 1.0) -> str:
        """获取颜色 rgba 字符串。e.g. tokens.rgba('pine', 0.5) → 'rgba(109,139,94,0.5)'"""
        h = self.hex(token_name).lstrip("#")
        if len(h) != 6:
            return f"rgba(0,0,0,{alpha})"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    def to_css_variables(self) -> str:
        """生成 CSS :root 变量块。"""
        lines = [":root {"]
        for name, info in self.colors.items():
            lines.append(f"  --{name}: {info['hex']};")
        # Typography
        lines.append(f"  --font-family: {self.typography.get('font_family', 'sans-serif')};")
        lines.append(f"  --h1-size: {self.typography.get('h1', {}).get('size', 56)}px;")
        lines.append(f"  --h2-size: {self.typography.get('h2', {}).get('size', 24)}px;")
        lines.append(f"  --body-size: {self.typography.get('body', {}).get('size', 14)}px;")
        lines.append(f"  --caption-size: {self.typography.get('caption', {}).get('size', 10)}px;")
        # Spacing
        for name, value in self.spacing.items():
            lines.append(f"  --space-{name}: {value}px;")
        lines.append("}")
        return "\n".join(lines)

    def to_js_tokens(self) -> str:
        """生成 JS 内嵌设计令牌对象。"""
        entries = []
        for name, info in self.colors.items():
            entries.append(f'    "{name}": "{info["hex"]}"')
        return "const DESIGN_TOKENS = {{\n{0}\n}};".format(",\n".join(entries))

    @classmethod
    def load(cls) -> "DesignTokens":
        """从内置配置创建设计令牌。"""
        return cls(
            colors=COLOR_TOKENS_CONFIG,
            typography=TYPOGRAPHY_TOKENS_CONFIG,
            spacing=SPACING_TOKENS_CONFIG,
        )

    @classmethod
    def load_from_file(cls, path: str) -> "DesignTokens":
        """从 JSON 配置文件创建设计令牌，支持覆盖内置默认值。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        colors = {**COLOR_TOKENS_CONFIG, **data.get("colors", {})}
        typography = {**TYPOGRAPHY_TOKENS_CONFIG, **data.get("typography", {})}
        spacing = {**SPACING_TOKENS_CONFIG, **data.get("spacing", {})}
        return cls(colors=colors, typography=typography, spacing=spacing)


# ================================================================
# CanvasBuilder — Canvas 2D 通用绘制工具
# ================================================================

class CanvasBuilder:
    """基于 DesignTokens 的 Canvas 2D 通用绘制函数集合。"""

    def __init__(self, tokens: Optional[DesignTokens] = None):
        self.tokens = tokens or DesignTokens.load()

    # ---- 路线绘制 ----

    def draw_trail_shadow(
        self, ctx, points: list, map_x, map_y,
        shadow_width: int = 18, shadow_alpha: float = 0.06,
        line_cap: str = "round", line_join: str = "round",
    ):
        """绘制路线阴影（垫在彩色路线下方增强立体感）。"""
        ctx.save()
        ctx.strokeStyle = f"rgba(0,0,0,{shadow_alpha})"
        ctx.lineWidth = shadow_width
        ctx.lineCap = line_cap
        ctx.lineJoin = line_join
        ctx.beginPath()
        for i, p in enumerate(points):
            x, y = map_x(p[0]), map_y(p[-1])  # x, z → canvas
            if i == 0:
                ctx.moveTo(x, y)
            else:
                ctx.lineTo(x, y)
        ctx.stroke()
        ctx.restore()

    def draw_trail_glow(
        self, ctx, points: list, map_x, map_y,
        glow_width: int = 12, glow_alpha: float = 0.15,
    ):
        """绘制路线辉光（大地金色半透明垫层）。"""
        ctx.save()
        ctx.strokeStyle = self.tokens.rgba("earth_gold", glow_alpha)
        ctx.lineWidth = glow_width
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        ctx.beginPath()
        for i, p in enumerate(points):
            x, y = map_x(p[0]), map_y(p[-1])
            if i == 0:
                ctx.moveTo(x, y)
            else:
                ctx.lineTo(x, y)
        ctx.stroke()
        ctx.restore()

    def draw_trail_speed_colored(
        self, ctx, points: list, speeds: list, map_x, map_y,
        line_width: float = 3.5, alpha: float = 0.88,
    ):
        """按速度分段着色绘制路线。

        速度 → 颜色映射：
          0 m/s   → 深绿 (stopped)
          1.5 m/s → 翠绿 (walking)
          3.0 m/s → 黄绿 (fast walk)
          4.0 m/s+→ 暖红 (running/sprint)
        """
        speed_color_map = [
            (0.0, self.tokens.hex("marker_stop")),
            (1.5, self.tokens.hex("marker_walk")),
            (3.0, self.tokens.hex("marker_fast")),
            (4.0, self.tokens.hex("marker_run")),
            (99.0, self.tokens.hex("marker_sprint")),
        ]

        def _speed_to_hex(spd: float) -> str:
            for i in range(len(speed_color_map) - 1):
                lo, c_lo = speed_color_map[i]
                hi, c_hi = speed_color_map[i + 1]
                if lo <= spd <= hi:
                    t = (spd - lo) / max(hi - lo, 0.01)
                    r1, g1, b1 = _hex_to_rgb(c_lo)
                    r2, g2, b2 = _hex_to_rgb(c_hi)
                    r = round(r1 + (r2 - r1) * t)
                    g = round(g1 + (g2 - g1) * t)
                    b = round(b1 + (b2 - b1) * t)
                    return f"rgb({r},{g},{b})"
            return speed_color_map[0][1]

        if not speeds or len(speeds) < len(points):
            # Fallback: uniform pine green
            ctx.save()
            ctx.strokeStyle = self.tokens.rgba("pine", alpha)
            ctx.lineWidth = line_width
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.beginPath()
            for i, p in enumerate(points):
                x, y = map_x(p[0]), map_y(p[-1])
                if i == 0:
                    ctx.moveTo(x, y)
                else:
                    ctx.lineTo(x, y)
            ctx.stroke()
            ctx.restore()
            return

        ctx.save()
        ctx.lineWidth = line_width
        ctx.lineCap = "round"
        for i in range(1, len(points)):
            x1, y1 = map_x(points[i - 1][0]), map_y(points[i - 1][-1])
            x2, y2 = map_x(points[i][0]), map_y(points[i][-1])
            s = speeds[min(i, len(speeds) - 1)]
            ctx.strokeStyle = _speed_to_hex(s)
            ctx.globalAlpha = alpha
            ctx.beginPath()
            ctx.moveTo(x1, y1)
            ctx.lineTo(x2, y2)
            ctx.stroke()
        ctx.restore()

    def draw_trail_elevation_gradient(
        self, ctx, points: list, map_x, map_y,
        line_width: float = 4.0, shadow_blur: float = 10,
    ):
        """按海拔渐变着色绘制路线（旧版兼容）。低海拔绿 → 高海拔红。"""
        ctx.save()
        elevations = [p[1] if len(p) > 1 else 0 for p in points]
        e_min = min(elevations) if elevations else 0
        e_max = max(elevations) if elevations else 1
        e_range = max(e_max - e_min, 1)

        ctx.lineWidth = line_width
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        ctx.shadowBlur = shadow_blur
        ctx.shadowColor = self.tokens.rgba("pine", 0.3)

        for i in range(1, len(points)):
            x1, y1 = map_x(points[i - 1][0]), map_y(points[i - 1][-1])
            x2, y2 = map_x(points[i][0]), map_y(points[i][-1])
            t = (elevations[i] - e_min) / e_range
            # Green (pine) → Gold (earth_gold) → Hot (accent)
            if t < 0.5:
                s = t * 2
                r = int(109 + (196 - 109) * s)
                g = int(139 + (168 - 139) * s)
                b = int(94 + (122 - 94) * s)
            else:
                s = (t - 0.5) * 2
                r = int(196 + (224 - 196) * s)
                g = int(168 + (123 - 168) * s)
                b = int(122 + (60 - 122) * s)
            ctx.strokeStyle = f"rgb({r},{g},{b})"
            ctx.beginPath()
            ctx.moveTo(x1, y1)
            ctx.lineTo(x2, y2)
            ctx.stroke()
        ctx.restore()

    # ---- 标记点绘制 ----

    def draw_marker_dot(
        self, ctx, x: float, y: float, radius: float = 5,
        fill_color: str = None, glow_color: str = None, glow_radius: float = 14,
    ):
        """绘制单个标记点（带光晕）。"""
        fill = fill_color or self.tokens.hex("pine_dark")
        glow = glow_color or self.tokens.rgba("earth_gold", 0.4)

        # Glow
        grad = ctx.createRadialGradient(x, y, radius * 0.3, x, y, glow_radius)
        grad.addColorStop(0, glow)
        grad.addColorStop(1, "transparent")
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(x, y, glow_radius, 0, math.pi * 2)
        ctx.fill()

        # Dot
        ctx.fillStyle = fill
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, math.pi * 2)
        ctx.fill()

    def draw_label_pill(
        self, ctx, x: float, y: float, text: str,
        bg_color: str = None, text_color: str = None,
        font_size: int = 11, pad_x: int = 10, pad_y: int = 6, radius: int = 4,
    ):
        """绘制标签 pill（带背景圆角矩形）。"""
        bg = bg_color or self.tokens.rgba("text_primary", 0.85)
        fg = text_color or self.tokens.hex("cream")
        ctx.font = f'bold {font_size}px "{self.tokens.typography["font_family"].split(",")[0].strip()}", sans-serif'
        metrics = ctx.measureText(text)
        tw = metrics.width
        th = font_size
        bw = tw + pad_x * 2
        bh = th + pad_y * 2

        ctx.fillStyle = bg
        ctx.beginPath()
        _round_rect(ctx, x, y, bw, bh, radius)
        ctx.fill()

        ctx.fillStyle = fg
        ctx.fillText(text, x + pad_x, y + pad_y + th * 0.75)

        return bw, bh  # Return dimensions for layout

    # ---- 海拔剖面 ----

    def draw_elevation_profile(
        self, ctx, points: list, width: int, height: int,
        pad: dict = None,
    ):
        """绘制海拔剖面图。points: [[distance_km, elevation], ...]"""
        if pad is None:
            pad = {"top": 4, "right": 4, "bottom": 4, "left": 4}
        pw = width - pad["left"] - pad["right"]
        ph = height - pad["top"] - pad["bottom"]

        elevs = [p[1] for p in points]
        e_min, e_max = min(elevs), max(elevs)
        e_range = max(e_max - e_min, 1)

        def _px(d_km):
            return pad["left"] + (d_km / max(points[-1][0], 1)) * pw

        def _py(ele):
            return pad["top"] + (1 - (ele - e_min) / e_range) * ph

        # Area fill gradient
        ctx.beginPath()
        ctx.moveTo(_px(points[0][0]), height)
        ctx.lineTo(_px(points[0][0]), _py(points[0][1]))
        for p in points:
            ctx.lineTo(_px(p[0]), _py(p[1]))
        ctx.lineTo(_px(points[-1][0]), height)
        ctx.closePath()

        grad = ctx.createLinearGradient(0, 0, 0, height)
        grad.addColorStop(0, self.tokens.rgba("pine", 0.3))
        grad.addColorStop(1, self.tokens.rgba("earth_gold", 0.1))
        ctx.fillStyle = grad
        ctx.fill()

        # Line
        ctx.beginPath()
        ctx.moveTo(_px(points[0][0]), _py(points[0][1]))
        for p in points:
            ctx.lineTo(_px(p[0]), _py(p[1]))
        ctx.strokeStyle = self.tokens.hex("pine")
        ctx.lineWidth = 1.5
        ctx.stroke()

        # Min/max labels
        ctx.fillStyle = self.tokens.hex("text_muted")
        font = f"9px {CSS_FONT_STACK}"
        ctx.font = font
        ctx.fillText(f"{e_min:.0f}m", pad["left"] + 2, height - pad["bottom"] + 2)
        ctx.fillText(f"{e_max:.0f}m", pad["left"] + pw - 28, pad["top"] + 10)

    # ---- 装饰元素 ----

    def draw_contour_rings(
        self, ctx, centers: list, width: int, height: int, alpha: float = 0.04,
    ):
        """绘制装饰性等高线环（背景纹理）。"""
        ctx.save()
        ctx.globalAlpha = alpha
        ctx.strokeStyle = self.tokens.hex("pine")
        ctx.lineWidth = 0.5
        for cx, cy, r in centers:
            for ring in range(1, 6):
                ctx.beginPath()
                ctx.arc(cx, cy, r * (0.3 + ring * 0.18), 0, math.pi * 2)
                ctx.stroke()
        ctx.restore()

    def draw_paper_grain(self, ctx, width: int, height: int, count: int = 400):
        """绘制纸质肌理噪点。"""
        import random as _random  # noqa
        for _ in range(count):
            gx = _random.random() * width
            gy = _random.random() * height
            ctx.fillStyle = "rgba(0,0,0,0.015)"
            ctx.fillRect(gx, gy, 1, 1)

    def draw_top_bottom_fade(
        self, ctx, width: int, height: int,
        top_height: int = 0, bottom_height: int = 0,
    ):
        """绘制顶部和底部的渐隐遮罩（让标题和数据条可读）。"""
        bg_hex = self.tokens.hex("cream")
        if top_height > 0:
            grad = ctx.createLinearGradient(0, 0, 0, top_height)
            grad.addColorStop(0, _hex_to_rgba_str(bg_hex, 0.95))
            grad.addColorStop(0.6, _hex_to_rgba_str(bg_hex, 0.7))
            grad.addColorStop(1, "transparent")
            ctx.fillStyle = grad
            ctx.fillRect(0, 0, width, top_height)
        if bottom_height > 0:
            grad = ctx.createLinearGradient(0, height - bottom_height, 0, height)
            grad.addColorStop(0, "transparent")
            grad.addColorStop(0.5, _hex_to_rgba_str(bg_hex, 0.7))
            grad.addColorStop(1, _hex_to_rgba_str(bg_hex, 0.95))
            ctx.fillStyle = grad
            ctx.fillRect(0, height - bottom_height, width, bottom_height)


# ================================================================
# HTMLFormatter — HTML 输出格式化器
# ================================================================

class HTMLFormatter:
    """生成自包含 HTML 文件（内嵌 CSS 变量 + 数据）。"""

    def __init__(self, tokens: Optional[DesignTokens] = None):
        self.tokens = tokens or DesignTokens.load()

    def wrap(self, title: str, css: str, body_html: str, scripts: str = "") -> str:
        """将 CSS + body + scripts 包装为完整 HTML 文档。"""
        css_vars = self.tokens.to_css_variables()
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{css_vars}

{css}
</style>
</head>
<body>
{body_html}

{scripts}
</body>
</html>"""


# ================================================================
# TemplateRegistry — 模板注册与覆盖
# ================================================================

class TemplateRegistry:
    """注册和检索品类模板，支持 per-template 设计令牌覆盖。"""

    def __init__(self, tokens: Optional[DesignTokens] = None):
        self.tokens = tokens or DesignTokens.load()
        self._templates: dict = {}

    def register(self, name: str, token_overrides: dict = None):
        """注册一个模板。token_overrides 可覆盖默认 DesignTokens。"""
        template_tokens = self.tokens
        if token_overrides:
            merged_colors = {**self.tokens.colors, **token_overrides}
            template_tokens = DesignTokens(
                colors=merged_colors,
                typography=self.tokens.typography,
                spacing=self.tokens.spacing,
            )
        self._templates[name] = {"tokens": template_tokens}
        return template_tokens

    def get_tokens(self, name: str) -> Optional[DesignTokens]:
        """获取指定模板的设计令牌（含覆盖）。"""
        entry = self._templates.get(name)
        return entry["tokens"] if entry else self.tokens

    def list_templates(self) -> list:
        """列出所有已注册模板名。"""
        return list(self._templates.keys())


# ================================================================
# 工具函数
# ================================================================

def _hex_to_rgb(hex_color: str) -> tuple:
    """#6d8b5e → (109, 139, 94)"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex_to_rgba_str(hex_color: str, alpha: float) -> str:
    """#6d8b5e → 'rgba(109,139,94,0.5)'"""
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def _round_rect(ctx, x: float, y: float, w: float, h: float, r: float):
    """Canvas roundRect polyfill。"""
    ctx.moveTo(x + r, y)
    ctx.lineTo(x + w - r, y)
    ctx.quadraticCurveTo(x + w, y, x + w, y + r)
    ctx.lineTo(x + w, y + h - r)
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
    ctx.lineTo(x + r, y + h)
    ctx.quadraticCurveTo(x, y + h, x, y + h - r)
    ctx.lineTo(x, y + r)
    ctx.quadraticCurveTo(x, y, x + r, y)
    ctx.closePath()


# ================================================================
# 全局单例
# ================================================================

# 延迟初始化，首次 import 时创建
_TOKENS: Optional[DesignTokens] = None
_CANVAS: Optional[CanvasBuilder] = None
_FORMATTER: Optional[HTMLFormatter] = None


def get_tokens() -> DesignTokens:
    global _TOKENS
    if _TOKENS is None:
        _TOKENS = DesignTokens.load()
    return _TOKENS


def get_canvas() -> CanvasBuilder:
    global _CANVAS
    if _CANVAS is None:
        _CANVAS = CanvasBuilder(get_tokens())
    return _CANVAS


def get_formatter() -> HTMLFormatter:
    global _FORMATTER
    if _FORMATTER is None:
        _FORMATTER = HTMLFormatter(get_tokens())
    return _FORMATTER


# ================================================================
# CLI 支持（可选）
# ================================================================

if __name__ == "__main__":
    tokens = get_tokens()
    print("=== 山野路迹 统一配色系统 ===")
    print()
    print("| 令牌 | 十六进制 | 五行 | 用途 |")
    print("|------|---------|------|------|")
    for name, info in tokens.colors.items():
        print(f"| `{name}` | `{info['hex']}` | {info['wu_xing']} | {info['role']} |")
    print()
    print("CSS 变量预览:")
    print(tokens.to_css_variables())
