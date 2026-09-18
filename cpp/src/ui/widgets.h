// 通用 UI 控件：图标按钮、胶囊按钮、卡片、进度条、轮播圆点、滑动开关。
// 对应 Python ui/widgets.py。
#pragma once

#include <QAbstractButton>
#include <QPushButton>
#include <QString>
#include <QWidget>

class QVariantAnimation;

namespace wordmem {

// 圆形悬停感的图标按钮
class IconButton : public QAbstractButton {
    Q_OBJECT
public:
    explicit IconButton(const QString &name,
                        const QString &color = QStringLiteral("#5a6b72"),
                        int size = 32, int iconSize = 18,
                        const QString &tooltip = QString(), bool checkable = false,
                        bool filledOnCheck = false, QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *event) override;
    void enterEvent(QEnterEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    QString m_name;
    QString m_color;
    int m_iconSize;
    bool m_filledOnCheck;  // 选中时切换为「{name}_on」实心图标
};

// 底部大号胶囊按钮（图标 + 文案），底色随超透明模式变化
class PillButton : public QPushButton {
    Q_OBJECT
public:
    PillButton(const QString &text, const QString &iconName,
               const QString &color, QWidget *parent = nullptr);

    // 透明模式切换后重刷底色，保留当前悬停态
    void refresh();

protected:
    void enterEvent(QEnterEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    void applyQss(int alpha);
    QString m_color;
};

// 半透明白色圆角卡片容器
class Card : public QWidget {
    Q_OBJECT
public:
    explicit Card(int alpha = 165, int radius = 12, QWidget *parent = nullptr);

    void setAlpha(int alpha);

protected:
    void paintEvent(QPaintEvent *event) override;
    int m_alpha;

private:
    int m_radius;
};

// 圆角进度条：渐变填充 + 顶部高光 + 平滑动画，可内置居中百分比
class SmoothBar : public QWidget {
    Q_OBJECT
public:
    explicit SmoothBar(bool showLabel = false,
                       const QString &fillColor = QStringLiteral("#fdfdf4"),
                       QWidget *parent = nullptr);

    // 设置进度 0~1；数值变化时以平滑动画过渡
    void setFraction(double fraction);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    void drawLabel(class QPainter &p, const QRectF &track, const QRectF &fillRect,
                   bool hasFill);

    double m_fraction = 0.0;
    double m_shown = 0.0;  // 动画过程中的显示值
    bool m_showLabel;
    QString m_fill;
    QVariantAnimation *m_anim = nullptr;
};

// 例句轮播圆点指示器
class Dots : public QWidget {
    Q_OBJECT
public:
    explicit Dots(QWidget *parent = nullptr);

    void setState(int count, int index);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    int m_count = 1;
    int m_index = 0;
};

// 滑动开关：胶囊轨道 + 平滑移动的圆形滑块
class Switch : public QAbstractButton {
    Q_OBJECT
public:
    explicit Switch(QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    void onToggled(bool checked);
    void stopAnim();

    double m_pos = 0.0;  // 滑块位置 0=左(关) 1=右(开)
    QVariantAnimation *m_anim = nullptr;
};

}  // namespace wordmem
