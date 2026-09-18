#include "ui/titlebar.h"

#include <QHBoxLayout>
#include <QMouseEvent>

#include "ui/widgets.h"

namespace wordmem {

TitleBar::TitleBar(QWidget *parent) : QWidget(parent) {
    setFixedHeight(38);

    auto *layout = new QHBoxLayout(this);
    layout->setContentsMargins(10, 4, 8, 0);
    layout->setSpacing(2);
    layout->addStretch(1);  // 先占位拉伸，把所有按钮推到最右侧

    // ---- 最右侧：透明 / 不透明度滑条 / 置顶 / 自动隐藏 / 最小化 / 关闭 ----
    btn_ghost = new IconButton(QStringLiteral("ghost"),
                               QStringLiteral("#5a6b72"), 32, 18,
                               QStringLiteral("背景超透明模式（保留轮廓）"), true,
                               false, this);
    btn_opacity = new IconButton(QStringLiteral("opacity"),
                                 QStringLiteral("#5a6b72"), 32, 18,
                                 QStringLiteral("调节按钮与字体不透明度"), false,
                                 false, this);
    btn_pin = new IconButton(QStringLiteral("pin"), QStringLiteral("#5a6b72"), 32,
                             18, QStringLiteral("窗口置顶"), true, true, this);
    btn_fold = new IconButton(QStringLiteral("fold"), QStringLiteral("#5a6b72"), 32,
                              18,
                              QStringLiteral("鼠标移出窗口时自动隐藏（仅保留菜单栏）"),
                              true, true, this);
    btn_min = new IconButton(QStringLiteral("minimize"),
                             QStringLiteral("#5a6b72"), 32, 18,
                             QStringLiteral("最小化"), false, false, this);
    btn_close = new IconButton(QStringLiteral("close"), QStringLiteral("#7d5a5a"),
                               32, 18, QStringLiteral("关闭"), false, false, this);

    for (IconButton *b : {btn_ghost, btn_opacity, btn_pin, btn_fold, btn_min,
                          btn_close})
        layout->addWidget(b, 0, Qt::AlignTop);

    connect(btn_ghost, &QAbstractButton::toggled, this, &TitleBar::ghostToggled);
    connect(btn_opacity, &QAbstractButton::clicked, this,
            &TitleBar::opacityRequested);
    connect(btn_pin, &QAbstractButton::toggled, this, &TitleBar::pinToggled);
    connect(btn_fold, &QAbstractButton::toggled, this, &TitleBar::foldToggled);
    connect(btn_min, &QAbstractButton::clicked, this, &TitleBar::minimizeRequested);
    connect(btn_close, &QAbstractButton::clicked, this, &TitleBar::closeRequested);
}

void TitleBar::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton) {
        m_dragging = true;
        m_dragPos = event->globalPosition().toPoint() - window()->pos();
    }
    QWidget::mousePressEvent(event);
}

void TitleBar::mouseMoveEvent(QMouseEvent *event) {
    if (m_dragging && (event->buttons() & Qt::LeftButton))
        window()->move(event->globalPosition().toPoint() - m_dragPos);
    QWidget::mouseMoveEvent(event);
}

void TitleBar::mouseReleaseEvent(QMouseEvent *event) {
    m_dragging = false;
    QWidget::mouseReleaseEvent(event);
}

}  // namespace wordmem
