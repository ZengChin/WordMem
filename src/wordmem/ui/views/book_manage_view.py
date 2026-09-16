# -*- coding: utf-8 -*-
"""词书管理视图 + 导入词书视图（主窗口内页面切换，不弹窗）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wordmem.ui import theme
from wordmem.ui.icons import icon
from wordmem.ui.widgets import IconButton, SmoothBar

# 格式下拉项：(显示文本, 传给 BookManager 的 fmt 值, None 表示自动识别)
_FORMAT_OPTIONS = [
    ("自动识别", None),
    ("WordMem JSON", "wordmem"),
    ("简单 JSON", "simple"),
    ("JSONL", "jsonl"),
    ("TXT", "txt"),
    ("CSV", "csv"),
    ("Anki .apkg", "apkg"),
]

# 推荐词库下载源：(名称, 链接, 简介)
_DOWNLOAD_SOURCES = [
    ("AnkiWeb 共享牌组",
     "https://ankiweb.net/shared/decks?search=english",
     "海量 .apkg 牌组，导入时自动识别字段"),
    ("KyleBing/english-vocabulary",
     "https://github.com/KyleBing/english-vocabulary",
     "含 CET4/CET6/考研，TXT/JSON 格式"),
    ("skywind3000/ECDICT",
     "https://github.com/skywind3000/ECDICT",
     "77 万词条 CSV，含音标释义"),
    ("mahavivo/english-wordlists",
     "https://github.com/mahavivo/english-wordlists",
     "多种分类词库"),
]


# ============================================================ 词书管理页面
class BookManageView(QWidget):
    """词书管理页面：当前词书信息 + 内置/导入词书列表 + 导入/下载入口。"""

    back_requested = Signal()
    book_switched = Signal()
    import_requested = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 4)
        lay.setSpacing(8)

        # ---- 顶栏 ----
        head = QHBoxLayout()
        self.btn_back = IconButton("back", size=34, icon_size=19,
                                   tooltip="返回首页")
        title = QLabel("词书")
        title.setStyleSheet(
            f"color:{theme.INK_DARK}; font-size:16px; font-weight:600;")
        self.count_label = QLabel()
        self.count_label.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:13px;")
        head.addWidget(self.btn_back)
        head.addSpacing(6)
        head.addWidget(title)
        head.addWidget(self.count_label)
        head.addStretch(1)
        lay.addLayout(head)

        # ---- 当前词书信息块 ----
        self._build_current_block()

        # ---- 词书列表滚动区 ----
        self._build_list_area()

        # ---- 底部操作栏 ----
        self._build_bottom_bar()

        # ---- 信号 ----
        self.btn_back.clicked.connect(self.back_requested)
        self.btn_import.clicked.connect(self.import_requested)

        self._refresh_list()

    # -------------------------------------------------- 当前词书信息块
    def _build_current_block(self) -> None:
        block = QFrame()
        block.setObjectName("curBlock")
        # 用 #curBlock 而非 QFrame 选择器：QLabel 也是 QFrame 子类，
        # 类型选择器会级联给内部文字标签加上边框，形成多余的线框
        block.setStyleSheet(
            f"#curBlock {{ background:{theme.GREEN_BG}; border-radius:10px;"
            f" border:1px solid #cfe5d8; }}")
        lay = QVBoxLayout(block)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(3)

        self.cur_name = QLabel()
        self.cur_name.setStyleSheet(
            f"color:{theme.GREEN}; font-size:15px; font-weight:600;")
        self.cur_desc = QLabel()
        self.cur_desc.setWordWrap(True)
        self.cur_desc.setStyleSheet(f"color:{theme.INK}; font-size:12px;")
        self.cur_info = QLabel()
        self.cur_info.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:11px;")
        self.cur_bar = SmoothBar(fill_color=theme.GREEN_ICON)
        self.cur_bar.setFixedHeight(14)
        lay.addWidget(self.cur_name)
        lay.addWidget(self.cur_desc)
        lay.addWidget(self.cur_info)
        lay.addWidget(self.cur_bar)
        # block 自带布局 lay，直接挂到根布局即可；
        # 切勿把「装着 block 的子布局」再塞回 block 自身的 lay，否则布局循环嵌套会死循环
        self._current_block = block
        self.layout().addWidget(block)

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
        self.list_layout.setSpacing(7)
        self.list_layout.addStretch(1)
        scroll.setWidget(container)
        self.layout().addWidget(scroll, 1)

    # -------------------------------------------------- 底部操作栏
    def _build_bottom_bar(self) -> None:
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_import = QPushButton(" 导入词书")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setFixedHeight(34)
        self.btn_import.setIcon(icon("upload", theme.GREEN, 15))
        self.btn_import.setStyleSheet(
            f"QPushButton {{ color:{theme.GREEN}; border:1px solid #cfe5d8;"
            f" border-radius:17px; padding:0 16px; font-size:13px;"
            f" background:transparent; }}"
            f"QPushButton:hover {{ background:{theme.GREEN_BG}; }}")

        self.btn_download = QPushButton(" 下载更多")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.setFixedHeight(34)
        self.btn_download.setIcon(icon("download", theme.INK_SOFT, 15))
        self.btn_download.setStyleSheet(
            f"QPushButton {{ color:{theme.INK_SOFT}; border:1px solid #dbe3e6;"
            f" border-radius:17px; padding:0 16px; font-size:13px;"
            f" background:transparent; }}"
            f"QPushButton:hover {{ background:#f4f7f8; }}")
        self.btn_download.clicked.connect(self._open_download_url)

        bar.addWidget(self.btn_import)
        bar.addStretch(1)
        bar.addWidget(self.btn_download)
        self.layout().addLayout(bar)

    # -------------------------------------------------- 刷新
    def refresh(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        """重建当前词书信息 + 词书列表。"""
        book = self.ctx.book_manager.get_active_book()
        summary = self.ctx.service.home_summary()
        self.cur_name.setText(book.name if book else "（无词书）")
        self.cur_desc.setText(
            book.description if book and book.description else "暂无描述")
        total = summary['total']
        learned = summary['learned']
        self.cur_info.setText(
            f"共 {total} 词 · 已学 {learned} · "
            f"待复习 {summary['review_left']}")
        self.cur_bar.set_fraction(learned / max(1, total))

        # 清空列表区（保留末尾的 stretch）
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        active_id = (book.id if book else None)
        count = 0

        # 内置词书分组
        builtins = self.ctx.book_manager.list_builtin_books()
        if builtins:
            count += len(builtins)
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
            count += len(imported)
            self.list_layout.insertWidget(
                self.list_layout.count() - 1,
                self._section_label("我的导入"))
            for b in imported:
                self.list_layout.insertWidget(
                    self.list_layout.count() - 1,
                    self._book_row(b, active_id, deletable=True))

        self.count_label.setText(f"共 {count} 本")

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:11px; font-weight:600;"
            f" padding:8px 2px 4px 2px;")
        return lab

    def _book_row(self, book, active_id: int | None,
                  deletable: bool) -> QFrame:
        """单行词书：名称 + 词数 + 切换/状态 + 可选删除，整行可点击切换。"""
        is_active = (book.id == active_id)
        row = QFrame()
        row.setObjectName("bookRow")

        if is_active:
            row.setStyleSheet(
                f"#bookRow {{ background:{theme.GREEN_BG}; border-radius:8px;"
                f" border:1px solid {theme.GREEN_ICON}; }}")
        else:
            row.setCursor(Qt.PointingHandCursor)
            row.setStyleSheet(
                f"#bookRow {{ background:#f4f7f8; border-radius:8px;"
                f" border:1px solid transparent; }}"
                f"#bookRow:hover {{ background:#edf2f3;"
                f" border-color:#dbe3e6; }}")
            row.mousePressEvent = lambda ev, bid=book.id: (
                self._switch_book(bid) if ev.button() == Qt.LeftButton
                else None)

        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 8, 10, 8)
        lay.setSpacing(10)

        name = QLabel(book.name)
        name.setStyleSheet(
            f"color:{theme.INK_DARK if is_active else theme.INK};"
            f" font-size:13px; font-weight:{'600' if is_active else '400'};")
        lay.addWidget(name, 1)

        count = QLabel(f"{book.word_count} 词")
        count.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:11px;")
        lay.addWidget(count)

        if is_active:
            tag = QLabel("使用中")
            tag.setStyleSheet(
                f"color:{theme.GREEN}; font-size:11px; font-weight:600;"
                f" padding:2px 8px; border:1px solid #cfe5d8;"
                f" border-radius:10px; background:white;")
            lay.addWidget(tag)
        else:
            btn = QPushButton("切换")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                f"QPushButton {{ color:{theme.GREEN}; border:1px solid #cfe5d8;"
                f" border-radius:13px; padding:0 12px; font-size:12px;"
                f" background:white; }}"
                f"QPushButton:hover {{ background:{theme.GREEN_BG};"
                f" border-color:{theme.GREEN_ICON}; }}")
            btn.clicked.connect(
                lambda _, bid=book.id: self._switch_book(bid))
            lay.addWidget(btn)

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

    def _open_download_url(self) -> None:
        QDesktopServices.openUrl(QUrl(
            "https://github.com/KyleBing/english-vocabulary"))


# ============================================================ 导入词书页面
class _FileDropZone(QFrame):
    """文件拖放区：点击选择、拖放文件。"""

    file_selected = Signal(str)  # 空字符串表示点击浏览

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(72)
        self.setObjectName("fileZone")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self.label = QLabel("点击选择或拖拽文件到此处")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.hint = QLabel("支持 JSON / JSONL / TXT / CSV / apkg")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        lay.addStretch(1)
        lay.addWidget(self.label)
        lay.addWidget(self.hint)
        lay.addStretch(1)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.file_selected.emit("")
        super().mousePressEvent(ev)

    def dragEnterEvent(self, ev) -> None:  # noqa: N802
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:  # noqa: N802
        urls = ev.mimeData().urls()
        if urls:
            self.file_selected.emit(urls[0].toLocalFile())


class ImportBookView(QWidget):
    """导入词书页面：拖拽/选择文件 → 格式 → 名称/描述 → 推荐源 → 导入。"""

    back_requested = Signal()
    imported = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._file_path = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 4)
        lay.setSpacing(8)

        # ---- 顶栏 ----
        head = QHBoxLayout()
        self.btn_back = IconButton("back", size=34, icon_size=19,
                                   tooltip="返回词书管理")
        title = QLabel("导入词书")
        title.setStyleSheet(
            f"color:{theme.INK_DARK}; font-size:16px; font-weight:600;")
        head.addWidget(self.btn_back)
        head.addSpacing(6)
        head.addWidget(title)
        head.addStretch(1)
        lay.addLayout(head)

        # ---- 滚动内容区 ----
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
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)

        # 文件拖放区
        self.file_zone = _FileDropZone()
        self.file_zone.file_selected.connect(self._on_file_selected)
        cl.addWidget(self.file_zone)

        # 表单
        self.fmt_combo = QComboBox()
        for label, _fmt in _FORMAT_OPTIONS:
            self.fmt_combo.addItem(label)
        cl.addWidget(self._form_row("格式", self.fmt_combo))

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("留空则用文件名")
        cl.addWidget(self._form_row("名称", self.name_edit))

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("可选")
        cl.addWidget(self._form_row("描述", self.desc_edit))

        # 推荐下载源
        cap = QLabel("推荐词库下载")
        cap.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:12px;"
            f" padding:6px 2px 4px 2px;")
        cl.addWidget(cap)
        for name, url, desc in _DOWNLOAD_SOURCES:
            cl.addWidget(self._download_row(name, url, desc))

        cl.addStretch(1)
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

        # ---- 底部：错误提示 + 导入按钮 ----
        self.error_label = QLabel()
        self.error_label.setStyleSheet(
            "color:#b03a3a; font-size:12px; padding:2px 2px;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        lay.addWidget(self.error_label)

        self.btn_import = QPushButton("导入")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setFixedHeight(38)
        self.btn_import.setStyleSheet(
            f"QPushButton {{ color:white; background:{theme.GREEN};"
            f" border-radius:19px; font-size:14px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{theme.GREEN_ICON}; }}"
            f"QPushButton:disabled {{ background:#c9d6d3; }}")
        self.btn_import.clicked.connect(self._start_import)
        lay.addWidget(self.btn_import)

        # ---- 信号 ----
        self.btn_back.clicked.connect(self.back_requested)

        self._update_file_zone()

    # -------------------------------------------------- 表单构件
    @staticmethod
    def _form_row(label: str, widget: QWidget) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lab = QLabel(label)
        lab.setFixedWidth(38)
        lab.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:13px;"
            " background:transparent; border:none;")
        lay.addWidget(lab)
        widget.setFixedHeight(34)
        widget.setStyleSheet(ImportBookView._input_qss())
        lay.addWidget(widget, 1)
        return row

    @staticmethod
    def _input_qss() -> str:
        return (
            "QLineEdit, QComboBox { background:white; border:1px solid #dbe3e6;"
            " border-radius:8px; padding:0 10px; color:#2f3e46; font-size:13px; }"
            "QLineEdit:focus, QComboBox:focus { border:1px solid #3fa26b; }"
            "QComboBox::drop-down { border:none; width:20px; }"
            "QComboBox QAbstractItemView { background:white; border:1px solid"
            " #dbe3e6; border-radius:4px; selection-background-color:#e9f5ee; }")

    @staticmethod
    def _download_row(name: str, url: str, desc: str) -> QFrame:
        row = QFrame()
        row.setObjectName("dlRow")
        row.setStyleSheet(
            f"#dlRow {{ background:#f4f7f8; border-radius:8px;"
            f" border:1px solid transparent; }}"
            f"#dlRow:hover {{ background:{theme.GREEN_BG};"
            f" border-color:#cfe5d8; }}")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 7, 12, 7)
        lay.setSpacing(8)

        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel(
            f'<a href="{url}" '
            f'style="color:#2e8b5f;text-decoration:none">{name}</a>')
        title.setOpenExternalLinks(True)
        title.setTextInteractionFlags(Qt.TextBrowserInteraction)
        title.setStyleSheet(
            f"color:{theme.GREEN}; font-size:13px;"
            " background:transparent; border:none;")
        sub = QLabel(desc)
        sub.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:11px;"
            " background:transparent; border:none;")
        text.addWidget(title)
        text.addWidget(sub)
        lay.addLayout(text, 1)

        arrow = QLabel("↗")
        arrow.setStyleSheet(
            f"color:{theme.INK_SOFT}; font-size:14px;"
            " background:transparent; border:none;")
        lay.addWidget(arrow)
        return row

    # -------------------------------------------------- 文件选择
    def _on_file_selected(self, path: str) -> None:
        if not path:
            self._pick_file()
        else:
            self._set_file(path)

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择词书文件", "",
            "词书文件 (*.json *.jsonl *.txt *.csv *.apkg)")
        if path:
            self._set_file(path)

    def _set_file(self, path: str) -> None:
        self._file_path = path
        if not self.name_edit.text().strip():
            self.name_edit.setText(Path(path).stem)
        self._update_file_zone()

    def _update_file_zone(self) -> None:
        if self._file_path:
            name = Path(self._file_path).name
            self.file_zone.label.setText(name)
            self.file_zone.label.setStyleSheet(
                f"color:{theme.GREEN}; font-size:13px; font-weight:600;"
                " background:transparent; border:none;")
            self.file_zone.hint.setText("点击重新选择")
            self.file_zone.hint.setStyleSheet(
                f"color:{theme.INK_SOFT}; font-size:11px;"
                " background:transparent; border:none;")
            self.file_zone.setStyleSheet(f"""
                #fileZone {{
                    background: {theme.GREEN_BG};
                    border: 2px solid {theme.GREEN_ICON};
                    border-radius: 10px;
                }}
                #fileZone:hover {{
                    border-color: {theme.GREEN};
                }}""")
        else:
            self.file_zone.label.setText("点击选择或拖拽文件到此处")
            self.file_zone.label.setStyleSheet(
                f"color:{theme.INK_SOFT}; font-size:13px;"
                " background:transparent; border:none;")
            self.file_zone.hint.setText("支持 JSON / JSONL / TXT / CSV / apkg")
            self.file_zone.hint.setStyleSheet(
                f"color:{theme.INK_SOFT}; font-size:11px;"
                " background:transparent; border:none;")
            self.file_zone.setStyleSheet(f"""
                #fileZone {{
                    background: #f8fafb;
                    border: 2px dashed #c9d6d3;
                    border-radius: 10px;
                }}
                #fileZone:hover {{
                    border-color: {theme.GREEN_ICON};
                    background: {theme.GREEN_BG};
                }}""")

    # -------------------------------------------------- 导入逻辑
    def reset(self) -> None:
        """进入页面时重置状态。"""
        self._file_path = ""
        self.name_edit.clear()
        self.desc_edit.clear()
        self.fmt_combo.setCurrentIndex(0)
        self.error_label.setVisible(False)
        self._update_file_zone()

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def _start_import(self) -> None:
        path = self._file_path
        if not path:
            self._show_error("请先选择要导入的词书文件。")
            return
        if not Path(path).exists():
            self._show_error(f"找不到文件：{path}")
            return

        self.error_label.setVisible(False)
        idx = self.fmt_combo.currentIndex()
        fmt = _FORMAT_OPTIONS[idx][1]
        name = self.name_edit.text().strip() or None
        description = self.desc_edit.text().strip()

        self._set_importing(True)
        QApplication.processEvents()

        try:
            self.ctx.book_manager.import_book(path, fmt, name, description)
            self._set_importing(False)
            self.imported.emit()
        except Exception as e:  # noqa: BLE001
            self._set_importing(False)
            self._show_error(str(e))

    def _set_importing(self, on: bool) -> None:
        self.btn_import.setEnabled(not on)
        self.btn_back.setEnabled(not on)
        self.btn_import.setText("导入中…" if on else "导入")
        self.file_zone.setEnabled(not on)
        self.fmt_combo.setEnabled(not on)
        self.name_edit.setEnabled(not on)
        self.desc_edit.setEnabled(not on)
