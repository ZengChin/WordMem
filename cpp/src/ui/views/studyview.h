// 背单词页：出题态（单词+音标）与作答态（释义+例句轮播），含判分调度。
// 对应 Python ui/views/study_view.py。
#pragma once

#include <QWidget>

#include "core/models.h"
#include "ui/widgets.h"

class QLabel;
class QVBoxLayout;

namespace wordmem {

struct AppContext;
class FontToggle;

// 将例句中的目标词加粗显示（富文本）
QString boldHeadword(const QString &sentence, const QString &word);

class StudyView : public QWidget {
    Q_OBJECT
public:
    StudyView(AppContext &ctx, QWidget *parent = nullptr);

    // 开始一组新的学习会话
    void begin(const StudySession &session);
    const StudySession &session() const;

signals:
    void backRequested();
    void spellRequested();  // 完成页点击「开始拼写」

protected:
    void showEvent(QShowEvent *event) override;

private:
    void showIdle();
    void setMeaningsVisible(bool visible);
    void showQuestion();
    void updateProgress();
    void showAnswer(bool knownClicked);
    void renderExample();
    void switchExample(int delta);
    void onLeft();
    void onRight();
    void gradeAndAdvance(bool passed);
    int quality(bool passed) const;
    void showDone();
    void pronounce();
    void cycleFont();
    void applyFontScale();

    AppContext &m_ctx;
    StudySession m_session;
    const SessionItem *m_currentItem = nullptr;
    bool m_knownClicked = false;  // 出题态点了「已认识」还是「不认识」
    bool m_answerMode = false;    // 是否处于作答态
    int m_exampleIndex = 0;

    IconButton *m_btnBack = nullptr;
    FontToggle *m_btnFont = nullptr;
    QLabel *m_wordLabel = nullptr;
    IconButton *m_btnSpeaker = nullptr;
    QLabel *m_phonetic = nullptr;
    QVBoxLayout *m_meaningBox = nullptr;
    QList<QLabel *> m_meaningLabels;
    Card *m_exampleCard = nullptr;
    QLabel *m_exampleText = nullptr;
    QLabel *m_exampleTrans = nullptr;
    Dots *m_dots = nullptr;
    IconButton *m_btnPrev = nullptr;
    IconButton *m_btnNext = nullptr;
    QLabel *m_doneLabel = nullptr;
    QLabel *m_doneSummary = nullptr;
    QLabel *m_progressLabel = nullptr;
    SmoothBar *m_bar = nullptr;
    PillButton *m_btnLeft = nullptr;
    PillButton *m_btnRight = nullptr;
};

// Aa 字号切换按钮（复用图标按钮的悬停效果）
class FontToggle : public IconButton {
    Q_OBJECT
public:
    explicit FontToggle(QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *event) override;
};

}  // namespace wordmem
