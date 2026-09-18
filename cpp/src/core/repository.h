// 数据访问层：SQLite 持久化与多词书管理（对应 Python core/repository.py）。
#pragma once

#include <QDate>
#include <QJsonObject>
#include <QList>
#include <QString>
#include <QSqlDatabase>
#include <optional>

#include "core/models.h"

namespace wordmem {

struct StatsSummary {
    int total = 0;
    int learned = 0;
    int learning = 0;
    int mastered = 0;
    int due = 0;
    int reviewedToday = 0;
};

class Repository {
public:
    explicit Repository(const QString &dbPath = QStringLiteral(":memory:"));
    ~Repository();
    Repository(const Repository &) = delete;
    Repository &operator=(const Repository &) = delete;

    void close();

    // ------------------------------------------------------------ 词书
    int addBook(const QString &name, const QString &description = QString(),
                const QString &source = QStringLiteral("builtin"),
                const QString &filePath = QString(), int wordCount = 0);
    // items 为单词 dict：{word, phonetic, meanings[], examples[]}
    void addWords(int bookId, const QList<QJsonObject> &items);
    QList<Book> listBooks() const;
    std::optional<Book> getBookById(int bookId) const;
    std::optional<int> getActiveBookId() const;
    void setActiveBookId(int bookId);
    std::optional<Book> getActiveBook() const;
    int countWordsInBook(int bookId) const;
    void clearWordsForBook(int bookId);
    void deleteBook(int bookId);

    // ------------------------------------------------------------ 单词
    std::optional<Word> getWord(int wordId) const;
    int countWords() const;
    int countLearned() const;
    int countStatus(const QString &status) const;
    int countDue(const QDate &today) const;
    int countReviewedToday(const QDate &today) const;
    QList<Word> getNewWords(int limit) const;
    QList<Word> getDueWords(const QDate &today, int limit) const;
    QList<Word> getAllWords() const;

    // ------------------------------------------------------------ 状态
    std::optional<WordState> getState(int wordId) const;
    void saveState(const WordState &state, bool passed, const QDate &today);
    void resetProgress();

    // ------------------------------------------------------------ 元数据
    QString getMeta(const QString &key) const;  // 不存在返回空串
    void setMeta(const QString &key, const QString &value);

    StatsSummary statsSummary(const QDate &today) const;
    void clearLibrary();

private:
    void migrate();
    QSqlDatabase m_db;
    QString m_conn;
};

}  // namespace wordmem
