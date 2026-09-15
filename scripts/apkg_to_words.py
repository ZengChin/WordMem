# -*- coding: utf-8 -*-
"""将 Anki 词库包（.apkg）转换为 WordMem 词库 JSON。

用法:
    python scripts/apkg_to_words.py <apkg> <out_json> [book_name] [description]

.apkg 本质是 ZIP，内含 SQLite 词库（collection.anki2 / .anki21）。单词存于
notes 表，字段以 \\x1f 分隔，常含 HTML 与 [sound:] 标签，需要清洗。

核心解析逻辑（clean_field / parse_definition / parse_apkg 等）已抽取至
wordmem.core.importers，本脚本仅保留 CLI 入口。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 确保能导入 wordmem 包（脚本可能从项目根目录直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wordmem.core.importers import (  # noqa: E402
    DEFAULT_BOOK,
    DEFAULT_DESC,
    clean_field,
    parse_apkg,
    parse_definition,
)


def convert(apkg_path: str, out_path: str,
            book_name: str = DEFAULT_BOOK,
            description: str = DEFAULT_DESC) -> int:
    """委托 parse_apkg 解析 apkg，写入 JSON 文件，返回词数。"""
    data = parse_apkg(Path(apkg_path))
    # 用调用方提供的词书名/描述覆盖默认值
    data["book"]["name"] = book_name
    data["book"]["description"] = description
    words = data.get("words") or []
    out_dir = os.path.dirname(out_path)
    if out_dir:                         # 纯文件名时 dirname 为空，跳过建目录
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=1)
    print(f"imported={len(words)} -> {out_path}")
    return len(words)


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        raise SystemExit(__doc__)
    convert(argv[1], argv[2],
            argv[3] if len(argv) > 3 else DEFAULT_BOOK,
            argv[4] if len(argv) > 4 else DEFAULT_DESC)


if __name__ == "__main__":
    main(sys.argv)
