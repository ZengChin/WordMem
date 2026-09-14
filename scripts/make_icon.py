# -*- coding: utf-8 -*-
"""生成 WordMem 占位应用图标（绿色圆角底 + 白色 W），多尺寸 ICO。

后续想换图标：直接用同名文件替换 packaging/app.ico 重新打包即可；
或修改本脚本后运行 `python scripts/make_icon.py` 重新生成。
"""
from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packaging" / "app.ico"

_app = QApplication([])

SIZES = (16, 24, 32, 48, 64, 128, 256)
GRAD_TOP, GRAD_BOTTOM = "#4cb87e", "#2e8b5f"


def render(size: int) -> bytes:
    """渲染单尺寸图标并返回 PNG 字节。"""
    s = float(size)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setPen(Qt.NoPen)

    radius = s * 0.24
    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor(GRAD_TOP))
    grad.setColorAt(1.0, QColor(GRAD_BOTTOM))
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(0, 0, s, s), radius, radius)

    f = QFont("Segoe UI")
    f.setBold(True)
    f.setPixelSize(round(s * 0.66))
    p.setFont(f)
    fm = p.fontMetrics()
    text = "W"
    x = (s - fm.horizontalAdvance(text)) / 2
    y = (s - fm.ascent()) / 2 + fm.ascent()
    p.setPen(QColor(255, 255, 255))
    p.drawText(QPointF(x, y), text)
    p.end()

    buf = QBuffer()
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    return bytes(buf.data())


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    """按 ICO 规范组装：ICONDIR + ICONDIRENTRY 列表 + PNG 数据。"""
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    entries, offset = b"", 6 + 16 * count
    for size, data in images:
        wh = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", wh, wh, 0, 0, 1, 32,
                               len(data), offset)
        offset += len(data)
    return header + entries + b"".join(d for _, d in images)


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(build_ico([(s, render(s)) for s in SIZES]))
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
