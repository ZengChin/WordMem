// 线性不透明度调节条：按钮下方的横向滑杆弹窗，点击外部即隐藏。
// 对应 Python ui/opacity_popup.py。
#pragma once

#include <QWidget>

class QLabel;
class QSlider;

namespace wordmem {

inline constexpr double MIN_OPACITY = 0.25;
inline constexpr double MAX_OPACITY = 1.0;

class OpacitySliderPopup : public QWidget {
    Q_OBJECT
public:
    explicit OpacitySliderPopup(double current = 1.0, QWidget *parent = nullptr);

    double value() const;
    // 设置数值（0.25 ~ 1.0），经滑杆联动后触发 valueChanged
    void setValue(double v);

signals:
    void valueChanged(double value);
    void closed();

protected:
    void hideEvent(QHideEvent *event) override;
    void paintEvent(QPaintEvent *event) override;

private:
    static double clamp(double v);

    double m_value;
    QSlider *m_slider = nullptr;
    QLabel *m_label = nullptr;
};

}  // namespace wordmem
