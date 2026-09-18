// 拼写练习页：显示中文释义与发音，用户输入英文拼写，回车校验，空格提示。
// 对应 Python ui/views/spell_view.py。
#pragma once

#include <QLineEdit>
#include <QWidget>

#include <functional>

#include "core/models.h"

class QLabel;
class QTimer;

namespace wordmem {

struct AppContext;
class IconButton;
class PillButton;
class SmoothBar;

// 会话内去重后的拼写单词列表（按首次出现顺序）
QList<Word> spellWords(const StudySession &session);

// 拼写输入框：回车提交校验，空格显示英文提示
class SpellInput : public QLineEdit {
    Q_OBJECT
public:
    explicit SpellInput(QWidget *parent = nullptr);

signals:
    void submitRequested();
    void hintRequested();

protected:
    void keyPressEvent(QKeyEvent *event) override;
};

class SpellView : public QWidget {
    Q_OBJECT
public:
    SpellView(AppContext &ctx, QWidget *parent = nullptr);

    // 以本次会话去重后的单词开始拼写练习
    void begin(const StudySession &session);

signals:
    void backRequested();

protected:
    void showEvent(QShowEvent *event) override;

private:
    void showIdle();
    void loadWord();
    void submit();
    void showHint();
    void next();
    void pronounce();
    void setFeedback(const QString &text, const QString &color, int ms,
                     const std::function<void()> &onDone);
    void hideFeedback(bool clearInput);
    void clearTimer();
    void clearFeedback();
    void showDone();

    AppContext &m_ctx;
    QList<Word> m_words;
    int m_index = 0;
    int m_correctCount = 0;   // 拼写正确的词数
    int m_firstTryOk = 0;     // 一次即拼对的词数
    int m_missed = 0;         // 曾拼错的词数
    bool m_wordAttempted = false;  // 当前词是否拼错过
    bool m_locked = false;         // 正确反馈期间锁定输入
    QTimer *m_feedbackTimer = nullptr;

    IconButton *m_btnBack = nullptr;
    QLabel *m_progressLabel = nullptr;
    QLabel *m_meaningLabel = nullptr;
    IconButton *m_btnSpeaker = nullptr;
    QLabel *m_phonetic = nullptr;
    SpellInput *m_inputEdit = nullptr;
    QLabel *m_feedbackLabel = nullptr;
    QLabel *m_doneLabel = nullptr;
    QLabel *m_doneSummary = nullptr;
    SmoothBar *m_bar = nullptr;
    PillButton *m_btnFinish = nullptr;
};

}  // namespace wordmem
