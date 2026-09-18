#include "core/repository.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QSqlError>
#include <QSqlDriver>
#include <QSqlQuery>
#include <QStringList>
#include <QVariant>
#include <atomic>

namespace wordmem {

namespace {

const char *kSchema = R"SQL(
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
)SQL";

QString dateStr(const QDate &d) {
    return d.isValid() ? d.toString(Qt::ISODate) : QString();
}

QDate dateFrom(const QVariant &v) {
    const QString s = v.toString();
    return s.isEmpty() ? QDate() : QDate::fromString(s, Qt::ISODate);
}

QString compactJson(const QJsonValue &v) {
    return QString::fromUtf8(QJsonDocument(v.toArray()).toJson(QJsonDocument::Compact));
}

// 绑定 NOT NULL 文本列：null QString 会被 SQLite 驱动当作 NULL，
// 违反 NOT NULL 约束；此处统一强制成非 null 的空串（对齐 Python ""）。
QVariant bindText(const QString &s) {
    return s.isNull() ? QVariant(QStringLiteral("")) : QVariant(s);
}

}  // namespace

Repository::Repository(const QString &dbPath) {
    static std::atomic<int> seq{0};
    m_conn = QStringLiteral("wordmem_%1").arg(seq.fetch_add(1));
    m_db = QSqlDatabase::addDatabase(QLatin1String("QSQLITE"), m_conn);
    m_db.setDatabaseName(dbPath);
    if (!m_db.open())
        return;
    QSqlQuery q(m_db);
    for (const QString &stmt : QString(kSchema).split(QLatin1Char(';'),
                                                      Qt::SkipEmptyParts)) {
        const QString trimmed = stmt.trimmed();
        if (!trimmed.isEmpty())  // 跳过末尾换行产生的空语句，避免 "empty query" 告警
            q.exec(trimmed);
    }
    migrate();
}

Repository::~Repository() {
    if (m_db.isOpen())
        m_db.close();
    QSqlDatabase::removeDatabase(m_conn);
}

void Repository::close() {
    if (m_db.isOpen())
        m_db.close();
}

void Repository::migrate() {
    // 为旧版本数据库补齐新列，避免进度丢失
    QSqlQuery info(m_db);
    info.exec(QLatin1String("PRAGMA table_info(study_state)"));
    QStringList cols;
    while (info.next())
        cols << info.value(1).toString();

    QSqlQuery alt(m_db);
    bool any = false;
    const QStringList additions = {
        QLatin1String("ease REAL NOT NULL DEFAULT 2.5"),
        QLatin1String("interval INTEGER NOT NULL DEFAULT 0"),
        QLatin1String("reps INTEGER NOT NULL DEFAULT 0"),
        QLatin1String("lapses INTEGER NOT NULL DEFAULT 0"),
    };
    for (const QString &decl : additions) {
        const QString name = decl.split(QLatin1Char(' ')).first();
        if (!cols.contains(name)) {
            alt.exec(QLatin1String("ALTER TABLE study_state ADD COLUMN ") + decl);
            any = true;
        }
    }
    if (any) {
        // 旧 Leitner 档位 -> SM-2 间隔的近似映射，保留既有复习节奏
        alt.exec(QLatin1String(
            "UPDATE study_state SET reps = level, ease = 2.5, "
            "interval = CASE level "
            "WHEN 0 THEN 0 WHEN 1 THEN 1 WHEN 2 THEN 2 "
            "WHEN 3 THEN 4 WHEN 4 THEN 7 WHEN 5 THEN 15 ELSE 15 END"));
    }

    info.exec(QLatin1String("PRAGMA table_info(books)"));
    cols.clear();
    while (info.next())
        cols << info.value(1).toString();
    const QStringList bookAdditions = {
        QLatin1String("source TEXT NOT NULL DEFAULT 'builtin'"),
        QLatin1String("file_path TEXT"),
        QLatin1String("word_count INTEGER NOT NULL DEFAULT 0"),
    };
    for (const QString &decl : bookAdditions) {
        const QString name = decl.split(QLatin1Char(' ')).first();
        if (!cols.contains(name))
            alt.exec(QLatin1String("ALTER TABLE books ADD COLUMN ") + decl);
    }
}

// ------------------------------------------------------------------ 词书
int Repository::addBook(const QString &name, const QString &description,
                        const QString &source, const QString &filePath,
                        int wordCount) {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "INSERT INTO books(name, description, source, file_path, word_count) "
        "VALUES(?, ?, ?, ?, ?)"));
    q.addBindValue(bindText(name));
    q.addBindValue(bindText(description));
    q.addBindValue(bindText(source));
    q.addBindValue(filePath.isEmpty() ? QVariant() : QVariant(filePath));
    q.addBindValue(wordCount);
    q.exec();
    const int bookId = q.lastInsertId().toInt();
    // 首本词书自动设为活动词书
    if (getMeta(QLatin1String("active_book_id")).isEmpty())
        setMeta(QLatin1String("active_book_id"), QString::number(bookId));
    return bookId;
}

void Repository::addWords(int bookId, const QList<QJsonObject> &items) {
    if (items.isEmpty())
        return;
    // 单事务批量插入：逐行自动提交会每行 fsync，导入大词书（数千词）将慢到不可用；
    // 与 Python executemany()+commit() 的一次性提交对齐。
    const bool useTx = m_db.driver()->hasFeature(QSqlDriver::Transactions);
    if (useTx)
        m_db.transaction();
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "INSERT INTO words(book_id, word, phonetic, meanings, examples) "
        "VALUES(?, ?, ?, ?, ?)"));
    for (const QJsonObject &it : items) {
        q.addBindValue(bookId);
        q.addBindValue(bindText(it.value(QLatin1String("word")).toString().trimmed()));
        q.addBindValue(bindText(it.value(QLatin1String("phonetic")).toString()));
        q.addBindValue(compactJson(it.value(QLatin1String("meanings"))));
        q.addBindValue(compactJson(it.value(QLatin1String("examples"))));
        q.exec();
    }
    if (useTx)
        m_db.commit();
}

namespace {
Book rowToBook(const QSqlQuery &q) {
    Book b;
    b.id = q.value(0).toInt();
    b.name = q.value(1).toString();
    b.description = q.value(2).toString();
    b.source = q.value(3).toString();
    if (b.source.isEmpty())
        b.source = QStringLiteral("builtin");
    b.filePath = q.value(4).toString();
    b.wordCount = q.value(5).toInt();
    return b;
}
}  // namespace

QList<Book> Repository::listBooks() const {
    QList<Book> out;
    QSqlQuery q(m_db);
    q.exec(QLatin1String(
        "SELECT id, name, description, source, file_path, word_count "
        "FROM books ORDER BY id"));
    while (q.next())
        out << rowToBook(q);
    return out;
}

std::optional<Book> Repository::getBookById(int bookId) const {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT id, name, description, source, file_path, word_count "
        "FROM books WHERE id=?"));
    q.addBindValue(bookId);
    if (!q.exec() || !q.next())
        return std::nullopt;
    return rowToBook(q);
}

std::optional<int> Repository::getActiveBookId() const {
    const QString raw = getMeta(QLatin1String("active_book_id"));
    if (raw.isEmpty())
        return std::nullopt;
    return raw.toInt();
}

void Repository::setActiveBookId(int bookId) {
    setMeta(QLatin1String("active_book_id"), QString::number(bookId));
}

std::optional<Book> Repository::getActiveBook() const {
    const auto id = getActiveBookId();
    if (!id)
        return std::nullopt;
    return getBookById(*id);
}

int Repository::countWordsInBook(int bookId) const {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String("SELECT COUNT(*) FROM words WHERE book_id=?"));
    q.addBindValue(bookId);
    q.exec();
    return q.next() ? q.value(0).toInt() : 0;
}

void Repository::clearWordsForBook(int bookId) {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "DELETE FROM study_state WHERE word_id IN "
        "(SELECT id FROM words WHERE book_id=?)"));
    q.addBindValue(bookId);
    q.exec();
    q.prepare(QLatin1String("DELETE FROM words WHERE book_id=?"));
    q.addBindValue(bookId);
    q.exec();
}

void Repository::deleteBook(int bookId) {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String("DELETE FROM books WHERE id=?"));
    q.addBindValue(bookId);
    q.exec();
}

// ------------------------------------------------------------------ 单词
namespace {
Word rowToWord(const QSqlQuery &q) {
    Word w;
    w.id = q.value(QLatin1String("id")).toInt();
    w.bookId = q.value(QLatin1String("book_id")).toInt();
    w.text = q.value(QLatin1String("word")).toString();
    w.phonetic = q.value(QLatin1String("phonetic")).toString();
    const QJsonArray ms = QJsonDocument::fromJson(
        q.value(QLatin1String("meanings")).toString().toUtf8()).array();
    for (const QJsonValue &v : ms) {
        const QJsonObject o = v.toObject();
        Meaning m;
        m.pos = o.value(QLatin1String("pos")).toString();
        m.meaning = o.value(QLatin1String("meaning")).toString();
        w.meanings << m;
    }
    const QJsonArray es = QJsonDocument::fromJson(
        q.value(QLatin1String("examples")).toString().toUtf8()).array();
    for (const QJsonValue &v : es) {
        const QJsonObject o = v.toObject();
        Example e;
        e.text = o.value(QLatin1String("text")).toString();
        // 兼容 trans / translation 两种字段名
        e.translation = o.value(QLatin1String("translation")).toString(
            o.value(QLatin1String("trans")).toString());
        w.examples << e;
    }
    return w;
}
}  // namespace

std::optional<Word> Repository::getWord(int wordId) const {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String("SELECT * FROM words WHERE id=?"));
    q.addBindValue(wordId);
    if (!q.exec() || !q.next())
        return std::nullopt;
    return rowToWord(q);
}

int Repository::countWords() const {
    const auto id = getActiveBookId();
    if (!id)
        return 0;
    return countWordsInBook(*id);
}

int Repository::countLearned() const {
    const auto id = getActiveBookId();
    if (!id)
        return 0;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
        "WHERE w.book_id=?"));
    q.addBindValue(*id);
    q.exec();
    return q.next() ? q.value(0).toInt() : 0;
}

int Repository::countStatus(const QString &status) const {
    const auto id = getActiveBookId();
    if (!id)
        return 0;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
        "WHERE w.book_id=? AND s.status=?"));
    q.addBindValue(*id);
    q.addBindValue(status);
    q.exec();
    return q.next() ? q.value(0).toInt() : 0;
}

int Repository::countDue(const QDate &today) const {
    const auto id = getActiveBookId();
    if (!id)
        return 0;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
        "WHERE w.book_id=? AND s.due_date IS NOT NULL AND s.due_date<=?"));
    q.addBindValue(*id);
    q.addBindValue(dateStr(today));
    q.exec();
    return q.next() ? q.value(0).toInt() : 0;
}

int Repository::countReviewedToday(const QDate &today) const {
    const auto id = getActiveBookId();
    if (!id)
        return 0;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT COUNT(*) FROM study_state s JOIN words w ON w.id=s.word_id "
        "WHERE w.book_id=? AND s.last_review=?"));
    q.addBindValue(*id);
    q.addBindValue(dateStr(today));
    q.exec();
    return q.next() ? q.value(0).toInt() : 0;
}

QList<Word> Repository::getNewWords(int limit) const {
    QList<Word> out;
    const auto id = getActiveBookId();
    if (!id)
        return out;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT w.* FROM words w LEFT JOIN study_state s ON s.word_id=w.id "
        "WHERE w.book_id=? AND s.word_id IS NULL ORDER BY RANDOM() LIMIT ?"));
    q.addBindValue(*id);
    q.addBindValue(limit);
    if (!q.exec())
        return out;
    while (q.next())
        out << rowToWord(q);
    return out;
}

QList<Word> Repository::getDueWords(const QDate &today, int limit) const {
    QList<Word> out;
    const auto id = getActiveBookId();
    if (!id)
        return out;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "SELECT w.* FROM words w JOIN study_state s ON s.word_id=w.id "
        "WHERE w.book_id=? AND s.due_date IS NOT NULL AND s.due_date<=? "
        "ORDER BY s.due_date, RANDOM() LIMIT ?"));
    q.addBindValue(*id);
    q.addBindValue(dateStr(today));
    q.addBindValue(limit);
    if (!q.exec())
        return out;
    while (q.next())
        out << rowToWord(q);
    return out;
}

QList<Word> Repository::getAllWords() const {
    QList<Word> out;
    const auto id = getActiveBookId();
    if (!id)
        return out;
    QSqlQuery q(m_db);
    q.prepare(QLatin1String("SELECT * FROM words WHERE book_id=? ORDER BY id"));
    q.addBindValue(*id);
    if (!q.exec())
        return out;
    while (q.next())
        out << rowToWord(q);
    return out;
}

// ------------------------------------------------------------------ 状态
std::optional<WordState> Repository::getState(int wordId) const {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String("SELECT * FROM study_state WHERE word_id=?"));
    q.addBindValue(wordId);
    if (!q.exec() || !q.next())
        return std::nullopt;
    WordState st;
    st.wordId = q.value(QLatin1String("word_id")).toInt();
    st.status = q.value(QLatin1String("status")).toString();
    st.ease = q.value(QLatin1String("ease")).toDouble();
    st.interval = q.value(QLatin1String("interval")).toInt();
    st.reps = q.value(QLatin1String("reps")).toInt();
    st.lapses = q.value(QLatin1String("lapses")).toInt();
    st.dueDate = dateFrom(q.value(QLatin1String("due_date")));
    st.lastReview = dateFrom(q.value(QLatin1String("last_review")));
    st.reviews = q.value(QLatin1String("reviews")).toInt();
    st.correct = q.value(QLatin1String("correct")).toInt();
    return st;
}

void Repository::saveState(const WordState &state, bool passed,
                           const QDate &today) {
    Q_UNUSED(passed)
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "INSERT INTO study_state(word_id, status, ease, interval, reps, lapses,"
        " due_date, last_review, reviews, correct) VALUES(?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(word_id) DO UPDATE SET status=excluded.status,"
        " ease=excluded.ease, interval=excluded.interval,"
        " reps=excluded.reps, lapses=excluded.lapses,"
        " due_date=excluded.due_date, last_review=excluded.last_review,"
        " reviews=excluded.reviews, correct=excluded.correct"));
    q.addBindValue(state.wordId);
    q.addBindValue(bindText(state.status));
    q.addBindValue(state.ease);
    q.addBindValue(state.interval);
    q.addBindValue(state.reps);
    q.addBindValue(state.lapses);
    q.addBindValue(dateStr(state.dueDate));
    q.addBindValue(dateStr(today));
    q.addBindValue(state.reviews);
    q.addBindValue(state.correct);
    q.exec();
}

void Repository::resetProgress() {
    const auto id = getActiveBookId();
    QSqlQuery q(m_db);
    if (id) {
        q.prepare(QLatin1String(
            "DELETE FROM study_state WHERE word_id IN "
            "(SELECT id FROM words WHERE book_id=?)"));
        q.addBindValue(*id);
        q.exec();
        // 会话快照与已背组数按词书隔离，只清当前词书的键（含旧版全局键）
        q.prepare(QLatin1String(
            "DELETE FROM meta WHERE key IN (?,?,?,"
            "'session_new','session_review','completed_batches')"));
        q.addBindValue(QStringLiteral("session_new:%1").arg(*id));
        q.addBindValue(QStringLiteral("session_review:%1").arg(*id));
        q.addBindValue(QStringLiteral("completed_batches:%1").arg(*id));
        q.exec();
    } else {
        q.exec(QLatin1String("DELETE FROM study_state"));
        q.exec(QLatin1String(
            "DELETE FROM meta WHERE key LIKE 'session_new%' "
            "OR key LIKE 'session_review%' OR key LIKE 'completed_batches%'"));
    }
}

// ------------------------------------------------------------------ 元数据
QString Repository::getMeta(const QString &key) const {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String("SELECT value FROM meta WHERE key=?"));
    q.addBindValue(key);
    if (!q.exec() || !q.next())
        return QString();
    return q.value(0).toString();
}

void Repository::setMeta(const QString &key, const QString &value) {
    QSqlQuery q(m_db);
    q.prepare(QLatin1String(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value"));
    q.addBindValue(key);
    q.addBindValue(bindText(value));
    q.exec();
}

StatsSummary Repository::statsSummary(const QDate &today) const {
    StatsSummary s;
    s.total = countWords();
    s.learned = countLearned();
    s.learning = countStatus(QString::fromLatin1(STATUS_LEARNING));
    s.mastered = countStatus(QString::fromLatin1(STATUS_MASTERED));
    s.due = countDue(today);
    s.reviewedToday = countReviewedToday(today);
    return s;
}

void Repository::clearLibrary() {
    QSqlQuery q(m_db);
    q.exec(QLatin1String("DELETE FROM study_state"));
    q.exec(QLatin1String("DELETE FROM words"));
    q.exec(QLatin1String("DELETE FROM books"));
    q.exec(QLatin1String(
        "DELETE FROM meta WHERE key='active_book_id' "
        "OR key LIKE 'session_new%' OR key LIKE 'session_review%' "
        "OR key LIKE 'completed_batches%'"));
}

}  // namespace wordmem
