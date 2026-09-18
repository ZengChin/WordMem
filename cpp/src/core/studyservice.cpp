#include "core/studyservice.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRandomGenerator>
#include <QSqlQuery>

namespace wordmem {

StudyService::StudyService(Repository &repo, int batchSize, int requeueGap)
    : repo(repo),
      batchSize(qMax(1, batchSize)),
      requeueGap(qMax(0, requeueGap)) {}

// ------------------------------------------------------------ 会话管理
StudySession StudyService::startSession(const QString &mode,
                                        const QDate &today) {
    StudySession session;
    session.mode = mode;
    QList<Word> words;
    if (mode == QLatin1String("new"))
        words = repo.getNewWords(batchSize);
    else if (mode == QLatin1String("review"))
        words = repo.getDueWords(today, batchSize);
    for (const Word &w : words) {
        SessionItem it;
        it.word = w;
        it.state = repo.getState(w.id);
        session.items << it;
    }
    return session;
}

// 会话快照按活动词书隔离：多词书共用 words 表且 word_id 全局唯一，
// 若键名不带 book_id，切词书后 resume 会命中旧词书的词，把进度写错地方。
QString StudyService::sessionKey(const QString &mode) const {
    const auto id = repo.getActiveBookId();
    return QStringLiteral("session_%1:%2")
        .arg(mode, id ? QString::number(*id) : QStringLiteral("None"));
}

QString StudyService::batchesKey() const {
    const auto id = repo.getActiveBookId();
    return QStringLiteral("completed_batches:%1")
        .arg(id ? QString::number(*id) : QStringLiteral("None"));
}

void StudyService::saveSession(const StudySession &session) {
    QJsonObject data;
    data.insert(QLatin1String("mode"), session.mode);
    data.insert(QLatin1String("index"), session.index);
    data.insert(QLatin1String("passed"), session.passed);
    data.insert(QLatin1String("failed"), session.failed);
    data.insert(QLatin1String("done"), session.done);
    QJsonArray items;
    for (const SessionItem &it : session.items) {
        QJsonObject o;
        o.insert(QLatin1String("id"), it.word.id);
        o.insert(QLatin1String("requeued"), it.requeued);
        items << o;
    }
    data.insert(QLatin1String("items"), items);
    repo.setMeta(sessionKey(session.mode),
                 QString::fromUtf8(
                     QJsonDocument(data).toJson(QJsonDocument::Compact)));
}

void StudyService::clearSession(const QString &mode) {
    repo.setMeta(sessionKey(mode), QString());
}

std::optional<StudySession> StudyService::resumeSession(const QString &mode) {
    const QString raw = repo.getMeta(sessionKey(mode));
    if (raw.isEmpty())
        return std::nullopt;
    QJsonParseError err{};
    const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &err);
    if (err.error != QJsonParseError::NoError || !doc.isObject()) {
        clearSession(mode);
        return std::nullopt;
    }
    const QJsonObject data = doc.object();
    if (data.value(QLatin1String("mode")).toString() != mode)
        return std::nullopt;

    StudySession session;
    session.mode = mode;
    const QJsonArray arr = data.value(QLatin1String("items")).toArray();
    for (const QJsonValue &v : arr) {
        const QJsonObject o = v.toObject();
        const auto w = repo.getWord(o.value(QLatin1String("id")).toInt());
        if (!w) {  // 词库已更换，旧会话失效
            clearSession(mode);
            return std::nullopt;
        }
        SessionItem it;
        it.word = *w;
        it.state = repo.getState(w->id);
        it.requeued = o.value(QLatin1String("requeued")).toBool(false);
        session.items << it;
    }
    session.index = qMin(data.value(QLatin1String("index")).toInt(0),
                         int(session.items.size()));
    session.passed = data.value(QLatin1String("passed")).toInt(0);
    session.failed = data.value(QLatin1String("failed")).toInt(0);
    session.done = data.value(QLatin1String("done")).toInt(0);
    if (session.finished()) {  // 已完成但未清除的异常残留
        clearSession(mode);
        return std::nullopt;
    }
    return session;
}

int StudyService::completedBatches() const {
    const QString raw = repo.getMeta(batchesKey());
    if (raw.isEmpty())
        return 0;
    bool ok = false;
    const int n = raw.toInt(&ok);
    return ok ? n : 0;
}

void StudyService::completeSession(const StudySession &session) {
    clearSession(session.mode);
    if (session.mode == QLatin1String("new"))
        repo.setMeta(batchesKey(), QString::number(completedBatches() + 1));
}

void StudyService::advance(StudySession &session) { session.index += 1; }

// ------------------------------------------------------------ 判分调度
GradeResult StudyService::grade(StudySession &session, const SessionItem &item,
                                int quality, const QDate &today) {
    // 先复制入参：答错重现会向 items 插入元素，可能使该引用失效
    const SessionItem cur = item;
    const bool passed = quality >= PASS_THRESHOLD;
    WordState state = cur.requeued
                          ? cur.state.value_or(WordState{cur.word.id})
                          : nextSchedule(cur.state, quality, today);
    state.wordId = cur.word.id;
    state.reviews += 1;
    if (passed)
        state.correct += 1;
    repo.saveState(state, passed, today);

    bool requeued = false;
    if (!passed) {
        // 答错：隔 requeueGap~requeueGap+1 个词后随机重新排入本组，直到答对
        const int insertAt = qMin(session.index + 1 + requeueOffset(),
                                  int(session.items.size()));
        SessionItem copy;
        copy.word = cur.word;
        copy.state = state;
        copy.requeued = true;
        session.items.insert(insertAt, copy);
        requeued = true;
    }

    if (!cur.requeued) {  // 仅首次作答计入唯一词统计
        if (passed)
            session.passed += 1;
        else
            session.failed += 1;
    }
    if (passed)
        session.done += 1;  // 进度：仅「记住」才推进；答错会重现，不计入
    return GradeResult{state, requeued};
}

int StudyService::requeueOffset() const {
    if (requeueOffsetFn)
        return requeueOffsetFn();
    const int base = requeueGap;
    if (base <= 0)
        return 0;
    return QRandomGenerator::global()->bounded(base, base + 2);  // [base, base+1]
}

// ------------------------------------------------------------ 统计
HomeSummary StudyService::homeSummary(const QDate &today) {
    HomeSummary s;
    s.total = repo.countWords();
    s.learned = repo.countLearned();
    s.newLeft = s.total - s.learned;
    s.reviewLeft = repo.countDue(today);
    s.completedBatches = completedBatches();
    return s;
}

}  // namespace wordmem
