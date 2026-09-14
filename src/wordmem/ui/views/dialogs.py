# -*- coding: utf-8 -*-
"""对话框：学习统计 / 设置 / 词书详情。统一无边框卡片风格。"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wordmem.ui import theme
from wordmem.ui.widgets import IconButton, SmoothBar


class BaseDialog(QDialog):
    """无边框白色圆角对话框基类：标题 + 关闭按钮 + 内容区。"""

    def __init__(self, title: str, parent: QWidget | None = None,
                 size: tuple[int, int] = (360, 340)) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(*size)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.panel = QFrame(self)
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet(
            "#panel { background: white; border-radius: 14px; }")
        outer.addWidget(self.panel)

        panel_lay = QVBoxLayout(self.panel)
        panel_lay.setContentsMargins(20, 14, 16, 18)
        panel_lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel(title)
        title.setStyleSheet(
            f"color:{theme.INK_DARK}; font-size:16px; font-weight:600;")
        close = IconButton("close", color="#8a8f93", size=26, icon_size=13,
                           tooltip="关闭")
        close.clicked.connect(self.reject)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(close)
        panel_lay.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        panel_lay.addLayout(self.body)


class StatsDialog(BaseDialog):
    """学习统计。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__("学习统计", parent, (360, 330))
        stats = ctx.repo.stats_summary(date.today())

        rows = [
            ("词书总词数", stats["total"]),
            ("已学习", stats["learned"]),
            ("学习中", stats["learning"]),
            ("已掌握", stats["mastered"]),
            ("今日待复习", stats["due"]),
            ("今日已复习", stats["reviewed_today"]),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        for i, (k, v) in enumerate(rows):
            key = QLabel(k)
            key.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:14px;")
            val = QLabel(str(v))
            val.setStyleSheet(
                f"color:{theme.INK_DARK}; font-size:16px; font-weight:600;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(key, i, 0)
            grid.addWidget(val, i, 1)
        self.body.addLayout(grid)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#e3e8ea;")
        self.body.addWidget(line)

        total = max(1, stats["total"])
        self.body.addWidget(QLabel("总体进度"))
        bar = SmoothBar(show_label=True, fill_color=theme.GREEN_ICON)
        bar.set_fraction(stats["learned"] / total)
        self.body.addWidget(bar)
        self.body.addStretch(1)


class SettingsDialog(BaseDialog):
    """学习设置。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__("设置", parent, (360, 310))
        self.ctx = ctx
        cfg = ctx.config

        row1 = QHBoxLayout()
        label = QLabel("每组学习词数")
        label.setStyleSheet(f"color:{theme.INK}; font-size:14px;")
        self.spin = QSpinBox()
        self.spin.setRange(5, 50)
        self.spin.setValue(cfg.batch_size)
        self.spin.setFixedWidth(80)
        self.spin.setStyleSheet(
            "QSpinBox { border:1px solid #d6dee2; border-radius:6px;"
            " padding:4px 8px; }")
        row1.addWidget(label)
        row1.addStretch(1)
        row1.addWidget(self.spin)
        self.body.addLayout(row1)

        row2 = QHBoxLayout()
        gap_label = QLabel("答错重现间隔（词数）")
        gap_label.setStyleSheet(f"color:{theme.INK}; font-size:14px;")
        self.gap_spin = QSpinBox()
        self.gap_spin.setRange(1, 5)
        self.gap_spin.setValue(cfg.requeue_gap)
        self.gap_spin.setToolTip("答错后在该词数与其 +1 之间随机重现，"
                                 "如设 3 则随机 3~4 个词后再次出现")
        self.gap_spin.setFixedWidth(80)
        self.gap_spin.setStyleSheet(
            "QSpinBox { border:1px solid #d6dee2; border-radius:6px;"
            " padding:4px 8px; }")
        row2.addWidget(gap_label)
        row2.addStretch(1)
        row2.addWidget(self.gap_spin)
        self.body.addLayout(row2)

        self.auto_pron = QCheckBox("出词时自动发音")
        self.auto_pron.setChecked(cfg.auto_pronounce)
        self.auto_pron.setStyleSheet(f"color:{theme.INK}; font-size:14px;")
        self.body.addWidget(self.auto_pron)

        reset_btn = QPushButton("恢复初始学习进度")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setFixedHeight(34)
        reset_btn.setStyleSheet(
            "QPushButton { color:#b03a3a; border:1px solid #e5c4c4;"
            " border-radius:8px; }"
            "QPushButton:hover { background:#fdf1f1; }")
        reset_btn.clicked.connect(self._reset_progress)
        self.body.addWidget(reset_btn)
        self.body.addStretch(1)

        apply_btn = QPushButton("保存")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setFixedHeight(36)
        apply_btn.setStyleSheet(
            f"QPushButton {{ color:white; background:{theme.GREEN};"
            f" border-radius:18px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{theme.GREEN_ICON}; }}")
        apply_btn.clicked.connect(self._save)
        self.body.addWidget(apply_btn)

    def _save(self) -> None:
        self.ctx.config.batch_size = self.spin.value()
        self.ctx.config.requeue_gap = self.gap_spin.value()
        self.ctx.config.auto_pronounce = self.auto_pron.isChecked()
        self.ctx.configs.save()
        self.accept()

    def _reset_progress(self) -> None:
        ret = QMessageBox.question(
            self, "确认", "确定要清空全部学习记录吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.ctx.repo.reset_progress()
            QMessageBox.information(self, "完成", "学习进度已重置。")
            self.accept()


class BookInfoDialog(BaseDialog):
    """词书详情。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__("词书详情", parent, (360, 240))
        book = ctx.repo.get_book()
        summary = ctx.service.home_summary()

        name = QLabel(book.name)
        name.setStyleSheet(
            f"color:{theme.GREEN}; font-size:18px; font-weight:600;")
        desc = QLabel(book.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{theme.INK}; font-size:14px;")
        info = QLabel(
            f"共 {summary['total']} 词 · 已学 {summary['learned']} 词 · "
            f"待复习 {summary['review_left']} 词")
        info.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:13px;")

        self.body.addWidget(name)
        self.body.addWidget(desc)
        self.body.addSpacing(6)
        self.body.addWidget(info)
        self.body.addStretch(1)
