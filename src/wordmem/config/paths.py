# -*- coding: utf-8 -*-
"""运行时路径管理：数据目录优先放在 %APPDATA%，便于打包安装后使用。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "WordMem"


def app_data_dir() -> Path:
    """返回应用数据目录（配置 / 数据库 / 日志均存放于此）。"""
    base = os.environ.get("APPDATA")
    if not base:  # 非 Windows 或无 APPDATA 时回退到用户目录
        base = str(Path.home() / ".wordmem")
    path = Path(base) / APP_DIR_NAME
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
