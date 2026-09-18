// 自定义标题栏：透明模式 / 不透明度滑杆 / 窗口置顶 / 自动隐藏 / 最小化 / 关闭。
// 对应 Python ui/title_bar.py。
#pragma once

#include <QPoint>
#include <QWidget>

namespace wordmem {

class IconButton;

class TitleBar : public QWidget {
    Q_OBJECT
public:
    explicit TitleBar(QWidget *parent = nullptr);

    IconButton *btn_ghost = nullptr;
    IconButton *btn_opacity = nullptr;
    IconButton *btn_pin = nullptr;
    IconButton *btn_fold = nullptr;
    IconButton *btn_min = nullptr;
    IconButton *btn_close = nullptr;

signals:
    void ghostToggled(bool checked);
    void opacityRequested();
    void pinToggled(bool checked);
    void foldToggled(bool checked);
    void minimizeRequested();
    void closeRequested();

protected:
    // 拖拽移动（窗口边缘缩放由原生 WM_NCHITTEST 处理）
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;

private:
    bool m_dragging = false;
    QPoint m_dragPos;
};

}  // namespace wordmem
