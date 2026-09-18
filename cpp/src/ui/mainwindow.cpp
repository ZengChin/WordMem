#include "ui/mainwindow.h"

#include <QApplication>
#include <QByteArray>
#include <QCloseEvent>
#include <QCursor>
#include <QEasingCurve>
#include <QFont>
#include <QGraphicsOpacityEffect>
#include <QHBoxLayout>
#include <QLinearGradient>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPoint>
#include <QRectF>
#include <QStackedWidget>
#include <QTimer>
#include <QVariantAnimation>
#include <QVBoxLayout>

#ifdef Q_OS_WIN
#include <windows.h>
#endif

#include "core/bookmanager.h"
#include "core/models.h"
#include "core/repository.h"
#include "core/settings.h"
#include "core/studyservice.h"
#include "ui/appcontext.h"
#include "ui/opacitypopup.h"
#include "ui/theme.h"
#include "ui/titlebar.h"
#include "ui/views/bookmanageview.h"
#include "ui/views/homeview.h"
#include "ui/views/spellview.h"
#include "ui/views/studyview.h"
#include "ui/views/wordlistview.h"
#include "ui/widgets.h"

namespace wordmem {

AppConfig &AppContext::config() const { return configs->config; }

#ifdef Q_OS_WIN
namespace {
// ---- Windows 原生命中测试：WM/HT* 常量均由 windows.h 提供 ----
constexpr quint32 WM_NCHITTEST_MSG = 0x0084;

// 把 64 位 lParam 的低 32 位按「有符号 16 位高低字」解成物理像素坐标
int signedLowWord(quintptr v) { return static_cast<short>(v & 0xFFFF); }
int signedHighWord(quintptr v) { return static_cast<short>((v >> 16) & 0xFFFF); }
}  // namespace
#endif

namespace {
QColor alphaColor(const char *hexColor, int alpha) {
    QColor c{QLatin1String(hexColor)};
    c.setAlpha(alpha);
    return c;
}
}  // namespace

MainWindow::MainWindow(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    setWindowFlags(Qt::FramelessWindowHint | Qt::Window);
    setAttribute(Qt::WA_TranslucentBackground);
    setMinimumSize(MIN_W, MIN_H);
    resize(theme::WINDOW_W, theme::WINDOW_H);

    auto *root = new QVBoxLayout(this);
    root->setContentsMargins(0, 0, 0, 0);
    root->setSpacing(0);

    m_titleBar = new TitleBar(this);
    m_stack = new QStackedWidget(this);

    m_homeView = new HomeView(m_ctx, this);
    m_studyView = new StudyView(m_ctx, this);
    m_spellView = new SpellView(m_ctx, this);
    m_wordListView = new WordListPage(m_ctx, this);
    m_bookManageView = new BookManageView(m_ctx, this);
    m_importBookView = new ImportBookView(m_ctx, this);
    m_stack->addWidget(m_homeView);
    m_stack->addWidget(m_studyView);
    m_stack->addWidget(m_spellView);
    m_stack->addWidget(m_wordListView);
    m_stack->addWidget(m_bookManageView);
    m_stack->addWidget(m_importBookView);

    m_content = new QWidget(this);
    auto *contentLayout = new QHBoxLayout(m_content);
    contentLayout->setContentsMargins(14, 0, 14, 14);
    contentLayout->addWidget(m_stack);
    root->addWidget(m_titleBar);
    root->setAlignment(m_titleBar, Qt::AlignTop);  // 内容隐藏时菜单栏仍钉在顶部
    root->addWidget(m_content, 1);

    // ---- 信号接线 ----
    connect(m_titleBar, &TitleBar::ghostToggled, this, &MainWindow::onGhost);
    connect(m_titleBar, &TitleBar::opacityRequested, this,
            &MainWindow::showOpacityDial);
    connect(m_titleBar, &TitleBar::pinToggled, this, &MainWindow::onPin);
    connect(m_titleBar, &TitleBar::foldToggled, this, &MainWindow::onFold);
    connect(m_titleBar, &TitleBar::minimizeRequested, this, &QWidget::showMinimized);
    connect(m_titleBar, &TitleBar::closeRequested, this, &QWidget::close);

    connect(m_homeView, &HomeView::startSession, this, &MainWindow::startSession);
    connect(m_homeView, &HomeView::wordListRequested, this,
            &MainWindow::openWordList);
    connect(m_homeView, &HomeView::bookManageRequested, this,
            &MainWindow::openBookManage);
    connect(m_studyView, &StudyView::backRequested, this, &MainWindow::goHome);
    connect(m_studyView, &StudyView::spellRequested, this, &MainWindow::beginSpell);
    connect(m_spellView, &SpellView::backRequested, this, &MainWindow::goHome);
    connect(m_wordListView, &WordListPage::backRequested, this, &MainWindow::goHome);
    connect(m_bookManageView, &BookManageView::backRequested, this,
            &MainWindow::goHome);
    connect(m_bookManageView, &BookManageView::bookSwitched, m_homeView,
            &HomeView::refresh);
    connect(m_bookManageView, &BookManageView::importRequested, this,
            &MainWindow::openImportBook);
    connect(m_importBookView, &ImportBookView::backRequested, this,
            &MainWindow::backToBookManage);
    connect(m_importBookView, &ImportBookView::imported, this,
            &MainWindow::onImportDone);

    applyConfig();
    m_stack->setCurrentWidget(m_homeView);
    startAutoHideWatch();
}

// ------------------------------------------------------------ 配置
void MainWindow::applyConfig() {
    theme::setGhostMode(m_ctx.config().ghostMode);  // 卡片/进度条同步
    applyFgOpacity(m_ctx.config().uiOpacity);
    m_titleBar->btn_ghost->setChecked(m_ctx.config().ghostMode);
    m_titleBar->btn_fold->setChecked(m_ctx.config().autoHide);
}

void MainWindow::setEffect(QWidget *widget, double opacity) {
    // 为控件设置不透明度效果；1.0 时移除效果避免渲染开销
    if (opacity < 0 || opacity >= 0.995) {
        widget->setGraphicsEffect(nullptr);
        return;
    }
    auto *effect = new QGraphicsOpacityEffect(widget);
    effect->setOpacity(opacity);
    widget->setGraphicsEffect(effect);
}

void MainWindow::applyFgOpacity(double value) {
    // 按钮与字体不透明度：内容区跟随数值，菜单栏特殊处理
    value = qBound(0.25, value, 1.0);
    m_ctx.config().uiOpacity = value;
    setEffect(m_stack, value);
    // 透明模式下菜单栏保持半透明，普通模式跟随整体数值
    const double titlebarOpacity =
        m_ctx.config().ghostMode ? GHOST_TITLEBAR_OPACITY : value;
    setEffect(m_titleBar, titlebarOpacity);
}

// ------------------------------------------------------------ 背景透明模式
void MainWindow::onGhost(bool checked) {
    // 切换背景/边框是否超透明；按钮底色隐形但文字保留，仅菜单栏转半透明
    m_ctx.config().ghostMode = checked;
    theme::setGhostMode(checked);        // 卡片/进度条变超透明
    applyFgOpacity(m_ctx.config().uiOpacity);  // 刷新菜单栏透明度
    for (QWidget *w : QApplication::allWidgets()) {  // 全量重绘
        if (auto *pill = qobject_cast<PillButton *>(w))
            pill->refresh();  // 按钮底色随透明模式隐形（文字保留）
        else
            w->update();
    }
}

void MainWindow::showOpacityDial() {
    // 点击调节按钮弹出/隐藏线性滑条（类似进度条）
    if (m_opacityPopup != nullptr) {
        m_opacityPopup->close();
        m_opacityPopup = nullptr;
        return;
    }
    auto *popup = new OpacitySliderPopup(m_ctx.config().uiOpacity);
    connect(popup, &OpacitySliderPopup::valueChanged, this,
            &MainWindow::applyFgOpacity);
    connect(popup, &OpacitySliderPopup::closed, this, &MainWindow::onDialClosed);
    IconButton *btn = m_titleBar->btn_opacity;
    const QPoint center = btn->mapToGlobal(btn->rect().center());
    popup->adjustSize();
    popup->move(center.x() - popup->width() / 2, center.y() + 6);
    m_opacityPopup = popup;
    popup->show();
}

void MainWindow::onDialClosed() {
    m_ctx.configs->save();
    if (m_opacityPopup != nullptr) {
        m_opacityPopup->deleteLater();
        m_opacityPopup = nullptr;
    }
}

// ------------------------------------------------------------ 置顶
void MainWindow::onPin(bool checked) {
    const bool visible = isVisible();
    const QPoint pos = this->pos();
    const QSize size = this->size();
    setWindowFlag(Qt::WindowStaysOnTopHint, checked);
    if (visible) {
        hide();
        show();
        move(pos);
        resize(size);
    }
}

// ------------------------------------------------------------ 自动隐藏
void MainWindow::onFold(bool checked) {
    // 开关「鼠标移出窗口时自动隐藏内容（仅保留菜单栏）」
    m_ctx.config().autoHide = checked;
    if (!checked && m_contentHidden)
        restoreContent();
}

void MainWindow::startAutoHideWatch() {
    // 分层窗口透明区不可靠地触发 hover 事件，改为定时检测鼠标是否在窗口矩形内
    m_autoHideTimer = new QTimer(this);
    m_autoHideTimer->setInterval(120);
    connect(m_autoHideTimer, &QTimer::timeout, this, &MainWindow::checkAutoHide);
    m_autoHideTimer->start();
}

void MainWindow::checkAutoHide() {
    if (!m_ctx.config().autoHide || isMinimized())
        return;
    const QPoint pos = QCursor::pos();
    if (frameGeometry().contains(pos)) {
        if (m_contentHidden)
            restoreContent();
        return;
    }
    if (!m_contentHidden && !isMaximized() &&
        !(QApplication::mouseButtons() & Qt::LeftButton) &&
        m_opacityPopup == nullptr && QApplication::activeModalWidget() == nullptr &&
        QApplication::activePopupWidget() == nullptr)
        hideContent();
}

void MainWindow::hideContent() {
    // 隐藏内容区：整体淡出，窗口原位原尺寸，仅菜单栏可见
    if (m_contentHidden || isMaximized() || !isVisible())
        return;
    m_contentHidden = true;
    runHideAnim(1.0);
}

void MainWindow::restoreContent() {
    // 恢复内容区：淡入显示
    if (!m_contentHidden)
        return;
    m_contentHidden = false;
    if (!m_content->isVisible()) {
        m_content->show();
        if (auto *eff = qobject_cast<QGraphicsOpacityEffect *>(
                m_content->graphicsEffect()))
            eff->setOpacity(0.0);
    }
    runHideAnim(0.0);
}

void MainWindow::runHideAnim(double target) {
    // 从当前进度平滑过渡到 target（0=完全显示，1=完全隐藏）
    if (m_hideAnim != nullptr) {
        m_hideAnim->stop();
        m_hideAnim->deleteLater();
        m_hideAnim = nullptr;
    }
    auto *anim = new QVariantAnimation(this);
    anim->setStartValue(m_hideProgress);
    anim->setEndValue(target);
    anim->setDuration(220);
    anim->setEasingCurve(QEasingCurve::OutCubic);
    connect(anim, &QVariantAnimation::valueChanged, this, [this](const QVariant &v) {
        m_hideProgress = v.toDouble();
        auto *eff = qobject_cast<QGraphicsOpacityEffect *>(m_content->graphicsEffect());
        if (eff == nullptr) {
            eff = new QGraphicsOpacityEffect(m_content);
            m_content->setGraphicsEffect(eff);
        }
        eff->setOpacity(1.0 - m_hideProgress);
        update();  // 背景随进度重绘
    });
    connect(anim, &QVariantAnimation::finished, this, [this, target] {
        m_hideAnim = nullptr;
        if (target >= 0.999)
            m_content->hide();
        else
            m_content->setGraphicsEffect(nullptr);
    });
    m_hideAnim = anim;
    anim->start();
}

// ------------------------------------------------------------ 视图切换
void MainWindow::startSession(const QString &mode) {
    // 设置即时生效
    m_ctx.service->batchSize = m_ctx.config().batchSize;
    m_ctx.service->requeueGap = m_ctx.config().requeueGap;
    // 优先恢复上次未完成的一组，否则开启新一组
    auto session = m_ctx.service->resumeSession(mode);
    if (!session) {
        StudySession fresh = m_ctx.service->startSession(mode);
        int unique = 0;
        for (const SessionItem &it : fresh.items)
            if (!it.requeued)
                ++unique;
        if (unique == 0)
            return;
        session = fresh;
    }
    m_ctx.service->saveSession(*session);
    m_studyView->begin(*session);
    m_stack->setCurrentWidget(m_studyView);
}

void MainWindow::goHome() {
    m_homeView->refresh();
    m_stack->setCurrentWidget(m_homeView);
}

void MainWindow::beginSpell() {
    // 完成页点击「开始拼写」后进入拼写练习
    m_spellView->begin(m_studyView->session());
    m_stack->setCurrentWidget(m_spellView);
}

void MainWindow::openWordList() {
    m_wordListView->refresh();
    m_stack->setCurrentWidget(m_wordListView);
}

void MainWindow::openBookManage() {
    m_bookManageView->refresh();
    m_stack->setCurrentWidget(m_bookManageView);
}

void MainWindow::openImportBook() {
    m_importBookView->reset();
    m_stack->setCurrentWidget(m_importBookView);
}

void MainWindow::backToBookManage() {
    m_bookManageView->refresh();
    m_stack->setCurrentWidget(m_bookManageView);
}

void MainWindow::onImportDone() {
    // 导入成功后刷新词书管理页并返回
    m_bookManageView->refresh();
    emit m_bookManageView->bookSwitched();
    m_stack->setCurrentWidget(m_bookManageView);
}

// ------------------------------------------------------------ 原生拖边缩放
bool MainWindow::nativeEvent(const QByteArray &eventType, void *message,
                             qintptr *result) {
#ifdef Q_OS_WIN
    // 拦截 WM_NCHITTEST，把窗口边缘变成系统缩放热区（资源管理器手感）
    if (eventType == QByteArrayLiteral("windows_generic_MSG")) {
        MSG *msg = static_cast<MSG *>(message);
        if (msg->message == WM_NCHITTEST_MSG && !isMaximized() && !m_contentHidden) {
            // lParam 为物理像素坐标（有符号 16 位高低字）
            const int physX = signedLowWord(msg->lParam);
            const int physY = signedHighWord(msg->lParam);
            const qreal dpr = devicePixelRatioF() > 0 ? devicePixelRatioF() : 1.0;
            const QPoint gp(qRound(physX / dpr), qRound(physY / dpr));
            const QPoint pos = mapFromGlobal(gp);
            const int m = RESIZE_MARGIN;
            const int w = width(), h = height();
            const bool onLeft = pos.x() < m;
            const bool onRight = pos.x() >= w - m;
            const bool onTop = pos.y() < m;
            const bool onBottom = pos.y() >= h - m;
            int hit = HTCLIENT;
            if (onTop && onLeft)
                hit = HTTOPLEFT;
            else if (onTop && onRight)
                hit = HTTOPRIGHT;
            else if (onBottom && onLeft)
                hit = HTBOTTOMLEFT;
            else if (onBottom && onRight)
                hit = HTBOTTOMRIGHT;
            else if (onLeft)
                hit = HTLEFT;
            else if (onRight)
                hit = HTRIGHT;
            else if (onTop)
                hit = HTTOP;
            else if (onBottom)
                hit = HTBOTTOM;
            if (hit != HTCLIENT) {
                *result = hit;
                return true;
            }
        }
    }
#else
    Q_UNUSED(eventType);
    Q_UNUSED(message);
    Q_UNUSED(result);
#endif
    return QWidget::nativeEvent(eventType, message, result);
}

// ------------------------------------------------------------ 绘制
void MainWindow::paintBackground(QPainter &p, double k, const QRectF &region) {
    // 绘制天空渐变背景（及沙滩高光）。k=强度系数
    const bool ghost = m_ctx.config().ghostMode;
    QLinearGradient grad(0, 0, 0, height());
    if (ghost) {
        grad.setColorAt(0.00, alphaColor(theme::SKY_TOP, qRound(10 * k)));
        grad.setColorAt(0.45, alphaColor(theme::SKY_MID, qRound(8 * k)));
        grad.setColorAt(0.60, alphaColor(theme::SEA_BAND, qRound(7 * k)));
        grad.setColorAt(0.72, alphaColor(theme::SAND_LIGHT, qRound(5 * k)));
        grad.setColorAt(1.00, alphaColor(theme::SAND, qRound(4 * k)));
    } else {
        grad.setColorAt(0.00, alphaColor(theme::SKY_TOP, qRound(255 * k)));
        grad.setColorAt(0.45, alphaColor(theme::SKY_MID, qRound(255 * k)));
        grad.setColorAt(0.60, alphaColor(theme::SEA_BAND, qRound(255 * k)));
        grad.setColorAt(0.72, alphaColor(theme::SAND_LIGHT, qRound(255 * k)));
        grad.setColorAt(1.00, alphaColor(theme::SAND, qRound(255 * k)));
    }
    p.setPen(Qt::NoPen);
    p.setBrush(grad);
    p.drawRect(region);
    if (!ghost) {
        // 沙滩高光带
        p.setBrush(QColor(255, 250, 238, qRound(60 * k)));
        p.drawRect(QRectF(region.x(), height() * 0.78, region.width(),
                          height() * 0.10));
    }
}

void MainWindow::paintBorder(QPainter &p, double k) {
    // 绘制窗口圆角描边。k=强度系数
    const QColor border = m_ctx.config().ghostMode ? theme::ghostBorder()
                                                   : QColor(255, 255, 255, 70);
    QColor c(border);
    c.setAlpha(qRound(border.alpha() * k));
    QPen pen(c);
    pen.setWidthF(1.0);
    p.setBrush(Qt::NoBrush);
    p.setPen(pen);
    p.drawRoundedRect(QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5), theme::RADIUS,
                      theme::RADIUS);
}

void MainWindow::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    QPainterPath winPath;
    winPath.addRoundedRect(QRectF(rect()), theme::RADIUS, theme::RADIUS);
    p.setClipPath(winPath);

    const double prog = m_hideProgress;  // 0=完整窗口, 1=仅菜单栏
    const double bgK = 1.0 - prog;       // 背景淡出系数

    // ---- 背景（随 prog 平滑淡出，prog=1 时全透明） ----
    paintBackground(p, bgK, QRectF(rect()));

    // ---- 菜单栏区域保持原样式（不改变背景与描边） ----
    if (prog > 0.004) {
        const QRectF bar(0, 0, width(), m_titleBar->height());
        QPainterPath barPath;
        barPath.addRect(bar);
        p.save();
        p.setClipPath(winPath.intersected(barPath));
        paintBackground(p, 1.0, bar);
        paintBorder(p, 1.0);
        p.restore();
    }

    // ---- 轮廓描边（随背景一起淡出） ----
    paintBorder(p, bgK);
}

// ------------------------------------------------------------ 关闭
void MainWindow::closeEvent(QCloseEvent *event) {
    if (m_opacityPopup != nullptr) {
        m_opacityPopup->close();
        m_opacityPopup = nullptr;
    }
    m_ctx.configs->save();
    emit closed();
    QWidget::closeEvent(event);
}

}  // namespace wordmem
