# -*- coding: utf-8 -*-
"""多格式词库解析：JSON / JSONL / TXT / CSV / Anki apkg -> 统一 dict 结构。

所有 parser 返回:
    {"book": {"name": str, "description": str},
     "words": [{"word", "phonetic", "meanings", "examples"}, ...]}

字段约定:
- meanings:  [{"pos": "n.", "meaning": "..."}]
- examples:  [{"text": "english", "translation": "中文"}]
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

# Anki apkg 默认词书元信息（apkg 内不含词书名，由调用方覆盖）
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
_NUM_EX_RE = re.compile(r'\(\d+\)\s*')   # 多例句编号标记：(1)(2)(3)
_LI_RE = re.compile(r'<li[^>]*>(.*?)</li>', re.IGNORECASE | re.DOTALL)
_P_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.IGNORECASE | re.DOTALL)
_CJK_RE = re.compile(r'[\u4e00-\u9fff]')   # 判定是否含中文字符


# ---------------------------------------------------------------------- 通用
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


def _split_numbered_examples(en: str, zh: str) -> list[dict]:
    """把 '(1) … (2) … (3) …' 形式的多例句拆成多条，并与译文按序配对。

    - 英文按 (n) 编号切分；切出多段时中文同样切分并按序配对；
    - 无编号（单句）时整体作为一条例句；
    - 中英段数不一致：多出的英文段译文留空，多余译文丢弃；
    - 英文为空返回 []（该词无例句）。
    """
    en = (en or "").strip()
    zh = (zh or "").strip()
    if not en:
        return []
    en_parts = [p.strip() for p in _NUM_EX_RE.split(en) if p.strip()]
    if len(en_parts) <= 1:                    # 无编号单句
        return [{"text": en, "translation": zh}]
    zh_parts = [p.strip() for p in _NUM_EX_RE.split(zh) if p.strip()]
    return [
        {"text": e, "translation": zh_parts[i] if i < len(zh_parts) else ""}
        for i, e in enumerate(en_parts)
    ]


def _raw_at(fields: list[str], i: Optional[int]) -> str:
    """取第 i 个 Anki 字段的原始值（不清洗，保留 HTML 供后续解析）。"""
    if i is None:
        return ""
    return fields[i] if 0 <= i < len(fields) else ""


def _extract_collins_examples(raw_html: str) -> list[dict]:
    """从 Collins 双语词典 HTML 提取 <li><p>英文</p><p>中文</p></li> 例句对。

    某些牌组（如考研）的「例句翻译」列整列为空，但「拓展」列内嵌了 Collins
    词典 HTML，其中每个词性下都有成对的英文例句与中文译文。仅当某个 <li>
    含 >=2 个 <p>、第一段为纯英文、第二段含中文时才采纳，避免把语法说明或
    词组误当例句；同一英文例句去重。返回 [{"text", "translation"}]。
    """
    if not raw_html:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for li in _LI_RE.findall(raw_html):
        ps = _P_RE.findall(li)
        if len(ps) < 2:
            continue
        en = clean_field(ps[0])
        zh = clean_field(ps[1])
        if not en or not zh:
            continue
        if _CJK_RE.search(en) or not _CJK_RE.search(zh):
            continue                          # 第一段须英文、第二段须中文
        if en in seen:
            continue
        seen.add(en)
        out.append({"text": en, "translation": zh})
    return out


def _normalize_simple(obj: dict) -> dict:
    """把 KyleBing simple 单词对象转为 WordMem 单词 dict。

    translations[].type  -> meanings[].pos（加 . 后缀）
    translations[].translation -> meanings[].meaning
    phrases -> examples（phrase -> text, translation -> translation，只取前 3 个）
    """
    word = (obj.get("word") or "").strip()
    meanings: list[dict] = []
    for t in obj.get("translations") or []:
        pos = (t.get("type") or "").strip()
        if pos and not pos.endswith("."):
            pos = pos + "."
        meanings.append({
            "pos": pos,
            "meaning": (t.get("translation") or "").strip(),
        })
    examples: list[dict] = []
    for p in (obj.get("phrases") or [])[:3]:
        examples.append({
            "text": p.get("phrase", ""),
            "translation": p.get("translation", ""),
        })
    return {
        "word": word,
        "phonetic": obj.get("phonetic", ""),
        "meanings": meanings,
        "examples": examples,
    }


def _dedupe(words: list[dict]) -> list[dict]:
    """同一单词只保留首次出现（按小写比较）。"""
    seen: set[str] = set()
    out: list[dict] = []
    for w in words:
        key = (w.get("word") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def _empty_book(name: str = "", description: str = "") -> dict:
    """构造空词书结构。"""
    return {"book": {"name": name, "description": description}, "words": []}


def _normalize_wordmem_word(w: dict) -> dict:
    """规整 WordMem 单词对象（兼容 trans/translation 两种字段名）。"""
    examples: list[dict] = []
    for e in w.get("examples") or []:
        examples.append({
            "text": e.get("text", ""),
            "translation": e.get("translation", e.get("trans", "")),
        })
    return {
        "word": w.get("word", ""),
        "phonetic": w.get("phonetic", ""),
        "meanings": w.get("meanings") or [],
        "examples": examples,
    }


# ---------------------------------------------------------------------- apkg
def _pick_db(zf: zipfile.ZipFile, tmp: str) -> str:
    """从 apkg 中定位 Anki collection 数据库并解压到临时目录。"""
    names = set(zf.namelist())
    for cand in ("collection.anki21", "collection.anki2", "collection.anki21b"):
        if cand in names:
            zf.extract(cand, tmp)              # 仅解出数据库，跳过海量媒体
            return os.path.join(tmp, cand)
    raise ValueError("未在 apkg 中找到 collection 数据库")


def _field_index(conn: sqlite3.Connection) -> dict:
    """从 col.models 读取首个笔记类型的 字段名 -> 序号 映射。"""
    row = conn.execute("SELECT models FROM col").fetchone()
    models = json.loads(row[0]) if row and row[0] else {}
    if not models:
        return {}
    model = next(iter(models.values()))
    return {f.get("name"): f.get("ord", i)
            for i, f in enumerate(model.get("flds", []))}


def _field_at(fields: list[str], i: Optional[int]) -> str:
    """从 Anki 字段数组取第 i 个并清洗，i 为 None 或越界返回空串。"""
    if i is None:
        return ""
    return clean_field(fields[i]) if 0 <= i < len(fields) else ""


# 不同来源牌组的字段命名差异很大（英文 word/definition 或中文 单词/中文释义），
# 按角色给出别名优先级；匹配时先精确后包含，且每个字段只认领一次。
_ROLE_KEYS = {
    "word": ("word", "英语单词", "英文单词", "单词", "english"),
    "phonetic": ("phonetic", "英美音标", "音标", "注音", "pos"),
    "definition": ("definition", "中文释义", "释义1", "释义", "翻译", "意思", "含义"),
    "example_en": ("example_en", "英语例句", "英文例句", "例句", "example"),
    "example_zh": ("example_zh", "中文例句", "例句翻译", "例句中文", "翻译例句"),
    "collins": ("collins", "拓展", "扩展", "词典", "双语"),
}


def _map_fields(idx: dict) -> dict:
    """把 Anki 模型字段名映射到 word/phonetic/definition/example_en/example_zh 角色。

    idx: {字段名: ord}。返回 {role: ord}，未匹配到的角色不出现在结果里。
    先按别名精确匹配（优先级高的别名先匹配），再退化为包含匹配；
    每个字段只会被一个角色认领，避免释义/例句等互相串位。
    """
    names = list(idx.keys())
    claimed: set = set()
    result: dict = {}
    for role, keys in _ROLE_KEYS.items():
        matched = None
        for mode in ("exact", "contains"):
            for key in keys:
                klow = key.lower()
                for nm in names:
                    if nm in claimed:
                        continue
                    low = nm.strip().lower()
                    if (mode == "exact" and low == klow) or \
                       (mode == "contains" and klow in low):
                        matched = nm
                        break
                if matched is not None:
                    break
            if matched is not None:
                break
        if matched is not None:
            claimed.add(matched)
            result[role] = idx[matched]
    return result


# ---------------------------------------------------------------------- parsers
def parse_wordmem_json(path: Path) -> dict:
    """WordMem 原生 JSON（含 book + words）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    book = data.get("book") or {}
    words = [_normalize_wordmem_word(w) for w in (data.get("words") or [])]
    return {
        "book": {
            "name": book.get("name", ""),
            "description": book.get("description", ""),
        },
        "words": _dedupe(words),
    }


def parse_simple_json(path: Path) -> dict:
    """KyleBing 格式 JSON：word + translations[{translation, type}] + phrases[]。

    支持单行 JSON（数组）和 JSONL（每行一个对象）。
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return _empty_book()

    items: list[dict] = []
    if raw.startswith("["):
        # JSON 数组
        items = json.loads(raw)
    elif raw.startswith("{"):
        # 尝试解析为单个 JSON 对象（可能是单个 simple 对象，也可能是多行 JSONL）
        try:
            obj = json.loads(raw)
            if isinstance(obj, list):
                items = obj
            elif isinstance(obj, dict) and "word" in obj:
                items = [obj]              # 单个 simple 格式对象
            else:
                return _empty_book()
        except json.JSONDecodeError:
            # 多行内容且非合法单个 JSON -> JSONL：逐行解析
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    words = [_normalize_simple(it) for it in items if isinstance(it, dict)]
    return {"book": {"name": "", "description": ""}, "words": _dedupe(words)}


def parse_plain_txt(path: Path) -> dict:
    """每行 word<TAB>释义 或 word 空格 释义。调 parse_definition() 拆词性。"""
    path = Path(path)
    words: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        # 优先按 TAB 分隔，其次按多空格分隔
        if "\t" in line:
            parts = line.split("\t", 1)
        else:
            parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        word = parts[0].strip()
        definition = parts[1].strip()
        if not word or not definition:
            continue
        words.append({
            "word": word,
            "phonetic": "",
            "meanings": parse_definition(definition),
            "examples": [],
        })
    return {"book": {"name": "", "description": ""}, "words": _dedupe(words)}


def parse_csv(path: Path) -> dict:
    """通用 CSV。若表头含 word/phonetic/translation 走 ECDICT 路径，否则前两列为 word/释义。"""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return _empty_book()

    header = [h.strip().lower() for h in rows[0]]
    # ECDICT 路径：表头含 word + translation
    if "word" in header and "translation" in header:
        wi = header.index("word")
        pi = header.index("phonetic") if "phonetic" in header else -1
        ti = header.index("translation")
        words: list[dict] = []
        for row in rows[1:]:
            if len(row) <= max(wi, ti):
                continue
            word = row[wi].strip()
            trans = row[ti].strip()
            if not word or not trans:
                continue
            phonetic = row[pi].strip() if pi >= 0 and pi < len(row) else ""
            words.append({
                "word": word,
                "phonetic": phonetic,
                "meanings": parse_definition(trans),
                "examples": [],
            })
        return {"book": {"name": "", "description": ""}, "words": _dedupe(words)}

    # 通用路径：前两列为 word/释义（无表头识别，全部按数据行处理）
    words: list[dict] = []
    for row in rows:
        if len(row) < 2:
            continue
        word = row[0].strip()
        definition = row[1].strip()
        if not word or not definition:
            continue
        words.append({
            "word": word,
            "phonetic": "",
            "meanings": parse_definition(definition),
            "examples": [],
        })
    return {"book": {"name": "", "description": ""}, "words": _dedupe(words)}


def parse_apkg(path: Path) -> dict:
    """Anki .apkg：复用 apkg_to_words.py 的 convert() 核心逻辑，返回 dict 而非写文件。"""
    path = Path(path)
    tmp = tempfile.mkdtemp(prefix="apkg_conv_")
    try:
        with zipfile.ZipFile(path) as zf:
            db_path = _pick_db(zf, tmp)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            idx = _field_index(conn)
            fm = _map_fields(idx)          # 按字段名智能映射，兼容中英文命名
            wi = fm.get("word", 0)         # 无 word 字段时退化到第 0 列
            pi = fm.get("phonetic")
            di = fm.get("definition")
            ei = fm.get("example_en")
            ti = fm.get("example_zh")
            ci = fm.get("collins")          # Collins 双语词典 HTML 列（如考研的拓展）

            words: list[dict] = []
            seen: set[str] = set()
            for r in conn.execute("SELECT flds FROM notes ORDER BY id"):
                f = r["flds"].split("\x1f")
                word, definition = _field_at(f, wi), _field_at(f, di)
                if not word or not definition:
                    continue
                key = word.lower()
                if key in seen:            # 去重，保留首次出现
                    continue
                seen.add(key)

                ex_en, ex_zh = _field_at(f, ei), _field_at(f, ti)
                examples = _split_numbered_examples(ex_en, ex_zh)
                # 例句翻译列整列为空时（如考研牌组），退化到从 Collins
                # 双语 HTML 列提取带译文的多例句（需原始 HTML，故不经 clean_field）
                if not any(e.get("translation") for e in examples):
                    cx = _extract_collins_examples(_raw_at(f, ci))
                    if cx:
                        examples = cx
                words.append({
                    "word": word,
                    "phonetic": _field_at(f, pi),
                    "meanings": parse_definition(definition),
                    "examples": examples,
                })
        finally:
            conn.close()
    finally:
        # 清理临时目录（Windows 上需先关闭 db 连接再删文件）
        shutil.rmtree(tmp, ignore_errors=True)

    return {
        "book": {"name": DEFAULT_BOOK, "description": DEFAULT_DESC},
        "words": words,
    }


def parse_auto(path: Path) -> dict:
    """按扩展名自动路由。.json 内部根据结构判定 WordMem / simple。"""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".json":
        # 先尝试作为单个 JSON 解析以判定内部结构
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            # 单个 JSON 解析失败，可能是 JSONL（.json 扩展名但实为逐行对象）
            return parse_simple_json(path)
        if isinstance(data, dict) and "book" in data and "words" in data:
            return parse_wordmem_json(path)
        return parse_simple_json(path)
    if ext == ".jsonl":
        return parse_simple_json(path)
    if ext in (".txt", ".text"):
        return parse_plain_txt(path)
    if ext == ".csv":
        return parse_csv(path)
    if ext == ".apkg":
        return parse_apkg(path)
    raise ValueError(f"不支持的文件格式: {ext}")
