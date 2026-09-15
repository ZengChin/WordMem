# -*- coding: utf-8 -*-
"""业务服务层：学习会话编排与记忆曲线调度。"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date
from typing import Optional

from wordmem.core.models import (
    PASS_THRESHOLD,
    SessionItem,
    StudySession,
    WordState,
    next_schedule,
)
from wordmem.core.repository import Repository


@dataclass
class GradeResult:
    """一次判分的结果，供界面刷新。"""

    state: WordState
    requeued: bool


class StudyService:
    """封装「新词学习 / 到期复习」两条业务流。"""

    def __init__(self, repo: Repository, batch_size: int = 20,
                 requeue_gap: int = 3,
                 rng: Optional[random.Random] = None) -> None:
        self.repo = repo
        self.batch_size = max(1, batch_size)
        self.requeue_gap = max(0, requeue_gap)
        self._rng = rng if rng is not None else random.Random()

    # ------------------------------------------------------------ 会话管理
    def start_session(self, mode: str, today: Optional[date] = None) -> StudySession:
        """开启一组学习：mode 为 new（学新词）或 review（复习词）。"""
        today = today or date.today()
        session = StudySession(mode=mode)
        if mode == "new":
            words = self.repo.get_new_words(self.batch_size)
        elif mode == "review":
            words = self.repo.get_due_words(today, self.batch_size)
        else:
            raise ValueError(f"unknown session mode: {mode}")
        for w in words:
            session.items.append(SessionItem(word=w, state=self.repo.get_state(w.id)))
        return session

    # ------------------------------------------------------------ 会话持久化
    def _session_key(self, mode: str) -> str:
        """会话快照的 meta 键，按活动词书隔离。

        多词书共用一张 words 表、word_id 全局唯一，若快照不区分词书，
        切换词书后 resume 仍会命中旧词书的词（get_word 照样取得到），把进度
        写进旧词书，导致当前词书复习数恒为 0。故键名带上 active_book_id。
        """
        return f"session_{mode}:{self.repo.get_active_book_id()}"

    def _batches_key(self) -> str:
        """已背组数的 meta 键，同样按活动词书隔离（复习入口门槛）。"""
        return f"completed_batches:{self.repo.get_active_book_id()}"

    def save_session(self, session: StudySession) -> None:
        """快照当前会话：单词顺序（含重现副本）、进度与统计，供中途退出后恢复。"""
        data = {
            "mode": session.mode,
            "index": session.index,
            "passed": session.passed,
            "failed": session.failed,
            "done": session.done,
            "items": [
                {"id": it.word.id, "requeued": it.requeued}
                for it in session.items
            ],
        }
        self.repo.set_meta(self._session_key(session.mode),
                           json.dumps(data, ensure_ascii=False))

    def clear_session(self, mode: str) -> None:
        self.repo.set_meta(self._session_key(mode), "")

    def resume_session(self, mode: str) -> Optional[StudySession]:
        """恢复上次未完成的会话；无快照或已失效时返回 None。"""
        raw = self.repo.get_meta(self._session_key(mode))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            self.clear_session(mode)
            return None
        if data.get("mode") != mode:
            return None
        items: list[SessionItem] = []
        for it in data.get("items", []):
            word = self.repo.get_word(it["id"])
            if word is None:            # 词库已更换，旧会话失效
                self.clear_session(mode)
                return None
            items.append(SessionItem(
                word=word,
                state=self.repo.get_state(word.id),
                requeued=bool(it.get("requeued", False)),
            ))
        session = StudySession(mode=mode, items=items)
        session.index = min(int(data.get("index", 0)), len(items))
        session.passed = int(data.get("passed", 0))
        session.failed = int(data.get("failed", 0))
        session.done = int(data.get("done", 0))
        if session.finished:            # 已完成但未清除的异常残留
            self.clear_session(mode)
            return None
        return session

    def completed_batches(self) -> int:
        """当前活动词书已完整背完的学新词组数（复习入口门槛）。"""
        try:
            return int(self.repo.get_meta(self._batches_key()) or 0)
        except ValueError:
            return 0

    def complete_session(self, session: StudySession) -> None:
        """会话完成：清除快照；学新词整组背完记为一次已背组数。"""
        self.clear_session(session.mode)
        if session.mode == "new":
            self.repo.set_meta(self._batches_key(),
                               str(self.completed_batches() + 1))

    # ------------------------------------------------------------ 判分调度
    def grade(self, session: StudySession, item: SessionItem, quality: int,
              today: Optional[date] = None) -> GradeResult:
        """对当前词判分（quality 为 SM-2 质量分）。

        - 本会话首次作答：按 SM-2 更新长期记忆状态，并计入唯一词统计；
        - 组内重现副本：仅刷新作答计数，不再改动难度因子/间隔，
          避免同一天反复答错把 ease 打穿；
        - 答错：隔 requeue_gap~requeue_gap+1 个词后随机重新排入本组，
          直到答对为止（默认基数 3 → 随机 3~4 词后重现，避免机械感）。
        """
        today = today or date.today()
        passed = quality >= PASS_THRESHOLD
        if item.requeued:
            state = item.state or WordState(word_id=item.word.id)
        else:
            state = next_schedule(item.state, quality, today)
        state.word_id = item.word.id
        state.reviews += 1
        state.correct += 1 if passed else 0
        self.repo.save_state(state, passed, today)

        requeued = False
        if not passed:
            insert_at = min(session.index + 1 + self._requeue_offset(),
                            len(session.items))
            session.items.insert(
                insert_at,
                SessionItem(word=item.word, state=state, requeued=True),
            )
            requeued = True

        if not item.requeued:          # 仅首次作答计入唯一词统计
            if passed:
                session.passed += 1
            else:
                session.failed += 1
        if passed:
            session.done += 1          # 进度：仅「记住」才推进；答错会重现，不计入
        return GradeResult(state=state, requeued=requeued)

    def _requeue_offset(self) -> int:
        """答错后重现的间隔词数：在 [requeue_gap, requeue_gap+1] 内随机。

        默认 requeue_gap=3 → 随机 3~4 个词后重现；requeue_gap=0 时立即重现。
        随机源 self._rng 可注入，便于测试确定性。
        """
        base = self.requeue_gap
        if base <= 0:
            return 0
        return self._rng.randint(base, base + 1)

    # ------------------------------------------------------------ 统计
    def home_summary(self, today: Optional[date] = None) -> dict:
        """首页所需统计：总数 / 已学 / 剩余新词 / 待复习。"""
        today = today or date.today()
        total = self.repo.count_words()
        learned = self.repo.count_learned()
        return {
            "total": total,
            "learned": learned,
            "new_left": total - learned,
            "review_left": self.repo.count_due(today),
            "completed_batches": self.completed_batches(),
        }
