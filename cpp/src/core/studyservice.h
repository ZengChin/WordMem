// 业务服务层：学习会话编排与记忆曲线调度（对应 Python core/study_service.py）。
#pragma once

#include <QDate>
#include <QString>
#include <functional>
#include <optional>

#include "core/models.h"
#include "core/repository.h"

namespace wordmem {

struct GradeResult {
    WordState state;
    bool requeued = false;
};

struct HomeSummary {
    int total = 0;
    int learned = 0;
    int newLeft = 0;
    int reviewLeft = 0;
    int completedBatches = 0;
};

class StudyService {
public:
    StudyService(Repository &repo, int batchSize = 20, int requeueGap = 3);

    // ------------------------------------------------------------ 会话管理
    // mode: "new"（学新词）或 "review"（复习词），非法模式返回空会话
    StudySession startSession(const QString &mode,
                              const QDate &today = QDate::currentDate());
    void saveSession(const StudySession &session);
    void clearSession(const QString &mode);
    std::optional<StudySession> resumeSession(
        const QString &mode);
    int completedBatches() const;
    void completeSession(const StudySession &session);
    void advance(StudySession &session);  // 推进到下一词

    // ------------------------------------------------------------ 判分调度
    // item 以 const 引用传入：内部会复制，重现插入不会破坏调用方数据
    GradeResult grade(StudySession &session, const SessionItem &item,
                      int quality, const QDate &today = QDate::currentDate());

    // ------------------------------------------------------------ 统计
    HomeSummary homeSummary(const QDate &today = QDate::currentDate());

    // 测试注入点：覆盖答错重现间隔（默认 [requeueGap, requeueGap+1] 随机）
    std::function<int()> requeueOffsetFn;
    int requeueOffset() const;  // 公开以便单测断言随机区间

    Repository &repo;
    int batchSize = 20;
    int requeueGap = 3;

private:
    QString sessionKey(const QString &mode) const;
    QString batchesKey() const;
};

}  // namespace wordmem
