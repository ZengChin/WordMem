# -*- coding: utf-8 -*-
"""主题：调色板与全局样式表（贴近截图的清新海滩配色）。"""
from __future__ import annotations

from PySide6.QtGui import QColor

# ---- 调色板 -------------------------------------------------------------
WINDOW_W, WINDOW_H = 430, 560
RADIUS = 14

# 渐变背景（天空 -> 海面 -> 沙滩）
SKY_TOP = "#b6c9d4"
SKY_MID = "#c9d6d3"
SEA_BAND = "#9db8bb"
SAND = "#eee2c6"
SAND_LIGHT = "#f2e9d3"

INK = "#3d5a66"          # 单词主文字（青灰）
INK_SOFT = "#6f8590"     # 音标/次要文字
INK_DARK = "#2f3e46"     # 例句强调
GREEN = "#2e8b5f"        # 主操作绿（文字）
GREEN_ICON = "#3fa26b"   # 图标绿
GREEN_BG = "#e9f5ee"     # 绿色浅底
ORANGE = "#c0762a"       # 警示橙（文字）
ORANGE_ICON = "#e8963c"  # 图标橙

CARD = ("255,255,255", 165)     # 卡片底 rgba
CARD_STRONG = ("255,255,255", 205)
PILL = ("255,255,255", 150)     # 胶囊按钮底
TRACK = ("255,255,255", 130)    # 进度条轨道
FILL = ("255,255,255", 235)     # 进度条填充

# ---- 超透明模式全局状态（由 MainWindow 同步，卡片/进度条据此重绘） ----
GHOST_CARD_ALPHA = 12          # 透明模式下卡片底色（仅纯白底上隐约可见）
GHOST_TRACK_ALPHA = 45         # 透明模式下进度条轨道
GHOST_BORDER = QColor(88, 100, 110, 42)  # 边框：深灰蓝，纯白底上隐约可见
GHOST_PILL_ALPHA = 0           # 透明模式下按钮底色（隐形，仅保留文字）
GHOST_PILL_HOVER = 26          # 透明模式下按钮悬停反馈
GHOST_PILL_PRESSED = 42        # 透明模式下按钮按下反馈

_ghost_state = {"on": False}


def set_ghost_mode(on: bool) -> None:
    """同步超透明模式全局状态。"""
    _ghost_state["on"] = bool(on)


def ghost_mode() -> bool:
    return _ghost_state["on"]


def rgba(color: str, alpha: int) -> str:
    """#rrggbb -> rgba() 字符串。"""
    c = QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


GLOBAL_QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    outline: none;
}}
QLabel {{ color: {INK}; background: transparent; }}
QPushButton {{ background: transparent; border: none; }}
QToolTip {{
    background: rgba(47,62,70,230); color: white; border: none;
    padding: 4px 8px; border-radius: 4px; font-size: 12px;
}}
QDialog {{ background: white; }}
"""
