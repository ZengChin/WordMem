// 测试共用工具：构造 30 个合成单词（与 Python 测试的 WORDS 等价）。
#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QList>
#include <QString>

namespace wordmem {
namespace testing {

inline QString wordName(int i) {
    return QStringLiteral("w%1").arg(i, 2, 10, QLatin1Char('0'));
}

inline QList<QJsonObject> makeWords(int n = 30) {
    QList<QJsonObject> out;
    for (int i = 0; i < n; ++i) {
        QJsonObject m;
        m.insert(QLatin1String("pos"), QLatin1String("n."));
        m.insert(QLatin1String("meaning"), QStringLiteral("测试"));
        QJsonObject e;
        e.insert(QLatin1String("text"),
                 QStringLiteral("this is %1").arg(wordName(i)));
        e.insert(QLatin1String("trans"), QStringLiteral("测试"));
        QJsonArray meanings, examples;
        meanings << m;
        examples << e;

        QJsonObject w;
        w.insert(QLatin1String("word"), wordName(i));
        w.insert(QLatin1String("phonetic"), QStringLiteral("[test%1]").arg(i));
        w.insert(QLatin1String("meanings"), meanings);
        w.insert(QLatin1String("examples"), examples);
        out << w;
    }
    return out;
}

}  // namespace testing
}  // namespace wordmem
