# -*- coding: utf-8 -*-
"""对话框：学习统计 / 设置 / 词书管理。统一无边框卡片风格。"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wordmem.ui import theme
from wordmem.ui.widgets import IconButton, SmoothBar, Switch


class BaseDialog(QDialog):
    """无边框白色圆角对话框基类：标题 + 关闭按钮 + 内容区。

    popup_close=True 时以弹层模式展示：点击窗口外空白区域自动关闭。
    """

    def __init__(self, title: str, parent: QWidget | None = None,
                 size: tuple[int, int] = (360, 340),
                 popup_close: bool = False) -> None:
        super().__init__(parent)
        if popup_close:
            self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint
                                | Qt.NoDropShadowWindowHint)
            # 关闭弹层的那次点击不回放给下层控件，避免误触按钮
            self.setAttribute(Qt.WA_NoMouseReplay, True)
        else:
            self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
            self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
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
    """学习统计：统计块网格 + 总体进度；点击窗口外空白处可关闭。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__("学习统计", parent, (360, 340), popup_close=True)
        stats = ctx.repo.stats_summary(date.today())

        tiles = [
            ("词书总词数", stats["total"], theme.INK_DARK),
            ("已学习", stats["learned"], theme.GREEN),
            ("学习中", stats["learning"], theme.INK_DARK),
            ("已掌握", stats["mastered"], theme.GREEN),
            ("今日待复习", stats["due"], theme.ORANGE),
            ("今日已复习", stats["reviewed_today"], theme.INK_DARK),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for i, (key, value, color) in enumerate(tiles):
            grid.addWidget(self._tile(key, value, color), i // 2, i % 2)
        self.body.addLayout(grid)
        self.body.addSpacing(4)

        cap = QLabel("总体进度")
        cap.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:13px; padding-left:2px;")
        self.body.addWidget(cap)
        bar = SmoothBar(show_label=True, fill_color=theme.GREEN_ICON)
        bar.set_fraction(stats["learned"] / max(1, stats["total"]))
        bar.setFixedHeight(20)
        self.body.addWidget(bar)
        self.body.addStretch(1)

    @staticmethod
    def _tile(key: str, value, color: str) -> QFrame:
        """浅色圆角统计块：大数值 + 小标签。"""
        tile = QFrame()
        tile.setStyleSheet("QFrame { background:#f4f7f8; border-radius:10px; }")
        lay = QVBoxLayout(tile)
        lay.setContentsMargins(14, 10, 14, 9)
        lay.setSpacing(1)
        v = QLabel(str(value))
        v.setStyleSheet(f"color:{color}; font-size:19px; font-weight:700;")
        k = QLabel(key)
        k.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:12px;")
        lay.addWidget(v)
        lay.addWidget(k)
        return tile


class SettingsDialog(BaseDialog):
    """学习设置：分组行卡片 + 步进器 + 滑动开关。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__("设置", parent, (360, 336), popup_close=True)
        self.ctx = ctx
        cfg = ctx.config

        self.spin, box1 = self._stepper(5, 50, cfg.batch_size)
        self.body.addWidget(self._tile("每组学习词数", box1))

        self.gap_spin, box2 = self._stepper(1, 5, cfg.requeue_gap)
        self.body.addWidget(self._tile(
            "答错重现间隔（词数）", box2,
            "答错后在该词数与其 +1 之间随机重现，如设 3 则随机 3~4 个词后再次出现"))

        self.auto_pron = Switch()
        self.auto_pron.setChecked(cfg.auto_pronounce)
        self.body.addWidget(self._tile("出词时自动发音", self.auto_pron))

        reset_btn = QPushButton("恢复初始学习进度")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setFixedHeight(34)
        reset_btn.setStyleSheet(
            "QPushButton { color:#b03a3a; border:1px solid #e5c4c4;"
            " border-radius:10px; font-size:13px; }"
            "QPushButton:hover { background:#fdf1f1; }"
            "QPushButton:pressed { background:#f8e4e4; }")
        reset_btn.clicked.connect(self._reset_progress)
        self.body.addWidget(reset_btn)

        apply_btn = QPushButton("保存")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setFixedHeight(38)
        apply_btn.setStyleSheet(
            f"QPushButton {{ color:white; background:{theme.GREEN};"
            f" border-radius:19px; font-size:15px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{theme.GREEN_ICON}; }}")
        apply_btn.clicked.connect(self._save)
        self.body.addWidget(apply_btn)

    # ------------------------------------------------------------ 构件
    @staticmethod
    def _tile(text: str, content: QWidget, tooltip: str = "") -> QFrame:
        """浅色圆角分组行：左侧说明文字 + 右侧控件。"""
        tile = QFrame()
        tile.setStyleSheet("QFrame { background:#f4f7f8; border-radius:10px; }")
        lay = QHBoxLayout(tile)
        lay.setContentsMargins(14, 9, 12, 9)
        lay.setSpacing(8)
        label = QLabel(text)
        label.setStyleSheet(f"color:{theme.INK}; font-size:14px;")
        lay.addWidget(label)
        lay.addStretch(1)
        lay.addWidget(content)
        if tooltip:
            for w in (tile, *tile.findChildren(QWidget)):
                w.setToolTip(tooltip)
        return tile

    @staticmethod
    def _stepper(lo: int, hi: int, value: int) -> tuple[QSpinBox, QWidget]:
        """“− 数值 +”步进器。"""
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(value)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignCenter)
        spin.setFixedSize(54, 28)
        spin.setStyleSheet(
            "QSpinBox { background:white; border:1px solid #dbe3e6;"
            " border-radius:8px; color:#2f3e46; font-size:14px;"
            " font-weight:600; }"
            "QSpinBox:focus { border:1px solid #3fa26b; }")
        minus = IconButton("minus", color=theme.GREEN, size=28, icon_size=12,
                           tooltip="减少")
        plus = IconButton("plus", color=theme.GREEN, size=28, icon_size=12,
                          tooltip="增加")
        minus.clicked.connect(lambda: spin.stepBy(-1))
        plus.clicked.connect(lambda: spin.stepBy(1))
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(minus)
        lay.addWidget(spin)
        lay.addWidget(plus)
        return spin, box

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
    """词书管理：当前词书信息 + 内置/导入词书列表 + 切换/删除/导入入口。"""

    book_switched = Signal()   # 切换/删除词书后发出，通知外部刷新

    def __init__(self, ctx, parent=None) -> None:
        super().__init__("词书", parent, (380, 500))
        self.ctx = ctx
        self._build_current_block()
        self._build_list_area()
        self._build_bottom_bar()
        self._refresh_list()

    # -------------------------------------------------- 当前词书信息块
    def _build_current_block(self) -> None:
        block = QFrame()
        block.setStyleSheet(
            f"QFrame {{ background:{theme.GREEN_BG}; border-radius:10px;"
            f" border:1px solid #cfe5d8; }}")
        lay = QVBoxLayout(block)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(3)

        book = self.ctx.book_manager.get_active_book()
        summary = self.ctx.service.home_summary()

        name_text = book.name if book else "（无词书）"
        desc_text = book.description if book and book.description else "暂无描述"
        info_text = (f"共 {summary['total']} 词 · 已学 {summary['learned']} 词 · "
                     f"待复习 {summary['review_left']} 词")

        self.cur_name = QLabel(name_text)
        self.cur_name.setStyleSheet(
            f"color:{theme.GREEN}; font-size:16px; font-weight:600;")
        self.cur_desc = QLabel(desc_text)
        self.cur_desc.setWordWrap(True)
        self.cur_desc.setStyleSheet(f"color:{theme.INK}; font-size:13px;")
        self.cur_info = QLabel(info_text)
        self.cur_info.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:12px;")
        lay.addWidget(self.cur_name)
        lay.addWidget(self.cur_desc)
        lay.addWidget(self.cur_info)
        self.body.addWidget(block)

    # -------------------------------------------------- 词书列表滚动区
    def _build_list_area(self) -> None:
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
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch(1)   # 占位，后续由 _refresh_list 动态填充
        scroll.setWidget(container)
        self.body.addWidget(scroll, 1)

    def _build_bottom_bar(self) -> None:
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_import = QPushButton("导入词书...")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setFixedHeight(32)
        self.btn_import.setStyleSheet(
            f"QPushButton {{ color:{theme.GREEN}; border:1px solid #cfe5d8;"
            f" border-radius:16px; padding:0 14px; font-size:13px;"
            f" background:transparent; }}"
            f"QPushButton:hover {{ background:{theme.GREEN_BG}; }}")
        self.btn_import.clicked.connect(self._open_import_dialog)

        self.btn_download = QPushButton("下载更多词库 ↗")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.setFixedHeight(32)
        self.btn_download.setStyleSheet(
            f"QPushButton {{ color:{theme.INK_SOFT}; border:1px solid #dbe3e6;"
            f" border-radius:16px; padding:0 14px; font-size:13px;"
            f" background:transparent; }}"
            f"QPushButton:hover {{ background:#f4f7f8; }}")
        self.btn_download.clicked.connect(self._open_download_url)

        bar.addWidget(self.btn_import)
        bar.addStretch(1)
        bar.addWidget(self.btn_download)
        self.body.addLayout(bar)

    # -------------------------------------------------- 刷新词书列表
    def _refresh_list(self) -> None:
        """重建当前词书信息 + 词书列表（切换/删除后调用）。"""
        # 刷新当前词书信息块
        book = self.ctx.book_manager.get_active_book()
        summary = self.ctx.service.home_summary()
        self.cur_name.setText(book.name if book else "（无词书）")
        self.cur_desc.setText(
            book.description if book and book.description else "暂无描述")
        self.cur_info.setText(
            f"共 {summary['total']} 词 · 已学 {summary['learned']} 词 · "
            f"待复习 {summary['review_left']} 词")

        # 清空列表区（保留末尾的 stretch）
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        active_id = (book.id if book else None)

        # 内置词书分组
        builtins = self.ctx.book_manager.list_builtin_books()
        if builtins:
            self.list_layout.insertWidget(
                self.list_layout.count() - 1,
                self._section_label("内置词书"))
            for b in builtins:
                self.list_layout.insertWidget(
                    self.list_layout.count() - 1,
                    self._book_row(b, active_id, deletable=False))

        # 用户导入词书分组
        imported = self.ctx.book_manager.list_imported_books()
        if imported:
            self.list_layout.insertWidget(
                self.list_layout.count() - 1,
                self._section_label("我的导入"))
            for b in imported:
                self.list_layout.insertWidget(
                    self.list_layout.count() - 1,
                    self._book_row(b, active_id, deletable=True))

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:12px; padding:6px 2px 2px 2px;")
        return lab

    def _book_row(self, book, active_id: int | None,
                  deletable: bool) -> QFrame:
        """单行词书：状态/切换按钮 + 名称 + 词数 + 可选删除。"""
        is_active = (book.id == active_id)
        row = QFrame()
        if is_active:
            row.setStyleSheet(
                f"QFrame {{ background:{theme.GREEN_BG}; border-radius:8px;"
                f" border:1px solid {theme.GREEN_ICON}; }}")
        else:
            row.setStyleSheet(
                "QFrame { background:#f4f7f8; border-radius:8px;"
                " border:1px solid transparent; }")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(8)

        if is_active:
            tag = QLabel("✓ 使用中")
            tag.setStyleSheet(
                f"color:{theme.GREEN}; font-size:12px; font-weight:600;"
                f" padding:2px 6px; border:1px solid #cfe5d8;"
                f" border-radius:8px; background:white;")
            lay.addWidget(tag)
        else:
            btn = QPushButton("切换")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                f"QPushButton {{ color:{theme.GREEN}; border:1px solid #cfe5d8;"
                f" border-radius:12px; padding:0 10px; font-size:12px;"
                f" background:white; }}"
                f"QPushButton:hover {{ background:{theme.GREEN_BG}; }}")
            btn.clicked.connect(
                lambda _, bid=book.id: self._switch_book(bid))
            lay.addWidget(btn)

        name = QLabel(book.name)
        name.setStyleSheet(
            f"color:{theme.INK_DARK if is_active else theme.INK};"
            f" font-size:13px; font-weight:{'600' if is_active else '400'};")
        lay.addWidget(name, 1)

        count = QLabel(f"{book.word_count} 词")
        count.setStyleSheet(f"color:{theme.INK_SOFT}; font-size:12px;")
        lay.addWidget(count)

        if deletable and not is_active:
            del_btn = IconButton("close", color="#b03a3a", size=22,
                                icon_size=11, tooltip="删除词书")
            del_btn.clicked.connect(
                lambda _, bid=book.id: self._delete_book(bid))
            lay.addWidget(del_btn)
        return row

    # -------------------------------------------------- 交互
    def _switch_book(self, book_id: int) -> None:
        book = self.ctx.repo.get_book_by_id(book_id)
        if book is None:
            return
        ret = QMessageBox.question(
            self, "切换词书",
            f"切换到《{book.name}》？\n当前词书的学习进度会保留，下次切回时继续。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        self.ctx.book_manager.switch_book(book_id)
        self._refresh_list()
        self.book_switched.emit()

    def _delete_book(self, book_id: int) -> None:
        book = self.ctx.repo.get_book_by_id(book_id)
        if book is None:
            return
        ret = QMessageBox.question(
            self, "删除词书",
            f"确定删除导入词书《{book.name}》？\n词书及其学习进度将被清除，不可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        try:
            self.ctx.book_manager.delete_book(book_id)
        except ValueError as e:
            QMessageBox.warning(self, "无法删除", str(e))
            return
        self._refresh_list()
        self.book_switched.emit()

    def _open_import_dialog(self) -> None:
        from wordmem.ui.views.import_dialog import ImportBookDialog

        dlg = ImportBookDialog(self.ctx, self)
        dlg.exec()
        # 导入后刷新列表（无论是否成功导入都刷新一次）
        self._refresh_list()
        self.book_switched.emit()

    def _open_download_url(self) -> None:
        QDesktopServices.openUrl(QUrl(
            "https://github.com/KyleBing/english-vocabulary"))
