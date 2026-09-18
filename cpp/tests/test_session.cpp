// 学习会话编排测试（对应 Python SessionTestCase）。
#include <QSet>
#include <QtTest>

#include "core/models.h"
#include "core/repository.h"
#include "core/studyservice.h"
#include "helpers.h"

using namespace wordmem;

namespace {
QList<int> positionsOf(const StudySession &s, int wordId) {
    QList<int> out;
    for (int i = 0; i < s.items.size(); ++i)
        if (s.items.at(i).word.id == wordId)
            out << i;
    return out;
}
}  // namespace

class TestSession : public QObject {
    Q_OBJECT
private slots:
    void init();
    void newSessionBatch();
    void requeueInsertsAfterGap();
    void requeueRepeatsUntilCorrect();
    void requeuedAttemptDoesNotChangeEase();
    void requeueGapIsRandomized();
    void finishSession();
    void reviewModeEmpty();
    void homeSummary();
    void sessionSnapshotRoundTrip();
    void completeSessionCountsBatch();

private:
    QScopedPointer<Repository> m_repo;
    QScopedPointer<StudyService> m_svc;
    QDate m_today = QDate::currentDate();
};

void TestSession::init() {
    m_repo.reset(new Repository(QStringLiteral(":memory:")));
    m_repo->addWords(m_repo->addBook(QStringLiteral("测试词书")),
                     testing::makeWords(30));
    // 注入确定性重现间隔：恒为基数 2，位置断言稳定
    m_svc.reset(new StudyService(*m_repo, 20, 2));
    m_svc->requeueOffsetFn = [] { return 2; };
}

void TestSession::newSessionBatch() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    QCOMPARE(s.total(), 20);
    QCOMPARE(s.position(), 1);
    QVERIFY(!s.finished());
    QVERIFY(s.current() != nullptr);
}

void TestSession::requeueInsertsAfterGap() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    const int wid = s.current()->word.id;
    const GradeResult r = m_svc->grade(s, s.items.at(0), GRADE_AGAIN, m_today);
    QVERIFY(r.requeued);
    m_svc->advance(s);
    // 显示总数保持本组唯一词数，不随重现增长；序列长度含重现副本
    QCOMPARE(s.total(), 20);
    QCOMPARE(int(s.items.size()), 21);
    // gap=2：原词在下标 0，重现副本被插到下标 3（隔 2 个词后）
    QCOMPARE(positionsOf(s, wid), QList<int>({0, 3}));
}

void TestSession::requeueRepeatsUntilCorrect() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    const int wid = s.current()->word.id;

    m_svc->grade(s, s.items.at(0), GRADE_AGAIN, m_today);  // 首次答错
    QCOMPARE(s.total(), 20);
    QCOMPARE(int(s.items.size()), 21);

    s.index = 3;                                            // 重现位再答错
    m_svc->grade(s, s.items.at(3), GRADE_AGAIN, m_today);
    QCOMPARE(int(s.items.size()), 22);

    const QList<int> pos = positionsOf(s, wid);
    s.index = pos.last();                                   // 最新副本答对
    m_svc->grade(s, s.items.at(s.index), GRADE_GOOD, m_today);
    QCOMPARE(int(s.items.size()), 22);  // 答对不再重现

    QCOMPARE(s.total(), 20);
    QCOMPARE(s.failed, 1);   // 唯一词统计只算首次作答（此词首次答错）
    QCOMPARE(s.passed, 0);
    QCOMPARE(s.done, 1);     // 进度按「记住」推进

    const auto saved = m_repo->getState(wid);
    QVERIFY(saved.has_value());
    QCOMPARE(saved->lapses, 1);
    QCOMPARE(saved->reps, 0);
    QCOMPARE(saved->interval, FIRST_INTERVAL);
    QCOMPARE(saved->reviews, 3);
    QCOMPARE(saved->correct, 1);
}

void TestSession::requeuedAttemptDoesNotChangeEase() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    const int wid = s.current()->word.id;
    m_svc->grade(s, s.items.at(0), GRADE_AGAIN, m_today);
    const double easeAfterFirst = m_repo->getState(wid)->ease;
    // 组内重现副本再次答错，不应继续降低难度因子
    s.index = 3;
    m_svc->grade(s, s.items.at(3), GRADE_AGAIN, m_today);
    QVERIFY(qAbs(m_repo->getState(wid)->ease - easeAfterFirst) < 1e-9);
}

void TestSession::requeueGapIsRandomized() {
    // 默认基数 3：重现间隔随机落在 {3, 4}，而非写死 3
    StudyService svc(*m_repo, 20, 3);
    QSet<int> offsets;
    for (int i = 0; i < 60; ++i)
        offsets.insert(svc.requeueOffset());
    QCOMPARE(offsets, QSet<int>({3, 4}));
}

void TestSession::finishSession() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    while (!s.finished()) {
        m_svc->grade(s, *s.current(), GRADE_GOOD, m_today);
        m_svc->advance(s);
    }
    QVERIFY(s.finished());
    QCOMPARE(s.passed, 20);
    QCOMPARE(s.done, 20);
    QCOMPARE(m_repo->countLearned(), 20);
    QCOMPARE(s.position(), 20);
}

void TestSession::reviewModeEmpty() {
    const StudySession s =
        m_svc->startSession(QStringLiteral("review"), m_today);
    QCOMPARE(s.total(), 0);
    QVERIFY(s.finished());
}

void TestSession::homeSummary() {
    const HomeSummary sum = m_svc->homeSummary(m_today);
    QCOMPARE(sum.total, 30);
    QCOMPARE(sum.newLeft, 30);
    QCOMPARE(sum.reviewLeft, 0);
    QCOMPARE(sum.completedBatches, 0);
}

void TestSession::sessionSnapshotRoundTrip() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    m_svc->grade(s, s.items.at(0), GRADE_AGAIN, m_today);
    m_svc->advance(s);
    m_svc->saveSession(s);

    const auto restored = m_svc->resumeSession(QStringLiteral("new"));
    QVERIFY(restored.has_value());
    QCOMPARE(restored->mode, QStringLiteral("new"));
    QCOMPARE(restored->items.size(), s.items.size());
    QCOMPARE(restored->index, s.index);
    QCOMPARE(restored->failed, s.failed);
    QVERIFY(restored->items.at(3).requeued);
    // 快照按活动词书隔离：另一模式不受影响
    QVERIFY(!m_svc->resumeSession(QStringLiteral("review")).has_value());

    m_svc->clearSession(QStringLiteral("new"));
    QVERIFY(!m_svc->resumeSession(QStringLiteral("new")).has_value());
}

void TestSession::completeSessionCountsBatch() {
    StudySession s = m_svc->startSession(QStringLiteral("new"), m_today);
    while (!s.finished()) {
        m_svc->grade(s, *s.current(), GRADE_GOOD, m_today);
        m_svc->advance(s);
    }
    QCOMPARE(m_svc->completedBatches(), 0);
    m_svc->completeSession(s);  // 学新词整组背完记为一次已背组数
    QCOMPARE(m_svc->completedBatches(), 1);
    QVERIFY(!m_svc->resumeSession(QStringLiteral("new")).has_value());

    // 复习模式完成不计入已背组数
    StudySession r = m_svc->startSession(QStringLiteral("review"), m_today);
    while (!r.finished()) {
        m_svc->grade(r, *r.current(), GRADE_GOOD, m_today);
        m_svc->advance(r);
    }
    m_svc->completeSession(r);
    QCOMPARE(m_svc->completedBatches(), 1);
}

QTEST_GUILESS_MAIN(TestSession)
#include "test_session.moc"
