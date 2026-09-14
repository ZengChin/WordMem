# -*- coding: utf-8 -*-
"""线性不透明度调节条：按钮下方的横向滑杆弹窗，再次点击按钮或点击外部即隐藏。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

MIN_OPACITY, MAX_OPACITY = 0.25, 1.0

_SLIDER_QSS = """
QSlider::groove:horizontal {
    height: 6px; border-radius: 3px; background: rgba(255,255,255,50);
}
QSlider::sub-page:horizontal {
    height: 6px; border-radius: 3px; background: #7ed8a8;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -5px 0;
    border-radius: 7px; background: #ffffff;
}
QSlider::handle:horizontal:hover { background: #eafff3; }
"""


class OpacitySliderPopup(QWidget):
    """弹出式横向滑杆（类似进度条），用于调节按钮与字体不透明度。"""

    value_changed = Signal(float)
    closed = Signal()

    def __init__(self, current: float = 1.0, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._value = self._clamp(current)

        self._slider = QSlider(Qt.Horizontal, self)
        self._slider.setRange(round(MIN_OPACITY * 100), round(MAX_OPACITY * 100))
        self._slider.setValue(round(self._value * 100))
        self._slider.setFixedWidth(160)
        self._slider.setCursor(Qt.PointingHandCursor)
        self._slider.setStyleSheet(_SLIDER_QSS)

        self._label = QLabel(f"{round(self._value * 100)}%", self)
        self._label.setStyleSheet(
            "color:#ffffff; font-size:13px; font-weight:600; background:transparent;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 12, 10)
        lay.setSpacing(9)
        lay.addWidget(self._slider)
        lay.addWidget(self._label)

        self._slider.valueChanged.connect(self._on_slider_changed)

    # ------------------------------------------------------------ 数值
    @staticmethod
    def _clamp(v: float) -> float:
        return max(MIN_OPACITY, min(MAX_OPACITY, v))

    def value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        """设置数值（0.25 ~ 1.0），经滑杆联动后触发 value_changed。"""
        self._slider.setValue(round(self._clamp(v) * 100))

    def _on_slider_changed(self, v: int) -> None:
        self._value = self._clamp(v / 100.0)
        self._label.setText(f"{round(self._value * 100)}%")
        self.value_changed.emit(self._value)

    # ------------------------------------------------------------ 关闭
    def hideEvent(self, ev) -> None:  # noqa: N802
        # Qt.Popup 点击外部 / Esc / close() 都会走 hide，统一在此通知
        self.closed.emit()
        super().hideEvent(ev)

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(45, 60, 68, 235))
        p.drawRoundedRect(self.rect(), 12, 12)
