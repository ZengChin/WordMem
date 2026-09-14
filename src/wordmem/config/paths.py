# -*- coding: utf-8 -*-
"""运行时路径管理：数据目录跟随主程序所在位置，便于随应用整体迁移。"""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR_NAME = "WordMem"


def app_data_dir() -> Path:
    """返回应用数据目录（配置 / 数据库 / 日志均存放于此）。

    打包后放在 exe 同目录；开发运行放在项目根（run.py 所在）。数据随主程序走。
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent  # 打包后的 exe 所在目录
    else:
        # 开发模式：src/wordmem/config/paths.py 上溯 4 层即项目根
        base = Path(__file__).resolve().parent.parent.parent.parent
    path = base / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return app_data_dir() / "config.json"


def database_file() -> Path:
    return app_data_dir() / "wordmem.db"


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_data_dir() -> Path:
    """包内资源目录（随包分发，只读）。"""
    return Path(__file__).resolve().parent.parent / "resources" / "data"


def seed_words_file() -> Path:
    return resource_data_dir() / "ielts_words.json"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)
