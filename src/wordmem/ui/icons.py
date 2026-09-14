# -*- coding: utf-8 -*-
"""程序化图标工厂：全部用 QPainter 绘制，避免二进制资源依赖。"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

_SIZE = 64  # 内部绘制分辨率，保证缩放清晰


def _painter(pix: QPixmap, color: str, width: float) -> QPainter:
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    return p


def _draw(name: str, p: QPainter) -> None:
    s = _SIZE
    m = 10
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    center = QPointF(s / 2, s / 2)

    if name == "settings":  # 齿轮设置
        p.save()
        p.translate(center)
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        for i in range(8):          # 8 个轮齿，45° 均布
            p.save()
            p.rotate(i * 45)
            p.drawRoundedRect(QRectF(-s * 0.078, -s * 0.344,
                                     s * 0.156, s * 0.078),
                              s * 0.03, s * 0.03)
            p.restore()
        p.restore()
        ring_pen = QPen(p.pen())    # 齿圈：粗描边圆，与轮齿融合
        ring_pen.setWidthF(s * 0.094)
        p.setPen(ring_pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(center, s * 0.235, s * 0.235)
    elif name == "chart":  # 统计柱状图
        p.drawLine(QPointF(m + 4, m + 2), QPointF(m + 4, s - m - 4))
        p.drawLine(QPointF(m + 4, s - m - 4), QPointF(s - m - 2, s - m - 4))
        for i, h in enumerate((0.32, 0.55, 0.80)):
            x = s * (0.38 + 0.18 * i)
            p.drawLine(QPointF(x, s - m - 4), QPointF(x, s - m - 4 - (s - 2 * m - 8) * h))
    elif name == "chevron":
        path = QPainterPath()
        path.moveTo(s * 0.38, s * 0.28)
        path.lineTo(s * 0.62, s * 0.5)
        path.lineTo(s * 0.38, s * 0.72)
        p.drawPath(path)
    elif name == "back":
        p.drawEllipse(rect.adjusted(2, 2, -2, -2))
        p.drawLine(QPointF(s * 0.58, s * 0.34), QPointF(s * 0.42, s * 0.5))
        p.drawLine(QPointF(s * 0.42, s * 0.5), QPointF(s * 0.58, s * 0.66))
    elif name == "ghost":  # 透明模式：半填充圆角方块
        p.drawRoundedRect(rect, 12, 12)
        p.save()
        p.setClipRect(QRectF(m, m, rect.width() / 2, rect.height()))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(p.pen().color()))
        p.drawRoundedRect(rect, 12, 12)
        p.restore()
    elif name == "opacity":  # 不透明度：斜分半填充圆
        p.drawEllipse(rect)
        path = QPainterPath()
        path.moveTo(rect.center().x(), rect.top())
        path.arcTo(rect, 90, 180)
        path.closeSubpath()
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(p.pen().color()))
        p.drawPath(path)
        p.restore()
    elif name == "pin":  # 置顶（未开启）：空心外描的大头针
        p.drawRoundedRect(QRectF(s * 0.34, s * 0.18, s * 0.32, s * 0.32), 6, 6)
        p.drawLine(QPointF(s * 0.5, s * 0.50), QPointF(s * 0.5, s * 0.62))
        p.drawLine(QPointF(s * 0.36, s * 0.62), QPointF(s * 0.64, s * 0.62))
        p.drawLine(QPointF(s * 0.5, s * 0.62), QPointF(s * 0.5, s * 0.84))
    elif name == "pin_on":  # 置顶（开启）：针头实心填充
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(p.pen().color()))
        p.drawRoundedRect(QRectF(s * 0.34, s * 0.18, s * 0.32, s * 0.32), 6, 6)
        p.setPen(_pen_of(p))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(s * 0.5, s * 0.50), QPointF(s * 0.5, s * 0.62))
        p.drawLine(QPointF(s * 0.36, s * 0.62), QPointF(s * 0.64, s * 0.62))
        p.drawLine(QPointF(s * 0.5, s * 0.62), QPointF(s * 0.5, s * 0.84))
    elif name == "minimize":
        p.drawLine(QPointF(s * 0.28, s * 0.5), QPointF(s * 0.72, s * 0.5))
    elif name == "close":
        p.drawLine(QPointF(s * 0.32, s * 0.32), QPointF(s * 0.68, s * 0.68))
        p.drawLine(QPointF(s * 0.68, s * 0.32), QPointF(s * 0.32, s * 0.68))
    elif name == "fold":  # 自动隐藏（未开启）：顶部横条 + 向上箭头，全为描边
        p.drawRect(QRectF(s * 0.24, s * 0.26, s * 0.52, s * 0.08))
        p.drawLine(QPointF(s * 0.5, s * 0.78), QPointF(s * 0.5, s * 0.44))
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.36, s * 0.58))
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.64, s * 0.58))
    elif name == "fold_on":  # 自动隐藏（开启）：顶部横条实心填充
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(p.pen().color()))
        p.drawRect(QRectF(s * 0.24, s * 0.26, s * 0.52, s * 0.08))
        p.setPen(_pen_of(p))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(s * 0.5, s * 0.78), QPointF(s * 0.5, s * 0.44))
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.36, s * 0.58))
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.64, s * 0.58))
    elif name == "speaker":
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        horn = QPolygonF([
            QPointF(s * 0.24, s * 0.42), QPointF(s * 0.38, s * 0.42),
            QPointF(s * 0.52, s * 0.28), QPointF(s * 0.52, s * 0.72),
            QPointF(s * 0.38, s * 0.58), QPointF(s * 0.24, s * 0.58),
        ])
        p.drawPolygon(horn)
        p.setPen(_pen_of(p))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(s * 0.56, s * 0.36, s * 0.18, s * 0.28), -60, 120)
        p.drawArc(QRectF(s * 0.60, s * 0.28, s * 0.26, s * 0.44), -60, 120)
    elif name == "book_new":
        body = QRectF(m + 6, m + 10, s - 2 * m - 12, s - 2 * m - 14)
        p.drawRoundedRect(body, 6, 6)
        p.drawLine(QPointF(body.center().x(), body.top()),
                   QPointF(body.center().x(), body.bottom()))
        cx, cy = s * 0.72, s * 0.28
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(cx, cy), 10, 10)
        p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
        p.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5))
    elif name == "book_review":
        p.drawArc(QRectF(m + 2, m + 8, s - 2 * m - 4, s - 2 * m), 0, 180)
        p.drawLine(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.5, s * 0.84))
        p.drawLine(QPointF(m + 2, s * 0.5), QPointF(s * 0.5, s * 0.5))
        p.drawLine(QPointF(s - m - 2, s * 0.5), QPointF(s * 0.5, s * 0.5))
    elif name == "alert":  # 不认识
        p.drawEllipse(rect)
        p.drawLine(QPointF(s * 0.5, s * 0.30), QPointF(s * 0.5, s * 0.56))
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.68), 2.6, 2.6)
    elif name == "check":  # 已认识
        p.drawEllipse(rect)
        path = QPainterPath()
        path.moveTo(s * 0.33, s * 0.52)
        path.lineTo(s * 0.46, s * 0.65)
        path.lineTo(s * 0.68, s * 0.38)
        p.drawPath(path)
    elif name == "undo":  # 记错了
        p.drawArc(QRectF(s * 0.22, s * 0.30, s * 0.56, s * 0.44), 90 * 16, 200 * 16)
        arrow = QPolygonF([
            QPointF(s * 0.20, s * 0.42), QPointF(s * 0.34, s * 0.40),
            QPointF(s * 0.26, s * 0.54),
        ])
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        p.drawPolygon(arrow)
    elif name == "arrow_right":
        p.drawLine(QPointF(s * 0.26, s * 0.5), QPointF(s * 0.70, s * 0.5))
        p.drawLine(QPointF(s * 0.70, s * 0.5), QPointF(s * 0.54, s * 0.34))
        p.drawLine(QPointF(s * 0.70, s * 0.5), QPointF(s * 0.54, s * 0.66))
    elif name == "list":  # 单词列表：三条带圆点行
        ys = (s * 0.30, s * 0.50, s * 0.70)
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        for y in ys:
            p.drawEllipse(QPointF(s * 0.28, y), 2.6, 2.6)
        p.setPen(_pen_of(p))
        p.setBrush(Qt.NoBrush)
        for y in ys:
            p.drawLine(QPointF(s * 0.38, y), QPointF(s * 0.74, y))
    elif name == "eye":  # 显示/隐藏中文：眼睛
        p.drawEllipse(QRectF(s * 0.16, s * 0.30, s * 0.68, s * 0.40))
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), 5, 5)
    elif name == "minus":  # 减少
        p.drawLine(QPointF(s * 0.30, s * 0.5), QPointF(s * 0.70, s * 0.5))
    elif name == "plus":  # 增加
        p.drawLine(QPointF(s * 0.30, s * 0.5), QPointF(s * 0.70, s * 0.5))
        p.drawLine(QPointF(s * 0.5, s * 0.30), QPointF(s * 0.5, s * 0.70))
    else:  # 兜底：实心圆
        p.setBrush(QColor(p.pen().color()))
        p.setPen(Qt.NoPen)
        p.drawEllipse(center, 8, 8)


def _pen_of(p: QPainter) -> QPen:
    pen = p.pen()
    pen.setStyle(Qt.SolidLine)
    return pen


@lru_cache(maxsize=256)
def icon(name: str, color: str = "#5a6b72", size: int = 18,
         stroke: float = 1.8) -> QIcon:
    """按名称/颜色生成 QIcon（带缓存）。stroke 为目标显示线宽（px）。"""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    k = size / _SIZE
    p = _painter(pix, color, stroke / k)  # 缩放后线宽仍为 stroke px
    p.scale(k, k)
    _draw(name, p)
    p.end()
    return QIcon(pix)
