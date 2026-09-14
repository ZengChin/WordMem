# -*- coding: utf-8 -*-
"""通用 UI 控件：图标按钮、胶囊按钮、卡片、进度条、轮播圆点。"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QSize, QVariantAnimation
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPen
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
        ghost = theme.ghost_mode()
        base = theme.GHOST_PILL_ALPHA if ghost else alpha
        hover = theme.GHOST_PILL_HOVER if ghost else 215
        pressed = theme.GHOST_PILL_PRESSED if ghost else 235
        disabled = base if ghost else 90
        self.setStyleSheet(
            f"PillButton {{ color: {self._color}; font-size: 15px; font-weight: 500;"
            f" padding: 0 22px; border-radius: 23px;"
            f" background: rgba(255,255,255,{base}); }}"
            f"PillButton:hover {{ background: rgba(255,255,255,{hover}); }}"
            f"PillButton:pressed {{ background: rgba(255,255,255,{pressed}); }}"
            f"PillButton:disabled {{ color: #9aa8ae;"
            f" background: rgba(255,255,255,{disabled}); }}"
        )

    def refresh(self) -> None:
        """透明模式切换后重刷底色，保留当前悬停态。"""
        self._apply_qss(215 if self.underMouse() else 150)

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
    """圆角进度条：渐变填充 + 顶部高光 + 平滑动画，可内置居中百分比。"""

    def __init__(self, show_label: bool = False, fill_color: str = "#fdfdf4",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fraction = 0.0
        self._shown = 0.0            # 动画过程中的显示值
        self._show_label = show_label
        self._fill = fill_color
        self._anim: QVariantAnimation | None = None
        self.setFixedHeight(18)

    def set_fraction(self, fraction: float) -> None:
        """设置进度 0~1；数值变化时以平滑动画过渡。"""
        target = max(0.0, min(1.0, fraction))
        if abs(target - self._fraction) < 1e-4 and self._anim is None:
            return
        self._fraction = target
        if self._anim is not None:
            self._anim.stop()
            self._anim.deleteLater()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._shown)
        anim.setEndValue(target)
        anim.setDuration(450)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._on_tick)
        anim.finished.connect(self._on_done)
        self._anim = anim
        anim.start()

    def _on_tick(self, value) -> None:
        self._shown = float(value)
        self.update()

    def _on_done(self) -> None:
        if self._anim is not None:
            self._anim.deleteLater()
            self._anim = None

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bar_h = 12.0
        radius = bar_h / 2
        track = QRectF(0, (self.height() - bar_h) / 2, self.width(), bar_h)

        # 轨道：半透明胶囊 + 内描边
        p.setPen(Qt.NoPen)
        track_alpha = theme.GHOST_TRACK_ALPHA if theme.ghost_mode() else theme.TRACK[1]
        p.setBrush(QColor(255, 255, 255, track_alpha))
        p.drawRoundedRect(track, radius, radius)
        p.setBrush(Qt.NoBrush)
        pen = QPen(QColor(47, 62, 70, 26))
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5),
                          radius - 0.5, radius - 0.5)
        p.setPen(Qt.NoPen)

        # 填充：垂直渐变 + 顶部高光
        fill_rect = None
        if self._shown > 0.005:
            w = max(track.width() * self._shown, bar_h)   # 最短为一个整圆
            fill_rect = QRectF(track.x(), track.y(), w, track.height())
            base = QColor(self._fill)
            grad = QLinearGradient(fill_rect.topLeft(), fill_rect.bottomLeft())
            grad.setColorAt(0.0, base.lighter(118))
            grad.setColorAt(1.0, base.darker(106))
            p.setBrush(grad)
            p.drawRoundedRect(fill_rect, radius, radius)
            gloss = fill_rect.adjusted(2.5, 1.5, -2.5, -radius)
            p.setBrush(QColor(255, 255, 255, 52))
            p.drawRoundedRect(gloss, gloss.height() / 2, gloss.height() / 2)

        if self._show_label:
            self._draw_label(p, track, fill_rect)

    def _draw_label(self, p: QPainter, track: QRectF,
                    fill_rect: QRectF | None) -> None:
        """百分比文字居中：压在填充上为白色，其余为青灰，跨界时分段着色。"""
        text = f"{self._shown * 100:.1f}%"
        f = p.font()
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(text)
        left = track.center().x() - tw / 2
        pos = QPointF(left, track.center().y() + (fm.ascent() - fm.descent()) / 2)
        covered = fill_rect is not None and fill_rect.right() >= left + tw
        bare = fill_rect is None or fill_rect.right() <= left
        if covered or bare:
            p.setPen(QColor(255, 255, 255, 240) if covered else QColor(theme.INK_SOFT))
            p.drawText(pos, text)
        else:
            p.setPen(QColor(theme.INK_SOFT))
            p.drawText(pos, text)
            p.save()
            p.setClipRect(fill_rect)
            p.setPen(QColor(255, 255, 255, 240))
            p.drawText(pos, text)
            p.restore()


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


class Switch(QAbstractButton):
    """滑动开关：胶囊轨道 + 平滑移动的圆形滑块。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._pos = 0.0              # 滑块位置 0=左(关) 1=右(开)
        self._anim: QVariantAnimation | None = None
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        if not self.isVisible():     # 程序化初始化直接到位
            self._pos = target
            self.update()
            return
        if self._anim is not None:
            self._anim.stop()
            self._anim.deleteLater()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._pos)
        anim.setEndValue(target)
        anim.setDuration(170)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._on_tick)
        anim.finished.connect(self._on_done)
        self._anim = anim
        anim.start()

    def _on_tick(self, value) -> None:
        self._pos = float(value)
        self.update()

    def _on_done(self) -> None:
        if self._anim is not None:
            self._anim.deleteLater()
            self._anim = None

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        h = self.height()
        r = h / 2 - 1
        track = QRectF(1, 1, self.width() - 2, h - 2)
        p.setBrush(QColor(theme.GREEN_ICON) if self.isChecked()
                   else QColor(47, 62, 70, 42))
        p.drawRoundedRect(track, r, r)
        cx = 1 + r + self._pos * (self.width() - 2 - 2 * r)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(QPointF(cx, h / 2), r - 1.5, r - 1.5)
