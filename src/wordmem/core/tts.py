# -*- coding: utf-8 -*-
"""发音服务：基于 Windows SAPI（pyttsx3）的后台朗读，缺失时优雅降级。"""
from __future__ import annotations

import queue
import threading

try:  # pragma: no cover - 依赖环境
    import pyttsx3  # noqa: F401

    _AVAILABLE = True
except Exception:  # ImportError 或驱动缺失
    _AVAILABLE = False


class Speaker:
    """串行朗读队列，避免 pyttsx3 多线程冲突。"""

    def __init__(self) -> None:
        self._q: "queue.Queue[str]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self.available = _AVAILABLE

    def _loop(self) -> None:  # pragma: no cover - 需要真实 TTS 引擎
        import pyttsx3

        engine = pyttsx3.init()
        try:
            while True:
                text = self._q.get()
                if text is None:
                    break
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass
        finally:
            engine.stop()

    def speak(self, text: str) -> None:
        """异步朗读文本；不可用时静默忽略。"""
        if not self.available or not text:
            return
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        # 清空积压，只读最新一条
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._q.put(text)


speaker = Speaker()
