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

from PySide6.QtCore import Qt  # noqa: E402
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

    window.close()
    ctx.repo.close()      # 释放临时目录中的 wordmem.db，便于清理
    app.quit()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
