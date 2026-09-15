# -*- coding: utf-8 -*-
"""数据访问层：SQLite 持久化与多词书管理。"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from wordmem.core.models import (
    STATUS_LEARNING,
    STATUS_MASTERED,
    Book,
    Example,
    Meaning,
    Word,
    WordState,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT 'builtin',
    file_path   TEXT,
    word_count  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS words (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id  INTEGER NOT NULL REFERENCES books(id),
    word     TEXT NOT NULL,
    phonetic TEXT NOT NULL DEFAULT '',
    meanings TEXT NOT NULL DEFAULT '[]',
    examples TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_words_book ON words(book_id);
CREATE TABLE IF NOT EXISTS study_state (
    word_id     INTEGER PRIMARY KEY REFERENCES words(id),
    status      TEXT NOT NULL DEFAULT 'learning',
    level       INTEGER NOT NULL DEFAULT 0,
    ease        REAL NOT NULL DEFAULT 2.5,
    interval    INTEGER NOT NULL DEFAULT 0,
    reps        INTEGER NOT NULL DEFAULT 0,
    lapses      INTEGER NOT NULL DEFAULT 0,
    due_date    TEXT,
    last_review TEXT,
    reviews     INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _date_str(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


class Repository:
    """SQLite 数据仓库（单连接，供服务层调用）。"""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ 迁移
    def _migrate(self) -> None:
        """为旧版本数据库补齐新列，避免进度丢失。

        - study_state：补齐 SM-2 列（ease/interval/reps/lapses），按旧 level 回填
        - books：补齐 source/file_path/word_count 列（多词书支持）
        """
        cols = {r["name"] for r in
                self._conn.execute("PRAGMA table_info(study_state)").fetchall()}
        additions = (
            ("ease", "REAL NOT NULL DEFAULT 2.5"),
            ("interval", "INTEGER NOT NULL DEFAULT 0"),
            ("reps", "INTEGER NOT NULL DEFAULT 0"),
            ("lapses", "INTEGER NOT NULL DEFAULT 0"),
        )
        missing = [(n, d) for n, d in additions if n not in cols]
        for name, decl in missing:
            self._conn.execute(
                f"ALTER TABLE study_state ADD COLUMN {name} {decl}")
        if missing:
            # 旧 Leitner 档位 -> SM-2 间隔的近似映射，保留既有复习节奏
            self._conn.execute(
                "UPDATE study_state SET reps = level, ease = 2.5, "
                "interval = CASE level "
                "WHEN 0 THEN 0 WHEN 1 THEN 1 WHEN 2 THEN 2 "
                "WHEN 3 THEN 4 WHEN 4 THEN 7 WHEN 5 THEN 15 ELSE 15 END")

        # books 表列迁移：补齐 source / file_path / word_count
        book_cols = {r["name"] for r in
                     self._conn.execute("PRAGMA table_info(books)").fetchall()}
        book_additions = (
            ("source", "TEXT NOT NULL DEFAULT 'builtin'"),
            ("file_path", "TEXT"),
            ("word_count", "INTEGER NOT NULL DEFAULT 0"),
        )
        book_missing = [(n, d) for n, d in book_additions if n not in book_cols]
        for name, decl in book_missing:
            self._conn.execute(f"ALTER TABLE books ADD COLUMN {name} {decl}")
        self._conn.commit()

    # ------------------------------------------------------------------ 种子
    def ensure_seeded(self) -> None:
        """委托 BookManager 处理（空实现，保留接口兼容旧调用方）。"""
        return

    def _clear_library(self) -> None:
        """清空全部词书 / 单词 / 学习状态（紧急清理用）。"""
        self._conn.execute("DELETE FROM study_state")
        self._conn.execute("DELETE FROM words")
        self._conn.execute("DELETE FROM books")
        # 会话快照、已背组数（含按词书隔离的键）与活动词书 ID 一并清除
        self._conn.execute(
            "DELETE FROM meta WHERE key='active_book_id' "
            "OR key LIKE 'session_new%' OR key LIKE 'session_review%' "
            "OR key LIKE 'completed_batches%'")
        self._conn.commit()

    def add_book(self, name: str, description: str = "",
                 source: str = "builtin", file_path: Optional[str] = None,
                 word_count: int = 0) -> int:
        """新增词书并返回 book_id；首本词书自动设为活动词书。"""
        cur = self._conn.execute(
            "INSERT INTO books(name, description, source, file_path, word_count) "
            "VALUES(?, ?, ?, ?, ?)",
            (name, description, source, file_path, word_count),
        )
        book_id = int(cur.lastrowid)
        # 首本词书自动设为活动词书（便于旧代码 add_book 后直接查询）
        if self.get_meta("active_book_id") is None:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES('active_book_id', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(book_id),),
            )
        self._conn.commit()
        return book_id

    def add_words(self, book_id: int, items: Iterable[dict]) -> None:
        rows = [
            (
                book_id,
                it["word"].strip(),
                it.get("phonetic", ""),
                json.dumps(it.get("meanings", []), ensure_ascii=False),
                json.dumps(it.get("examples", []), ensure_ascii=False),
            )
            for it in items
        ]
        self._conn.executemany(
            "INSERT INTO words(book_id, word, phonetic, meanings, examples) "
            "VALUES(?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    # ------------------------------------------------------------------ 词书查询
    def _row_to_book(self, row: sqlite3.Row) -> Book:
        """把数据库行转为 Book 对象（file_path NULL -> 空串）。"""
        return Book(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            source=row["source"] or "builtin",
            file_path=row["file_path"] or "",
            word_count=row["word_count"] or 0,
        )

    def list_books(self) -> list[Book]:
        """所有词书（按 id 排序）。"""
        rows = self._conn.execute(
            "SELECT id, name, description, source, file_path, word_count "
            "FROM books ORDER BY id"
        ).fetchall()
        return [self._row_to_book(r) for r in rows]

    def get_book_by_id(self, book_id: int) -> Optional[Book]:
        """按 id 查单个词书。"""
        row = self._conn.execute(
            "SELECT id, name, description, source, file_path, word_count "
            "FROM books WHERE id=?", (book_id,)
        ).fetchone()
        return self._row_to_book(row) if row else None

    def get_active_book_id(self) -> Optional[int]:
        """读 meta.active_book_id，无则 None。"""
        raw = self.get_meta("active_book_id")
        return int(raw) if raw else None

    def set_active_book_id(self, book_id: int) -> None:
        """更新活动词书 ID。"""
        self.set_meta("active_book_id", str(book_id))

    def get_active_book(self) -> Optional[Book]:
        """活动词书对象。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return None
        return self.get_book_by_id(book_id)

    def get_book(self) -> Optional[Book]:
        """向后兼容：返回活动词书（旧代码调用）。"""
        return self.get_active_book()

    def count_words_in_book(self, book_id: int) -> int:
        """指定词书的总词数。"""
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM words WHERE book_id=?", (book_id,)
        ).fetchone()[0])

    def clear_words_for_book(self, book_id: int) -> None:
        """删除指定词书的 words 和 study_state（切词书前清理用）。"""
        self._conn.execute(
            "DELETE FROM study_state WHERE word_id IN "
            "(SELECT id FROM words WHERE book_id=?)", (book_id,))
        self._conn.execute("DELETE FROM words WHERE book_id=?", (book_id,))
        self._conn.commit()

    def delete_book(self, book_id: int) -> None:
        """删除词书记录（调用方需先清理 words 并校验来源）。"""
        self._conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        self._conn.commit()

    # ------------------------------------------------------------------ 单词查询
    def _to_word(self, row: sqlite3.Row) -> Word:
        meanings = [
            Meaning(pos=m.get("pos", ""), meaning=m.get("meaning", ""))
            for m in json.loads(row["meanings"])
        ]
        # 兼容 trans / translation 两种字段名
        examples = [
            Example(text=e.get("text", ""),
                    translation=e.get("translation", e.get("trans", "")))
            for e in json.loads(row["examples"])
        ]
        return Word(
            id=row["id"],
            book_id=row["book_id"],
            text=row["word"],
            phonetic=row["phonetic"],
            meanings=meanings,
            examples=examples,
        )

    def get_word(self, word_id: int) -> Optional[Word]:
        row = self._conn.execute(
            "SELECT * FROM words WHERE id=?", (word_id,)
        ).fetchone()
        return self._to_word(row) if row else None

    def count_words(self) -> int:
        """活动词书的总词数。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return 0
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM words WHERE book_id=?", (book_id,)
        ).fetchone()[0])

    def count_learned(self) -> int:
        """已学习 = 活动词书中存在学习状态的词。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return 0
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
                "WHERE w.book_id=?", (book_id,)
            ).fetchone()[0]
        )

    def count_status(self, status: str) -> int:
        """活动词书中指定状态的词数。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return 0
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
                "WHERE w.book_id=? AND s.status=?", (book_id, status)
            ).fetchone()[0]
        )

    def count_due(self, today: date) -> int:
        """今日待复习数（到期即计，含需周期性唤醒的已掌握词）。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return 0
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
                "WHERE w.book_id=? AND s.due_date IS NOT NULL AND s.due_date<=?",
                (book_id, _date_str(today)),
            ).fetchone()[0]
        )

    def count_reviewed_today(self, today: date) -> int:
        """今日已复习数（活动词书）。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return 0
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
                "WHERE w.book_id=? AND s.last_review=?",
                (book_id, _date_str(today)),
            ).fetchone()[0]
        )

    def get_new_words(self, limit: int) -> list[Word]:
        """未学习的新词（随机乱序抽取，仅活动词书）。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return []
        rows = self._conn.execute(
            "SELECT w.* FROM words w LEFT JOIN study_state s ON s.word_id=w.id "
            "WHERE w.book_id=? AND s.word_id IS NULL ORDER BY RANDOM() LIMIT ?",
            (book_id, limit),
        ).fetchall()
        return [self._to_word(r) for r in rows]

    def get_due_words(self, today: date, limit: int) -> list[Word]:
        """今日到期需要复习的词（到期日优先、同日随机乱序；仅活动词书）。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return []
        rows = self._conn.execute(
            "SELECT w.* FROM words w JOIN study_state s ON s.word_id=w.id "
            "WHERE w.book_id=? AND s.due_date IS NOT NULL AND s.due_date<=? "
            "ORDER BY s.due_date, RANDOM() LIMIT ?",
            (book_id, _date_str(today), limit),
        ).fetchall()
        return [self._to_word(r) for r in rows]

    def get_all_words(self) -> list[Word]:
        """获取活动词书全部单词（按词库顺序）。"""
        book_id = self.get_active_book_id()
        if book_id is None:
            return []
        rows = self._conn.execute(
            "SELECT * FROM words WHERE book_id=? ORDER BY id", (book_id,)
        ).fetchall()
        return [self._to_word(r) for r in rows]

    # ------------------------------------------------------------------ 状态
    def get_state(self, word_id: int) -> Optional[WordState]:
        row = self._conn.execute(
            "SELECT * FROM study_state WHERE word_id=?", (word_id,)
        ).fetchone()
        if not row:
            return None
        return WordState(
            word_id=row["word_id"],
            status=row["status"],
            ease=row["ease"],
            interval=row["interval"],
            reps=row["reps"],
            lapses=row["lapses"],
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            last_review=(
                date.fromisoformat(row["last_review"]) if row["last_review"] else None
            ),
            reviews=row["reviews"],
            correct=row["correct"],
        )

    def save_state(self, state: WordState, passed: bool, today: date) -> None:
        """插入或更新学习状态。"""
        self._conn.execute(
            "INSERT INTO study_state(word_id, status, ease, interval, reps, lapses,"
            " due_date, last_review, reviews, correct) VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(word_id) DO UPDATE SET status=excluded.status,"
            " ease=excluded.ease, interval=excluded.interval,"
            " reps=excluded.reps, lapses=excluded.lapses,"
            " due_date=excluded.due_date, last_review=excluded.last_review,"
            " reviews=excluded.reviews, correct=excluded.correct",
            (
                state.word_id,
                state.status,
                state.ease,
                state.interval,
                state.reps,
                state.lapses,
                _date_str(state.due_date),
                _date_str(today),
                state.reviews,
                state.correct,
            ),
        )
        self._conn.commit()

    def reset_progress(self) -> None:
        """重置活动词书的学习进度（只清活动词书的 study_state + 会话快照）。"""
        book_id = self.get_active_book_id()
        if book_id is not None:
            self._conn.execute(
                "DELETE FROM study_state WHERE word_id IN "
                "(SELECT id FROM words WHERE book_id=?)", (book_id,))
            # 会话快照与已背组数按词书隔离，只清当前词书的键（含旧版全局键）
            self._conn.execute(
                "DELETE FROM meta WHERE key IN (?,?,?,"
                "'session_new','session_review','completed_batches')",
                (f"session_new:{book_id}", f"session_review:{book_id}",
                 f"completed_batches:{book_id}"))
        else:
            self._conn.execute("DELETE FROM study_state")
            self._conn.execute(
                "DELETE FROM meta WHERE key LIKE 'session_new%' "
                "OR key LIKE 'session_review%' OR key LIKE 'completed_batches%'")
        self._conn.commit()

    # ------------------------------------------------------------------ 元数据
    def get_meta(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ 统计
    def stats_summary(self, today: date) -> dict:
        """活动词书的统计摘要。"""
        return {
            "total": self.count_words(),
            "learned": self.count_learned(),
            "learning": self.count_status(STATUS_LEARNING),
            "mastered": self.count_status(STATUS_MASTERED),
            "due": self.count_due(today),
            "reviewed_today": self.count_reviewed_today(today),
        }
