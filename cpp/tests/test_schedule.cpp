// SM-2 记忆调度纯函数测试（对应 Python RepoTestCase 中的调度断言）。
#include <QDate>
#include <QtTest>

#include "core/models.h"

using namespace wordmem;

class TestSchedule : public QObject {
    Q_OBJECT
private slots:
    void meaningLabelJoinsPosAndText();
    void firstPassSetsShortInterval();
    void hardPassAdvancesButLowersEase();
    void intervalProgressionToMastery();
    void lapseResetsRepsAndInterval();
};

void TestSchedule::meaningLabelJoinsPosAndText() {
    Meaning m{QStringLiteral("n."), QStringLiteral("苹果")};
    QCOMPARE(m.label(), QStringLiteral("n. 苹果"));
    Meaning bare{QString(), QStringLiteral("苹果")};
    QCOMPARE(bare.label(), QStringLiteral("苹果"));
}

void TestSchedule::firstPassSetsShortInterval() {
    const QDate today(2026, 1, 1);
    const WordState st = nextSchedule(std::nullopt, GRADE_GOOD, today);
    QCOMPARE(st.reps, 1);
    QCOMPARE(st.interval, FIRST_INTERVAL);
    QCOMPARE(st.status, QString::fromLatin1(STATUS_LEARNING));
    QCOMPARE(st.dueDate, today.addDays(FIRST_INTERVAL));
    QCOMPARE(st.lastReview, today);
    // 质量分 5 使难度因子上浮 0.1
    QVERIFY(qAbs(st.ease - (EF_INIT + 0.1)) < 1e-6);
}

void TestSchedule::hardPassAdvancesButLowersEase() {
    // 看答案才想起（GRADE_HARD）：仍算答对，但难度因子下降 0.14
    const QDate today(2026, 1, 1);
    const WordState st = nextSchedule(std::nullopt, GRADE_HARD, today);
    QCOMPARE(st.reps, 1);
    QCOMPARE(st.interval, FIRST_INTERVAL);
    QCOMPARE(st.status, QString::fromLatin1(STATUS_LEARNING));
    QVERIFY(qAbs(st.ease - (EF_INIT - 0.14)) < 1e-6);
}

void TestSchedule::intervalProgressionToMastery() {
    // 连续答对：间隔 0 -> 2 -> 6 -> round(6*ease) -> ... 直至成熟
    const QDate today(2026, 1, 1);
    std::optional<WordState> st;
    QList<int> intervals;
    for (int i = 0; i < 5; ++i) {
        st = nextSchedule(st, GRADE_GOOD, today);
        intervals << st->interval;
    }
    QCOMPARE(intervals.at(0), FIRST_INTERVAL);   // 0（当天即可复习）
    QCOMPARE(intervals.at(1), SECOND_INTERVAL);  // 2
    QCOMPARE(intervals.at(2), THIRD_INTERVAL);   // 6
    QCOMPARE(intervals.at(3), 17);               // round(6 * 2.8)
    QCOMPARE(intervals.at(4), 49);               // round(17 * 2.9)
    QVERIFY(st->interval >= MATURITY_DAYS);
    QCOMPARE(st->status, QString::fromLatin1(STATUS_MASTERED));
}

void TestSchedule::lapseResetsRepsAndInterval() {
    const QDate today(2026, 1, 1);
    std::optional<WordState> st = nextSchedule(std::nullopt, GRADE_GOOD, today);
    st = nextSchedule(st, GRADE_GOOD, today);
    const WordState lapsed = nextSchedule(st, GRADE_AGAIN, today);
    QCOMPARE(lapsed.reps, 0);
    QCOMPARE(lapsed.interval, FIRST_INTERVAL);
    QCOMPARE(lapsed.lapses, st->lapses + 1);
    QCOMPARE(lapsed.status, QString::fromLatin1(STATUS_LEARNING));
    QVERIFY(lapsed.ease < st->ease);  // 忘记会拉低难度因子
}

QTEST_APPLESS_MAIN(TestSchedule)
#include "test_schedule.moc"
