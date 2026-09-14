# -*- coding: utf-8 -*-
"""首页：词书进度卡片 + 学新词 / 复习词入口。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wordmem.ui import theme
from wordmem.ui.widgets import Card, IconButton, PillButton, SmoothBar


class NumberCard(Card):
    """底部统计卡片：大数字 + 胶囊操作按钮；点击整张卡片即可触发操作。"""

    clicked = Signal()

    def __init__(self, action_text: str, icon_name: str, parent=None) -> None:
        super().__init__(alpha=190, radius=12, parent=parent)
        self._base_alpha = 190
        self._hover_alpha = 225
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(action_text)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 16, 14, 14)
        lay.setSpacing(12)

        self.number = QLabel("0")
        self.number.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPixelSize(24)
        f.setBold(True)
        self.number.setFont(f)
        self.number.setStyleSheet(f"color:{theme.INK_DARK};")

        self.button = PillButton(action_text, icon_name, theme.GREEN)
        self.button.setFixedHeight(40)
        # 按钮点击同样视为整卡点击（QPushButton 拦截鼠标事件，需单独接线）
        self.button.clicked.connect(self.clicked)

        lay.addStretch(1)
        lay.addWidget(self.number)
        lay.addWidget(self.button)
        lay.addStretch(1)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)

    def enterEvent(self, ev) -> None:  # noqa: N802
        self._alpha = self._hover_alpha
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802
        self._alpha = self._base_alpha
        self.update()
        super().leaveEvent(ev)


class BookCard(Card):
    """词书进度卡片。"""

    def __init__(self, parent=None) -> None:
        super().__init__(alpha=175, radius=14, parent=parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 14, 16)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self.name = QLabel("词书")
        self.name.setStyleSheet(f"color:{theme.GREEN}; font-size:15px; font-weight:600;")
        self.list_btn = IconButton("list", color=theme.GREEN, size=26,
                                   icon_size=14, tooltip="查看全部单词")
        self.more = IconButton("chevron", color=theme.GREEN, size=26, icon_size=14,
                               tooltip="词书详情")
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.list_btn)
        top.addWidget(self.more)
        lay.addLayout(top)

        lay.addStretch(1)
        self.counter = QLabel("0 / 0")
        self.counter.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPixelSize(19)
        self.counter.setFont(f)
        self.counter.setStyleSheet(f"color:{theme.INK};")
        lay.addWidget(self.counter)
        lay.addSpacing(6)

        self.bar = SmoothBar(show_label=True)
        self.bar.setFixedHeight(20)
        lay.addWidget(self.bar)


class HomeView(QWidget):
    """首页视图。"""

    start_session = Signal(str)  # "new" / "review"
    word_list_requested = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 4)
        lay.setSpacing(0)

        header = QHBoxLayout()
        self.btn_settings = IconButton("settings", size=34, icon_size=19,
                                       tooltip="设置")
        self.btn_stats = IconButton("chart", size=34, icon_size=19,
                                    tooltip="学习统计")
        header.addWidget(self.btn_settings)
        header.addStretch(1)
        header.addWidget(self.btn_stats)
        lay.addLayout(header)

        lay.addStretch(2)
        self.book_card = BookCard()
        lay.addWidget(self.book_card)
        lay.addStretch(3)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        self.card_new = NumberCard("学新词", "book_new")
        self.card_review = NumberCard("复习词", "book_review")
        bottom.addWidget(self.card_new, 1)
        bottom.addWidget(self.card_review, 1)
        lay.addLayout(bottom)

        # ---- 信号 ----
        self.card_new.clicked.connect(lambda: self._start("new"))
        self.card_review.clicked.connect(lambda: self._start("review"))
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_stats.clicked.connect(self._open_stats)
        self.book_card.more.clicked.connect(self._open_book_info)
        self.book_card.list_btn.clicked.connect(self._open_word_list)

        self.refresh()

    def _start(self, mode: str) -> None:
        """整卡点击入口；无可用词时按钮禁用，不触发会话。"""
        button = self.card_new.button if mode == "new" else self.card_review.button
        if button.isEnabled():
            self.start_session.emit(mode)

    # ------------------------------------------------------------ 数据刷新
    def refresh(self) -> None:
        summary = self.ctx.service.home_summary()
        book = self.ctx.repo.get_book()
        total, learned = summary["total"], summary["learned"]

        self.book_card.name.setText(book.name if book else "词书")
        self.book_card.counter.setText(f"{learned} / {total}")
        fraction = learned / total if total else 0.0
        self.book_card.bar.set_fraction(fraction)

        self.card_new.number.setText(str(summary["new_left"]))
        self.card_review.number.setText(str(summary["review_left"]))
        self.card_new.button.setEnabled(summary["new_left"] > 0)
        # 复习需先完整背完至少一组
        review_ready = (summary["review_left"] > 0
                        and summary["completed_batches"] > 0)
        self.card_review.button.setEnabled(review_ready)

    # ------------------------------------------------------------ 弹窗
    def _open_settings(self) -> None:
        from wordmem.ui.views.dialogs import SettingsDialog

        dlg = SettingsDialog(self.ctx, self.window())
        dlg.exec()

    def _open_stats(self) -> None:
        from wordmem.ui.views.dialogs import StatsDialog

        StatsDialog(self.ctx, self.window()).exec()

    def _open_book_info(self) -> None:
        from wordmem.ui.views.dialogs import BookInfoDialog

        BookInfoDialog(self.ctx, self.window()).exec()

    def _open_word_list(self) -> None:
        self.word_list_requested.emit()
