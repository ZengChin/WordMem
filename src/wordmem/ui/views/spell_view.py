# -*- coding: utf-8 -*-
"""拼写练习页：显示中文释义与发音，用户输入英文拼写，回车校验，空格提示。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from wordmem.core.models import StudySession, Word
from wordmem.ui import theme
from wordmem.ui.icons import icon
from wordmem.ui.widgets import IconButton, PillButton, SmoothBar

_COLOR_CORRECT = theme.GREEN       # 拼写正确：绿色
_COLOR_WRONG = "#c0392b"           # 拼写错误：红色
_COLOR_HINT = theme.INK_SOFT       # 空格提示：次要灰青


def spell_words(session: StudySession) -> list[Word]:
    """会话内去重后的拼写单词列表（按首次出现顺序）。"""
    seen: set[int] = set()
    words: list[Word] = []
    for item in session.items:
        if item.word.id not in seen:
            seen.add(item.word.id)
            words.append(item.word)
    return words


class SpellInput(QLineEdit):
    """拼写输入框：回车提交校验，空格显示英文提示。"""

    submit_requested = Signal()
    hint_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.IBeamCursor)
        self.setPlaceholderText("输入英文拼写后按回车校验 · 空格查看提示")

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.submit_requested.emit()
            return
        if ev.key() == Qt.Key_Space:
            self.hint_requested.emit()
            return
        super().keyPressEvent(ev)


class SpellView(QWidget):
    """拼写练习视图：中文+音标出题，输入校验，错误红字/正确绿字，空格提示。"""

    back_requested = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.words: list[Word] = []
        self.index = 0
        self.correct_count = 0       # 拼写正确的词数
        self.first_try_ok = 0        # 一次即拼对的词数
        self.missed = 0              # 曾拼错的词数
        self._word_attempted = False  # 当前词是否拼错过
        self._locked = False          # 正确反馈期间锁定输入
        self._feedback_timer: QTimer | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 2)
        lay.setSpacing(0)

        # ---- 顶部：返回 + 标题 + 进度 ----
        header = QHBoxLayout()
        self.btn_back = IconButton("back", size=30, icon_size=16, tooltip="返回首页")
        title = QLabel("拼写练习")
        title.setStyleSheet(f"color:{theme.INK}; font-size:16px; font-weight:600;")
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setStyleSheet(
            "color:#5f7480; font-size:14px; font-weight:500;")
        header.addWidget(self.btn_back)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.progress_label)
        lay.addLayout(header)
        lay.addSpacing(18)

        # ---- 中文释义（大字号） ----
        self.meaning_label = QLabel("")
        self.meaning_label.setAlignment(Qt.AlignCenter)
        self.meaning_label.setWordWrap(True)
        self.meaning_label.setStyleSheet(
            f"color:{theme.INK_DARK}; font-size:24px; font-weight:600;")
        lay.addWidget(self.meaning_label)
        lay.addSpacing(8)

        # ---- 发音：音标 + 喇叭 ----
        phon_row = QHBoxLayout()
        phon_row.setSpacing(6)
        self.btn_speaker = IconButton("speaker", color="#41606d", size=28,
                                      icon_size=16, tooltip="朗读单词")
        self.phonetic = QLabel("")
        self.phonetic.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:15px;")
        phon_row.addStretch(1)
        phon_row.addWidget(self.btn_speaker)
        phon_row.addWidget(self.phonetic)
        phon_row.addStretch(1)
        lay.addLayout(phon_row)
        lay.addSpacing(24)

        # ---- 输入框 ----
        self.input_edit = SpellInput()
        self.input_edit.setFixedHeight(46)
        self.input_edit.setAlignment(Qt.AlignCenter)
        self.input_edit.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,185);"
            f" border:1px solid #d6dee2; border-radius:23px;"
            f" padding:0 18px; font-size:18px; color:{theme.INK_DARK}; }}"
            f"QLineEdit:focus {{ border:2px solid {theme.GREEN}; }}")
        lay.addWidget(self.input_edit)
        lay.addSpacing(10)

        # ---- 反馈/提示区（红色错误、绿色正确、灰色空格提示） ----
        self.feedback_label = QLabel("")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setFixedHeight(48)
        lay.addWidget(self.feedback_label)

        # ---- 完成态（内容区） ----
        self.done_label = QLabel("拼写完成！")
        self.done_label.setAlignment(Qt.AlignCenter)
        self.done_label.setStyleSheet(
            f"color:{theme.INK}; font-size:24px; font-weight:600;")
        self.done_summary = QLabel("")
        self.done_summary.setAlignment(Qt.AlignCenter)
        self.done_summary.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:14px;")
        lay.addWidget(self.done_label)
        lay.addWidget(self.done_summary)

        lay.addStretch(1)

        # ---- 进度条 ----
        self.bar = SmoothBar(fill_color="#b7d8c8")
        lay.addWidget(self.bar)
        lay.addSpacing(12)

        # ---- 底部按钮 ----
        footer = QHBoxLayout()
        self.btn_finish = PillButton("结束拼写", "back", theme.GREEN)
        footer.addWidget(self.btn_finish, 1)
        lay.addLayout(footer)

        # ---- 信号 ----
        self.btn_back.clicked.connect(self.back_requested)
        self.btn_finish.clicked.connect(self.back_requested)
        self.btn_speaker.clicked.connect(self._pronounce)
        self.input_edit.submit_requested.connect(self._submit)
        self.input_edit.hint_requested.connect(self._show_hint)

        self._show_idle()

    # ================================================================ 状态
    def _show_idle(self) -> None:
        self.meaning_label.hide()
        self.btn_speaker.hide()
        self.phonetic.hide()
        self.input_edit.hide()
        self.feedback_label.hide()
        self.progress_label.hide()
        self.bar.hide()
        self.btn_finish.hide()
        self.done_label.hide()
        self.done_summary.hide()

    def begin(self, session: StudySession) -> None:
        """以本次会话去重后的单词开始拼写练习。"""
        self.words = spell_words(session)
        self.index = 0
        self.correct_count = 0
        self.first_try_ok = 0
        self.missed = 0
        self._clear_timer()
        if not self.words:
            self._show_done()
            return
        self._show_idle()
        self._load_word()

    def _load_word(self) -> None:
        word = self.words[self.index]
        self._word_attempted = False
        self._locked = False

        self.done_label.hide()
        self.done_summary.hide()
        self.meaning_label.show()
        self.btn_speaker.show()
        self.phonetic.show()
        self.input_edit.show()
        self.feedback_label.show()
        self.progress_label.show()
        self.bar.show()
        self.btn_finish.setText("结束拼写")
        self.btn_finish.setIcon(icon("back", theme.GREEN_ICON, 20))
        self.btn_finish.show()

        self.meaning_label.setText("；".join(m.label() for m in word.meanings))
        self.phonetic.setText(word.phonetic)
        self.progress_label.setText(f"{self.index + 1} / {len(self.words)}")
        self.bar.set_fraction(self.index / max(1, len(self.words)))
        self.input_edit.clear()
        self._clear_feedback()
        self.input_edit.setFocus()

        if self.ctx.config.auto_pronounce:
            self._pronounce()

    # ================================================================ 交互
    def _submit(self) -> None:
        """回车校验：错误显示红色英文（1 秒后隐藏），正确显示绿色并前进。"""
        if self._locked or not self.words or self.index >= len(self.words):
            return
        text = self.input_edit.text().strip()
        if not text:
            return
        word = self.words[self.index]
        if text.lower() == word.text.lower():
            self.correct_count += 1
            if self._word_attempted:
                self.missed += 1
            else:
                self.first_try_ok += 1
            self._locked = True
            self._set_feedback(word.text, _COLOR_CORRECT, 1000, self._next)
        else:
            self._word_attempted = True
            self._set_feedback(word.text, _COLOR_WRONG, 1000,
                               lambda: self._hide_feedback(clear_input=True))

    def _show_hint(self) -> None:
        """空格提示：显示英文 2 秒后隐藏，保留用户已输入内容。"""
        if self._locked or not self.words or self.index >= len(self.words):
            return
        word = self.words[self.index]
        self._set_feedback(word.text, _COLOR_HINT, 2000,
                           lambda: self._hide_feedback(clear_input=False))

    def _next(self) -> None:
        self.index += 1
        if self.index < len(self.words):
            self._load_word()
        else:
            self._show_done()

    def _pronounce(self) -> None:
        if self.words and 0 <= self.index < len(self.words):
            self.ctx.speaker.speak(self.words[self.index].text)

    # ------------------------------------------------------------ 反馈定时
    def _set_feedback(self, text: str, color: str, ms: int, on_done) -> None:
        self._clear_timer()
        self.feedback_label.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:600;")
        self.feedback_label.setText(text)
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(
            lambda: self._finish_feedback(on_done))
        self._feedback_timer.start(ms)

    def _finish_feedback(self, on_done) -> None:
        self._feedback_timer = None
        if on_done is not None:
            on_done()

    def _hide_feedback(self, clear_input: bool) -> None:
        self.feedback_label.clear()
        if clear_input:
            self.input_edit.clear()
        self.input_edit.setFocus()

    def _clear_timer(self) -> None:
        if self._feedback_timer is not None:
            self._feedback_timer.stop()
            self._feedback_timer.deleteLater()
            self._feedback_timer = None

    def _clear_feedback(self) -> None:
        self._clear_timer()
        self.feedback_label.clear()

    # ------------------------------------------------------------ 完成态
    def _show_done(self) -> None:
        self._clear_timer()
        self._locked = True
        self.meaning_label.hide()
        self.btn_speaker.hide()
        self.phonetic.hide()
        self.input_edit.hide()
        self.feedback_label.hide()
        self.progress_label.hide()
        self.bar.hide()

        total = len(self.words)
        self.done_label.setText("拼写完成！")
        self.done_summary.setText(
            f"共拼写 {total} 词 · 一次拼对 {self.first_try_ok} · 需重试 {self.missed}")
        self.done_label.show()
        self.done_summary.show()
        self.btn_finish.setText("返回首页")
        self.btn_finish.setIcon(icon("back", theme.GREEN_ICON, 20))
        self.btn_finish.show()

    # ================================================================ 其它
    def showEvent(self, ev) -> None:  # noqa: N802
        if self.words and self.index < len(self.words) and not self._locked:
            self.input_edit.setFocus()
        super().showEvent(ev)
