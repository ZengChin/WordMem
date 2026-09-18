#include "ui/widgets.h"

#include <QColor>
#include <QEasingCurve>
#include <QFont>
#include <QFontMetrics>
#include <QLinearGradient>
#include <QPainter>
#include <QPen>
#include <QVariantAnimation>

#include "ui/icons.h"
#include "ui/theme.h"

namespace wordmem {

// ============================================================ IconButton
IconButton::IconButton(const QString &name, const QString &color, int size,
                       int iconSize, const QString &tooltip, bool checkable,
                       bool filledOnCheck, QWidget *parent)
    : QAbstractButton(parent),
      m_name(name),
      m_color(color),
      m_iconSize(iconSize),
      m_filledOnCheck(filledOnCheck) {
    setFixedSize(size, size);
    setCheckable(checkable);
    setCursor(Qt::PointingHandCursor);
    if (!tooltip.isEmpty())
        setToolTip(tooltip);
}

void IconButton::paintEvent(QPaintEvent *) {
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

    const int x = (width() - m_iconSize) / 2;
    const int y = (height() - m_iconSize) / 2;
    const QString iconName =
        (m_filledOnCheck && isChecked()) ? m_name + QLatin1String("_on") : m_name;
    wordmem::icon(iconName, m_color, m_iconSize)
        .paint(&p, x, y, m_iconSize, m_iconSize);
}

void IconButton::enterEvent(QEnterEvent *event) {
    update();
    QAbstractButton::enterEvent(event);
}

void IconButton::leaveEvent(QEvent *event) {
    update();
    QAbstractButton::leaveEvent(event);
}

// ============================================================ PillButton
PillButton::PillButton(const QString &text, const QString &iconName,
                       const QString &color, QWidget *parent)
    : QPushButton(text, parent), m_color(color) {
    setCursor(Qt::PointingHandCursor);
    setFixedHeight(46);
    setIcon(wordmem::icon(iconName, color, 20));
    applyQss(theme::PILL_ALPHA);
}

void PillButton::applyQss(int alpha) {
    const bool ghost = theme::ghostMode();
    const int base = ghost ? theme::GHOST_PILL_ALPHA : alpha;
    const int hover = ghost ? theme::GHOST_PILL_HOVER : 215;
    const int pressed = ghost ? theme::GHOST_PILL_PRESSED : 235;
    const int disabled = ghost ? base : 90;
    setStyleSheet(QStringLiteral(
                      "PillButton { color: %1; font-size: 15px; font-weight: 500;"
                      " padding: 0 22px; border-radius: 23px;"
                      " background: rgba(255,255,255,%2); }"
                      "PillButton:hover { background: rgba(255,255,255,%3); }"
                      "PillButton:pressed { background: rgba(255,255,255,%4); }"
                      "PillButton:disabled { color: #9aa8ae;"
                      " background: rgba(255,255,255,%5); }")
                      .arg(m_color)
                      .arg(base)
                      .arg(hover)
                      .arg(pressed)
                      .arg(disabled));
}

void PillButton::refresh() {
    applyQss(underMouse() ? 215 : theme::PILL_ALPHA);
}

void PillButton::enterEvent(QEnterEvent *event) {
    applyQss(215);
    QPushButton::enterEvent(event);
}

void PillButton::leaveEvent(QEvent *event) {
    applyQss(theme::PILL_ALPHA);
    QPushButton::leaveEvent(event);
}

// ============================================================ Card
Card::Card(int alpha, int radius, QWidget *parent)
    : QWidget(parent), m_alpha(alpha), m_radius(radius) {}

void Card::setAlpha(int alpha) { m_alpha = alpha; }

void Card::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(Qt::NoPen);
    const int alpha = theme::ghostMode() ? theme::GHOST_CARD_ALPHA : m_alpha;
    p.setBrush(QColor(255, 255, 255, alpha));
    p.drawRoundedRect(rect(), m_radius, m_radius);
}

// ============================================================ SmoothBar
SmoothBar::SmoothBar(bool showLabel, const QString &fillColor, QWidget *parent)
    : QWidget(parent), m_showLabel(showLabel), m_fill(fillColor) {
    setFixedHeight(18);
}

void SmoothBar::setFraction(double fraction) {
    const double target = qBound(0.0, fraction, 1.0);
    if (qAbs(target - m_fraction) < 1e-4 && m_anim == nullptr)
        return;
    m_fraction = target;
    if (m_anim != nullptr) {
        m_anim->stop();
        m_anim->deleteLater();
        m_anim = nullptr;
    }
    auto *anim = new QVariantAnimation(this);
    anim->setStartValue(m_shown);
    anim->setEndValue(target);
    anim->setDuration(450);
    anim->setEasingCurve(QEasingCurve::OutCubic);
    connect(anim, &QVariantAnimation::valueChanged, this, [this](const QVariant &v) {
        m_shown = v.toDouble();
        update();
    });
    connect(anim, &QVariantAnimation::finished, this, [this] {
        if (m_anim != nullptr) {
            m_anim->deleteLater();
            m_anim = nullptr;
        }
    });
    m_anim = anim;
    anim->start();
}

void SmoothBar::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    const double barH = 12.0;
    const double radius = barH / 2;
    const QRectF track(0, (height() - barH) / 2, width(), barH);

    // 轨道：半透明胶囊 + 内描边
    p.setPen(Qt::NoPen);
    const int trackAlpha = theme::ghostMode() ? theme::GHOST_TRACK_ALPHA
                                              : theme::TRACK_ALPHA;
    p.setBrush(QColor(255, 255, 255, trackAlpha));
    p.drawRoundedRect(track, radius, radius);
    p.setBrush(Qt::NoBrush);
    QPen edge(QColor(47, 62, 70, 26));
    edge.setWidthF(1.0);
    p.setPen(edge);
    p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), radius - 0.5,
                      radius - 0.5);
    p.setPen(Qt::NoPen);

    // 填充：垂直渐变 + 顶部高光
    QRectF fillRect;
    const bool hasFill = m_shown > 0.005;
    if (hasFill) {
        const double w = qMax(track.width() * m_shown, barH);  // 最短为一个整圆
        fillRect = QRectF(track.x(), track.y(), w, track.height());
        const QColor base(m_fill);
        QLinearGradient grad(fillRect.topLeft(), fillRect.bottomLeft());
        grad.setColorAt(0.0, base.lighter(118));
        grad.setColorAt(1.0, base.darker(106));
        p.setBrush(grad);
        p.drawRoundedRect(fillRect, radius, radius);
        const QRectF gloss = fillRect.adjusted(2.5, 1.5, -2.5, -radius);
        p.setBrush(QColor(255, 255, 255, 52));
        p.drawRoundedRect(gloss, gloss.height() / 2, gloss.height() / 2);
    }

    if (m_showLabel)
        drawLabel(p, track, fillRect, hasFill);
}

void SmoothBar::drawLabel(QPainter &p, const QRectF &track, const QRectF &fillRect,
                          bool hasFill) {
    // 百分比文字居中：压在填充上为白色，其余为青灰，跨界时分段着色
    const QString text =
        QStringLiteral("%1%").arg(m_shown * 100, 0, 'f', 1);
    QFont f = p.font();
    f.setPixelSize(10);
    f.setBold(true);
    p.setFont(f);
    const QFontMetrics fm(f);
    const double tw = fm.horizontalAdvance(text);
    const double left = track.center().x() - tw / 2;
    const QPointF pos(left,
                      track.center().y() + (fm.ascent() - fm.descent()) / 2.0);
    const bool covered = hasFill && fillRect.right() >= left + tw;
    const bool bare = !hasFill || fillRect.right() <= left;
    if (covered || bare) {
        p.setPen(covered ? QColor(255, 255, 255, 240)
                         : QColor(QLatin1String(theme::INK_SOFT)));
        p.drawText(pos, text);
    } else {
        p.setPen(QColor(QLatin1String(theme::INK_SOFT)));
        p.drawText(pos, text);
        p.save();
        p.setClipRect(fillRect);
        p.setPen(QColor(255, 255, 255, 240));
        p.drawText(pos, text);
        p.restore();
    }
}

// ============================================================ Dots
Dots::Dots(QWidget *parent) : QWidget(parent) { setFixedSize(64, 16); }

void Dots::setState(int count, int index) {
    m_count = qMax(1, count);
    m_index = qBound(0, index, m_count - 1);
    setFixedWidth(m_count * 16 + 8);
    update();
}

void Dots::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(Qt::NoPen);
    for (int i = 0; i < m_count; ++i) {
        const bool active = (i == m_index);
        const double r = active ? 4 : 3;
        p.setBrush(QColor(90, 105, 114, active ? 120 : 70));
        p.drawEllipse(QPointF(8 + i * 16.0, height() / 2.0), r, r);
    }
}

// ============================================================ Switch
Switch::Switch(QWidget *parent) : QAbstractButton(parent) {
    setCheckable(true);
    setCursor(Qt::PointingHandCursor);
    setFixedSize(40, 22);
    connect(this, &QAbstractButton::toggled, this, &Switch::onToggled);
}

void Switch::stopAnim() {
    if (m_anim != nullptr) {
        m_anim->stop();
        m_anim->deleteLater();
        m_anim = nullptr;
    }
}

void Switch::onToggled(bool checked) {
    const double target = checked ? 1.0 : 0.0;
    if (!isVisible()) {  // 程序化初始化直接到位
        m_pos = target;
        update();
        return;
    }
    stopAnim();
    auto *anim = new QVariantAnimation(this);
    anim->setStartValue(m_pos);
    anim->setEndValue(target);
    anim->setDuration(170);
    anim->setEasingCurve(QEasingCurve::OutCubic);
    connect(anim, &QVariantAnimation::valueChanged, this, [this](const QVariant &v) {
        m_pos = v.toDouble();
        update();
    });
    connect(anim, &QVariantAnimation::finished, this, [this] {
        if (m_anim != nullptr) {
            m_anim->deleteLater();
            m_anim = nullptr;
        }
    });
    m_anim = anim;
    anim->start();
}

void Switch::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(Qt::NoPen);
    const double h = height();
    const double r = h / 2 - 1;
    const QRectF track(1, 1, width() - 2, h - 2);
    p.setBrush(isChecked() ? QColor(QLatin1String(theme::GREEN_ICON))
                           : QColor(47, 62, 70, 42));
    p.drawRoundedRect(track, r, r);
    const double cx = 1 + r + m_pos * (width() - 2 - 2 * r);
    p.setBrush(QColor(255, 255, 255));
    p.drawEllipse(QPointF(cx, h / 2), r - 1.5, r - 1.5);
}

}  // namespace wordmem
