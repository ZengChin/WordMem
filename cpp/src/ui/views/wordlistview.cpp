#include "ui/views/wordlistview.h"

#include <QFont>
#include <QFontMetrics>
#include <QFrame>
#include <QHBoxLayout>
#include <QLabel>
#include <QMouseEvent>
#include <QPainter>
#include <QPushButton>
#include <QScrollBar>
#include <QScrollArea>
#include <QStringList>
#include <QVBoxLayout>

#include "core/repository.h"
#include "ui/appcontext.h"
#include "ui/icons.h"
#include "ui/theme.h"
#include "ui/widgets.h"

namespace wordmem {

QString scrollAreaQss() {
    return QStringLiteral(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }"
        "QScrollBar::handle:vertical { background:#c9d6d3; border-radius:3px;"
        " min-height:24px; }"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
        " background:none; }");
}

// ============================================================ WordListView
WordListView::WordListView(QWidget *parent) : QWidget(parent) {
    setMouseTracking(true);
    setCursor(Qt::PointingHandCursor);
}

void WordListView::setScrollArea(QScrollArea *area) { m_scrollArea = area; }

void WordListView::setWords(const QList<Word> &words) {
    m_words = words;
    m_shown.clear();
    m_hover = -1;
    // 高度 = 全部行，宽度由宿主滚动区撑满（widgetResizable=true）
    setMinimumHeight(m_words.size() * ROW_H);
    update();
}

void WordListView::showAll(bool show) {
    m_shown.clear();
    if (show) {
        for (int i = 0; i < m_words.size(); ++i)
            m_shown.insert(i);
    }
    update();
}

int WordListView::rowAt(int y) const {
    const int i = y / ROW_H;
    return (i >= 0 && i < m_words.size()) ? i : -1;
}

int WordListView::scrollOffset() const {
    return m_scrollArea != nullptr ? m_scrollArea->verticalScrollBar()->value() : 0;
}

int WordListView::viewportHeight() const {
    return m_scrollArea != nullptr ? m_scrollArea->viewport()->height() : height();
}

void WordListView::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton) {
        const int i = rowAt(static_cast<int>(event->position().y()));
        if (i >= 0) {
            if (m_shown.contains(i))
                m_shown.remove(i);
            else
                m_shown.insert(i);
            update();
        }
    }
    QWidget::mousePressEvent(event);
}

void WordListView::mouseMoveEvent(QMouseEvent *event) {
    const int i = rowAt(static_cast<int>(event->position().y()));
    if (i != m_hover) {
        m_hover = i;
        update();
    }
    QWidget::mouseMoveEvent(event);
}

void WordListView::leaveEvent(QEvent *event) {
    if (m_hover != -1) {
        m_hover = -1;
        update();
    }
    QWidget::leaveEvent(event);
}

void WordListView::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    const int n = m_words.size();
    if (n == 0)
        return;
    const int offset = scrollOffset();
    const int viewH = viewportHeight();
    const int w = width();
    const int first = qMax(0, offset / ROW_H);
    const int last = qMin(n - 1, (offset + viewH) / ROW_H);
    const int leftW = qMax(160, static_cast<int>(w * 0.46));
    for (int i = first; i <= last; ++i) {
        const int y = i * ROW_H;
        const Word &word = m_words[i];
        if (i == m_hover)
            p.fillRect(0, y, w, ROW_H, QColor(47, 62, 70, 16));
        // 英文（加粗）
        QFont f = p.font();
        f.setPixelSize(15);
        f.setBold(true);
        p.setFont(f);
        const QFontMetrics fm(f);
        p.setPen(QColor(QLatin1String(theme::INK_DARK)));
        p.drawText(QRect(16, y, leftW - 12, ROW_H),
                   Qt::AlignVCenter | Qt::AlignLeft, word.text);
        // 音标（紧随英文之后）
        if (!word.phonetic.isEmpty()) {
            const int ww = fm.horizontalAdvance(word.text);
            QFont f2 = f;
            f2.setBold(false);
            f2.setPixelSize(12);
            p.setFont(f2);
            p.setPen(QColor(QLatin1String(theme::INK_SOFT)));
            const QFontMetrics fm2(p.font());
            const int avail = qMax(20, leftW - 24 - ww);
            const QString ph = fm2.elidedText(word.phonetic, Qt::ElideRight, avail);
            p.drawText(QRect(16 + ww + 8, y, avail, ROW_H),
                       Qt::AlignVCenter | Qt::AlignLeft, ph);
        }
        // 中文释义（默认隐藏，点行后显示在右侧）
        if (m_shown.contains(i)) {
            QStringList labels;
            labels.reserve(word.meanings.size());
            for (const Meaning &m : word.meanings)
                labels << m.label();
            QFont f3 = p.font();
            f3.setPixelSize(13);
            f3.setBold(false);
            p.setFont(f3);
            p.setPen(QColor(QLatin1String(theme::GREEN)));
            const int region = w - 16 - leftW;
            if (region > 30) {
                const QString elided = p.fontMetrics().elidedText(
                    labels.join(QLatin1String("; ")), Qt::ElideRight, region);
                p.drawText(QRect(leftW, y, region, ROW_H),
                           Qt::AlignVCenter | Qt::AlignRight, elided);
            }
        }
        // 行分隔线
        p.setPen(QColor(232, 238, 240));
        p.drawLine(16, y + ROW_H - 1, w - 16, y + ROW_H - 1);
    }
}

// ============================================================ WordListPage
WordListPage::WordListPage(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(2, 2, 2, 4);
    lay->setSpacing(8);

    auto *head = new QHBoxLayout;
    auto *btnBack = new IconButton(QStringLiteral("back"),
                                   QStringLiteral("#5a6b72"), 34, 19,
                                   QStringLiteral("返回首页"), false, false, this);
    auto *title = new QLabel(QStringLiteral("全部单词"), this);
    title->setStyleSheet(QStringLiteral("color:%1; font-size:16px; font-weight:600;")
                             .arg(QLatin1String(theme::INK_DARK)));
    m_countLabel = new QLabel(this);
    m_countLabel->setStyleSheet(QStringLiteral("color:%1; font-size:13px;")
                                    .arg(QLatin1String(theme::INK_SOFT)));
    m_btnToggle = new QPushButton(this);
    m_btnToggle->setCursor(Qt::PointingHandCursor);
    m_btnToggle->setFixedHeight(30);
    m_btnToggle->setIcon(icon(QStringLiteral("eye"), QLatin1String(theme::GREEN), 15));
    m_btnToggle->setStyleSheet(QStringLiteral(
                                   "QPushButton { color:%1; border:1px solid #cfe5d8;"
                                   " border-radius:15px; padding:0 14px;"
                                   " font-size:13px; background:transparent; }"
                                   "QPushButton:hover { background:%2; }")
                                   .arg(QLatin1String(theme::GREEN),
                                        QLatin1String(theme::GREEN_BG)));
    updateToggleText();
    head->addWidget(btnBack);
    head->addSpacing(6);
    head->addWidget(title);
    head->addWidget(m_countLabel);
    head->addStretch(1);
    head->addWidget(m_btnToggle);
    lay->addLayout(head);

    m_listView = new WordListView;
    auto *scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setStyleSheet(scrollAreaQss());
    m_listView->setScrollArea(scroll);
    scroll->setWidget(m_listView);
    connect(scroll->verticalScrollBar(), &QScrollBar::valueChanged, m_listView,
            [this](int) { m_listView->update(); });
    lay->addWidget(scroll, 1);

    connect(btnBack, &QAbstractButton::clicked, this, &WordListPage::backRequested);
    connect(m_btnToggle, &QPushButton::clicked, this, &WordListPage::onToggleAll);

    refresh();
}

void WordListPage::refresh() {
    const QList<Word> words = m_ctx.repo->getAllWords();
    m_listView->setWords(words);
    m_countLabel->setText(QStringLiteral("共 %1 词").arg(words.size()));
    m_allShown = false;
    m_listView->showAll(false);
    updateToggleText();
}

void WordListPage::updateToggleText() {
    m_btnToggle->setText(m_allShown ? QStringLiteral("隐藏全部中文")
                                    : QStringLiteral("显示全部中文"));
}

void WordListPage::onToggleAll() {
    m_allShown = !m_allShown;
    m_listView->showAll(m_allShown);
    updateToggleText();
}

}  // namespace wordmem
