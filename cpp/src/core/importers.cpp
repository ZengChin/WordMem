#include "core/importers.h"

#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QRegularExpressionMatchIterator>
#include <QSet>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QTemporaryDir>
#include <atomic>
#include <cstring>

#include <miniz.h>

namespace wordmem {

namespace {

// 词性标记：需位于串首或分隔符之后，避免误伤 etc. / 括号内英文
const QRegularExpression &posRe() {
    static const QRegularExpression re(QStringLiteral(
        "(?:^|(?<=[；;）)，,、\\s]))"
        "(vt|vi|adj|adv|prep|conj|pron|num|interj|int|aux|abbr|art|modal|pl|ad|"
        "n|v|a)\\.\\s*"));
    return re;
}

QString trimChars(const QString &s, const QString &chars) {
    int i = 0;
    int j = s.size();
    while (i < j && chars.contains(s.at(i)))
        ++i;
    while (j > i && chars.contains(s.at(j - 1)))
        --j;
    return s.mid(i, j - i);
}

// 解码 HTML 实体（对应 Python html.unescape 的常用子集）：
// 先处理数字实体 &#NN; / &#xHH;，再处理常见命名实体（&amp; 最后替换避免二次解码）。
QString htmlUnescape(const QString &s) {
    if (!s.contains(QLatin1Char('&')))
        return s;
    static const QRegularExpression numRe(QStringLiteral("&#(x?)([0-9a-fA-F]+);"));
    QString out;
    out.reserve(s.size());
    int last = 0;
    QRegularExpressionMatchIterator it = numRe.globalMatch(s);
    while (it.hasNext()) {
        const QRegularExpressionMatch m = it.next();
        out += s.mid(last, int(m.capturedStart()) - last);
        const bool hex =
            m.captured(1).compare(QLatin1Char('x'), Qt::CaseInsensitive) == 0;
        bool ok = false;
        const uint cp = m.captured(2).toUInt(&ok, hex ? 16 : 10);
        if (ok && cp > 0 && cp <= 0x10FFFF) {
            const char32_t c32 = static_cast<char32_t>(cp);
            out += QString::fromUcs4(&c32, 1);
        } else {
            out += m.captured(0);
        }
        last = int(m.capturedEnd());
    }
    out += s.mid(last);
    out.replace(QLatin1String("&lt;"), QLatin1String("<"))
        .replace(QLatin1String("&gt;"), QLatin1String(">"))
        .replace(QLatin1String("&quot;"), QLatin1String("\""))
        .replace(QLatin1String("&apos;"), QLatin1String("'"))
        .replace(QLatin1String("&nbsp;"), QLatin1String(" "))
        .replace(QLatin1String("&amp;"), QLatin1String("&"));
    return out;
}

// 读文件（utf-8-sig）；文件不可读时返回 nullopt 并写入 err
std::optional<QString> readText(const QString &path, QString *err) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        if (err)
            *err = QStringLiteral("无法读取文件：%1").arg(path);
        return std::nullopt;
    }
    QByteArray bytes = f.readAll();
    if (bytes.startsWith("\xEF\xBB\xBF"))  // utf-8-sig
        bytes.remove(0, 3);
    return QString::fromUtf8(bytes);
}

QJsonObject meaningObj(const QString &pos, const QString &meaning) {
    QJsonObject o;
    o.insert(QLatin1String("pos"), pos);
    o.insert(QLatin1String("meaning"), meaning);
    return o;
}

QJsonObject exampleObj(const QString &text, const QString &translation) {
    QJsonObject o;
    o.insert(QLatin1String("text"), text);
    o.insert(QLatin1String("translation"), translation);
    return o;
}

QJsonObject wordObj(const QString &word, const QString &phonetic,
                    const QJsonArray &meanings, const QJsonArray &examples) {
    QJsonObject o;
    o.insert(QLatin1String("word"), word);
    o.insert(QLatin1String("phonetic"), phonetic);
    o.insert(QLatin1String("meanings"), meanings);
    o.insert(QLatin1String("examples"), examples);
    return o;
}

QJsonArray toArray(const QList<QJsonObject> &list) {
    QJsonArray arr;
    for (const QJsonObject &o : list)
        arr << o;
    return arr;
}

// KyleBing simple 单词对象 -> WordMem 单词 dict
QJsonObject normalizeSimple(const QJsonObject &obj) {
    const QString word = obj.value(QLatin1String("word")).toString().trimmed();
    QList<QJsonObject> meanings;
    for (const QJsonValue &tv : obj.value(QLatin1String("translations")).toArray()) {
        const QJsonObject t = tv.toObject();
        QString pos = t.value(QLatin1String("type")).toString().trimmed();
        if (!pos.isEmpty() && !pos.endsWith(QLatin1Char('.')))
            pos += QLatin1Char('.');
        meanings << meaningObj(
            pos, t.value(QLatin1String("translation")).toString().trimmed());
    }
    QList<QJsonObject> examples;
    const QJsonArray phrases = obj.value(QLatin1String("phrases")).toArray();
    for (int i = 0; i < phrases.size() && i < 3; ++i) {  // 只取前 3 个短语
        const QJsonObject p = phrases.at(i).toObject();
        examples << exampleObj(p.value(QLatin1String("phrase")).toString(),
                               p.value(QLatin1String("translation")).toString());
    }
    return wordObj(word, obj.value(QLatin1String("phonetic")).toString(),
                   toArray(meanings), toArray(examples));
}

// 规整 WordMem 单词对象（兼容 trans/translation 两种字段名）
QJsonObject normalizeWordmemWord(const QJsonObject &w) {
    QList<QJsonObject> examples;
    for (const QJsonValue &ev : w.value(QLatin1String("examples")).toArray()) {
        const QJsonObject e = ev.toObject();
        const QString tr = e.contains(QLatin1String("translation"))
                               ? e.value(QLatin1String("translation")).toString()
                               : e.value(QLatin1String("trans")).toString();
        examples << exampleObj(e.value(QLatin1String("text")).toString(), tr);
    }
    return wordObj(w.value(QLatin1String("word")).toString(),
                   w.value(QLatin1String("phonetic")).toString(),
                   w.value(QLatin1String("meanings")).toArray(),
                   toArray(examples));
}

QList<QJsonObject> normalizeSimpleItems(const QList<QJsonObject> &items) {
    QList<QJsonObject> out;
    for (const QJsonObject &it : items)
        out << normalizeSimple(it);
    return out;
}

// 取第 i 个 Anki 字段的原始值（不清洗，保留 HTML 供后续解析）
QString rawAt(const QStringList &fields, int i) {
    if (i < 0 || i >= fields.size())
        return QString();
    return fields.at(i);
}

QString fieldAt(const QStringList &fields, int i) {
    if (i < 0 || i >= fields.size())
        return QString();
    return cleanField(fields.at(i));
}

// 极简 CSV 解析（支持引号包裹、内嵌逗号/换行/转义双引号）
QList<QStringList> parseCsvText(const QString &text) {
    QList<QStringList> rows;
    QStringList cur;
    QString field;
    bool inQuotes = false;
    for (int i = 0; i < text.size(); ++i) {
        const QChar c = text.at(i);
        if (inQuotes) {
            if (c == QLatin1Char('"')) {
                if (i + 1 < text.size() && text.at(i + 1) == QLatin1Char('"')) {
                    field += QLatin1Char('"');
                    ++i;
                } else {
                    inQuotes = false;
                }
                continue;
            }
            field += c;
            continue;
        }
        if (c == QLatin1Char('"'))
            inQuotes = true;
        else if (c == QLatin1Char(',')) {
            cur << field;
            field.clear();
        } else if (c == QLatin1Char('\r')) {
            continue;
        } else if (c == QLatin1Char('\n')) {
            cur << field;
            rows << cur;
            cur.clear();
            field.clear();
        } else {
            field += c;
        }
    }
    if (!cur.isEmpty() || !field.isEmpty()) {
        cur << field;
        rows << cur;
    }
    return rows;
}

ParsedBook emptyBook() { return ParsedBook{}; }

}  // namespace

// ---------------------------------------------------------------------- 通用
QString cleanField(const QString &raw) {
    if (raw.isEmpty())
        return QString();
    static const QRegularExpression soundRe(
        QStringLiteral("\\[sound:[^\\]]*\\]"),
        QRegularExpression::CaseInsensitiveOption);
    static const QRegularExpression tagRe(QStringLiteral("<[^>]+>"));
    static const QRegularExpression wsRe(QStringLiteral("\\s+"));
    QString s = raw;
    s.remove(soundRe);
    s.replace(QLatin1String("<br>"), QLatin1String(" "))
        .replace(QLatin1String("<br/>"), QLatin1String(" "))
        .replace(QLatin1String("<br />"), QLatin1String(" "));
    s.remove(tagRe);
    s = htmlUnescape(s);
    s.replace(wsRe, QLatin1String(" "));
    return s.trimmed();
}

QList<QJsonObject> parseDefinition(const QString &text) {
    const QString t = text.trimmed();
    if (t.isEmpty())
        return {};
    QList<QJsonObject> meanings;
    static const QString kTrim = QStringLiteral(" ；;，,");

    QVector<int> starts, ends;
    QStringList poss;
    QRegularExpressionMatchIterator it = posRe().globalMatch(t);
    while (it.hasNext()) {
        const QRegularExpressionMatch m = it.next();
        starts << int(m.capturedStart());
        ends << int(m.capturedEnd());
        poss << m.captured(1);
    }
    if (starts.isEmpty())
        return {meaningObj(QString(), t)};

    const QString lead = trimChars(t.left(starts.first()), kTrim);
    if (!lead.isEmpty())  // 首个词性前的游离内容（少见）
        meanings << meaningObj(QString(), lead);

    for (int i = 0; i < starts.size(); ++i) {
        const int stop = (i + 1 < starts.size()) ? starts.at(i + 1) : t.size();
        const QString seg = trimChars(t.mid(ends.at(i), stop - ends.at(i)), kTrim);
        if (!seg.isEmpty())
            meanings << meaningObj(poss.at(i) + QLatin1Char('.'), seg);
    }
    if (meanings.isEmpty())
        return {meaningObj(QString(), t)};
    return meanings;
}

QList<QJsonObject> dedupeWords(const QList<QJsonObject> &words) {
    QSet<QString> seen;
    QList<QJsonObject> out;
    for (const QJsonObject &w : words) {
        const QString key = w.value(QLatin1String("word")).toString().toLower();
        if (key.isEmpty() || seen.contains(key))
            continue;  // 同一单词只保留首次出现（按小写比较）
        seen.insert(key);
        out << w;
    }
    return out;
}

QList<QJsonObject> splitNumberedExamples(const QString &en, const QString &zh) {
    static const QRegularExpression numEx(QStringLiteral("\\(\\d+\\)\\s*"));
    const QString e = en.trimmed();
    const QString z = zh.trimmed();
    if (e.isEmpty())
        return {};
    QStringList enParts;
    const QStringList rawEn = e.split(numEx);
    for (const QString &p : rawEn) {
        const QString t = p.trimmed();
        if (!t.isEmpty())
            enParts << t;
    }
    if (enParts.size() <= 1)  // 无编号单句
        return {exampleObj(e, z)};

    QStringList zhParts;
    const QStringList rawZh = z.split(numEx);
    for (const QString &p : rawZh) {
        const QString t = p.trimmed();
        if (!t.isEmpty())
            zhParts << t;
    }
    // 中英段数不一致：多出的英文段译文留空，多余译文丢弃
    QList<QJsonObject> out;
    for (int i = 0; i < enParts.size(); ++i)
        out << exampleObj(enParts.at(i),
                          i < zhParts.size() ? zhParts.at(i) : QString());
    return out;
}

QList<QJsonObject> extractCollinsExamples(const QString &rawHtml) {
    static const QRegularExpression liRe(
        QStringLiteral("<li[^>]*>(.*?)</li>"),
        QRegularExpression::CaseInsensitiveOption |
            QRegularExpression::DotMatchesEverythingOption);
    static const QRegularExpression pRe(
        QStringLiteral("<p[^>]*>(.*?)</p>"),
        QRegularExpression::CaseInsensitiveOption |
            QRegularExpression::DotMatchesEverythingOption);
    static const QRegularExpression cjkRe(QStringLiteral("[\\x{4e00}-\\x{9fff}]"));

    if (rawHtml.isEmpty())
        return {};
    QList<QJsonObject> out;
    QSet<QString> seen;
    QRegularExpressionMatchIterator liIt = liRe.globalMatch(rawHtml);
    while (liIt.hasNext()) {
        const QString li = liIt.next().captured(1);
        QStringList ps;
        QRegularExpressionMatchIterator pIt = pRe.globalMatch(li);
        while (pIt.hasNext())
            ps << pIt.next().captured(1);
        if (ps.size() < 2)
            continue;  // 至少一英一中两段
        const QString en = cleanField(ps.at(0));
        const QString zh = cleanField(ps.at(1));
        if (en.isEmpty() || zh.isEmpty())
            continue;
        // 第一段须英文、第二段须中文，避免把语法说明或词组误当例句
        if (cjkRe.match(en).hasMatch() || !cjkRe.match(zh).hasMatch())
            continue;
        if (seen.contains(en))
            continue;
        seen.insert(en);
        out << exampleObj(en, zh);
    }
    return out;
}

AnkiFields readAnkiFields(QSqlQuery &q) {
    AnkiFields out;
    q.exec(QLatin1String("SELECT models FROM col"));
    if (!q.next())
        return out;
    const QJsonDocument doc =
        QJsonDocument::fromJson(q.value(0).toString().toUtf8());
    const QJsonObject models = doc.object();
    if (models.isEmpty())
        return out;
    const QJsonObject model = models.begin().value().toObject();
    const QJsonArray flds = model.value(QLatin1String("flds")).toArray();
    for (int i = 0; i < flds.size(); ++i) {
        const QJsonObject f = flds.at(i).toObject();
        const QString name = f.value(QLatin1String("name")).toString();
        const int ord = f.contains(QLatin1String("ord"))
                            ? f.value(QLatin1String("ord")).toInt()
                            : i;
        out.names << name;
        out.ord.insert(name, ord);
    }
    return out;
}

QHash<QString, int> mapAnkiFields(const AnkiFields &fields) {
    // 不同来源牌组的字段命名差异很大（英文 word/definition 或中文 单词/中文释义），
    // 按角色给出别名优先级；匹配时先精确后包含，且每个字段只认领一次。
    struct Role {
        const char *name;
        QStringList keys;
    };
    static const Role kRoles[] = {
        {"word", {QStringLiteral("word"), QStringLiteral("英语单词"),
                  QStringLiteral("英文单词"), QStringLiteral("单词"),
                  QStringLiteral("english")}},
        {"phonetic", {QStringLiteral("phonetic"), QStringLiteral("英美音标"),
                      QStringLiteral("音标"), QStringLiteral("注音"),
                      QStringLiteral("pos")}},
        {"definition", {QStringLiteral("definition"),
                        QStringLiteral("中文释义"), QStringLiteral("释义1"),
                        QStringLiteral("释义"), QStringLiteral("翻译"),
                        QStringLiteral("意思"), QStringLiteral("含义")}},
        {"example_en", {QStringLiteral("example_en"),
                        QStringLiteral("英语例句"),
                        QStringLiteral("英文例句"), QStringLiteral("例句"),
                        QStringLiteral("example")}},
        {"example_zh", {QStringLiteral("example_zh"),
                        QStringLiteral("中文例句"),
                        QStringLiteral("例句翻译"),
                        QStringLiteral("例句中文"),
                        QStringLiteral("翻译例句")}},
        {"collins", {QStringLiteral("collins"), QStringLiteral("拓展"),
                     QStringLiteral("扩展"), QStringLiteral("词典"),
                     QStringLiteral("双语")}},
    };

    QHash<QString, int> result;
    QSet<QString> claimed;
    for (const Role &role : kRoles) {
        QString matched;
        bool found = false;
        for (int mode = 0; mode < 2 && !found; ++mode) {  // 0=精确 1=包含
            for (const QString &key : role.keys) {
                const QString klow = key.toLower();
                for (const QString &nm : fields.names) {
                    if (claimed.contains(nm))
                        continue;
                    const QString low = nm.trimmed().toLower();
                    if ((mode == 0 && low == klow) ||
                        (mode == 1 && low.contains(klow))) {
                        matched = nm;
                        found = true;
                        break;
                    }
                }
                if (found)
                    break;
            }
        }
        if (found) {
            claimed.insert(matched);
            result.insert(QLatin1String(role.name), fields.ord.value(matched));
        }
    }
    return result;
}

// ---------------------------------------------------------------------- parsers
std::optional<ParsedBook> parseWordmemJson(const QString &path, QString *err) {
    const auto rawOpt = readText(path, err);
    if (!rawOpt)
        return std::nullopt;
    const QString &raw = *rawOpt;
    if (raw.isEmpty())
        return emptyBook();
    QJsonParseError perr{};
    const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &perr);
    if (perr.error != QJsonParseError::NoError || !doc.isObject()) {
        if (err)
            *err = QStringLiteral("JSON 解析失败：%1").arg(perr.errorString());
        return std::nullopt;
    }
    const QJsonObject data = doc.object();
    const QJsonObject book = data.value(QLatin1String("book")).toObject();
    QList<QJsonObject> words;
    for (const QJsonValue &v : data.value(QLatin1String("words")).toArray())
        words << normalizeWordmemWord(v.toObject());

    ParsedBook out;
    out.name = book.value(QLatin1String("name")).toString();
    out.description = book.value(QLatin1String("description")).toString();
    out.words = dedupeWords(words);
    return out;
}

std::optional<ParsedBook> parseSimpleJson(const QString &path, QString *err) {
    const auto rawOpt = readText(path, err);
    if (!rawOpt)
        return std::nullopt;
    const QString raw = rawOpt->trimmed();
    if (raw.isEmpty())
        return emptyBook();

    QList<QJsonObject> items;
    if (raw.startsWith(QLatin1Char('['))) {
        const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8());
        for (const QJsonValue &v : doc.array())
            items << v.toObject();
    } else if (raw.startsWith(QLatin1Char('{'))) {
        QJsonParseError perr{};
        const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &perr);
        if (perr.error == QJsonParseError::NoError) {
            if (doc.isArray()) {
                for (const QJsonValue &v : doc.array())
                    items << v.toObject();
            } else if (doc.isObject() &&
                       doc.object().contains(QLatin1String("word"))) {
                items << doc.object();  // 单个 simple 格式对象
            }
        } else {
            // 多行内容且非合法单个 JSON -> JSONL：逐行解析
            const QStringList lines = raw.split(QLatin1Char('\n'));
            for (const QString &l : lines) {
                const QString line = l.trimmed();
                if (line.isEmpty())
                    continue;
                const QJsonDocument d = QJsonDocument::fromJson(line.toUtf8());
                if (d.isObject())
                    items << d.object();
            }
        }
    }

    ParsedBook out;
    out.words = dedupeWords(normalizeSimpleItems(items));
    return out;
}

std::optional<ParsedBook> parsePlainText(const QString &path, QString *err) {
    const auto rawOpt = readText(path, err);
    if (!rawOpt)
        return std::nullopt;
    const QString &raw = *rawOpt;
    if (raw.isEmpty())
        return emptyBook();

    QList<QJsonObject> words;
    const QStringList lines = raw.split(QLatin1Char('\n'));
    for (const QString &l : lines) {
        const QString line = l.trimmed();
        if (line.isEmpty())
            continue;
        // 优先按 TAB 分隔，其次按多空格分隔
        QString word, definition;
        const int tab = line.indexOf(QLatin1Char('\t'));
        if (tab >= 0) {
            word = line.left(tab);
            definition = line.mid(tab + 1);
        } else {
            int sp = 0;
            while (sp < line.size() && line.at(sp).isSpace())
                ++sp;
            int cut = sp;
            while (cut < line.size() && !line.at(cut).isSpace())
                ++cut;
            if (cut >= line.size())
                continue;
            word = line.left(cut);
            definition = line.mid(cut);
        }
        word = word.trimmed();
        definition = definition.trimmed();
        if (word.isEmpty() || definition.isEmpty())
            continue;
        words << wordObj(word, QString(), toArray(parseDefinition(definition)),
                         QJsonArray());
    }
    ParsedBook out;
    out.words = dedupeWords(words);
    return out;
}

std::optional<ParsedBook> parseCsv(const QString &path, QString *err) {
    const auto rawOpt = readText(path, err);
    if (!rawOpt)
        return std::nullopt;
    const QString &raw = *rawOpt;
    if (raw.isEmpty())
        return emptyBook();
    const QList<QStringList> rows = parseCsvText(raw);
    if (rows.isEmpty())
        return emptyBook();

    QStringList header = rows.first();
    for (QString &h : header)
        h = h.trimmed().toLower();

    ParsedBook out;
    QList<QJsonObject> words;
    if (header.contains(QLatin1String("word")) &&
        header.contains(QLatin1String("translation"))) {
        // ECDICT 路径：表头含 word + translation
        const int wi = header.indexOf(QLatin1String("word"));
        const int pi = header.indexOf(QLatin1String("phonetic"));
        const int ti = header.indexOf(QLatin1String("translation"));
        for (int r = 1; r < rows.size(); ++r) {
            const QStringList &row = rows.at(r);
            if (row.size() <= qMax(wi, ti))
                continue;
            const QString word = row.at(wi).trimmed();
            const QString trans = row.at(ti).trimmed();
            if (word.isEmpty() || trans.isEmpty())
                continue;
            const QString phonetic =
                (pi >= 0 && pi < row.size()) ? row.at(pi).trimmed() : QString();
            words << wordObj(word, phonetic, toArray(parseDefinition(trans)),
                             QJsonArray());
        }
    } else {
        // 通用路径：前两列为 word/释义（无表头识别，全部按数据行处理）
        for (const QStringList &row : rows) {
            if (row.size() < 2)
                continue;
            const QString word = row.at(0).trimmed();
            const QString definition = row.at(1).trimmed();
            if (word.isEmpty() || definition.isEmpty())
                continue;
            words << wordObj(word, QString(),
                             toArray(parseDefinition(definition)), QJsonArray());
        }
    }
    out.words = dedupeWords(words);
    return out;
}

std::optional<ParsedBook> parseApkg(const QString &path, QString *err) {
    QFile src(path);
    if (!src.exists()) {
        if (err)
            *err = QStringLiteral("文件不存在：%1").arg(path);
        return std::nullopt;
    }
    const QByteArray pathUtf8 = QFile::encodeName(path);

    QTemporaryDir tmp(QStringLiteral("apkg_conv_"));
    if (!tmp.isValid()) {
        if (err)
            *err = QStringLiteral("无法创建临时目录");
        return std::nullopt;
    }

    // 仅解出 collection 数据库，跳过海量媒体
    mz_zip_archive zip;
    memset(&zip, 0, sizeof(zip));
    if (!mz_zip_reader_init_file(&zip, pathUtf8.constData(), 0)) {
        if (err)
            *err = QStringLiteral("无法打开 apkg（非法 zip）：%1").arg(path);
        return std::nullopt;
    }
    static const char *kCandidates[] = {"collection.anki21", "collection.anki2",
                                        "collection.anki21b"};
    int found = -1;
    const mz_uint n = mz_zip_reader_get_num_files(&zip);
    for (const char *cand : kCandidates) {
        for (mz_uint i = 0; i < n; ++i) {
            char name[512];
            mz_zip_reader_get_filename(&zip, i, name, sizeof(name));
            if (QLatin1String(name) == QLatin1String(cand)) {
                found = int(i);
                break;
            }
        }
        if (found >= 0)
            break;
    }
    if (found < 0) {
        mz_zip_reader_end(&zip);
        if (err)
            *err = QStringLiteral("未在 apkg 中找到 collection 数据库");
        return std::nullopt;
    }
    const QString dbPath = tmp.path() + QLatin1String("/collection.db");
    const bool extracted = mz_zip_reader_extract_to_file(
        &zip, mz_uint(found), QFile::encodeName(dbPath).constData(), 0);
    mz_zip_reader_end(&zip);
    if (!extracted) {
        if (err)
            *err = QStringLiteral("解压 collection 数据库失败");
        return std::nullopt;
    }

    ParsedBook out;
    out.name = QString::fromUtf8(DEFAULT_BOOK);
    out.description = QString::fromUtf8(DEFAULT_DESC);

    static std::atomic<int> seq{0};
    const QString conn =
        QStringLiteral("apkg_%1").arg(seq.fetch_add(1));
    {
        QSqlDatabase db = QSqlDatabase::addDatabase(QLatin1String("QSQLITE"), conn);
        db.setDatabaseName(dbPath);
        if (!db.open()) {
            if (err)
                *err = QStringLiteral("无法打开 apkg 内数据库");
            QSqlDatabase::removeDatabase(conn);
            return std::nullopt;
        }
        QSqlQuery q(db);
        const AnkiFields fields = readAnkiFields(q);
        // 按字段名智能映射，兼容中英文命名
        const QHash<QString, int> fm = mapAnkiFields(fields);
        const int wi = fm.value(QLatin1String("word"), 0);  // 无 word 列时退化到第 0 列
        const int pi = fm.value(QLatin1String("phonetic"), -1);
        const int di = fm.value(QLatin1String("definition"), -1);
        const int ei = fm.value(QLatin1String("example_en"), -1);
        const int ti = fm.value(QLatin1String("example_zh"), -1);
        const int ci = fm.value(QLatin1String("collins"), -1);

        QList<QJsonObject> words;
        QSet<QString> seen;
        q.exec(QLatin1String("SELECT flds FROM notes ORDER BY id"));
        while (q.next()) {
            const QStringList f =
                q.value(0).toString().split(QLatin1Char('\x1f'));
            const QString word = fieldAt(f, wi);
            const QString definition = fieldAt(f, di);
            if (word.isEmpty() || definition.isEmpty())
                continue;
            const QString key = word.toLower();
            if (seen.contains(key))
                continue;  // 去重，保留首次出现
            seen.insert(key);

            QList<QJsonObject> examples =
                splitNumberedExamples(fieldAt(f, ei), fieldAt(f, ti));
            // 例句翻译列整列为空时（如考研牌组），退化到从 Collins 双语 HTML
            // 列提取带译文的多例句（需原始 HTML，故不经 cleanField）
            bool anyTranslation = false;
            for (const QJsonObject &e : examples) {
                if (!e.value(QLatin1String("translation")).toString().isEmpty()) {
                    anyTranslation = true;
                    break;
                }
            }
            if (!anyTranslation) {
                const auto cx = extractCollinsExamples(rawAt(f, ci));
                if (!cx.isEmpty())
                    examples = cx;
            }
            words << wordObj(word, fieldAt(f, pi),
                             toArray(parseDefinition(definition)),
                             toArray(examples));
        }
        out.words = words;
        db.close();
    }
    QSqlDatabase::removeDatabase(conn);  // 须在临时目录析构前释放文件句柄
    return out;
}

std::optional<ParsedBook> parseAuto(const QString &path, QString *err) {
    const QString suffix = QFileInfo(path).suffix().toLower();
    if (suffix == QLatin1String("json")) {
        // 先尝试作为单个 JSON 解析以判定内部结构
        QString ignore;
        const QString raw = readText(path, &ignore).value_or(QString());
        QJsonParseError perr{};
        const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &perr);
        if (perr.error != QJsonParseError::NoError)
            return parseSimpleJson(path, err);  // 实为 JSONL
        if (doc.isObject() && doc.object().contains(QLatin1String("book")) &&
            doc.object().contains(QLatin1String("words")))
            return parseWordmemJson(path, err);
        return parseSimpleJson(path, err);
    }
    if (suffix == QLatin1String("jsonl"))
        return parseSimpleJson(path, err);
    if (suffix == QLatin1String("txt") || suffix == QLatin1String("text"))
        return parsePlainText(path, err);
    if (suffix == QLatin1String("csv"))
        return parseCsv(path, err);
    if (suffix == QLatin1String("apkg"))
        return parseApkg(path, err);
    if (err)
        *err = QStringLiteral("不支持的文件格式: .%1").arg(suffix);
    return std::nullopt;
}

}  // namespace wordmem
