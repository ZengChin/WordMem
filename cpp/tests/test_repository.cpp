// 数据仓库与词书编排测试（对应 Python RepoTestCase / MigrationTestCase / SeedTestCase）。
#include <QFile>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QTemporaryDir>
#include <QtTest>

#include "core/bookmanager.h"
#include "core/models.h"
#include "core/paths.h"
#include "core/repository.h"
#include "helpers.h"
#include "testconfig.h"

using namespace wordmem;

namespace {
// 逐条执行以 ';' 分隔的建表脚本（Qt SQLite 驱动一次只准备单条语句）
void execScript(QSqlQuery &q, const QString &script) {
    const QStringList parts = script.split(QLatin1Char(';'), Qt::SkipEmptyParts);
    for (const QString &s : parts)
        q.exec(s.trimmed());
}
}  // namespace

class TestRepository : public QObject {
    Q_OBJECT
private slots:
    void seedCounts();
    void newWordsExcludeLearned();
    void firstPassPersists();
    void dueWordsAppearAfterInterval();
    void masteredWordReactivatesWhenDue();
    void metaRoundTrip();
    void bookIsolationAndDeleteRules();
    void migrateAddsColumnsAndBackfills();
    void builtinSeedIsIdempotent();
};

void TestRepository::seedCounts() {
    Repository repo(QStringLiteral(":memory:"));
    const QDate today = QDate::currentDate();
    const int bookId = repo.addBook(QStringLiteral("测试词书"),
                                    QStringLiteral("单元测试"));
    repo.addWords(bookId, testing::makeWords(30));
    QCOMPARE(repo.countWords(), 30);
    QCOMPARE(repo.countLearned(), 0);
    QCOMPARE(repo.countDue(today), 0);
    QCOMPARE(repo.listBooks().size(), 1);
    QCOMPARE(repo.getActiveBookId().value_or(0), bookId);  // 首本自动激活
}

void TestRepository::newWordsExcludeLearned() {
    Repository repo(QStringLiteral(":memory:"));
    const QDate today = QDate::currentDate();
    repo.addWords(repo.addBook(QStringLiteral("b")), testing::makeWords(30));

    const QList<Word> first = repo.getNewWords(20);
    QCOMPARE(first.size(), 20);

    WordState st = nextSchedule(std::nullopt, GRADE_GOOD, today);
    st.wordId = first.at(0).id;
    repo.saveState(st, true, today);

    const QList<Word> again = repo.getNewWords(20);
    for (const Word &w : again)
        QVERIFY(w.id != first.at(0).id);
}

void TestRepository::firstPassPersists() {
    Repository repo(QStringLiteral(":memory:"));
    const QDate today = QDate::currentDate();
    repo.addWords(repo.addBook(QStringLiteral("b")), testing::makeWords(30));

    const Word w = repo.getNewWords(1).at(0);
    WordState st = nextSchedule(std::nullopt, GRADE_GOOD, today);
    st.wordId = w.id;
    st.reviews += 1;
    st.correct += 1;
    repo.saveState(st, true, today);

    const auto saved = repo.getState(w.id);
    QVERIFY(saved.has_value());
    QCOMPARE(saved->reps, 1);
    QCOMPARE(saved->interval, FIRST_INTERVAL);
    QCOMPARE(saved->status, QString::fromLatin1(STATUS_LEARNING));
    QCOMPARE(saved->dueDate, today.addDays(FIRST_INTERVAL));
    QVERIFY(qAbs(saved->ease - (EF_INIT + 0.1)) < 1e-6);

    // 例句的 trans 字段名需被兼容读取为 translation
    const auto reloaded = repo.getWord(w.id);
    QVERIFY(reloaded.has_value());
    QCOMPARE(reloaded->meanings.size(), 1);
    QCOMPARE(reloaded->meanings.at(0).label(), QStringLiteral("n. 测试"));
    QCOMPARE(reloaded->examples.at(0).translation, QStringLiteral("测试"));
}

void TestRepository::dueWordsAppearAfterInterval() {
    Repository repo(QStringLiteral(":memory:"));
    const QDate today = QDate::currentDate();
    repo.addWords(repo.addBook(QStringLiteral("b")), testing::makeWords(30));

    const Word w = repo.getNewWords(1).at(0);
    WordState st = nextSchedule(std::nullopt, GRADE_GOOD, today);
    st.wordId = w.id;
    repo.saveState(st, true, today);

    QCOMPARE(repo.countDue(today.addDays(FIRST_INTERVAL - 1)), 0);
    QCOMPARE(repo.countDue(today.addDays(FIRST_INTERVAL)), 1);
    QCOMPARE(repo.countReviewedToday(today), 1);
}

void TestRepository::masteredWordReactivatesWhenDue() {
    Repository repo(QStringLiteral(":memory:"));
    const QDate today = QDate::currentDate();
    repo.addWords(repo.addBook(QStringLiteral("b")), testing::makeWords(30));

    const Word w = repo.getNewWords(1).at(0);
    std::optional<WordState> st;
    for (int i = 0; i < 5; ++i)
        st = nextSchedule(st, GRADE_GOOD, today);
    st->wordId = w.id;
    repo.saveState(*st, true, today);

    QCOMPARE(st->status, QString::fromLatin1(STATUS_MASTERED));
    QCOMPARE(repo.countDue(today), 0);              // 间隔未到期
    QCOMPARE(repo.countDue(st->dueDate), 1);        // 到期后重新唤醒
    QCOMPARE(repo.getDueWords(st->dueDate, 20).size(), 1);
}

void TestRepository::metaRoundTrip() {
    Repository repo(QStringLiteral(":memory:"));
    QVERIFY(repo.getMeta(QStringLiteral("nope")).isEmpty());
    repo.setMeta(QStringLiteral("k"), QStringLiteral("1"));
    QCOMPARE(repo.getMeta(QStringLiteral("k")), QStringLiteral("1"));
    repo.setMeta(QStringLiteral("k"), QStringLiteral("2"));  // upsert
    QCOMPARE(repo.getMeta(QStringLiteral("k")), QStringLiteral("2"));
    repo.setMeta(QStringLiteral("empty"), QString());
    QVERIFY(repo.getMeta(QStringLiteral("empty")).isEmpty());
}

void TestRepository::bookIsolationAndDeleteRules() {
    Repository repo(QStringLiteral(":memory:"));
    BookManager bm(repo);
    const int first = repo.addBook(QStringLiteral("书一"));
    repo.addWords(first, testing::makeWords(5));
    const int second = repo.addBook(QStringLiteral("书二"), QString(),
                                    QStringLiteral("imported"));
    repo.addWords(second, testing::makeWords(2));

    QCOMPARE(repo.countWords(), 5);  // 查询只看活动词书
    QVERIFY(bm.switchBook(second));
    QCOMPARE(repo.countWords(), 2);
    QCOMPARE(repo.getActiveBook()->name, QStringLiteral("书二"));
    QVERIFY(bm.switchBook(first));
    QCOMPARE(repo.countWords(), 5);

    QString err;
    QVERIFY(!bm.switchBook(999, &err));  // 不存在的词书
    QVERIFY(!bm.deleteBook(first, &err));  // 内置词书不可删除
    QVERIFY(err.contains(QStringLiteral("内置")));
    QVERIFY(bm.deleteBook(second, &err));
    QCOMPARE(repo.listBooks().size(), 1);
}

void TestRepository::migrateAddsColumnsAndBackfills() {
    static const char *kOldSchema = R"SQL(
    CREATE TABLE books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        word TEXT NOT NULL,
        phonetic TEXT NOT NULL DEFAULT '',
        meanings TEXT NOT NULL DEFAULT '[]',
        examples TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE study_state (
        word_id INTEGER PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'learning',
        level INTEGER NOT NULL DEFAULT 0,
        due_date TEXT,
        last_review TEXT,
        reviews INTEGER NOT NULL DEFAULT 0,
        correct INTEGER NOT NULL DEFAULT 0
    );
    )SQL";

    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString path = dir.path() + QLatin1String("/old.db");
    {
        QSqlDatabase db =
            QSqlDatabase::addDatabase(QLatin1String("QSQLITE"),
                                      QStringLiteral("legacy_conn"));
        db.setDatabaseName(path);
        QVERIFY(db.open());
        QSqlQuery q(db);
        execScript(q, QString(kOldSchema));
        q.exec(QLatin1String(
            "INSERT INTO books(id,name,description) VALUES(1,'b','')"));
        q.exec(QLatin1String(
            "INSERT INTO words(id,book_id,word) VALUES(1,1,'apple')"));
        q.exec(QLatin1String(
            "INSERT INTO study_state(word_id,status,level,due_date,reviews,correct)"
            " VALUES(1,'mastered',4,'2026-01-01',5,4)"));
        db.close();
    }
    QSqlDatabase::removeDatabase(QStringLiteral("legacy_conn"));

    Repository repo(path);  // 打开即触发迁移
    const auto state = repo.getState(1);
    QVERIFY(state.has_value());
    QVERIFY(qAbs(state->ease - EF_INIT) < 1e-6);
    QCOMPARE(state->reps, 4);       // 回填自旧 level
    QCOMPARE(state->interval, 7);   // level 4 -> 7 天
    QCOMPARE(state->status, QString::fromLatin1(STATUS_MASTERED));
    // books 表补齐的新列有默认值
    const auto book = repo.getBookById(1);
    QVERIFY(book.has_value());
    QCOMPARE(book->source, QStringLiteral("builtin"));
    QCOMPARE(book->wordCount, 0);
}

void TestRepository::builtinSeedIsIdempotent() {
    setResourceDataDir(QStringLiteral(WORDBOOK_DATA_DIR));
    if (!QFile::exists(builtinRegistryFile()))
        QSKIP("内置词书资源目录缺失（阶段 4 由 qrc 提供）");

    Repository repo(QStringLiteral(":memory:"));
    BookManager bm(repo);
    bm.registerBuiltinBooks();
    bm.registerBuiltinBooks();  // 幂等：重复注册不产生重复词书
    QVERIFY(!bm.listBuiltinBooks().isEmpty());

    bm.ensureDefaultActive();
    const auto active = bm.getActiveBook();
    QVERIFY(active.has_value());
    const int count = repo.countWords();
    QVERIFY(count > 0);
    bm.ensureDefaultActive();  // 已有活动词书 -> 不重复导入
    QCOMPARE(repo.countWords(), count);
}

QTEST_GUILESS_MAIN(TestRepository)
#include "test_repository.moc"
