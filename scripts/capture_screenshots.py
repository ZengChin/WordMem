# -*- coding: utf-8 -*-
"""README 界面截图：离屏渲染主窗口各状态，输出 PNG 到 docs/images/。

用法（在仓库根目录）：
    .venv\\Scripts\\python scripts\\capture_screenshots.py

说明：
- 数据目录重定向到临时副本（复制现有 wordmem.db / config.json），
  截图过程产生的会话快照不会污染真实学习数据；
- QT_SCALE_FACTOR=2，输出 2x 高清图；
- 窗口以 WA_DontShowOnScreen 显示，不会在屏幕上闪现。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("QT_SCALE_FACTOR", "2")   # 须在 QApplication 创建前设置
OUT_DIR = ROOT / "docs" / "images"

# ---- 数据目录重定向（须先于业务模块导入，settings 内部是 from-import）----
import wordmem.config.paths as paths  # noqa: E402

_tmp = tempfile.TemporaryDirectory(prefix="wordmem_shot_")
_tmp_dir = Path(_tmp.name)
_real_data = paths.app_data_dir()
for _name in ("wordmem.db", "config.json"):
    _src = _real_data / _name
    if _src.exists():
        shutil.copy2(_src, _tmp_dir / _name)

paths.app_data_dir = lambda: _tmp_dir
paths.config_file = lambda: _tmp_dir / "config.json"
paths.database_file = lambda: _tmp_dir / "wordmem.db"
paths.log_dir = lambda: _tmp_dir / "logs"
(_tmp_dir / "logs").mkdir(exist_ok=True)

from wordmem.config import settings as _settings_mod  # noqa: E402

_settings_mod.config_file = paths.config_file   # 覆盖已绑定的 from-import

from PySide6.QtCore import QPoint, QRect, QThread, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

from wordmem.app import build_context  # noqa: E402
from wordmem.ui.main_window import MainWindow  # noqa: E402


def _pump(app: QApplication, rounds: int = 6) -> None:
    """跑若干轮事件循环，让布局与绘制完成。"""
    for _ in range(rounds):
        app.processEvents()


def _grab(window: MainWindow, name: str) -> None:
    _pump(QApplication.instance())
    out = OUT_DIR / name
    window.grab().save(str(out), "PNG")
    print(f"saved {out.relative_to(ROOT)}")


# ---- 桌面背景合成：透明模式内容近乎隐形，需衬在"桌面"上才能看清 ----
def _fake_doc(p: QPainter, rect: QRect) -> None:
    """画一个经典 Windows 蓝色窗口：蓝色标题条 + 白色内容区 + 灰色横线。"""
    p.setPen(Qt.NoPen)
    # 外框（经典窗口蓝）
    p.setBrush(QColor("#1a5fc4"))
    p.drawRoundedRect(rect, 8, 8)
    # 标题条（亮蓝渐变，XP 风格）
    grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + 28)
    grad.setColorAt(0.0, QColor("#3d8bfd"))
    grad.setColorAt(1.0, QColor("#1a5fc4"))
    p.setBrush(grad)
    p.drawRoundedRect(rect.adjusted(2, 2, -2, -rect.height() + 28), 6, 6)
    # 标题条右侧三个控制钮（最小化 / 最大化 / 关闭，关闭在最右）
    btn_y = rect.top() + 8
    for i, color in enumerate(("#a8c8f0", "#a8c8f0", "#e81123")):
        p.setBrush(QColor(color))
        p.drawRoundedRect(rect.right() - 56 + i * 16, btn_y, 11, 11, 2, 2)
    # 白色内容区
    body = QRect(rect.left() + 3, rect.top() + 28, rect.width() - 6,
                 rect.height() - 31)
    p.setBrush(QColor(255, 255, 255, 245))
    p.drawRect(body)
    # 灰色横线模拟文字
    line_y = body.top() + 18
    for w_ratio in (0.72, 0.9, 0.8, 0.6, 0.85):
        p.setBrush(QColor(120, 130, 140, 70))
        p.drawRoundedRect(body.left() + 16, line_y,
                          int(body.width() * w_ratio), 9, 4, 4)
        line_y += 24


def _make_desktop(w: int, h: int) -> QImage:
    """合成 Windows 经典蓝色桌面背景（2x），尺寸为逻辑像素。"""
    img = QImage(w * 2, h * 2, QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(2.0)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0.0, QColor("#4e83c2"))
    grad.setColorAt(1.0, QColor("#2b5386"))
    p.fillRect(0, 0, w, h, grad)
    _fake_doc(p, QRect(16, 24, int(w * 0.55), int(h * 0.55)))
    _fake_doc(p, QRect(int(w * 0.42), int(h * 0.5), int(w * 0.52), int(h * 0.44)))
    p.end()
    return img


def _over_desktop(window: MainWindow, desktop: QImage, pos: QPoint) -> QImage:
    """把窗口抓帧叠加到桌面背景上，返回一帧合成图。"""
    frame = QImage(desktop)
    p = QPainter(frame)
    p.drawPixmap(pos, window.grab())
    p.end()
    return frame


def _grab_over_desktop(window: MainWindow, desktop: QImage, pos: QPoint,
                       name: str) -> None:
    _pump(QApplication.instance())
    out = OUT_DIR / name
    _over_desktop(window, desktop, pos).save(str(out), "PNG")
    print(f"saved {out.relative_to(ROOT)}")


def _record_gif(window: MainWindow, desktop: QImage, pos: QPoint,
                name: str) -> None:
    """录制自动隐藏动图：鼠标移出 -> 内容淡出仅留菜单栏 -> 移入 -> 淡入。"""
    from PIL import Image

    frame_geom = window.frameGeometry()
    inside = frame_geom.center()
    outside = frame_geom.bottomRight() + QPoint(600, 600)
    frames: list[QImage] = []

    def run(ms: int) -> None:
        """驱动事件循环并每 40ms 抓一帧。"""
        elapsed = 0
        while elapsed < ms:
            QApplication.instance().processEvents()
            frames.append(_over_desktop(window, desktop, pos))
            QThread.msleep(40)
            elapsed += 40

    run(400)                          # 鼠标在窗口内：内容完整显示
    window._check_auto_hide(outside)  # 移出：淡出动画 ~220ms
    run(320)
    run(500)                          # 仅菜单栏，停留
    window._check_auto_hide(inside)   # 移入：淡入恢复
    run(320)
    run(400)                          # 完整显示，停留（首尾呼应便于循环）

    # 转 Pillow：缩到物理宽 640，再量化到 256 色调色板
    imgs = []
    for f in frames:
        f = f.convertToFormat(QImage.Format_RGBA8888)
        pil = Image.frombytes("RGBA", (f.width(), f.height()),
                              bytes(f.constBits()))
        ratio = 640 / pil.width
        pil = pil.resize((640, round(pil.height * ratio)), Image.LANCZOS)
        imgs.append(pil.convert("P", palette=Image.ADAPTIVE, colors=256))
    out = OUT_DIR / name
    imgs[0].save(out, save_all=True, append_images=imgs[1:],
                 duration=40, loop=0, optimize=True)
    print(f"saved {out.relative_to(ROOT)} ({len(imgs)} frames)")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)

    ctx = build_context()
    # 截图用干净稳定的配置：不发音、不自动折叠、非透明模式、满不透明度
    ctx.config.auto_pronounce = False
    ctx.config.auto_hide = False
    ctx.config.ghost_mode = False
    ctx.config.ui_opacity = 1.0

    window = MainWindow(ctx)
    window.setAttribute(Qt.WA_DontShowOnScreen, True)
    window.show()
    _pump(app)

    # 1. 首页
    window.stack.setCurrentWidget(window.home_view)
    window.home_view.refresh()
    _grab(window, "home.png")

    # 2. 背单词·出题态
    window._start_session("new")
    if window.stack.currentWidget() is window.study_view and window.study_view.session:
        _grab(window, "study_question.png")

        # 3. 作答态（展开释义 + 例句卡片）：仅切 UI，不评分不落库
        window.study_view._on_right()
        _grab(window, "study_answer.png")

        # 4. 拼写练习
        window._begin_spell()
        _grab(window, "spell.png")
    else:
        print("no new words available, skip study/spell shots")

    # 5. 全部单词列表
    window._open_word_list()
    _grab(window, "word_list.png")

    # 6. 设置弹窗（首页左上齿轮）：Popup 独立窗口，合成到首页之上
    from wordmem.ui.views.dialogs import SettingsDialog

    window.stack.setCurrentWidget(window.home_view)
    window.home_view.refresh()
    dlg = SettingsDialog(ctx, window)
    dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
    dlg.show()
    _pump(app)

    pix = window.grab()
    painter = QPainter(pix)
    painter.drawPixmap((window.width() - dlg.width()) // 2,
                       (window.height() - dlg.height()) // 2,
                       dlg.grab())
    painter.end()
    out = OUT_DIR / "settings.png"
    pix.save(str(out), "PNG")
    print(f"saved {out.relative_to(ROOT)}")
    dlg.close()

    # ---- 透明（隐形）模式：需衬桌面背景合成 ----
    window.stack.setCurrentWidget(window.home_view)
    window.home_view.refresh()
    window.title_bar.btn_ghost.setChecked(True)   # 触发 _on_ghost
    _pump(app)

    desktop = _make_desktop(window.width() + 160, window.height() + 140)
    win_pos = QPoint(80, 70)

    # 7. 隐形模式·首页
    _grab_over_desktop(window, desktop, win_pos, "home_ghost.png")

    # 8. 隐形模式·背单词页（恢复此前的会话快照，回到出题态）
    window._start_session("new")
    if window.stack.currentWidget() is window.study_view and window.study_view.session:
        _grab_over_desktop(window, desktop, win_pos, "study_ghost.png")
    else:
        print("no session available, skip ghost study shot")

    # 9. 隐形模式·自动隐藏动图（鼠标移出/移入）
    window._go_home()
    window.title_bar.btn_fold.setChecked(True)    # 触发 _on_fold：auto_hide=True
    window._auto_hide_timer.stop()                # 停掉真实鼠标轮询，改为手动驱动
    _pump(app)
    _record_gif(window, desktop, win_pos, "ghost_autohide.gif")

    window.close()
    ctx.repo.close()      # 释放临时目录中的 wordmem.db，便于清理
    app.quit()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
