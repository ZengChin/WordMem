// 无边框主窗口：背景绘制、超透明模式、按钮/字体不透明度、原生拖边缩放。
// 对应 Python ui/main_window.py。
#pragma once

#include <QWidget>

class QStackedWidget;
class QVariantAnimation;
class QTimer;
class QPainter;

namespace wordmem {

struct AppContext;
class OpacitySliderPopup;
class TitleBar;
class HomeView;
class StudyView;
class SpellView;
class WordListPage;
class BookManageView;
class ImportBookView;

class MainWindow : public QWidget {
    Q_OBJECT
public:
    explicit MainWindow(AppContext &ctx, QWidget *parent = nullptr);

    static constexpr int RESIZE_MARGIN = 8;  // 边缘热区宽度（px）
    static constexpr int MIN_W = 320;
    static constexpr int MIN_H = 420;
    // 透明模式下菜单栏的固定半透明度
    static constexpr double GHOST_TITLEBAR_OPACITY = 0.55;

signals:
    void closed();

protected:
    bool nativeEvent(const QByteArray &eventType, void *message,
                     qintptr *result) override;
    void paintEvent(QPaintEvent *event) override;
    void closeEvent(QCloseEvent *event) override;

private:
    // ---- 配置 ----
    void applyConfig();
    static void setEffect(QWidget *widget, double opacity);  // <0 表示移除效果
    void applyFgOpacity(double value);

    // ---- 标题栏交互 ----
    void onGhost(bool checked);
    void showOpacityDial();
    void onDialClosed();
    void onPin(bool checked);
    void onFold(bool checked);

    // ---- 自动隐藏 ----
    void startAutoHideWatch();
    void checkAutoHide();
    void hideContent();
    void restoreContent();
    void runHideAnim(double target);

    // ---- 视图切换 ----
    void startSession(const QString &mode);
    void goHome();
    void beginSpell();
    void openWordList();
    void openBookManage();
    void openImportBook();
    void backToBookManage();
    void onImportDone();

    // ---- 绘制 ----
    void paintBackground(QPainter &p, double k, const QRectF &region);
    void paintBorder(QPainter &p, double k);

    AppContext &m_ctx;
    TitleBar *m_titleBar = nullptr;
    QStackedWidget *m_stack = nullptr;
    QWidget *m_content = nullptr;
    HomeView *m_homeView = nullptr;
    StudyView *m_studyView = nullptr;
    SpellView *m_spellView = nullptr;
    WordListPage *m_wordListView = nullptr;
    BookManageView *m_bookManageView = nullptr;
    ImportBookView *m_importBookView = nullptr;

    OpacitySliderPopup *m_opacityPopup = nullptr;
    bool m_contentHidden = false;  // 自动隐藏态：窗口原位不动，仅菜单栏可见
    double m_hideProgress = 0.0;   // 隐藏动画进度 0=显示 1=隐藏
    QVariantAnimation *m_hideAnim = nullptr;
    QTimer *m_autoHideTimer = nullptr;
};

}  // namespace wordmem
