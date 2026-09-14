# -*- coding: utf-8 -*-
"""单词列表页：当前词库全部单词，默认隐藏中文，点行显示，可一键切换。"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wordmem.ui import theme
from wordmem.ui.icons import icon
from wordmem.ui.widgets import IconButton


class WordListView(QWidget):
    """虚拟化单词列表：内部高度为全部行，仅绘制可见行。

    默认不显示中文释义；点击某行时切换该行中文显隐。
    必须通过 set_scroll_area 关联宿主滚动区，以获取滚动偏移与视口高度。
    """

    _ROW_H = 44

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._words = []
        self._shown: set[int] = set()
        self._hover = -1
        self._scroll_area: QScrollArea | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    # ------------------------------------------------------------ 数据
    def set_scroll_area(self, area: QScrollArea) -> None:
        self._scroll_area = area

    def set_words(self, words) -> None:
        self._words = list(words)
        self._shown.clear()
        self._hover = -1
        # 高度 = 全部行，宽度由宿主滚动区撑满（widgetResizable=True）
        self.setMinimumHeight(len(self._words) * self._ROW_H)
        self.update()

    def show_all(self, show: bool) -> None:
        self._shown = set(range(len(self._words))) if show else set()
        self.update()

    def _row_at(self, y: int) -> int:
        i = y // self._ROW_H
        return i if 0 <= i < len(self._words) else -1

    def _scroll_offset(self) -> int:
        if self._scroll_area is not None:
            return self._scroll_area.verticalScrollBar().value()
        return 0

    def _viewport_height(self) -> int:
        if self._scroll_area is not None:
            return self._scroll_area.viewport().height()
        return self.height()

    # ------------------------------------------------------------ 事件
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            i = self._row_at(int(ev.position().y()))
            if i >= 0:
                if i in self._shown:
                    self._shown.discard(i)
                else:
                    self._shown.add(i)
                self.update()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        i = self._row_at(int(ev.position().y()))
        if i != self._hover:
            self._hover = i
            self.update()
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(ev)

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self._words)
        if n == 0:
            return
        offset = self._scroll_offset()
        view_h = self._viewport_height()
        w = self.width()
        first = max(0, offset // self._ROW_H)
        last = min(n - 1, (offset + view_h) // self._ROW_H)
        left_w = max(160, int(w * 0.46))
        for i in range(first, last + 1):
            y = i * self._ROW_H
            word = self._words[i]
            if i == self._hover:
                p.fillRect(0, y, w, self._ROW_H, QColor(47, 62, 70, 16))
            # 英文（加粗）
            f = QFont()
            f.setPixelSize(15)
            f.setBold(True)
            p.setFont(f)
            fm = p.fontMetrics()
            p.setPen(QColor(theme.INK_DARK))
            p.drawText(QRect(16, y, left_w - 12, self._ROW_H),
                       Qt.AlignVCenter | Qt.AlignLeft, word.text)
            # 音标（紧随英文之后）
            if word.phonetic:
                ww = fm.horizontalAdvance(word.text)
                f2 = QFont(f)
                f2.setBold(False)
                f2.setPixelSize(12)
                p.setFont(f2)
                p.setPen(QColor(theme.INK_SOFT))
                fm2 = p.fontMetrics()
                ph = fm2.elidedText(word.phonetic, Qt.ElideRight,
                                    max(20, left_w - 24 - ww))
                p.drawText(QRect(16 + ww + 8, y, max(20, left_w - 24 - ww),
                                 self._ROW_H),
                           Qt.AlignVCenter | Qt.AlignLeft, ph)
            # 中文释义（默认隐藏，点行后显示在右侧）
            if i in self._shown:
                text = "; ".join(m.label() for m in word.meanings)
                f3 = QFont()
                f3.setPixelSize(13)
                p.setFont(f3)
                p.setPen(QColor(theme.GREEN))
                region = w - 16 - left_w
                if region > 30:
                    elided = p.fontMetrics().elidedText(
                        text, Qt.ElideRight, region)
                    p.drawText(QRect(left_w, y, region, self._ROW_H),
                               Qt.AlignVCenter | Qt.AlignRight, elided)
            # 行分隔线
            p.setPen(QColor(232, 238, 240))
            p.drawLine(16, y + self._ROW_H - 1, w - 16, y + self._ROW_H - 1)


class WordListPage(QWidget):
    """单词列表页（主窗口内切换展示，不弹新窗口）。"""

    back_requested = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 4)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.btn_back = IconButton("back", size=34, icon_size=19, tooltip="返回首页")
        title = QLabel("全部单词")
        title.setStyleSheet(
            f"color:{theme.INK_DARK}; font-size:16px; font-weight:600;")
        self.count_label = QLabel()
        self.count_label.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:13px;")
        self.btn_toggle = QPushButton()
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setFixedHeight(30)
        self.btn_toggle.setIcon(icon("eye", theme.GREEN, 15))
        self.btn_toggle.setStyleSheet(
            f"QPushButton {{ color:{theme.GREEN}; border:1px solid #cfe5d8;"
            f" border-radius:15px; padding:0 14px; font-size:13px;"
            f" background:transparent; }}"
            f"QPushButton:hover {{ background:{theme.GREEN_BG}; }}")
        self._all_shown = False
        self._update_toggle_text()
        head.addWidget(self.btn_back)
        head.addSpacing(6)
        head.addWidget(title)
        head.addWidget(self.count_label)
        head.addStretch(1)
        head.addWidget(self.btn_toggle)
        lay.addLayout(head)

        self.list_view = WordListView()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 6px;"
            " margin: 2px; }"
            "QScrollBar::handle:vertical { background:#c9d6d3;"
            " border-radius:3px; min-height:24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            " height:0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            " background:none; }")
        self.list_view.set_scroll_area(scroll)
        scroll.setWidget(self.list_view)
        scroll.verticalScrollBar().valueChanged.connect(self.list_view.update)
        lay.addWidget(scroll, 1)

        self.btn_back.clicked.connect(self.back_requested)
        self.btn_toggle.clicked.connect(self._on_toggle_all)

        self.refresh()

    # ------------------------------------------------------------ 数据
    def refresh(self) -> None:
        words = self.ctx.repo.get_all_words()
        self.list_view.set_words(words)
        self.count_label.setText(f"共 {len(words)} 词")
        self._all_shown = False
        self.list_view.show_all(False)
        self._update_toggle_text()

    def _update_toggle_text(self) -> None:
        self.btn_toggle.setText("隐藏全部中文" if self._all_shown else "显示全部中文")

    def _on_toggle_all(self) -> None:
        self._all_shown = not self._all_shown
        self.list_view.show_all(self._all_shown)
        self._update_toggle_text()
