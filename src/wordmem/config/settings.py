# -*- coding: utf-8 -*-
"""应用配置：内存数据类 + JSON 持久化。"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field

from wordmem.config.paths import config_file

_FONT_SCALES = (0.85, 1.0, 1.18)


@dataclass
class AppConfig:
    """全局用户配置。"""

    batch_size: int = 20            # 每组学习词数
    requeue_gap: int = 3            # 答错重现间隔基数：实际在 [gap, gap+1] 内随机（默认 3 → 随机 3~4 词后重现）
    auto_pronounce: bool = True     # 出词时自动发音
    ui_opacity: float = 1.0         # 界面不透明度（0.25 ~ 1.0）
    ghost_mode: bool = False        # 透明模式（低不透明度 + 高亮轮廓）
    auto_hide: bool = False         # 鼠标移出窗口时隐藏内容区（仅保留菜单栏，窗口原位不动）
    font_level: int = 1             # 单词字号档位 0/1/2

    def scale(self) -> float:
        """当前字号缩放系数。"""
        return _FONT_SCALES[self.font_level] if 0 <= self.font_level < len(_FONT_SCALES) else 1.0

    def cycle_font(self) -> float:
        """循环切换字号档位，返回新缩放系数。"""
        self.font_level = (self.font_level + 1) % len(_FONT_SCALES)
        return self.scale()


class ConfigManager:
    """线程安全的配置加载 / 保存。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.config = self.load()

    def load(self) -> AppConfig:
        try:
            raw = json.loads(config_file().read_text(encoding="utf-8"))
            valid = {f: raw[f] for f in AppConfig.__dataclass_fields__ if f in raw}
            return AppConfig(**valid)
        except (OSError, ValueError, TypeError):
            return AppConfig()

    def save(self) -> None:
        with self._lock:
            try:
                config_file().write_text(
                    json.dumps(asdict(self.config), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass  # 配置写入失败不致命，保持静默
