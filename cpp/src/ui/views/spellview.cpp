#include "ui/views/spellview.h"

#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLabel>
#include <QSet>
#include <QShowEvent>
#include <QStringList>
#include <QTimer>
#include <QVBoxLayout>

#include "core/settings.h"
#include "core/speaker.h"
#include "ui/appcontext.h"
#include "ui/icons.h"
#include "ui/theme.h"
#include "ui/widgets.h"

namespace wordmem {

namespace {
const char *kColorCorrect = theme::GREEN;  // 拼写正确：绿色
const char *kColorWrong = "#c0392b";       // 拼写错误：红色
}  // namespace

QList<Word> spellWords(const StudySession &session) {
    QSet<int> seen;
    QList<Word> words;
    for (const SessionItem &item : session.items) {
        if (!seen.contains(item.word.id)) {
            seen.insert(item.word.id);
            words.append(item.word);
        }
    }
    return words;
}

// ============================================================ SpellInput
SpellInput::SpellInput(QWidget *parent) : QLineEdit(parent) {
    setCursor(Qt::IBeamCursor);
    setPlaceholderText(
        QStringLiteral("输入英文拼写后按回车校验 · 空格查看提示"));
}

void SpellInput::keyPressEvent(QKeyEvent *event) {
    if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter) {
        emit submitRequested();
        return;
    }
    if (event->key() == Qt::Key_Space) {
        emit hintRequested();
        return;
    }
    QLineEdit::keyPressEvent(event);
}

// ============================================================ SpellView
SpellView::SpellView(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(6, 0, 6, 2);
    lay->setSpacing(0);

    // ---- 顶部：返回 + 标题 + 进度 ----
    auto *header = new QHBoxLayout;
    m_btnBack = new IconButton(QStringLiteral("back"), QStringLiteral("#5a6b72"), 30,
                               16, QStringLiteral("返回首页"), false, false, this);
    auto *title = new QLabel(QStringLiteral("拼写练习"), this);
    title->setStyleSheet(QStringLiteral("color:%1; font-size:16px; font-weight:600;")
                             .arg(QLatin1String(theme::INK)));
    m_progressLabel = new QLabel(QStringLiteral("0 / 0"), this);
    m_progressLabel->setStyleSheet(QStringLiteral(
        "color:#5f7480; font-size:14px; font-weight:500;"));
    header->addWidget(m_btnBack);
    header->addWidget(title);
    header->addStretch(1);
    header->addWidget(m_progressLabel);
    lay->addLayout(header);
    lay->addSpacing(18);

    // ---- 中文释义（大字号） ----
    m_meaningLabel = new QLabel(this);
    m_meaningLabel->setAlignment(Qt::AlignCenter);
    m_meaningLabel->setWordWrap(true);
    m_meaningLabel->setStyleSheet(QStringLiteral("color:%1; font-size:24px;"
                                                 " font-weight:600;")
                                      .arg(QLatin1String(theme::INK_DARK)));
    lay->addWidget(m_meaningLabel);
    lay->addSpacing(8);

    // ---- 发音：音标 + 喇叭 ----
    auto *phonRow = new QHBoxLayout;
    phonRow->setSpacing(6);
    m_btnSpeaker = new IconButton(QStringLiteral("speaker"),
                                  QStringLiteral("#41606d"), 28, 16,
                                  QStringLiteral("朗读单词"), false, false, this);
    m_phonetic = new QLabel(this);
    m_phonetic->setStyleSheet(QStringLiteral("color:%1; font-size:15px;")
                                  .arg(QLatin1String(theme::INK_SOFT)));
    phonRow->addStretch(1);
    phonRow->addWidget(m_btnSpeaker);
    phonRow->addWidget(m_phonetic);
    phonRow->addStretch(1);
    lay->addLayout(phonRow);
    lay->addSpacing(24);

    // ---- 输入框 ----
    m_inputEdit = new SpellInput(this);
    m_inputEdit->setFixedHeight(46);
    m_inputEdit->setAlignment(Qt::AlignCenter);
    m_inputEdit->setStyleSheet(QStringLiteral(
                                   "QLineEdit { background: rgba(255,255,255,185);"
                                   " border:1px solid #d6dee2; border-radius:23px;"
                                   " padding:0 18px; font-size:18px; color:%1; }"
                                   "QLineEdit:focus { border:2px solid %2; }")
                                   .arg(QLatin1String(theme::INK_DARK),
                                        QLatin1String(theme::GREEN)));
    lay->addWidget(m_inputEdit);
    lay->addSpacing(10);

    // ---- 反馈/提示区（红色错误、绿色正确、灰色空格提示） ----
    m_feedbackLabel = new QLabel(this);
    m_feedbackLabel->setAlignment(Qt::AlignCenter);
    m_feedbackLabel->setWordWrap(true);
    m_feedbackLabel->setFixedHeight(48);
    lay->addWidget(m_feedbackLabel);

    // ---- 完成态（内容区） ----
    m_doneLabel = new QLabel(QStringLiteral("拼写完成！"), this);
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

    // ---- 进度条 ----
    m_bar = new SmoothBar(false, QStringLiteral("#b7d8c8"), this);
    lay->addWidget(m_bar);
    lay->addSpacing(12);

    // ---- 底部按钮 ----
    auto *footer = new QHBoxLayout;
    m_btnFinish = new PillButton(QStringLiteral("结束拼写"), QStringLiteral("back"),
                                 QLatin1String(theme::GREEN), this);
    footer->addWidget(m_btnFinish, 1);
    lay->addLayout(footer);

    // ---- 信号 ----
    connect(m_btnBack, &QAbstractButton::clicked, this, &SpellView::backRequested);
    connect(m_btnFinish, &QPushButton::clicked, this, &SpellView::backRequested);
    connect(m_btnSpeaker, &QAbstractButton::clicked, this, &SpellView::pronounce);
    connect(m_inputEdit, &SpellInput::submitRequested, this, &SpellView::submit);
    connect(m_inputEdit, &SpellInput::hintRequested, this, &SpellView::showHint);

    showIdle();
}

// ================================================================ 状态
void SpellView::showIdle() {
    m_meaningLabel->hide();
    m_btnSpeaker->hide();
    m_phonetic->hide();
    m_inputEdit->hide();
    m_feedbackLabel->hide();
    m_progressLabel->hide();
    m_bar->hide();
    m_btnFinish->hide();
    m_doneLabel->hide();
    m_doneSummary->hide();
}

void SpellView::begin(const StudySession &session) {
    m_words = spellWords(session);
    m_index = 0;
    m_correctCount = 0;
    m_firstTryOk = 0;
    m_missed = 0;
    clearTimer();
    if (m_words.isEmpty()) {
        showDone();
        return;
    }
    showIdle();
    loadWord();
}

void SpellView::loadWord() {
    const Word &word = m_words[m_index];
    m_wordAttempted = false;
    m_locked = false;

    m_doneLabel->hide();
    m_doneSummary->hide();
    m_meaningLabel->show();
    m_btnSpeaker->show();
    m_phonetic->show();
    m_inputEdit->show();
    m_feedbackLabel->show();
    m_progressLabel->show();
    m_bar->show();
    m_btnFinish->setText(QStringLiteral("结束拼写"));
    m_btnFinish->setIcon(icon(QStringLiteral("back"),
                              QLatin1String(theme::GREEN_ICON), 20));
    m_btnFinish->show();

    QStringList labels;
    labels.reserve(word.meanings.size());
    for (const Meaning &m : word.meanings)
        labels << m.label();
    m_meaningLabel->setText(labels.join(QStringLiteral("；")));
    m_phonetic->setText(word.phonetic);
    m_progressLabel->setText(
        QStringLiteral("%1 / %2").arg(m_index + 1).arg(m_words.size()));
    m_bar->setFraction(static_cast<double>(m_index) / qMax(1, m_words.size()));
    m_inputEdit->clear();
    clearFeedback();
    m_inputEdit->setFocus();

    if (m_ctx.config().autoPronounce)
        pronounce();
}

// ================================================================ 交互
void SpellView::submit() {
    // 回车校验：错误显示红色英文（1 秒后隐藏），正确显示绿色并前进
    if (m_locked || m_words.isEmpty() || m_index >= m_words.size())
        return;
    const QString text = m_inputEdit->text().trimmed();
    if (text.isEmpty())
        return;
    const Word &word = m_words[m_index];
    if (text.compare(word.text, Qt::CaseInsensitive) == 0) {
        ++m_correctCount;
        if (m_wordAttempted)
            ++m_missed;
        else
            ++m_firstTryOk;
        m_locked = true;
        setFeedback(word.text, QLatin1String(kColorCorrect), 1000,
                    [this] { next(); });
    } else {
        m_wordAttempted = true;
        setFeedback(word.text, QLatin1String(kColorWrong), 1000,
                    [this] { hideFeedback(true); });
    }
}

void SpellView::showHint() {
    // 空格提示：显示英文 2 秒后隐藏，保留用户已输入内容
    if (m_locked || m_words.isEmpty() || m_index >= m_words.size())
        return;
    const Word &word = m_words[m_index];
    m_wordAttempted = true;  // 看过提示即不计入「一次拼对」
    setFeedback(word.text, QLatin1String(theme::INK_SOFT), 2000,
                [this] { hideFeedback(false); });
}

void SpellView::next() {
    ++m_index;
    if (m_index < m_words.size())
        loadWord();
    else
        showDone();
}

void SpellView::pronounce() {
    if (!m_words.isEmpty() && m_index >= 0 && m_index < m_words.size())
        m_ctx.speaker->speak(m_words[m_index].text);
}

// ------------------------------------------------------------ 反馈定时
void SpellView::setFeedback(const QString &text, const QString &color, int ms,
                            const std::function<void()> &onDone) {
    clearTimer();
    m_feedbackLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:20px; font-weight:600;").arg(color));
    m_feedbackLabel->setText(text);
    m_feedbackTimer = new QTimer(this);
    m_feedbackTimer->setSingleShot(true);
    connect(m_feedbackTimer, &QTimer::timeout, this, [this, onDone] {
        m_feedbackTimer = nullptr;
        if (onDone)
            onDone();
    });
    m_feedbackTimer->start(ms);
}

void SpellView::hideFeedback(bool clearInput) {
    m_feedbackLabel->clear();
    if (clearInput)
        m_inputEdit->clear();
    m_inputEdit->setFocus();
}

void SpellView::clearTimer() {
    if (m_feedbackTimer != nullptr) {
        m_feedbackTimer->stop();
        m_feedbackTimer->deleteLater();
        m_feedbackTimer = nullptr;
    }
}

void SpellView::clearFeedback() {
    clearTimer();
    m_feedbackLabel->clear();
}

// ------------------------------------------------------------ 完成态
void SpellView::showDone() {
    clearTimer();
    m_locked = true;
    m_meaningLabel->hide();
    m_btnSpeaker->hide();
    m_phonetic->hide();
    m_inputEdit->hide();
    m_feedbackLabel->hide();
    m_progressLabel->hide();
    m_bar->hide();

    const int total = m_words.size();
    m_doneLabel->setText(QStringLiteral("拼写完成！"));
    m_doneSummary->setText(QStringLiteral("共拼写 %1 词 · 一次拼对 %2 · 需重试 %3")
                               .arg(total)
                               .arg(m_firstTryOk)
                               .arg(m_missed));
    m_doneLabel->show();
    m_doneSummary->show();
    m_btnFinish->setText(QStringLiteral("返回首页"));
    m_btnFinish->setIcon(icon(QStringLiteral("back"),
                              QLatin1String(theme::GREEN_ICON), 20));
    m_btnFinish->show();
}

void SpellView::showEvent(QShowEvent *event) {
    if (!m_words.isEmpty() && m_index < m_words.size() && !m_locked)
        m_inputEdit->setFocus();
    QWidget::showEvent(event);
}

}  // namespace wordmem
