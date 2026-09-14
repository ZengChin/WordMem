# -*- coding: utf-8 -*-
"""背单词页：出题态（单词+音标）与作答态（释义+例句轮播），含判分调度。"""
from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wordmem.core.models import (
    GRADE_AGAIN,
    GRADE_GOOD,
    GRADE_HARD,
    StudySession,
)
from wordmem.ui import theme
from wordmem.ui.icons import icon
from wordmem.ui.widgets import Card, Dots, IconButton, PillButton, SmoothBar

_WORD_FONT_SIZES = (28, 34, 40)
_MEANING_FONT_SIZES = (17, 20, 23)


def _bold_headword(sentence: str, word: str) -> str:
    """将例句中的目标词加粗显示（富文本）。"""
    escaped = html.escape(sentence)
    if not word:
        return escaped
    pattern = re.compile(rf"\b({re.escape(word)})\b", re.IGNORECASE)
    return pattern.sub(r"<b>\1</b>", escaped)


class StudyView(QWidget):
    """学习视图：同一布局在出题 / 作答 / 完成 三种状态间切换。"""

    back_requested = Signal()
    spell_requested = Signal()    # 完成页点击"开始拼写"

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.session: StudySession | None = None
        self._known_clicked = False      # 出题态点了"已认识"还是"不认识"
        self._answer_mode = False        # 是否处于作答态
        self._example_index = 0
        self._current_item = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 2)
        lay.setSpacing(0)

        # ---- 顶部：返回 + 字号 ----
        header = QHBoxLayout()
        self.btn_back = IconButton("back", size=30, icon_size=16, tooltip="返回首页")
        self.btn_font = FontToggle()
        header.addWidget(self.btn_back)
        header.addStretch(1)
        header.addWidget(self.btn_font)
        lay.addLayout(header)
        lay.addSpacing(6)

        # ---- 单词区 ----
        self.word_label = QLabel("word")
        self.word_label.setStyleSheet(f"color:{theme.INK}; font-weight:600;")
        self.word_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self.word_label)
        lay.addSpacing(8)

        phon_row = QHBoxLayout()
        phon_row.setSpacing(6)
        self.btn_speaker = IconButton("speaker", color="#41606d", size=28,
                                      icon_size=16, tooltip="朗读单词")
        self.phonetic = QLabel("")
        self.phonetic.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:14px;")
        phon_row.addWidget(self.btn_speaker)
        phon_row.addWidget(self.phonetic)
        phon_row.addStretch(1)
        lay.addLayout(phon_row)
        lay.addSpacing(10)

        # ---- 释义区（作答态显示） ----
        self.meaning_box = QVBoxLayout()
        self.meaning_box.setSpacing(6)
        lay.addLayout(self.meaning_box)
        lay.addSpacing(12)

        # ---- 例句卡片（作答态显示） ----
        self.example_card = Card(alpha=150, radius=14)
        ex_lay = QVBoxLayout(self.example_card)
        ex_lay.setContentsMargins(18, 14, 14, 10)
        ex_lay.setSpacing(8)
        self.example_text = QLabel("")
        self.example_text.setWordWrap(True)
        self.example_text.setTextFormat(Qt.RichText)
        self.example_text.setStyleSheet(
            f"color:{theme.INK_DARK}; font-size:15px;")
        self.example_trans = QLabel("")
        self.example_trans.setWordWrap(True)
        self.example_trans.setStyleSheet("color:#5a6a72; font-size:14px;")
        nav = QHBoxLayout()
        self.dots = Dots()
        self.btn_prev = IconButton("back", color="#5a6a72", size=26, icon_size=13,
                                   tooltip="上一条例句")
        self.btn_next = IconButton("chevron", color="#5a6a72", size=26, icon_size=13,
                                   tooltip="下一条例句")
        nav.addWidget(self.dots)
        nav.addStretch(1)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        ex_lay.addWidget(self.example_text)
        ex_lay.addWidget(self.example_trans)
        ex_lay.addSpacing(4)
        ex_lay.addLayout(nav)
        lay.addWidget(self.example_card)

        # ---- 完成态 ----
        self.done_label = QLabel("本组完成")
        self.done_label.setAlignment(Qt.AlignCenter)
        self.done_label.setStyleSheet(
            f"color:{theme.INK}; font-size:24px; font-weight:600;")
        self.done_summary = QLabel("")
        self.done_summary.setAlignment(Qt.AlignCenter)
        self.done_summary.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:14px;")
        lay.addWidget(self.done_label)
        lay.addWidget(self.done_summary)

        lay.addStretch(1)

        # ---- 进度 ----
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet(
            f"color:#5f7480; font-size:15px; font-weight:500;")
        lay.addWidget(self.progress_label)
        lay.addSpacing(4)
        self.bar = SmoothBar(fill_color="#f4edc9")
        lay.addWidget(self.bar)
        lay.addSpacing(10)

        # ---- 底部操作按钮 ----
        footer = QHBoxLayout()
        footer.setSpacing(16)
        self.btn_left = PillButton("不认识", "alert", theme.ORANGE)
        self.btn_right = PillButton("已认识", "check", theme.GREEN)
        footer.addWidget(self.btn_left, 1)
        footer.addWidget(self.btn_right, 1)
        lay.addLayout(footer)

        # ---- 信号 ----
        self.btn_back.clicked.connect(self.back_requested)
        self.btn_font.clicked.connect(self._cycle_font)
        self.btn_speaker.clicked.connect(self._pronounce)
        self.btn_left.clicked.connect(self._on_left)
        self.btn_right.clicked.connect(self._on_right)
        self.btn_prev.clicked.connect(lambda: self._switch_example(-1))
        self.btn_next.clicked.connect(lambda: self._switch_example(1))

        self.meaning_labels: list[QLabel] = []
        self._show_idle()

    # ================================================================ 状态
    def _show_idle(self) -> None:
        self.word_label.hide()
        self.btn_speaker.hide()
        self.phonetic.hide()
        self._set_meanings_visible(False)
        self.example_card.hide()
        self.done_label.hide()
        self.done_summary.hide()
        self.btn_left.hide()
        self.btn_right.hide()
        self.progress_label.hide()
        self.bar.hide()

    def _set_meanings_visible(self, visible: bool) -> None:
        for lb in self.meaning_labels:
            lb.setVisible(visible)

    def begin(self, session: StudySession) -> None:
        """开始一组新的学习会话。"""
        self.session = session
        self._show_question()

    # ------------------------------------------------------------ 出题态
    def _show_question(self) -> None:
        item = self.session.current()
        self._current_item = item
        self._answer_mode = False
        word = item.word

        self.done_label.hide()
        self.done_summary.hide()
        self._set_meanings_visible(False)
        self.example_card.hide()

        self.word_label.show()
        self.btn_speaker.show()
        self.phonetic.show()
        self.word_label.setText(word.text)
        self.phonetic.setText(word.phonetic)

        self.btn_left.setText("不认识")
        self.btn_left.setIcon(icon("alert", theme.ORANGE_ICON, 20))
        self.btn_right.setText("已认识")
        self.btn_right.setIcon(icon("check", theme.GREEN_ICON, 20))

        self._update_progress()
        self.btn_left.show()
        self.btn_right.show()
        self.progress_label.show()
        self.bar.show()

        if self.ctx.config.auto_pronounce:
            self._pronounce()

    def _update_progress(self) -> None:
        self.progress_label.setText(
            f"{self.session.position} / {self.session.total}")
        self.bar.set_fraction((self.session.position - 1) / max(1, self.session.total))

    # ------------------------------------------------------------ 作答态
    def _show_answer(self, known_clicked: bool) -> None:
        self._known_clicked = known_clicked
        self._answer_mode = True
        word = self._current_item.word

        # 释义
        for lb in self.meaning_labels:
            self.meaning_box.removeWidget(lb)
            lb.deleteLater()
        self.meaning_labels = []
        for m in word.meanings:
            lb = QLabel(m.label())
            lb.setStyleSheet(f"color:{theme.INK}; font-weight:500;")
            lb.setWordWrap(True)
            self.meaning_box.addWidget(lb)
            self.meaning_labels.append(lb)
        self._set_meanings_visible(True)

        # 例句
        self._example_index = 0
        self._render_example()
        self.example_card.setVisible(bool(word.examples))

        # 按钮语义切换
        if known_clicked:
            self.btn_left.setText("记错了")
            self.btn_left.setIcon(icon("undo", theme.ORANGE_ICON, 20))
            self.btn_left.show()
        else:
            # "不认识"路径：只保留"下一词"一个按钮
            self.btn_left.hide()
        self.btn_right.setText("下一词")
        self.btn_right.setIcon(icon("arrow_right", theme.GREEN_ICON, 20))
        self._apply_font_scale()

    def _render_example(self) -> None:
        examples = self._current_item.word.examples
        if not examples:
            self.dots.set_state(1, 0)
            self.example_text.setText("")
            self.example_trans.setText("")
            return
        i = self._example_index
        ex = examples[i]
        self.example_text.setText(_bold_headword(ex.text, self._current_item.word.text))
        self.example_trans.setText(ex.translation)
        self.dots.set_state(len(examples), i)

    def _switch_example(self, delta: int) -> None:
        examples = self._current_item.word.examples
        if not examples:
            return
        self._example_index = (self._example_index + delta) % len(examples)
        self._render_example()

    # ================================================================ 交互
    def _on_left(self) -> None:
        if self.session is None:
            return
        if self.session.finished:          # 完成态下左键即"返回首页"
            self.back_requested.emit()
            return
        if not self._answer_mode:          # 出题态：不认识 -> 作答态
            self._show_answer(known_clicked=False)
            return
        # 作答态：仅"已认识 -> 记错了"会走到这里
        self._grade_and_advance(False)

    def _on_right(self) -> None:
        if self.session is None:
            return
        if self.session.finished:
            self.spell_requested.emit()   # 完成态：开始拼写
            return
        if not self._answer_mode:          # 出题态：已认识 -> 作答态
            self._show_answer(known_clicked=True)
            return
        # 作答态："下一词"：已认识来源判对，不认识来源判错
        self._grade_and_advance(self._known_clicked)

    def _grade_and_advance(self, passed: bool) -> None:
        item = self._current_item
        self.ctx.service.grade(self.session, item, self._quality(passed))
        self.session.index += 1
        if self.session.finished:
            self.ctx.service.complete_session(self.session)
            self._show_done()
        else:
            # 每次推进都保存快照，中途退出后可恢复本组
            self.ctx.service.save_session(self.session)
            self._show_question()

    def _quality(self, passed: bool) -> int:
        """将 UI 作答路径映射为 SM-2 质量分。"""
        if not passed:
            return GRADE_AGAIN              # 记错了 / 不认识直接下一词
        return GRADE_GOOD if self._known_clicked else GRADE_HARD

    # ------------------------------------------------------------ 完成态
    def _show_done(self) -> None:
        self.word_label.hide()
        self.btn_speaker.hide()
        self.phonetic.hide()
        self._set_meanings_visible(False)
        self.example_card.hide()
        self.btn_left.hide()
        self.btn_right.hide()
        self.progress_label.hide()
        self.bar.hide()

        mode = "复习" if self.session.mode == "review" else "学习"
        unique = self.session.passed + self.session.failed
        self.done_label.setText("本组完成！")
        self.done_summary.setText(
            f"本次{mode} {unique} 词 · "
            f"记住 {self.session.passed} · 需巩固 {self.session.failed}")
        self.done_label.show()
        self.done_summary.show()

        # 完成页提供"返回首页"与"开始拼写"两个入口
        self.btn_left.setText("返回首页")
        self.btn_left.setIcon(icon("back", theme.GREEN_ICON, 20))
        self.btn_right.setText("开始拼写")
        self.btn_right.setIcon(icon("check", theme.GREEN_ICON, 20))
        self.btn_left.show()
        self.btn_right.show()

    # ------------------------------------------------------------ 其它
    def _pronounce(self) -> None:
        if self._current_item is not None:
            self.ctx.speaker.speak(self._current_item.word.text)

    def _cycle_font(self) -> None:
        self.ctx.config.cycle_font()
        self.ctx.configs.save()
        self._apply_font_scale()

    def _apply_font_scale(self) -> None:
        level = self.ctx.config.font_level
        f = QFont()
        f.setPixelSize(_WORD_FONT_SIZES[level])
        f.setBold(True)
        self.word_label.setFont(f)
        mf = QFont()
        mf.setPixelSize(_MEANING_FONT_SIZES[level])
        for lb in self.meaning_labels:
            lb.setFont(mf)

    def showEvent(self, ev) -> None:  # noqa: N802
        self._apply_font_scale()
        super().showEvent(ev)


class FontToggle(IconButton):
    """Aa 字号切换按钮（复用图标按钮的悬停效果）。"""

    def __init__(self, parent=None) -> None:
        super().__init__("dot", color="#41606d", size=30, icon_size=0,
                         tooltip="切换单词字号", parent=parent)

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
        p.setPen(QColor("#41606d"))
        f = p.font()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, "Aa")
