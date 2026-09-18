#include "core/models.h"

#include <QtMath>

namespace wordmem {

QString Meaning::label() const {
    QString s = pos;
    if (!s.isEmpty() && !meaning.isEmpty())
        s += QLatin1Char(' ');
    s += meaning;
    return s.trimmed();
}

int StudySession::total() const {
    int n = 0;
    for (const SessionItem &it : items)
        if (!it.requeued)
            ++n;
    return n;
}

int StudySession::position() const { return qMin(done + 1, total()); }

bool StudySession::finished() const { return index >= int(items.size()); }

const SessionItem *StudySession::current() const {
    if (finished())
        return nullptr;
    return &items[index];
}

SessionItem *StudySession::current() {
    if (finished())
        return nullptr;
    return &items[index];
}

namespace {
double efDelta(int quality) {
    // 作答质量越高，难度因子增量越大（后续复习越轻松）
    const double d = 5 - quality;
    return 0.1 - d * (0.08 + d * 0.02);
}
}  // namespace

WordState nextSchedule(std::optional<WordState> in, int quality,
                       const QDate &today) {
    WordState st = in.value_or(WordState{});
    if (quality < PASS_THRESHOLD) {  // 忘记：重置连续答对，缩短间隔
        st.lapses += 1;
        st.reps = 0;
        st.interval = FIRST_INTERVAL;
    } else {  // 记得：按难度因子拉长间隔
        st.reps += 1;
        if (st.reps == 1)
            st.interval = FIRST_INTERVAL;
        else if (st.reps == 2)
            st.interval = SECOND_INTERVAL;
        else if (st.reps == 3)
            st.interval = THIRD_INTERVAL;
        else
            st.interval = qRound(st.interval * st.ease);
    }
    // 依据本次质量更新难度因子（下限 EF_MIN），须在计算间隔之后
    st.ease = qMax(EF_MIN, st.ease + efDelta(quality));
    st.status = (st.interval >= MATURITY_DAYS)
                    ? QString::fromLatin1(STATUS_MASTERED)
                    : QString::fromLatin1(STATUS_LEARNING);
    st.dueDate = today.addDays(st.interval);
    st.lastReview = today;
    return st;
}

}  // namespace wordmem
