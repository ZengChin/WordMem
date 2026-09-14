# -*- coding: utf-8 -*-
"""将 Anki 词库包（.apkg）转换为 WordMem 词库 JSON。

用法:
    python scripts/apkg_to_words.py <apkg> <out_json> [book_name] [description]

.apkg 本质是 ZIP，内含 SQLite 词库（collection.anki2 / .anki21）。单词存于
notes 表，字段以 \\x1f 分隔，常含 HTML 与 [sound:] 标签，需要清洗。

针对 "TOEFL 绿宝书" 模型做了字段映射（注意：该模型中名为 pos 的字段实为音标）。
"""
from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile

DEFAULT_BOOK = "雅思词汇"
DEFAULT_DESC = "雅思核心词汇（含音标、释义与例句）"

# 词性标记：需位于串首或分隔符之后，避免误伤 etc. / 括号内英文
_POS_RE = re.compile(
    r'(?:^|(?<=[；;）)，,、\s]))'
    r'(vt|vi|adj|adv|prep|conj|pron|num|interj|int|aux|abbr|art|modal|pl|ad|n|v|a)\.\s*'
)
_SOUND_RE = re.compile(r'\[sound:[^\]]*\]', re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def clean_field(raw: str) -> str:
    """清洗 Anki 字段：去 [sound:]、去 HTML 标签、还原实体、压缩空白。"""
    if not raw:
        return ""
    s = _SOUND_RE.sub("", raw)
    s = s.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    s = _TAG_RE.sub("", s)
    s = html.unescape(s)
    return _WS_RE.sub(" ", s).strip()


def parse_definition(text: str) -> list[dict]:
    """将 'a. 彩色的；柔和的（bland）n. 蜡笔' 拆成多条 {pos, meaning}。"""
    text = text.strip()
    if not text:
        return []
    matches = list(_POS_RE.finditer(text))
    if not matches:
        return [{"pos": "", "meaning": text}]
    meanings: list[dict] = []
    lead = text[:matches[0].start()].strip(" ；;，,")
    if lead:                                   # 首个词性前的游离内容（少见）
        meanings.append({"pos": "", "meaning": lead})
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[m.end():end].strip(" ；;，,")
        if seg:
            meanings.append({"pos": m.group(1) + ".", "meaning": seg})
    return meanings or [{"pos": "", "meaning": text}]


def _pick_db(zf: zipfile.ZipFile, tmp: str) -> str:
    names = set(zf.namelist())
    for cand in ("collection.anki21", "collection.anki2", "collection.anki21b"):
        if cand in names:
            zf.extract(cand, tmp)              # 仅解出数据库，跳过海量媒体
            return os.path.join(tmp, cand)
    raise SystemExit("未在 apkg 中找到 collection 数据库")


def _field_index(conn: sqlite3.Connection) -> dict:
    """从 col.models 读取首个笔记类型的 字段名 -> 序号 映射。"""
    row = conn.execute("SELECT models FROM col").fetchone()
    models = json.loads(row[0]) if row and row[0] else {}
    if not models:
        return {}
    model = next(iter(models.values()))
    return {f.get("name"): f.get("ord", i)
            for i, f in enumerate(model.get("flds", []))}


def convert(apkg_path: str, out_path: str,
            book_name: str = DEFAULT_BOOK,
            description: str = DEFAULT_DESC) -> int:
    tmp = tempfile.mkdtemp(prefix="apkg_conv_")
    with zipfile.ZipFile(apkg_path) as zf:      # 用 with 确保 ZipFile 关闭
        db_path = _pick_db(zf, tmp)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    idx = _field_index(conn)
    wi = idx.get("word", 0)
    pi = idx.get("pos", 1)          # 该模型 "pos" 字段实为音标
    di = idx.get("definition", 3)
    ei = idx.get("example_en", 4)
    ti = idx.get("example_zh", 5)

    words: list[dict] = []
    seen: set[str] = set()
    skipped = 0
    for r in conn.execute("SELECT flds FROM notes ORDER BY id"):
        f = r["flds"].split("\x1f")

        def g(i: int) -> str:
            return clean_field(f[i]) if 0 <= i < len(f) else ""

        word, definition = g(wi), g(di)
        if not word or not definition:
            skipped += 1
            continue
        key = word.lower()
        if key in seen:                          # 去重，保留首次出现
            skipped += 1
            continue
        seen.add(key)

        ex_en, ex_zh = g(ei), g(ti)
        examples = [{"text": ex_en, "translation": ex_zh}] if ex_en else []
        words.append({
            "word": word,
            "phonetic": g(pi),
            "meanings": parse_definition(definition),
            "examples": examples,
        })
    conn.close()

    payload = {"book": {"name": book_name, "description": description},
               "words": words}
    out_dir = os.path.dirname(out_path)
    if out_dir:                                 # 纯文件名时 dirname 为空，跳过建目录
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=1)
    print(f"imported={len(words)} skipped={skipped} -> {out_path}")
    return len(words)


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        raise SystemExit(__doc__)
    convert(argv[1], argv[2],
            argv[3] if len(argv) > 3 else DEFAULT_BOOK,
            argv[4] if len(argv) > 4 else DEFAULT_DESC)


if __name__ == "__main__":
    main(sys.argv)
