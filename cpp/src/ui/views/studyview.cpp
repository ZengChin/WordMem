#include "ui/views/studyview.h"

#include <QFont>
#include <QHBoxLayout>
#include <QLabel>
#include <QPainter>
#include <QRegularExpression>
#include <QShowEvent>
#include <QSizePolicy>
#include <QVBoxLayout>

#include "core/settings.h"
#include "core/speaker.h"
#include "core/studyservice.h"
#include "ui/appcontext.h"
#include "ui/icons.h"
#include "ui/theme.h"
#include "ui/widgets.h"

namespace wordmem {

namespace {
const int kWordFontSizes[3] = {28, 34, 40};
const int kMeaningFontSizes[3] = {17, 20, 23};
}  // namespace

QString boldHeadword(const QString &sentence, const QString &word) {
    // 将例句中的目标词加粗显示（富文本）
    const QString escaped = sentence.toHtmlEscaped();
    if (word.isEmpty())
        return escaped;
    const QRegularExpression re(
        QStringLiteral("\\b(%1)\\b").arg(QRegularExpression::escape(word)),
        QRegularExpression::CaseInsensitiveOption);
    QString out = escaped;
    out.replace(re, QStringLiteral("<b>\\1</b>"));
    return out;
}

// ============================================================ StudyView
StudyView::StudyView(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(6, 0, 6, 2);
    lay->setSpacing(0);

    // ---- 顶部：返回 + 字号 ----
    auto *header = new QHBoxLayout;
    m_btnBack = new IconButton(QStringLiteral("back"), QStringLiteral("#5a6b72"), 30,
                               16, QStringLiteral("返回首页"), false, false, this);
    m_btnFont = new FontToggle(this);
    header->addWidget(m_btnBack);
    header->addStretch(1);
    header->addWidget(m_btnFont);
    lay->addLayout(header);
    lay->addSpacing(6);

    // ---- 单词区 ----
    m_wordLabel = new QLabel(QStringLiteral("word"), this);
    m_wordLabel->setStyleSheet(QStringLiteral("color:%1; font-weight:600;")
                                   .arg(QLatin1String(theme::INK)));
    m_wordLabel->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    lay->addWidget(m_wordLabel);
    lay->addSpacing(8);

    auto *phonRow = new QHBoxLayout;
    phonRow->setSpacing(6);
    m_btnSpeaker = new IconButton(QStringLiteral("speaker"),
                                  QStringLiteral("#41606d"), 28, 16,
                                  QStringLiteral("朗读单词"), false, false, this);
    m_phonetic = new QLabel(this);
    m_phonetic->setStyleSheet(QStringLiteral("color:%1; font-size:14px;")
                                  .arg(QLatin1String(theme::INK_SOFT)));
    phonRow->addWidget(m_btnSpeaker);
    phonRow->addWidget(m_phonetic);
    phonRow->addStretch(1);
    lay->addLayout(phonRow);
    lay->addSpacing(10);

    // ---- 释义区（作答态显示） ----
    m_meaningBox = new QVBoxLayout;
    m_meaningBox->setSpacing(6);
    lay->addLayout(m_meaningBox);
    lay->addSpacing(12);

    // ---- 例句卡片（作答态显示） ----
    m_exampleCard = new Card(150, 14, this);
    auto *exLay = new QVBoxLayout(m_exampleCard);
    exLay->setContentsMargins(18, 14, 14, 10);
    exLay->setSpacing(8);
    m_exampleText = new QLabel(m_exampleCard);
    m_exampleText->setWordWrap(true);
    m_exampleText->setTextFormat(Qt::RichText);
    m_exampleText->setStyleSheet(QStringLiteral("color:%1; font-size:15px;")
                                     .arg(QLatin1String(theme::INK_DARK)));
    m_exampleTrans = new QLabel(m_exampleCard);
    m_exampleTrans->setWordWrap(true);
    m_exampleTrans->setStyleSheet(
        QStringLiteral("color:#5a6a72; font-size:14px;"));
    auto *nav = new QHBoxLayout;
    m_dots = new Dots(m_exampleCard);
    m_btnPrev = new IconButton(QStringLiteral("back"), QStringLiteral("#5a6a72"), 26,
                               13, QStringLiteral("上一条例句"), false, false,
                               m_exampleCard);
    m_btnNext = new IconButton(QStringLiteral("chevron"), QStringLiteral("#5a6a72"),
                               26, 13, QStringLiteral("下一条例句"), false, false,
                               m_exampleCard);
    nav->addWidget(m_dots);
    nav->addStretch(1);
    nav->addWidget(m_btnPrev);
    nav->addWidget(m_btnNext);
    exLay->addWidget(m_exampleText);
    exLay->addWidget(m_exampleTrans);
    exLay->addSpacing(4);
    exLay->addLayout(nav);
    lay->addWidget(m_exampleCard);

    // ---- 完成态 ----
    m_doneLabel = new QLabel(QStringLiteral("本组完成"), this);
    m_doneLabel->setAlignment(Qt::AlignCenter);
    m_doneLabel->setStyleSheet(QStringLiteral("color:%1; font-size:24px;"
                                              " font-weight:600;")
                                   .arg(QLatin1String(theme::INK)));
    m_doneSummary = new QLabel(this);
    m_doneSummary->setAlignment(Qt::AlignCenter);
    m_doneSummary->setStyleSheet(QStringLiteral("color:%1; font-size:14px;")
                                     .arg(QLatin1String(theme::INK_SOFT)));
    lay->addWidget(m_doneLabel);
    lay->addWidget(m_doneSummary);

    lay->addStretch(1);

    // ---- 进度 ----
    m_progressLabel = new QLabel(QStringLiteral("0 / 0"), this);
    m_progressLabel->setAlignment(Qt::AlignCenter);
    m_progressLabel->setStyleSheet(QStringLiteral(
        "color:#5f7480; font-size:15px; font-weight:500;"));
    lay->addWidget(m_progressLabel);
    lay->addSpacing(4);
    m_bar = new SmoothBar(false, QStringLiteral("#f4edc9"), this);
    lay->addWidget(m_bar);
    lay->addSpacing(10);

    // ---- 底部操作按钮 ----
    auto *footer = new QHBoxLayout;
    footer->setSpacing(16);
    m_btnLeft = new PillButton(QStringLiteral("不认识"), QStringLiteral("alert"),
                               QLatin1String(theme::ORANGE), this);
    m_btnRight = new PillButton(QStringLiteral("已认识"), QStringLiteral("check"),
                                QLatin1String(theme::GREEN), this);
    footer->addWidget(m_btnLeft, 1);
    footer->addWidget(m_btnRight, 1);
    lay->addLayout(footer);

    // ---- 信号 ----
    connect(m_btnBack, &QAbstractButton::clicked, this, &StudyView::backRequested);
    connect(m_btnFont, &QAbstractButton::clicked, this, &StudyView::cycleFont);
    connect(m_btnSpeaker, &QAbstractButton::clicked, this, &StudyView::pronounce);
    connect(m_btnLeft, &QPushButton::clicked, this, &StudyView::onLeft);
    connect(m_btnRight, &QPushButton::clicked, this, &StudyView::onRight);
    connect(m_btnPrev, &QAbstractButton::clicked, this,
            [this] { switchExample(-1); });
    connect(m_btnNext, &QAbstractButton::clicked, this,
            [this] { switchExample(1); });

    showIdle();
}

const StudySession &StudyView::session() const { return m_session; }

void StudyView::showIdle() {
    m_wordLabel->hide();
    m_btnSpeaker->hide();
    m_phonetic->hide();
    setMeaningsVisible(false);
    m_exampleCard->hide();
    m_doneLabel->hide();
    m_doneSummary->hide();
    m_btnLeft->hide();
    m_btnRight->hide();
    m_progressLabel->hide();
    m_bar->hide();
}

void StudyView::setMeaningsVisible(bool visible) {
    for (QLabel *lb : m_meaningLabels)
        lb->setVisible(visible);
}

void StudyView::begin(const StudySession &session) {
    m_session = session;
    showQuestion();
}

// ------------------------------------------------------------ 出题态
void StudyView::showQuestion() {
    m_currentItem = m_session.current();
    if (m_currentItem == nullptr)
        return;
    m_answerMode = false;
    const Word &word = m_currentItem->word;

    m_doneLabel->hide();
    m_doneSummary->hide();
    setMeaningsVisible(false);
    m_exampleCard->hide();

    m_wordLabel->show();
    m_btnSpeaker->show();
    m_phonetic->show();
    m_wordLabel->setText(word.text);
    m_phonetic->setText(word.phonetic);

    m_btnLeft->setText(QStringLiteral("不认识"));
    m_btnLeft->setIcon(icon(QStringLiteral("alert"),
                            QLatin1String(theme::ORANGE_ICON), 20));
    m_btnRight->setText(QStringLiteral("已认识"));
    m_btnRight->setIcon(icon(QStringLiteral("check"),
                             QLatin1String(theme::GREEN_ICON), 20));

    updateProgress();
    m_btnLeft->show();
    m_btnRight->show();
    m_progressLabel->show();
    m_bar->show();

    if (m_ctx.config().autoPronounce)
        pronounce();
}

void StudyView::updateProgress() {
    m_progressLabel->setText(
        QStringLiteral("%1 / %2").arg(m_session.position()).arg(m_session.total()));
    m_bar->setFraction(static_cast<double>(m_session.position() - 1) /
                       qMax(1, m_session.total()));
}

// ------------------------------------------------------------ 作答态
void StudyView::showAnswer(bool knownClicked) {
    m_knownClicked = knownClicked;
    m_answerMode = true;
    const Word &word = m_currentItem->word;

    // 释义
    for (QLabel *lb : m_meaningLabels) {
        m_meaningBox->removeWidget(lb);
        lb->deleteLater();
    }
    m_meaningLabels.clear();
    for (const Meaning &m : word.meanings) {
        auto *lb = new QLabel(m.label(), this);
        lb->setStyleSheet(QStringLiteral("color:%1; font-weight:500;")
                              .arg(QLatin1String(theme::INK)));
        lb->setWordWrap(true);
        m_meaningBox->addWidget(lb);
        m_meaningLabels.append(lb);
    }
    setMeaningsVisible(true);

    // 例句
    m_exampleIndex = 0;
    renderExample();
    m_exampleCard->setVisible(!word.examples.isEmpty());

    // 按钮语义切换
    if (knownClicked) {
        m_btnLeft->setText(QStringLiteral("记错了"));
        m_btnLeft->setIcon(icon(QStringLiteral("undo"),
                                QLatin1String(theme::ORANGE_ICON), 20));
        m_btnLeft->show();
    } else {
        // 「不认识」路径：只保留「下一词」一个按钮
        m_btnLeft->hide();
    }
    m_btnRight->setText(QStringLiteral("下一词"));
    m_btnRight->setIcon(icon(QStringLiteral("arrow_right"),
                             QLatin1String(theme::GREEN_ICON), 20));
    applyFontScale();
}

void StudyView::renderExample() {
    if (m_currentItem == nullptr)
        return;
    const QList<Example> &examples = m_currentItem->word.examples;
    if (examples.isEmpty()) {
        m_dots->setState(1, 0);
        m_exampleText->clear();
        m_exampleTrans->clear();
        return;
    }
    const Example &ex = examples[m_exampleIndex];
    m_exampleText->setText(boldHeadword(ex.text, m_currentItem->word.text));
    m_exampleTrans->setText(ex.translation);
    m_dots->setState(examples.size(), m_exampleIndex);
}

void StudyView::switchExample(int delta) {
    if (m_currentItem == nullptr)
        return;
    const int n = m_currentItem->word.examples.size();
    if (n == 0)
        return;
    m_exampleIndex = (m_exampleIndex + delta) % n;
    renderExample();
}

// ================================================================ 交互
void StudyView::onLeft() {
    if (m_session.finished()) {  // 完成态下左键即「返回首页」
        emit backRequested();
        return;
    }
    if (!m_answerMode) {  // 出题态：不认识 -> 作答态
        showAnswer(false);
        return;
    }
    // 作答态：仅「已认识 -> 记错了」会走到这里
    gradeAndAdvance(false);
}

void StudyView::onRight() {
    if (m_session.finished()) {  // 完成态：开始拼写
        emit spellRequested();
        return;
    }
    if (!m_answerMode) {  // 出题态：已认识 -> 作答态
        showAnswer(true);
        return;
    }
    // 作答态：「下一词」：已认识来源判对，不认识来源判错
    gradeAndAdvance(m_knownClicked);
}

void StudyView::gradeAndAdvance(bool passed) {
    if (m_currentItem == nullptr)
        return;
    m_ctx.service->grade(m_session, *m_currentItem, quality(passed));
    m_session.index += 1;
    m_currentItem = nullptr;  // 插入重现副本可能使旧指针失效
    if (m_session.finished()) {
        m_ctx.service->completeSession(m_session);
        showDone();
    } else {
        // 每次推进都保存快照，中途退出后可恢复本组
        m_ctx.service->saveSession(m_session);
        showQuestion();
    }
}

int StudyView::quality(bool passed) const {
    // 将 UI 作答路径映射为 SM-2 质量分
    if (!passed)
        return GRADE_AGAIN;  // 记错了 / 不认识直接下一词
    return m_knownClicked ? GRADE_GOOD : GRADE_HARD;
}

// ------------------------------------------------------------ 完成态
void StudyView::showDone() {
    m_wordLabel->hide();
    m_btnSpeaker->hide();
    m_phonetic->hide();
    setMeaningsVisible(false);
    m_exampleCard->hide();
    m_progressLabel->hide();
    m_bar->hide();

    const QString mode = (m_session.mode == QLatin1String("review"))
                             ? QStringLiteral("复习")
                             : QStringLiteral("学习");
    const int unique = m_session.passed + m_session.failed;
    m_doneLabel->setText(QStringLiteral("本组完成！"));
    m_doneSummary->setText(QStringLiteral("本次%1 %2 词 · 记住 %3 · 需巩固 %4")
                               .arg(mode)
                               .arg(unique)
                               .arg(m_session.passed)
                               .arg(m_session.failed));
    m_doneLabel->show();
    m_doneSummary->show();

    // 完成页提供「返回首页」与「开始拼写」两个入口
    m_btnLeft->setText(QStringLiteral("返回首页"));
    m_btnLeft->setIcon(icon(QStringLiteral("back"),
                            QLatin1String(theme::GREEN_ICON), 20));
    m_btnRight->setText(QStringLiteral("开始拼写"));
    m_btnRight->setIcon(icon(QStringLiteral("check"),
                             QLatin1String(theme::GREEN_ICON), 20));
    m_btnLeft->show();
    m_btnRight->show();
}

// ------------------------------------------------------------ 其它
void StudyView::pronounce() {
    if (m_currentItem != nullptr)
        m_ctx.speaker->speak(m_currentItem->word.text);
}

void StudyView::cycleFont() {
    m_ctx.config().cycleFont();
    m_ctx.configs->save();
    applyFontScale();
}

void StudyView::applyFontScale() {
    const int level = qBound(0, m_ctx.config().fontLevel, 2);
    QFont f = m_wordLabel->font();
    f.setPixelSize(kWordFontSizes[level]);
    f.setBold(true);
    m_wordLabel->setFont(f);
    QFont mf = m_wordLabel->font();
    mf.setPixelSize(kMeaningFontSizes[level]);
    mf.setBold(false);
    for (QLabel *lb : m_meaningLabels)
        lb->setFont(mf);
}

void StudyView::showEvent(QShowEvent *event) {
    applyFontScale();
    QWidget::showEvent(event);
}

// ============================================================ FontToggle
FontToggle::FontToggle(QWidget *parent)
    : IconButton(QStringLiteral("dot"), QStringLiteral("#41606d"), 30, 0,
                 QStringLiteral("切换单词字号"), false, false, parent) {}

void FontToggle::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    if (isDown() || isChecked())
        p.setBrush(QColor(47, 62, 70, 36));
    else if (underMouse())
        p.setBrush(QColor(47, 62, 70, 20));
    else
        p.setBrush(Qt::NoBrush);
    p.setPen(Qt::NoPen);
    p.drawRoundedRect(rect(), 8, 8);
    p.setPen(QColor(QStringLiteral("#41606d")));
    QFont f = p.font();
    f.setPixelSize(13);
    f.setBold(true);
    p.setFont(f);
    p.drawText(rect(), Qt::AlignCenter, QStringLiteral("Aa"));
}

}  // namespace wordmem
