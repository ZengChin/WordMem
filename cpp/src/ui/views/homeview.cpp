#include "ui/views/homeview.h"

#include <QHBoxLayout>
#include <QFont>
#include <QLabel>
#include <QMouseEvent>
#include <QVBoxLayout>

#include "core/bookmanager.h"
#include "core/repository.h"
#include "core/studyservice.h"
#include "ui/appcontext.h"
#include "ui/theme.h"
#include "ui/views/dialogs.h"
#include "ui/widgets.h"

namespace wordmem {

// ============================================================ NumberCard
NumberCard::NumberCard(const QString &actionText, const QString &iconName,
                       QWidget *parent)
    : Card(190, 12, parent), m_baseAlpha(190), m_hoverAlpha(225) {
    setCursor(Qt::PointingHandCursor);
    setToolTip(actionText);

    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(14, 16, 14, 14);
    lay->setSpacing(12);

    number = new QLabel(QStringLiteral("0"), this);
    number->setAlignment(Qt::AlignCenter);
    QFont f = number->font();
    f.setPixelSize(24);
    f.setBold(true);
    number->setFont(f);
    number->setStyleSheet(QStringLiteral("color:%1;").arg(QLatin1String(theme::INK_DARK)));

    button = new PillButton(actionText, iconName, QLatin1String(theme::GREEN), this);
    button->setFixedHeight(40);
    // 按钮点击同样视为整卡点击（QPushButton 拦截鼠标事件，需单独接线）
    connect(button, &QPushButton::clicked, this, &NumberCard::clicked);

    lay->addStretch(1);
    lay->addWidget(number);
    lay->addWidget(button);
    lay->addStretch(1);
}

void NumberCard::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton)
        emit clicked();
    Card::mousePressEvent(event);
}

void NumberCard::enterEvent(QEnterEvent *event) {
    setAlpha(m_hoverAlpha);
    update();
    Card::enterEvent(event);
}

void NumberCard::leaveEvent(QEvent *event) {
    setAlpha(m_baseAlpha);
    update();
    Card::leaveEvent(event);
}

// ============================================================ BookCard
BookCard::BookCard(QWidget *parent) : Card(175, 14, parent) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(18, 16, 14, 16);
    lay->setSpacing(6);

    auto *top = new QHBoxLayout;
    name = new QLabel(QStringLiteral("词书"), this);
    name->setStyleSheet(QStringLiteral("color:%1; font-size:15px; font-weight:600;")
                            .arg(QLatin1String(theme::GREEN)));
    list_btn = new IconButton(QStringLiteral("list"), QLatin1String(theme::GREEN), 26,
                              14, QStringLiteral("查看全部单词"), false, false, this);
    more = new IconButton(QStringLiteral("chevron"), QLatin1String(theme::GREEN), 26,
                          14, QStringLiteral("词书详情"), false, false, this);
    top->addWidget(name);
    top->addStretch(1);
    top->addWidget(list_btn);
    top->addWidget(more);
    lay->addLayout(top);

    lay->addStretch(1);
    counter = new QLabel(QStringLiteral("0 / 0"), this);
    counter->setAlignment(Qt::AlignCenter);
    QFont f = counter->font();
    f.setPixelSize(19);
    counter->setFont(f);
    counter->setStyleSheet(QStringLiteral("color:%1;").arg(QLatin1String(theme::INK)));
    lay->addWidget(counter);
    lay->addSpacing(6);

    bar = new SmoothBar(true, QLatin1String(theme::GREEN_ICON), this);
    bar->setFixedHeight(20);
    lay->addWidget(bar);
}

// ============================================================ HomeView
HomeView::HomeView(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(2, 2, 2, 4);
    lay->setSpacing(0);

    auto *header = new QHBoxLayout;
    auto *btnSettings =
        new IconButton(QStringLiteral("settings"), QStringLiteral("#5a6b72"), 34, 19,
                       QStringLiteral("设置"), false, false, this);
    auto *btnStats = new IconButton(QStringLiteral("chart"),
                                    QStringLiteral("#5a6b72"), 34, 19,
                                    QStringLiteral("学习统计"), false, false, this);
    header->addWidget(btnSettings);
    header->addStretch(1);
    header->addWidget(btnStats);
    lay->addLayout(header);

    lay->addStretch(2);
    m_bookCard = new BookCard(this);
    lay->addWidget(m_bookCard);
    lay->addStretch(3);

    auto *bottom = new QHBoxLayout;
    bottom->setSpacing(14);
    m_cardNew = new NumberCard(QStringLiteral("学新词"),
                               QStringLiteral("book_new"), this);
    m_cardReview = new NumberCard(QStringLiteral("复习词"),
                                  QStringLiteral("book_review"), this);
    bottom->addWidget(m_cardNew, 1);
    bottom->addWidget(m_cardReview, 1);
    lay->addLayout(bottom);

    // ---- 信号 ----
    connect(m_cardNew, &NumberCard::clicked, this,
            [this] { start(QStringLiteral("new")); });
    connect(m_cardReview, &NumberCard::clicked, this,
            [this] { start(QStringLiteral("review")); });
    connect(btnSettings, &QAbstractButton::clicked, this, &HomeView::openSettings);
    connect(btnStats, &QAbstractButton::clicked, this, &HomeView::openStats);
    connect(m_bookCard->more, &QAbstractButton::clicked, this,
            &HomeView::bookManageRequested);
    connect(m_bookCard->list_btn, &QAbstractButton::clicked, this,
            &HomeView::wordListRequested);

    refresh();
}

void HomeView::start(const QString &mode) {
    // 整卡点击入口；无可用词时按钮禁用，不触发会话
    PillButton *button = (mode == QLatin1String("new")) ? m_cardNew->button
                                                        : m_cardReview->button;
    if (button->isEnabled())
        emit startSession(mode);
}

void HomeView::refresh() {
    const HomeSummary summary = m_ctx.service->homeSummary();
    const auto book = m_ctx.repo->getActiveBook();
    const int total = summary.total;
    const int learned = summary.learned;

    m_bookCard->name->setText(book ? book->name : QStringLiteral("词书"));
    m_bookCard->counter->setText(QStringLiteral("%1 / %2").arg(learned).arg(total));
    m_bookCard->bar->setFraction(total > 0 ? static_cast<double>(learned) / total
                                           : 0.0);

    m_cardNew->number->setText(QString::number(summary.newLeft));
    m_cardReview->number->setText(QString::number(summary.reviewLeft));
    m_cardNew->button->setEnabled(summary.newLeft > 0);
    // 复习需先完整背完至少一组
    m_cardReview->button->setEnabled(summary.reviewLeft > 0 &&
                                     summary.completedBatches > 0);
}

void HomeView::openSettings() {
    SettingsDialog dlg(m_ctx, window());
    dlg.exec();
    refresh();  // 弹窗内可能重置进度/改动配置，关闭后刷新首页数据
}

void HomeView::openStats() {
    StatsDialog dlg(m_ctx, window());
    dlg.exec();
}

}  // namespace wordmem
