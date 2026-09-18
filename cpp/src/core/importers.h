// 多格式词库解析：JSON / JSONL / TXT / CSV / Anki apkg -> 统一结构。
// 对应 Python core/importers.py。
#pragma once

#include <QHash>
#include <QJsonObject>
#include <QList>
#include <QString>
#include <QStringList>
#include <optional>

class QSqlQuery;

namespace wordmem {

// apkg 内不含词书名，用默认元信息（由调用方覆盖）
inline constexpr const char *DEFAULT_BOOK = "雅思词汇";
inline constexpr const char *DEFAULT_DESC = "雅思核心词汇（含音标、释义与例句）";

struct ParsedBook {
    QString name;
    QString description;
    QList<QJsonObject> words;  // {word, phonetic, meanings[], examples[]}
};

// ------------------------------------------------------------ 通用工具
QString cleanField(const QString &raw);
// 把 "a. 彩色的；柔和的（bland）n. 蜡笔" 拆成多条 {pos, meaning}
QList<QJsonObject> parseDefinition(const QString &text);
QList<QJsonObject> dedupeWords(const QList<QJsonObject> &words);

// 把 "(1) … (2) … (3) …" 形式的多例句拆成多条，并与译文按序配对
QList<QJsonObject> splitNumberedExamples(const QString &en, const QString &zh);
// 从 Collins 双语词典 HTML 提取 <li><p>英文</p><p>中文</p></li> 例句对
QList<QJsonObject> extractCollinsExamples(const QString &rawHtml);

// ------------------------------------------------------------ apkg 字段映射
struct AnkiFields {
    QStringList names;      // 按模型 flds 顺序（匹配优先级依赖此顺序）
    QHash<QString, int> ord;  // 字段名 -> 序号
};

// 从 col.models 读取首个笔记类型的字段信息
AnkiFields readAnkiFields(QSqlQuery &q);
// 按角色别名映射：word/phonetic/definition/example_en/example_zh/collins -> ord
// 先精确后包含匹配，且每个字段只被一个角色认领；未匹配的角色不出现在结果中
QHash<QString, int> mapAnkiFields(const AnkiFields &fields);

// ------------------------------------------------------------ parsers
// 失败（文件不可读 / 格式不支持）返回 nullopt，err 写入原因。
std::optional<ParsedBook> parseWordmemJson(const QString &path,
                                           QString *err = nullptr);
std::optional<ParsedBook> parseSimpleJson(const QString &path,
                                          QString *err = nullptr);
std::optional<ParsedBook> parsePlainText(const QString &path,
                                         QString *err = nullptr);
std::optional<ParsedBook> parseCsv(const QString &path,
                                   QString *err = nullptr);
std::optional<ParsedBook> parseApkg(const QString &path,
                                    QString *err = nullptr);
// 按扩展名自动路由；.json 内部根据结构判定 WordMem / simple
std::optional<ParsedBook> parseAuto(const QString &path,
                                    QString *err = nullptr);

}  // namespace wordmem
