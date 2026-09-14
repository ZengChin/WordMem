# -*- coding: utf-8 -*-
"""数据访问层：SQLite 持久化与词库种子初始化。"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from wordmem.config.paths import seed_words_file
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
    description TEXT NOT NULL DEFAULT ''
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
        """为旧版本数据库补齐 SM-2 新列，并按遗留 level 回填，避免进度丢失。"""
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
        self._conn.commit()

    # ------------------------------------------------------------------ 种子
    def ensure_seeded(self) -> None:
        """导入包内词库；词库为空或默认词库已更换时（重新）播种。"""
        data = json.loads(seed_words_file().read_text(encoding="utf-8-sig"))
        book = data["book"]
        existing = self.get_book()
        if self.count_words() > 0 and existing and existing.name == book["name"]:
            return                              # 已是当前默认词库
        # 词库为空，或打包的默认词库已更换（如切换到“雅思词汇”）：清空后重播
        self._clear_library()
        book_id = self.add_book(book["name"], book.get("description", ""))
        self.add_words(book_id, data["words"])

    def _clear_library(self) -> None:
        """清空词书 / 单词 / 学习状态（切换默认词库时使用）。"""
        self._conn.execute("DELETE FROM study_state")
        self._conn.execute("DELETE FROM words")
        self._conn.execute("DELETE FROM books")
        self._conn.commit()

    def add_book(self, name: str, description: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO books(name, description) VALUES(?, ?)", (name, description)
        )
        self._conn.commit()
        return int(cur.lastrowid)

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

    # ------------------------------------------------------------------ 查询
    def get_book(self) -> Optional[Book]:
        row = self._conn.execute(
            "SELECT id, name, description FROM books ORDER BY id LIMIT 1"
        ).fetchone()
        return Book(**dict(row)) if row else None

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
        return int(self._conn.execute("SELECT COUNT(*) FROM words").fetchone()[0])

    def count_learned(self) -> int:
        """已学习 = 存在学习状态的词。"""
        return int(
            self._conn.execute("SELECT COUNT(*) FROM study_state").fetchone()[0]
        )

    def count_status(self, status: str) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state WHERE status=?", (status,)
            ).fetchone()[0]
        )

    def count_due(self, today: date) -> int:
        """今日待复习数（到期即计，含需周期性唤醒的已掌握词）。"""
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state "
                "WHERE due_date IS NOT NULL AND due_date<=?",
                (_date_str(today),),
            ).fetchone()[0]
        )

    def count_reviewed_today(self, today: date) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM study_state WHERE last_review=?",
                (_date_str(today),),
            ).fetchone()[0]
        )

    def get_new_words(self, limit: int) -> list[Word]:
        """未学习的新词（按词库顺序）。"""
        rows = self._conn.execute(
            "SELECT w.* FROM words w LEFT JOIN study_state s ON s.word_id=w.id "
            "WHERE s.word_id IS NULL ORDER BY w.id LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._to_word(r) for r in rows]

    def get_due_words(self, today: date, limit: int) -> list[Word]:
        """今日到期需要复习的词（含需周期性唤醒的已掌握词）。"""
        rows = self._conn.execute(
            "SELECT w.* FROM words w JOIN study_state s ON s.word_id=w.id "
            "WHERE s.due_date IS NOT NULL AND s.due_date<=? "
            "ORDER BY s.due_date, w.id LIMIT ?",
            (_date_str(today), limit),
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
        self._conn.execute("DELETE FROM study_state")
        self._conn.execute(
            "DELETE FROM meta WHERE key IN "
            "('session_new','session_review','completed_batches')")
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
        return {
            "total": self.count_words(),
            "learned": self.count_learned(),
            "learning": self.count_status(STATUS_LEARNING),
            "mastered": self.count_status(STATUS_MASTERED),
            "due": self.count_due(today),
            "reviewed_today": self.count_reviewed_today(today),
        }
