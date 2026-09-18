#include "ui/opacitypopup.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QPainter>
#include <QSlider>

namespace wordmem {

namespace {
const char *kSliderQss = R"QSS(
QSlider::groove:horizontal {
    height: 6px; border-radius: 3px; background: rgba(255,255,255,50);
}
QSlider::sub-page:horizontal {
    height: 6px; border-radius: 3px; background: #7ed8a8;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -5px 0;
    border-radius: 7px; background: #ffffff;
}
QSlider::handle:horizontal:hover { background: #eafff3; }
)QSS";
}  // namespace

OpacitySliderPopup::OpacitySliderPopup(double current, QWidget *parent)
    : QWidget(parent,
              Qt::Popup | Qt::FramelessWindowHint | Qt::NoDropShadowWindowHint),
      m_value(clamp(current)) {
    setAttribute(Qt::WA_TranslucentBackground);

    m_slider = new QSlider(Qt::Horizontal, this);
    m_slider->setRange(qRound(MIN_OPACITY * 100), qRound(MAX_OPACITY * 100));
    m_slider->setValue(qRound(m_value * 100));
    m_slider->setFixedWidth(160);
    m_slider->setCursor(Qt::PointingHandCursor);
    m_slider->setStyleSheet(QLatin1String(kSliderQss));

    m_label = new QLabel(QStringLiteral("%1%").arg(qRound(m_value * 100)), this);
    m_label->setStyleSheet(QStringLiteral(
        "color:#ffffff; font-size:13px; font-weight:600; background:transparent;"));

    auto *lay = new QHBoxLayout(this);
    lay->setContentsMargins(14, 10, 12, 10);
    lay->setSpacing(9);
    lay->addWidget(m_slider);
    lay->addWidget(m_label);

    connect(m_slider, &QSlider::valueChanged, this, [this](int v) {
        m_value = clamp(v / 100.0);
        m_label->setText(QStringLiteral("%1%").arg(qRound(m_value * 100)));
        emit valueChanged(m_value);
    });
}

double OpacitySliderPopup::clamp(double v) {
    return qBound(MIN_OPACITY, v, MAX_OPACITY);
}

double OpacitySliderPopup::value() const { return m_value; }

void OpacitySliderPopup::setValue(double v) {
    m_slider->setValue(qRound(clamp(v) * 100));
}

void OpacitySliderPopup::hideEvent(QHideEvent *event) {
    // Qt.Popup 点击外部 / Esc / close() 都会走 hide，统一在此通知
    emit closed();
    QWidget::hideEvent(event);
}

void OpacitySliderPopup::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(45, 60, 68, 235));
    p.drawRoundedRect(rect(), 12, 12);
}

}  // namespace wordmem
