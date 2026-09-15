# -*- coding: utf-8 -*-
"""核心业务单元测试：数据仓库、SM-2 记忆调度与学习会话。"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordmem.core.models import (  # noqa: E402
    EF_INIT,
    FIRST_INTERVAL,
    GRADE_AGAIN,
    GRADE_GOOD,
    GRADE_HARD,
    MATURITY_DAYS,
    SECOND_INTERVAL,
    STATUS_LEARNING,
    STATUS_MASTERED,
    THIRD_INTERVAL,
    next_schedule,
)
from wordmem.core.book_manager import BookManager  # noqa: E402
from wordmem.core.repository import Repository  # noqa: E402
from wordmem.core.study_service import StudyService  # noqa: E402

WORDS = [
    {"word": f"w{i:02d}", "phonetic": f"[test{i}]",
     "meanings": [{"pos": "n.", "meaning": "测试"}],
     "examples": [{"text": f"this is w{i:02d}", "trans": "测试"}]}
    for i in range(30)
]


class RepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repository(":memory:")
        self.today = date.today()
        self.book_id = self.repo.add_book("测试词书", "单元测试")
        self.repo.add_words(self.book_id, WORDS)

    def test_seed_counts(self) -> None:
        self.assertEqual(self.repo.count_words(), 30)
        self.assertEqual(self.repo.count_learned(), 0)
        self.assertEqual(self.repo.count_due(self.today), 0)

    def test_new_words_excludes_learned(self) -> None:
        first = self.repo.get_new_words(20)
        self.assertEqual(len(first), 20)
        state = next_schedule(None, GRADE_GOOD, self.today)
        state.word_id = first[0].id
        self.repo.save_state(state, True, self.today)
        again = self.repo.get_new_words(20)
        self.assertFalse(any(w.id == first[0].id for w in again))

    def test_first_pass_sets_short_interval(self) -> None:
        word = self.repo.get_new_words(1)[0]
        state = next_schedule(None, GRADE_GOOD, self.today)
        state.word_id = word.id
        state.reviews += 1
        state.correct += 1
        self.repo.save_state(state, True, self.today)
        saved = self.repo.get_state(word.id)
        self.assertEqual(saved.reps, 1)
        self.assertEqual(saved.interval, FIRST_INTERVAL)
        self.assertEqual(saved.status, STATUS_LEARNING)
        self.assertEqual(saved.due_date, self.today + timedelta(days=FIRST_INTERVAL))
        # 质量分 5 使难度因子上浮 0.1
        self.assertAlmostEqual(saved.ease, EF_INIT + 0.1, places=6)

    def test_hard_pass_advances_but_lowers_ease(self) -> None:
        """看答案才想起（GRADE_HARD）：仍算答对，但难度因子下降 0.14。"""
        state = next_schedule(None, GRADE_HARD, self.today)
        self.assertEqual(state.reps, 1)
        self.assertEqual(state.interval, FIRST_INTERVAL)
        self.assertEqual(state.status, STATUS_LEARNING)
        self.assertAlmostEqual(state.ease, EF_INIT - 0.14, places=6)

    def test_sm2_interval_progression_to_mastery(self) -> None:
        """连续答对：间隔 0 -> 2 -> 6 -> round(6*ease) -> ... 直至成熟。"""
        state = None
        intervals = []
        for _ in range(5):
            state = next_schedule(state, GRADE_GOOD, self.today)
            intervals.append(state.interval)
        self.assertEqual(intervals[0], FIRST_INTERVAL)    # 0（当天即可复习）
        self.assertEqual(intervals[1], SECOND_INTERVAL)   # 2
        self.assertEqual(intervals[2], THIRD_INTERVAL)    # 6
        self.assertEqual(intervals[3], 17)                # round(6 * 2.8)
        self.assertEqual(intervals[4], 49)                # round(17 * 2.9)
        self.assertGreaterEqual(state.interval, MATURITY_DAYS)
        self.assertEqual(state.status, STATUS_MASTERED)

    def test_lapse_resets_reps_and_interval(self) -> None:
        word = self.repo.get_new_words(1)[0]
        state = next_schedule(None, GRADE_GOOD, self.today)
        state = next_schedule(state, GRADE_GOOD, self.today)
        state.word_id = word.id
        self.repo.save_state(state, True, self.today)
        lapsed = next_schedule(self.repo.get_state(word.id), GRADE_AGAIN, self.today)
        lapsed.word_id = word.id
        self.repo.save_state(lapsed, False, self.today)
        saved = self.repo.get_state(word.id)
        self.assertEqual(saved.reps, 0)
        self.assertEqual(saved.interval, FIRST_INTERVAL)
        self.assertEqual(saved.lapses, 1)
        self.assertEqual(saved.status, STATUS_LEARNING)

    def test_due_words_appear_after_interval(self) -> None:
        word = self.repo.get_new_words(1)[0]
        state = next_schedule(None, GRADE_GOOD, self.today)
        state.word_id = word.id
        self.repo.save_state(state, True, self.today)
        # 首次答对后按 FIRST_INTERVAL 进入待复习（当前为 0，当天即到期）
        self.assertEqual(
            self.repo.count_due(self.today + timedelta(days=FIRST_INTERVAL - 1)), 0)
        self.assertEqual(
            self.repo.count_due(self.today + timedelta(days=FIRST_INTERVAL)), 1)

    def test_mastered_word_reactivates_when_due(self) -> None:
        """已掌握词到期后仍进入复习队列（周期性唤醒）。"""
        word = self.repo.get_new_words(1)[0]
        state = None
        for _ in range(5):
            state = next_schedule(state, GRADE_GOOD, self.today)
        state.word_id = word.id
        self.repo.save_state(state, True, self.today)
        self.assertEqual(state.status, STATUS_MASTERED)
        self.assertEqual(self.repo.count_due(self.today), 0)
        self.assertEqual(self.repo.count_due(state.due_date), 1)
        self.assertEqual(len(self.repo.get_due_words(state.due_date, 20)), 1)


class _LowerBoundRng:
    """确定性随机源：randint 恒返回下界，令重现间隔固定为基数，便于断言。"""

    def randint(self, a: int, b: int) -> int:  # noqa: ARG002
        return a


class SessionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repository(":memory:")
        self.today = date.today()
        self.book_id = self.repo.add_book("测试词书", "")
        self.repo.add_words(self.book_id, WORDS)
        # 注入确定性随机源：间隔恒为基数 2，位置断言稳定
        self.service = StudyService(self.repo, batch_size=20, requeue_gap=2,
                                    rng=_LowerBoundRng())

    def test_new_session_batch(self) -> None:
        session = self.service.start_session("new", self.today)
        self.assertEqual(session.total, 20)
        self.assertEqual(session.position, 1)
        self.assertFalse(session.finished)

    def test_requeue_inserts_after_gap(self) -> None:
        session = self.service.start_session("new", self.today)
        wid = session.current().word.id
        result = self.service.grade(session, session.items[0], GRADE_AGAIN, self.today)
        self.assertTrue(result.requeued)
        session.index += 1
        # 显示总数保持本组唯一词数，不随重现增长；序列长度含重现副本
        self.assertEqual(session.total, 20)
        self.assertEqual(len(session.items), 21)
        # gap=2：原词在下标 0，重现副本被插到下标 3（隔 2 个词后）
        positions = [i for i, it in enumerate(session.items) if it.word.id == wid]
        self.assertEqual(positions, [0, 3])

    def test_requeue_repeats_until_correct(self) -> None:
        session = self.service.start_session("new", self.today)
        wid = session.current().word.id
        # 首次答错 -> 隔 2 词重现
        self.service.grade(session, session.items[0], GRADE_AGAIN, self.today)
        self.assertEqual(session.total, 20)
        self.assertEqual(len(session.items), 21)
        # 重现位（下标 3）再答错 -> 继续重现
        session.index = 3
        self.service.grade(session, session.items[3], GRADE_AGAIN, self.today)
        self.assertEqual(session.total, 20)
        self.assertEqual(len(session.items), 22)
        # 最新副本答对 -> 不再重现
        positions = [i for i, it in enumerate(session.items) if it.word.id == wid]
        last = positions[-1]
        session.index = last
        self.service.grade(session, session.items[last], GRADE_GOOD, self.today)
        self.assertEqual(session.total, 20)
        self.assertEqual(len(session.items), 22)
        # 唯一词统计只算首次作答（此词首次答错）
        self.assertEqual(session.failed, 1)
        self.assertEqual(session.passed, 0)
        # 长期状态由首次作答确定，其后仅累计作答计数
        saved = self.repo.get_state(wid)
        self.assertEqual(saved.lapses, 1)
        self.assertEqual(saved.reps, 0)
        self.assertEqual(saved.interval, FIRST_INTERVAL)
        self.assertEqual(saved.reviews, 3)
        self.assertEqual(saved.correct, 1)

    def test_requeued_attempt_does_not_change_ease(self) -> None:
        session = self.service.start_session("new", self.today)
        wid = session.current().word.id
        self.service.grade(session, session.items[0], GRADE_AGAIN, self.today)
        ease_after_first = self.repo.get_state(wid).ease
        # 组内重现副本再次答错，不应继续降低难度因子
        session.index = 3
        self.service.grade(session, session.items[3], GRADE_AGAIN, self.today)
        self.assertAlmostEqual(
            self.repo.get_state(wid).ease, ease_after_first, places=9)

    def test_requeue_gap_is_randomized(self) -> None:
        """默认基数 3：重现间隔随机落在 {3, 4}，而非写死 3。"""
        service = StudyService(self.repo, batch_size=20, requeue_gap=3)
        offsets = {service._requeue_offset() for _ in range(60)}
        self.assertEqual(offsets, {3, 4})

    def test_finish_session(self) -> None:
        session = self.service.start_session("new", self.today)
        while not session.finished:
            self.service.grade(session, session.current(), GRADE_GOOD, self.today)
            session.index += 1
        self.assertTrue(session.finished)
        self.assertEqual(session.passed, 20)
        self.assertEqual(self.repo.count_learned(), 20)

    def test_review_mode_empty(self) -> None:
        session = self.service.start_session("review", self.today)
        self.assertEqual(session.total, 0)

    def test_home_summary(self) -> None:
        summary = self.service.home_summary(self.today)
        self.assertEqual(summary["total"], 30)
        self.assertEqual(summary["new_left"], 30)
        self.assertEqual(summary["review_left"], 0)


class MigrationTestCase(unittest.TestCase):
    """旧版本数据库升级到 SM-2 schema 的非破坏性迁移。"""

    _OLD_SCHEMA = """
    CREATE TABLE books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        word TEXT NOT NULL,
        phonetic TEXT NOT NULL DEFAULT '',
        meanings TEXT NOT NULL DEFAULT '[]',
        examples TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE study_state (
        word_id INTEGER PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'learning',
        level INTEGER NOT NULL DEFAULT 0,
        due_date TEXT,
        last_review TEXT,
        reviews INTEGER NOT NULL DEFAULT 0,
        correct INTEGER NOT NULL DEFAULT 0
    );
    """

    def test_migrate_adds_columns_and_backfills(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.executescript(self._OLD_SCHEMA)
            conn.execute("INSERT INTO books(id,name,description) VALUES(1,'b','')")
            conn.execute("INSERT INTO words(id,book_id,word) VALUES(1,1,'apple')")
            conn.execute(
                "INSERT INTO study_state(word_id,status,level,due_date,reviews,correct)"
                " VALUES(1,'mastered',4,'2026-01-01',5,4)")
            conn.commit()
            conn.close()

            repo = Repository(path)          # 打开即触发 _migrate
            state = repo.get_state(1)
            self.assertIsNotNone(state)
            self.assertAlmostEqual(state.ease, EF_INIT, places=6)
            self.assertEqual(state.reps, 4)      # 回填自旧 level
            self.assertEqual(state.interval, 7)  # level 4 -> 7 天
            self.assertEqual(state.status, STATUS_MASTERED)
            repo.close()
        finally:
            os.unlink(path)


class SeedTestCase(unittest.TestCase):
    """内置词书注册、默认词书播种（幂等）与多词书切换。"""

    def test_seed_loads_ielts_library(self) -> None:
        """BookManager 注册内置词书并设置默认活动词书（雅思词汇）。"""
        repo = Repository(":memory:")
        bm = BookManager(repo)
        bm.register_builtin_books()
        bm.ensure_default_active()
        self.assertEqual(repo.get_book().name, "雅思词汇")
        self.assertEqual(repo.count_words(), 4127)
        bm.ensure_default_active()    # 已有活动词书 -> 幂等，不重复导入
        self.assertEqual(repo.count_words(), 4127)
        repo.close()

    def test_switch_book_filters_by_active(self) -> None:
        """切换活动词书后，查询只看新词书的词，旧词书数据保留但不可见。"""
        repo = Repository(":memory:")
        bm = BookManager(repo)
        bm.register_builtin_books()
        bm.ensure_default_active()
        default_id = repo.get_active_book_id()
        self.assertEqual(repo.count_words(), 4127)

        # 新增第二本词书并导入 1 个词
        second_id = repo.add_book("自定义", "测试", source="imported")
        repo.add_words(second_id, [
            {"word": "custom1", "phonetic": "", "meanings": [], "examples": []}])
        # 切换到第二本词书：查询只看新词书
        bm.switch_book(second_id)
        self.assertEqual(repo.count_words(), 1)
        self.assertEqual(repo.get_book().name, "自定义")

        # 切换回默认词书：原数据仍在
        bm.switch_book(default_id)
        self.assertEqual(repo.count_words(), 4127)
        repo.close()


if __name__ == "__main__":
    unittest.main()
