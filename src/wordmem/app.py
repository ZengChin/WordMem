# -*- coding: utf-8 -*-
"""应用组装与入口：日志、异常兜底、依赖装配、主窗口启动。"""
from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from wordmem import __app_name__, __version__
from wordmem.config.paths import log_dir
from wordmem.config.settings import ConfigManager
from wordmem.core.book_manager import BookManager
from wordmem.core.repository import Repository
from wordmem.core.study_service import StudyService
from wordmem.core.tts import speaker as tts_speaker
from wordmem.ui.main_window import AppContext, MainWindow

logger = logging.getLogger("wordmem")


def _setup_logging() -> None:
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        log_dir() / "app.log", maxBytes=1_000_000, backupCount=2,
        encoding="utf-8")
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


def _excepthook(exc_type, exc, tb) -> None:  # pragma: no cover
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    logger.error("未捕获异常:\n%s", text)
    try:
        QMessageBox.critical(None, f"{__app_name__} 错误",
                             f"发生未处理的错误，详情请查看日志。\n\n{exc}")
    except Exception:
        pass


def build_context() -> AppContext:
    """依赖装配：配置 -> 仓库 -> 词书管理 -> 服务 -> 发音。"""
    configs = ConfigManager()
    repo = Repository(db_path=_db_path())
    book_mgr = BookManager(repo)
    book_mgr.register_builtin_books()
    book_mgr.ensure_default_active()
    service = StudyService(repo, batch_size=configs.config.batch_size,
                           requeue_gap=configs.config.requeue_gap)
    return AppContext(repo, service, configs, tts_speaker,
                     book_manager=book_mgr)


def _db_path():
    from wordmem.config.paths import database_file

    return database_file()


def main() -> int:
    _setup_logging()
    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(True)

    ctx = build_context()
    window = MainWindow(ctx)
    window.show()
    logger.info("%s v%s 启动完成", __app_name__, __version__)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
