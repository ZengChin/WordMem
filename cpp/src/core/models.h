// 领域模型：词书、单词、学习状态与学习会话（对应 Python core/models.py）。
#pragma once

#include <QDate>
#include <QList>
#include <QString>
#include <optional>

namespace wordmem {

// 状态常量
inline constexpr const char *STATUS_NEW = "new";
inline constexpr const char *STATUS_LEARNING = "learning";
inline constexpr const char *STATUS_MASTERED = "mastered";

// SM-2 记忆调度参数
inline constexpr double EF_INIT = 2.5;
inline constexpr double EF_MIN = 1.3;
inline constexpr int FIRST_INTERVAL = 0;   // 首次答对当天即进入复习列表
inline constexpr int SECOND_INTERVAL = 2;
inline constexpr int THIRD_INTERVAL = 6;
inline constexpr int MATURITY_DAYS = 21;   // 间隔达到该天数视为已掌握
inline constexpr int PASS_THRESHOLD = 3;   // 质量分 >= 该值视为答对

// 作答质量分（映射自 UI 的四种作答路径）
inline constexpr int GRADE_AGAIN = 1;      // 忘记：不认识 / 记错了
inline constexpr int GRADE_HARD = 3;       // 看答案才想起
inline constexpr int GRADE_GOOD = 5;       // 本来就会

struct Meaning {
    QString pos;      // 词性，如 "n." "a." "v."
    QString meaning;  // 中文释义
    QString label() const;
};

struct Example {
    QString text;         // 英文例句/短语
    QString translation;  // 中文翻译
};

struct Word {
    int id = 0;
    int bookId = 0;
    QString text;
    QString phonetic;
    QList<Meaning> meanings;
    QList<Example> examples;
};

struct Book {
    int id = 0;
    QString name;
    QString description;
    QString source = QStringLiteral("builtin");  // builtin / imported
    QString filePath;                            // imported 词书的源文件路径
    int wordCount = 0;
};

struct WordState {
    int wordId = 0;
    QString status = QString::fromLatin1(STATUS_NEW);
    double ease = EF_INIT;  // SM-2 难度因子
    int interval = 0;       // 当前复习间隔（天）
    int reps = 0;           // 连续答对次数
    int lapses = 0;         // 遗忘（答错）次数
    QDate dueDate;          // 无效 QDate == 无到期日
    QDate lastReview;
    int reviews = 0;        // 累计作答次数
    int correct = 0;        // 累计答对次数
};

struct SessionItem {
    Word word;
    std::optional<WordState> state;
    bool requeued = false;  // 是否为组内重现的副本
};

class StudySession {
public:
    QString mode;  // "new" | "review"
    QList<SessionItem> items;
    int index = 0;   // 当前下标（沿含重现副本的完整序列推进）
    int passed = 0;  // 首次作答即答对的唯一词数
    int failed = 0;  // 首次作答答错的唯一词数
    int done = 0;    // 已记住（答对）的唯一词数，用于进度展示

    int total() const;     // 本组唯一词数（重现副本不计入）
    int position() const;  // 人类可读进度（已记住词数 + 1）
    bool finished() const;
    const SessionItem *current() const;
    SessionItem *current();
};

// 按 SM-2 算法根据作答质量计算新的学习状态（纯函数，便于测试）。
WordState nextSchedule(std::optional<WordState> state, int quality,
                       const QDate &today);

}  // namespace wordmem
