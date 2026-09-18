// 对话框：学习统计 / 设置。统一无边框卡片风格。
// 对应 Python ui/views/dialogs.py。
#pragma once

#include <QDialog>
#include <QSize>

class QSpinBox;
class QVBoxLayout;
class QWidget;

namespace wordmem {

struct AppContext;
class IconButton;
class Switch;

// 无边框白色圆角对话框基类：标题 + 关闭按钮 + 内容区。
// popupClose=true 时以弹层模式展示：点击窗口外空白区域自动关闭。
class BaseDialog : public QDialog {
    Q_OBJECT
public:
    BaseDialog(const QString &title, QWidget *parent, const QSize &size,
               bool popupClose);

protected:
    QWidget *panel = nullptr;
    QVBoxLayout *body = nullptr;
};

// 学习统计：统计块网格 + 总体进度
class StatsDialog : public BaseDialog {
    Q_OBJECT
public:
    StatsDialog(AppContext &ctx, QWidget *parent = nullptr);

private:
    static QWidget *tile(const QString &key, int value, const QString &color);
};

// 学习设置：分组行卡片 + 步进器 + 滑动开关
class SettingsDialog : public BaseDialog {
    Q_OBJECT
public:
    SettingsDialog(AppContext &ctx, QWidget *parent = nullptr);

private:
    static QWidget *rowTile(const QString &text, QWidget *content,
                            const QString &tooltip = QString());
    static QWidget *stepper(int lo, int hi, int value, QSpinBox **outSpin);

    void save();
    void resetProgress();

    AppContext &m_ctx;
    QSpinBox *m_spin = nullptr;
    QSpinBox *m_gapSpin = nullptr;
    Switch *m_autoPron = nullptr;
};

}  // namespace wordmem
