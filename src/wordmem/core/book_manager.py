# -*- coding: utf-8 -*-
"""词书管理服务：内置词书注册、活动词书切换、外部词书导入与删除。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from wordmem.config.paths import (
    builtin_book_file,
    builtin_registry_file,
    user_books_dir,
)
from wordmem.core.importers import (
    parse_apkg,
    parse_auto,
    parse_csv,
    parse_plain_txt,
    parse_simple_json,
    parse_wordmem_json,
)
from wordmem.core.models import Book
from wordmem.core.repository import Repository


class BookManager:
    """词书管理服务：内置词书注册、活动词书切换、外部词书导入与删除。

    依赖 Repository 提供数据访问，自身只负责编排（解析文件 -> 写库 -> 切换活动词书）。
    """

    # 显式格式名 -> parser 映射（fmt 参数可选值）
    _FMT_MAP = {
        "wordmem": parse_wordmem_json,
        "simple": parse_simple_json,
        "jsonl": parse_simple_json,
        "txt": parse_plain_txt,
        "text": parse_plain_txt,
        "csv": parse_csv,
        "apkg": parse_apkg,
    }

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    # ---------------------------------------------------------- 内置词书注册
    def register_builtin_books(self) -> None:
        """扫描 book_registry.json，把尚未注册的内置词书写入 books 表（幂等）。

        幂等：按 name 去重，已注册的词书不会重复写入。
        """
        registry_path = builtin_registry_file()
        if not registry_path.exists():
            return
        registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        existing = {b.name for b in self.repo.list_books()
                    if b.source == "builtin"}
        for entry in registry.get("books", []):
            name = entry.get("name", "")
            if not name or name in existing:
                continue
            filename = entry.get("file", "")
            book_path = builtin_book_file(filename) if filename else Path()
            word_count = (self._count_words_in_json(book_path)
                         if book_path.exists() else 0)
            self.repo.add_book(
                name=name,
                description=entry.get("description", ""),
                source="builtin",
                file_path=str(book_path) if book_path else None,
                word_count=word_count,
            )

    def ensure_default_active(self) -> None:
        """首次启动时设置 active_book_id 为默认词书，并导入其 words。

        - 已有活动词书：确保其 words 已导入（延迟导入场景）
        - 无活动词书：从 registry 的 default_book 字段定位默认词书
        """
        active_id = self.repo.get_active_book_id()
        if active_id is not None and self.repo.get_book_by_id(active_id) is not None:
            # 已有活动词书：确保 words 已导入
            self._ensure_words_imported(active_id)
            return
        # 首次启动：从 registry 读取默认词书文件名
        registry_path = builtin_registry_file()
        default_file = ""
        if registry_path.exists():
            registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
            default_file = registry.get("default_book", "")
        # 按 file_path 文件名匹配默认词书
        for book in self.list_builtin_books():
            if book.file_path and Path(book.file_path).name == default_file:
                self.repo.set_active_book_id(book.id)
                self._ensure_words_imported(book.id)
                return
        # 降级：取第一本内置词书
        books = self.list_builtin_books()
        if books:
            self.repo.set_active_book_id(books[0].id)
            self._ensure_words_imported(books[0].id)

    # ---------------------------------------------------------- 切换词书
    def switch_book(self, book_id: int) -> None:
        """更新 active_book_id；若新词书 words 未导入则先导入。"""
        book = self.repo.get_book_by_id(book_id)
        if book is None:
            raise ValueError(f"词书不存在: id={book_id}")
        self.repo.set_active_book_id(book_id)
        self._ensure_words_imported(book_id)

    # ---------------------------------------------------------- 导入词书
    def import_book(self, path, fmt: Optional[str] = None,
                    name: Optional[str] = None, description: str = "") -> int:
        """解析外部文件 -> 复制 JSON 到 user_books_dir -> 注册到 books -> 返回新 book_id。

        - path: 外部文件路径（.json/.jsonl/.txt/.csv/.apkg）
        - fmt: 显式指定格式（wordmem/simple/jsonl/txt/csv/apkg），None 则按扩展名自动路由
        - name: 词书名（默认用文件名去扩展名）
        - description: 词书描述（默认用文件内 book.description）
        """
        path = Path(path)
        # 解析文件
        if fmt:
            key = fmt.lower().lstrip(".")
            parser = self._FMT_MAP.get(key, parse_auto)
            data = parser(path)
        else:
            data = parse_auto(path)
        # 词书名：优先调用方提供，否则用文件名去扩展名
        book_name = name or path.stem
        book_desc = description or (data.get("book") or {}).get("description", "")
        words = data.get("words") or []
        # 复制到 user_books_dir（统一存为 WordMem JSON）
        dest = user_books_dir() / f"{path.stem}.json"
        payload = {
            "book": {"name": book_name, "description": book_desc},
            "words": words,
        }
        dest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        # 注册到 books + 导入 words
        book_id = self.repo.add_book(
            name=book_name,
            description=book_desc,
            source="imported",
            file_path=str(dest),
            word_count=len(words),
        )
        self.repo.add_words(book_id, words)
        return book_id

    # ---------------------------------------------------------- 删除词书
    def delete_book(self, book_id: int) -> None:
        """仅允许删除 source='imported' 的词书。"""
        book = self.repo.get_book_by_id(book_id)
        if book is None:
            raise ValueError(f"词书不存在: id={book_id}")
        if book.source != "imported":
            raise ValueError(f"内置词书不可删除: {book.name}")
        # 清理 words 和 study_state，再删 books 记录
        self.repo.clear_words_for_book(book_id)
        self.repo.delete_book(book_id)
        # 删除 user_books_dir 中的 JSON 文件（若存在）
        if book.file_path:
            fp = Path(book.file_path)
            if fp.exists():
                try:
                    fp.unlink()
                except OSError:
                    pass  # 文件删除失败不致命

    # ---------------------------------------------------------- 查询
    def list_builtin_books(self) -> list[Book]:
        """所有内置词书（按 id 排序）。"""
        return [b for b in self.repo.list_books() if b.source == "builtin"]

    def list_imported_books(self) -> list[Book]:
        """所有用户导入词书（按 id 排序）。"""
        return [b for b in self.repo.list_books() if b.source == "imported"]

    def get_active_book(self) -> Optional[Book]:
        """活动词书对象。"""
        return self.repo.get_active_book()

    # ---------------------------------------------------------- 内部工具
    def _ensure_words_imported(self, book_id: int) -> None:
        """若词书 words 未导入（表中为空但 JSON 有词），则从 JSON 导入。"""
        book = self.repo.get_book_by_id(book_id)
        if book is None or not book.file_path:
            return
        # 表中已有词：视为已导入
        if self.repo.count_words_in_book(book_id) > 0:
            return
        path = Path(book.file_path)
        if not path.exists():
            return
        data = parse_auto(path)
        words = data.get("words") or []
        if words:
            self.repo.add_words(book_id, words)

    @staticmethod
    def _count_words_in_json(path: Path) -> int:
        """读取 WordMem JSON 文件并返回词数（不构造完整对象，仅计数）。"""
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return len(data.get("words") or [])
        except (OSError, ValueError):
            return 0
