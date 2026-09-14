# -*- coding: utf-8 -*-
"""自定义标题栏：透明模式 / 不透明度辐条 / 窗口置顶 / 最小化 / 关闭。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from wordmem.ui.widgets import IconButton


class TitleBar(QWidget):
    """无边框窗口的拖拽标题栏与窗口控制按钮。"""

    ghost_toggled = Signal(bool)
    opacity_requested = Signal()
    pin_toggled = Signal(bool)
    fold_toggled = Signal(bool)
    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(38)
        self._drag_pos: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 0)
        layout.setSpacing(2)
        layout.addStretch(1)  # 先占位拉伸，把所有按钮推到最右侧

        # ---- 最右侧：透明 / 不透明度滑条 / 置顶 / 自动隐藏 / 最小化 / 关闭 ----
        self.btn_ghost = IconButton("ghost", checkable=True,
                                    tooltip="背景超透明模式（保留轮廓）")
        self.btn_opacity = IconButton("opacity", tooltip="调节按钮与字体不透明度")
        self.btn_pin = IconButton("pin", checkable=True, filled_on_check=True,
                                  tooltip="窗口置顶")
        self.btn_fold = IconButton("fold", checkable=True, filled_on_check=True,
                                   tooltip="鼠标移出窗口时自动隐藏（仅保留菜单栏）")
        self.btn_min = IconButton("minimize", tooltip="最小化")
        self.btn_close = IconButton("close", color="#7d5a5a", tooltip="关闭")

        for b in (self.btn_ghost, self.btn_opacity, self.btn_pin,
                  self.btn_fold, self.btn_min, self.btn_close):
            layout.addWidget(b, 0, Qt.AlignTop)

        self.btn_ghost.toggled.connect(self.ghost_toggled)
        self.btn_opacity.clicked.connect(self.opacity_requested)
        self.btn_pin.toggled.connect(self.pin_toggled)
        self.btn_fold.toggled.connect(self.fold_toggled)
        self.btn_min.clicked.connect(self.minimize_requested)
        self.btn_close.clicked.connect(self.close_requested)

    # ---- 拖拽移动（窗口边缘缩放由原生 WM_NCHITTEST 处理） ----
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._drag_pos is not None and ev.buttons() & Qt.LeftButton:
            self.window().move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        self._drag_pos = None
