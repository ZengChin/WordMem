# -*- coding: utf-8 -*-
"""无边框主窗口：背景绘制、超透明模式、按钮/字体不透明度、原生拖边缩放。"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from wordmem.config.settings import ConfigManager
from wordmem.core.book_manager import BookManager
from wordmem.core.repository import Repository
from wordmem.core.study_service import StudyService
from wordmem.core.tts import Speaker
from wordmem.ui import theme
from wordmem.ui.opacity_popup import OpacitySliderPopup
from wordmem.ui.title_bar import TitleBar
from wordmem.ui.views.book_manage_view import BookManageView, ImportBookView
from wordmem.ui.views.home_view import HomeView
from wordmem.ui.views.spell_view import SpellView
from wordmem.ui.views.study_view import StudyView
from wordmem.ui.views.word_list_view import WordListPage
from wordmem.ui.widgets import PillButton

# ---- Windows 原生命中测试常量 ----
WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTLEFT, HTRIGHT = 10, 11
HTTOP, HTTOPLEFT, HTTOPRIGHT = 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17


class AppContext:
    """应用级上下文（依赖注入容器）。"""

    def __init__(self, repo: Repository, service: StudyService,
                 configs: ConfigManager, speaker: Speaker,
                 book_manager: BookManager | None = None) -> None:
        self.repo = repo
        self.service = service
        self.configs = configs
        self.speaker = speaker
        self.book_manager = book_manager

    @property
    def config(self):
        return self.configs.config


class MainWindow(QWidget):
    """应用主窗口。"""

    closed = Signal()

    RESIZE_MARGIN = 8          # 边缘热区宽度（px），接近资源管理器手感
    MIN_W, MIN_H = 320, 420    # 缩放最小尺寸
    GHOST_TITLEBAR_OPACITY = 0.55   # 透明模式下菜单栏的固定半透明度

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self._opacity_popup: OpacitySliderPopup | None = None
        self._content_hidden = False     # 自动隐藏态：窗口原位不动，仅菜单栏可见
        self._hide_progress = 0.0        # 隐藏动画进度 0=显示 1=隐藏
        self._hide_anim = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.resize(theme.WINDOW_W, theme.WINDOW_H)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = TitleBar(self)
        self.stack = QStackedWidget(self)

        self.home_view = HomeView(ctx, self)
        self.study_view = StudyView(ctx, self)
        self.spell_view = SpellView(ctx, self)
        self.word_list_view = WordListPage(ctx, self)
        self.book_manage_view = BookManageView(ctx, self)
        self.import_book_view = ImportBookView(ctx, self)
        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.study_view)
        self.stack.addWidget(self.spell_view)
        self.stack.addWidget(self.word_list_view)
        self.stack.addWidget(self.book_manage_view)
        self.stack.addWidget(self.import_book_view)

        content = QWidget(self)
        self.content = content          # 自动隐藏时需要整体隐藏/恢复
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(14, 0, 14, 14)
        content_layout.addWidget(self.stack)
        root.addWidget(self.title_bar)
        root.setAlignment(self.title_bar, Qt.AlignTop)  # 内容隐藏时菜单栏仍钉在顶部
        root.addWidget(content, 1)

        # ---- 信号接线 ----
        self.title_bar.ghost_toggled.connect(self._on_ghost)
        self.title_bar.opacity_requested.connect(self._show_opacity_dial)
        self.title_bar.pin_toggled.connect(self._on_pin)
        self.title_bar.fold_toggled.connect(self._on_fold)
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.close_requested.connect(self.close)

        self.home_view.start_session.connect(self._start_session)
        self.home_view.word_list_requested.connect(self._open_word_list)
        self.home_view.book_manage_requested.connect(self._open_book_manage)
        self.study_view.back_requested.connect(self._go_home)
        self.study_view.spell_requested.connect(self._begin_spell)
        self.spell_view.back_requested.connect(self._go_home)
        self.word_list_view.back_requested.connect(self._go_home)
        self.book_manage_view.back_requested.connect(self._go_home)
        self.book_manage_view.book_switched.connect(self.home_view.refresh)
        self.book_manage_view.import_requested.connect(self._open_import_book)
        self.import_book_view.back_requested.connect(self._back_to_book_manage)
        self.import_book_view.imported.connect(self._on_import_done)

        self._apply_config()
        self.stack.setCurrentWidget(self.home_view)
        self._start_auto_hide_watch()

    # ------------------------------------------------------------ 配置
    def _apply_config(self) -> None:
        theme.set_ghost_mode(self.ctx.config.ghost_mode)  # 卡片/进度条同步
        self._apply_fg_opacity(self.ctx.config.ui_opacity)
        self.title_bar.btn_ghost.setChecked(self.ctx.config.ghost_mode)
        self.title_bar.btn_fold.setChecked(self.ctx.config.auto_hide)

    @staticmethod
    def _set_effect(widget: QWidget, opacity: float | None) -> None:
        """为控件设置不透明度效果；1.0 时移除效果避免渲染开销。"""
        if opacity is None or opacity >= 0.995:
            widget.setGraphicsEffect(None)
        else:
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(opacity)
            widget.setGraphicsEffect(effect)

    def _apply_fg_opacity(self, value: float) -> None:
        """按钮与字体不透明度：内容区跟随数值，菜单栏特殊处理。"""
        value = max(0.25, min(1.0, value))
        self.ctx.config.ui_opacity = value
        self._set_effect(self.stack, value)
        # 透明模式下菜单栏保持半透明，普通模式跟随整体数值
        titlebar_opacity = (
            self.GHOST_TITLEBAR_OPACITY if self.ctx.config.ghost_mode else value
        )
        self._set_effect(self.title_bar, titlebar_opacity)

    # ------------------------------------------------------------ 背景透明模式
    def _on_ghost(self, checked: bool) -> None:
        """切换背景/边框是否超透明；按钮底色隐形但文字保留，仅菜单栏转半透明。"""
        self.ctx.config.ghost_mode = checked
        theme.set_ghost_mode(checked)          # 卡片/进度条变超透明
        self._apply_fg_opacity(self.ctx.config.ui_opacity)  # 刷新菜单栏透明度
        for w in QApplication.allWidgets():    # 全量重绘
            if isinstance(w, PillButton):      # 按钮底色随透明模式隐形（文字保留）
                w.refresh()
            else:
                w.update()

    def _show_opacity_dial(self) -> None:
        """点击调节按钮弹出/隐藏线性滑条（类似进度条）。"""
        if self._opacity_popup is not None:
            self._opacity_popup.close()
            self._opacity_popup = None
            return
        popup = OpacitySliderPopup(self.ctx.config.ui_opacity, self)
        popup.value_changed.connect(self._apply_fg_opacity)
        popup.closed.connect(self._on_dial_closed)
        btn = self.title_bar.btn_opacity
        center = btn.mapToGlobal(btn.rect().center())
        popup.adjustSize()
        popup.move(center.x() - popup.width() // 2, center.y() + 6)
        self._opacity_popup = popup
        popup.show()

    def _on_dial_closed(self) -> None:
        self.ctx.configs.save()
        self._opacity_popup = None

    # ------------------------------------------------------------ 置顶
    def _on_pin(self, checked: bool) -> None:
        visible = self.isVisible()
        pos, size = self.pos(), self.size()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        if visible:
            self.hide()
            self.show()
            self.move(pos)
            self.resize(size)

    # ------------------------------------------------------------ 自动隐藏
    def _on_fold(self, checked: bool) -> None:
        """开关"鼠标移出窗口时自动隐藏内容（仅保留菜单栏）"。"""
        self.ctx.config.auto_hide = checked
        if not checked and self._content_hidden:
            self._restore_content()

    def _start_auto_hide_watch(self) -> None:
        """启动鼠标位置轮询：分层窗口透明区不可靠地触发 hover 事件，
        改为定时检测鼠标是否在窗口矩形内，移出隐藏、移入恢复。"""
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setInterval(120)
        self._auto_hide_timer.timeout.connect(self._check_auto_hide)
        self._auto_hide_timer.start()

    def _check_auto_hide(self, pos: QPoint | None = None) -> None:
        """按鼠标位置执行隐藏/恢复；pos 可注入用于测试。"""
        if not self.ctx.config.auto_hide or self.isMinimized():
            return
        pos = pos if pos is not None else QCursor.pos()
        if self.frameGeometry().contains(pos):
            if self._content_hidden:
                self._restore_content()
        else:
            if (not self._content_hidden and not self.isMaximized()
                    and not (QApplication.mouseButtons() & Qt.LeftButton)
                    and self._opacity_popup is None
                    and QApplication.activeModalWidget() is None
                    and QApplication.activePopupWidget() is None):
                self._hide_content()

    def _hide_content(self) -> None:
        """隐藏内容区：整体淡出，窗口原位原尺寸，仅菜单栏可见。"""
        if self._content_hidden or self.isMaximized() or not self.isVisible():
            return
        self._content_hidden = True
        self._run_hide_anim(1.0)

    def _restore_content(self) -> None:
        """恢复内容区：淡入显示。"""
        if not self._content_hidden:
            return
        self._content_hidden = False
        if not self.content.isVisible():
            self.content.show()
            eff = self.content.graphicsEffect()
            if eff is not None:
                eff.setOpacity(0.0)
        self._run_hide_anim(0.0)

    # ---- 淡出/淡入动画 ----
    def _run_hide_anim(self, target: float) -> None:
        """从当前进度平滑过渡到 target（0=完全显示，1=完全隐藏）。"""
        if self._hide_anim is not None:
            self._hide_anim.stop()
            self._hide_anim.deleteLater()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._hide_progress)
        anim.setEndValue(target)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._on_hide_progress)
        anim.finished.connect(lambda: self._on_hide_anim_done(target))
        self._hide_anim = anim
        anim.start()

    def _on_hide_progress(self, value) -> None:  # noqa: N802
        self._hide_progress = float(value)
        eff = self.content.graphicsEffect()
        if eff is None:
            eff = QGraphicsOpacityEffect(self.content)
            self.content.setGraphicsEffect(eff)
        eff.setOpacity(1.0 - self._hide_progress)
        self.update()  # 背景随进度重绘

    def _on_hide_anim_done(self, target: float) -> None:  # noqa: N802
        if target >= 0.999:
            self.content.hide()
        else:
            self.content.setGraphicsEffect(None)

    # ------------------------------------------------------------ 视图切换
    def _start_session(self, mode: str) -> None:
        # 设置即时生效
        self.ctx.service.batch_size = self.ctx.config.batch_size
        self.ctx.service.requeue_gap = self.ctx.config.requeue_gap
        # 优先恢复上次未完成的一组，否则开启新一组
        session = self.ctx.service.resume_session(mode)
        if session is None:
            session = self.ctx.service.start_session(mode)
            if session.total == 0:
                return
        self.ctx.service.save_session(session)
        self.study_view.begin(session)
        self.stack.setCurrentWidget(self.study_view)

    def _go_home(self) -> None:
        self.home_view.refresh()
        self.stack.setCurrentWidget(self.home_view)

    def _begin_spell(self) -> None:
        """完成页点击"开始拼写"后进入拼写练习。"""
        self.spell_view.begin(self.study_view.session)
        self.stack.setCurrentWidget(self.spell_view)

    def _open_word_list(self) -> None:
        """首页词书卡列表按钮：在主窗口内切换到全部单词列表页。"""
        self.word_list_view.refresh()
        self.stack.setCurrentWidget(self.word_list_view)

    def _open_book_manage(self) -> None:
        """首页词书详情按钮：在主窗口内切换到词书管理页。"""
        self.book_manage_view.refresh()
        self.stack.setCurrentWidget(self.book_manage_view)

    def _open_import_book(self) -> None:
        """词书管理页 → 导入词书页。"""
        self.import_book_view.reset()
        self.stack.setCurrentWidget(self.import_book_view)

    def _back_to_book_manage(self) -> None:
        """导入词书页 → 返回词书管理页。"""
        self.book_manage_view.refresh()
        self.stack.setCurrentWidget(self.book_manage_view)

    def _on_import_done(self) -> None:
        """导入成功后刷新词书管理页并返回。"""
        self.book_manage_view.refresh()
        self.book_manage_view.book_switched.emit()
        self.stack.setCurrentWidget(self.book_manage_view)

    # ------------------------------------------------------------ 原生拖边缩放
    def nativeEvent(self, eventType, message):  # noqa: N802
        """拦截 WM_NCHITTEST，把窗口边缘 6px 变成系统缩放热区（资源管理器手感）。"""
        if sys.platform == "win32" and eventType in (b"windows_generic_MSG",
                                                     "windows_generic_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if (msg.message == WM_NCHITTEST and not self.isMaximized()
                    and not self._content_hidden):
                # lParam 为物理像素坐标（有符号 16 位高低字）
                phys_x = ctypes.c_short(msg.lParam & 0xFFFF).value
                phys_y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                dpr = self.devicePixelRatioF() or 1.0
                gp = QPoint(round(phys_x / dpr), round(phys_y / dpr))
                pos = self.mapFromGlobal(gp)
                m = self.RESIZE_MARGIN
                w, h = self.width(), self.height()
                on_left = pos.x() < m
                on_right = pos.x() >= w - m
                on_top = pos.y() < m
                on_bottom = pos.y() >= h - m
                hit = HTCLIENT
                if on_top and on_left:
                    hit = HTTOPLEFT
                elif on_top and on_right:
                    hit = HTTOPRIGHT
                elif on_bottom and on_left:
                    hit = HTBOTTOMLEFT
                elif on_bottom and on_right:
                    hit = HTBOTTOMRIGHT
                elif on_left:
                    hit = HTLEFT
                elif on_right:
                    hit = HTRIGHT
                elif on_top:
                    hit = HTTOP
                elif on_bottom:
                    hit = HTBOTTOM
                if hit != HTCLIENT:
                    return True, hit
        return False, 0

    # ------------------------------------------------------------ 绘制
    def _ghost_color(self, hex_color: str, alpha: int) -> QColor:
        c = QColor(hex_color)
        c.setAlpha(alpha)
        return c

    def _paint_background(self, p, k: float, region: QRectF | None = None) -> None:
        """绘制天空渐变背景（及沙滩高光）。k=强度系数，region=绘制区域。"""
        region = region if region is not None else QRectF(self.rect())
        ghost = self.ctx.config.ghost_mode
        if ghost:
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0.0, self._ghost_color(theme.SKY_TOP, round(10 * k)))
            grad.setColorAt(0.45, self._ghost_color(theme.SKY_MID, round(8 * k)))
            grad.setColorAt(0.60, self._ghost_color(theme.SEA_BAND, round(7 * k)))
            grad.setColorAt(0.72, self._ghost_color(theme.SAND_LIGHT, round(5 * k)))
            grad.setColorAt(1.0, self._ghost_color(theme.SAND, round(4 * k)))
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawRect(region)
        else:
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0.0, self._ghost_color(theme.SKY_TOP, round(255 * k)))
            grad.setColorAt(0.45, self._ghost_color(theme.SKY_MID, round(255 * k)))
            grad.setColorAt(0.60, self._ghost_color(theme.SEA_BAND, round(255 * k)))
            grad.setColorAt(0.72, self._ghost_color(theme.SAND_LIGHT, round(255 * k)))
            grad.setColorAt(1.0, self._ghost_color(theme.SAND, round(255 * k)))
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawRect(region)
            # 沙滩高光带
            p.setBrush(QColor(255, 250, 238, round(60 * k)))
            p.drawRect(QRectF(region.x(), self.height() * 0.78,
                              region.width(), self.height() * 0.10))

    def _paint_border(self, p, k: float) -> None:
        """绘制窗口圆角描边。k=强度系数。"""
        border = (theme.GHOST_BORDER if self.ctx.config.ghost_mode
                  else QColor(255, 255, 255, 70))
        c = QColor(border)
        c.setAlpha(round(border.alpha() * k))
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.NoBrush)
        pen = QPen(c)
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                          theme.RADIUS, theme.RADIUS)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        win_path = QPainterPath()
        win_path.addRoundedRect(QRectF(self.rect()), theme.RADIUS, theme.RADIUS)
        p.setClipPath(win_path)

        prog = self._hide_progress          # 0=完整窗口, 1=仅菜单栏
        bg_k = 1.0 - prog                    # 背景淡出系数

        # ---- 背景（随 prog 平滑淡出，prog=1 时全透明） ----
        self._paint_background(p, bg_k)

        # ---- 菜单栏区域保持原样式（不改变背景与描边） ----
        if prog > 0.004:
            bar = QRectF(0, 0, self.width(), self.title_bar.height())
            bar_path = QPainterPath()
            bar_path.addRect(bar)
            p.save()
            p.setClipPath(win_path.intersected(bar_path))
            self._paint_background(p, 1.0)
            self._paint_border(p, 1.0)
            p.restore()

        # ---- 轮廓描边（随背景一起淡出） ----
        self._paint_border(p, bg_k)

    # ------------------------------------------------------------ 关闭
    def closeEvent(self, ev) -> None:  # noqa: N802
        if self._opacity_popup is not None:
            self._opacity_popup.close()
        self.ctx.configs.save()
        self.closed.emit()
        super().closeEvent(ev)
