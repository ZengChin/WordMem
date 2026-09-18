// 单词列表页：当前词库全部单词，默认隐藏中文，点行显示，可一键切换。
// 对应 Python ui/views/word_list_view.py。
#pragma once

#include <QSet>
#include <QString>
#include <QWidget>

#include "core/models.h"

class QLabel;
class QPushButton;
class QScrollArea;

namespace wordmem {

struct AppContext;
class IconButton;

// 虚拟化单词列表：内部高度为全部行，仅绘制可见行。
// 必须通过 setScrollArea 关联宿主滚动区，以获取滚动偏移与视口高度。
class WordListView : public QWidget {
    Q_OBJECT
public:
    explicit WordListView(QWidget *parent = nullptr);

    void setScrollArea(QScrollArea *area);
    void setWords(const QList<Word> &words);
    void showAll(bool show);

protected:
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void leaveEvent(QEvent *event) override;
    void paintEvent(QPaintEvent *event) override;

private:
    int rowAt(int y) const;
    int scrollOffset() const;
    int viewportHeight() const;

    static constexpr int ROW_H = 44;
    QList<Word> m_words;
    QSet<int> m_shown;
    int m_hover = -1;
    QScrollArea *m_scrollArea = nullptr;
};

// 单词列表页（主窗口内切换展示，不弹新窗口）
class WordListPage : public QWidget {
    Q_OBJECT
public:
    WordListPage(AppContext &ctx, QWidget *parent = nullptr);

    void refresh();

signals:
    void backRequested();

private:
    void updateToggleText();
    void onToggleAll();

    AppContext &m_ctx;
    QLabel *m_countLabel = nullptr;
    QPushButton *m_btnToggle = nullptr;
    WordListView *m_listView = nullptr;
    bool m_allShown = false;
};

// 列表滚动区通用样式（细滚动条 + 透明背景）
QString scrollAreaQss();

}  // namespace wordmem
