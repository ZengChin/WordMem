# -*- coding: utf-8 -*-
"""领域模型：词书、单词、学习状态与学习会话。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# 状态常量
STATUS_NEW = "new"              # 未学习（无状态记录）
STATUS_LEARNING = "learning"    # 学习中（进入复习循环）
STATUS_MASTERED = "mastered"    # 已掌握

# SM-2 记忆调度参数
EF_INIT = 2.5                   # 难度因子初值
EF_MIN = 1.3                    # 难度因子下限
FIRST_INTERVAL = 0              # 首次答对后的间隔（天）：当天即进入复习列表
SECOND_INTERVAL = 2             # 第二次答对后的间隔（天）：隔 2 天再复习
THIRD_INTERVAL = 6              # 第三次答对后的间隔（天）：接着隔 6 天
MATURITY_DAYS = 21              # 间隔达到该天数视为已掌握
PASS_THRESHOLD = 3              # 质量分 >= 该值视为答对

# 作答质量分（映射自 UI 的四种作答路径）
GRADE_AGAIN = 1                 # 忘记：不认识 / 记错了
GRADE_HARD = 3                  # 看答案才想起：不认识 -> 记住了
GRADE_GOOD = 5                  # 本来就会：已认识 -> 确认


@dataclass
class Book:
    id: int
    name: str
    description: str
    source: str = "builtin"      # builtin / imported
    file_path: str = ""          # imported 词书的源文件路径
    word_count: int = 0          # 词数（冗余字段，便于列表展示）


@dataclass
class Meaning:
    pos: str      # 词性，如 "n." "a." "v."
    meaning: str  # 中文释义

    def label(self) -> str:
        return f"{self.pos} {self.meaning}".strip()


@dataclass
class Example:
    text: str        # 英文例句/短语
    translation: str  # 中文翻译


@dataclass
class Word:
    id: int
    book_id: int
    text: str
    phonetic: str
    meanings: list[Meaning] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)


@dataclass
class WordState:
    word_id: int
    status: str = STATUS_NEW
    ease: float = EF_INIT       # SM-2 难度因子
    interval: int = 0           # 当前复习间隔（天）
    reps: int = 0               # 连续答对次数
    lapses: int = 0             # 遗忘（答错）次数
    due_date: Optional[date] = None
    last_review: Optional[date] = None
    reviews: int = 0            # 累计作答次数
    correct: int = 0            # 累计答对次数


@dataclass
class SessionItem:
    """学习会话中的一个条目（答错的词隔几个词后重现，直到答对为止）。"""
    word: Word
    state: Optional[WordState]
    requeued: bool = False      # 是否为组内重现的副本


@dataclass
class StudySession:
    """一次学习/复习会话。"""

    mode: str                       # "new" | "review"
    items: list[SessionItem] = field(default_factory=list)
    index: int = 0                  # 当前下标（沿含重现副本的完整序列推进）
    passed: int = 0                 # 首次作答即答对的唯一词数
    failed: int = 0                 # 首次作答答错（需组内巩固）的唯一词数
    done: int = 0                   # 已记住（答对）的唯一词数，用于进度展示

    @property
    def total(self) -> int:
        """本组唯一词数（答错重现副本不计入），即用户设置的一组单词数。"""
        return sum(1 for it in self.items if not it.requeued)

    @property
    def position(self) -> int:
        """人类可读进度（已记住词数 + 1），如 3 / 20。"""
        return min(self.done + 1, self.total)

    @property
    def finished(self) -> bool:
        return self.index >= len(self.items)

    def current(self) -> Optional[SessionItem]:
        if self.finished:
            return None
        return self.items[self.index]


def _ef_delta(quality: int) -> float:
    """SM-2 难度因子增量：作答质量越高，难度因子越大（后续复习越轻松）。"""
    return 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)


def next_schedule(state: Optional[WordState], quality: int,
                  today: date) -> WordState:
    """按 SM-2 算法根据作答质量计算新的学习状态（纯函数，便于测试）。"""
    if state is None:
        state = WordState(word_id=-1)
    if quality < PASS_THRESHOLD:            # 忘记：重置连续答对，缩短间隔
        state.lapses += 1
        state.reps = 0
        state.interval = FIRST_INTERVAL
    else:                                   # 记得：按难度因子拉长间隔
        state.reps += 1
        if state.reps == 1:
            state.interval = FIRST_INTERVAL
        elif state.reps == 2:
            state.interval = SECOND_INTERVAL
        elif state.reps == 3:
            state.interval = THIRD_INTERVAL
        else:
            state.interval = round(state.interval * state.ease)
    # 依据本次质量更新难度因子（下限 EF_MIN），须在计算间隔之后
    state.ease = max(EF_MIN, state.ease + _ef_delta(quality))
    state.status = (STATUS_MASTERED if state.interval >= MATURITY_DAYS
                    else STATUS_LEARNING)
    state.due_date = today + timedelta(days=state.interval)
    state.last_review = today
    return state
