# -*- coding: utf-8 -*-
"""通用 UI 控件：图标按钮、胶囊按钮、卡片、进度条、轮播圆点。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QPushButton, QWidget

from wordmem.ui import theme
from wordmem.ui.icons import icon


class IconButton(QAbstractButton):
    """圆形悬停感的图标按钮。"""

    def __init__(self, name: str, color: str = "#5a6b72", size: int = 32,
                 icon_size: int = 18, tooltip: str = "", checkable: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._color = color
        self._icon_size = icon_size
        self.setFixedSize(size, size)
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.isDown() or self.isChecked():
            p.setBrush(QColor(47, 62, 70, 36))
        elif self.underMouse():
            p.setBrush(QColor(47, 62, 70, 20))
        else:
            p.setBrush(Qt.NoBrush)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 8, 8)
        x = (self.width() - self._icon_size) / 2
        y = (self.height() - self._icon_size) / 2
        icon(self._name, self._color, self._icon_size).paint(
            p, int(x), int(y), self._icon_size, self._icon_size)

    def enterEvent(self, ev) -> None:  # noqa: N802
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(ev)


class PillButton(QPushButton):
    """截图底部的大号胶囊按钮（图标 + 文案）。"""

    def __init__(self, text: str, icon_name: str, color: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._color = color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setIcon(icon(icon_name, color, 20))
        self._apply_qss(150)

    def _apply_qss(self, alpha: int) -> None:
        self.setStyleSheet(
            f"PillButton {{ color: {self._color}; font-size: 15px; font-weight: 500;"
            f" padding: 0 22px; border-radius: 23px;"
            f" background: rgba(255,255,255,{alpha}); }}"
            f"PillButton:hover {{ background: rgba(255,255,255,215); }}"
            f"PillButton:pressed {{ background: rgba(255,255,255,235); }}"
            f"PillButton:disabled {{ color: #9aa8ae; background: rgba(255,255,255,90); }}"
        )

    def enterEvent(self, ev) -> None:  # noqa: N802
        self._apply_qss(215)
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802
        self._apply_qss(150)
        super().leaveEvent(ev)


class Card(QWidget):
    """半透明白色圆角卡片容器。"""

    def __init__(self, alpha: int = 165, radius: int = 12,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._alpha = alpha
        self._radius = radius

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        alpha = theme.GHOST_CARD_ALPHA if theme.ghost_mode() else self._alpha
        p.setBrush(QColor(255, 255, 255, alpha))
        p.drawRoundedRect(self.rect(), self._radius, self._radius)


class SmoothBar(QWidget):
    """圆角进度条，可内置左侧百分比文字。"""

    def __init__(self, show_label: bool = False, fill_color: str = "#fdfdf4",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fraction = 0.0
        self._show_label = show_label
        self._fill = fill_color
        self.setFixedHeight(18)

    def set_fraction(self, fraction: float) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(0, (self.height() - 9) / 2, self.width(), 9)
        p.setPen(Qt.NoPen)
        track_alpha = theme.GHOST_TRACK_ALPHA if theme.ghost_mode() else theme.TRACK[1]
        p.setBrush(QColor(255, 255, 255, track_alpha))
        p.drawRoundedRect(track, 4.5, 4.5)
        if self._fraction > 0.005:
            w = max(track.width() * self._fraction, 12)
            p.setBrush(QColor(self._fill))
            p.drawRoundedRect(QRectF(track.x(), track.y(), w, track.height()), 4.5, 4.5)
        if self._show_label:
            p.setPen(QColor(122, 138, 148))
            p.drawText(QRectF(10, 0, 120, self.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, f"{self._fraction * 100:.2f}%")


class Dots(QWidget):
    """示例轮播圆点指示器。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = 1
        self._index = 0
        self.setFixedSize(64, 16)

    def set_state(self, count: int, index: int) -> None:
        self._count = max(1, count)
        self._index = max(0, min(index, count - 1))
        self.setFixedWidth(self._count * 16 + 8)
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for i in range(self._count):
            r = 4 if i == self._index else 3
            alpha = 120 if i == self._index else 70
            p.setBrush(QColor(90, 105, 114, alpha))
            p.drawEllipse(QPointF(8 + i * 16, self.height() / 2), r, r)
