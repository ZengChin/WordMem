// 首页：词书进度卡片 + 学新词 / 复习词入口（对应 Python ui/views/home_view.py）。
#pragma once

#include <QString>
#include <QWidget>

#include "ui/widgets.h"

class QLabel;

namespace wordmem {

struct AppContext;

// 底部统计卡片：大数字 + 胶囊操作按钮；点击整张卡片即可触发操作
class NumberCard : public Card {
    Q_OBJECT
public:
    NumberCard(const QString &actionText, const QString &iconName,
               QWidget *parent = nullptr);

    QLabel *number = nullptr;
    PillButton *button = nullptr;

signals:
    void clicked();

protected:
    void mousePressEvent(QMouseEvent *event) override;
    void enterEvent(QEnterEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    int m_baseAlpha;
    int m_hoverAlpha;
};

// 词书进度卡片
class BookCard : public Card {
    Q_OBJECT
public:
    explicit BookCard(QWidget *parent = nullptr);

    QLabel *name = nullptr;
    QLabel *counter = nullptr;
    IconButton *list_btn = nullptr;
    IconButton *more = nullptr;
    SmoothBar *bar = nullptr;
};

class HomeView : public QWidget {
    Q_OBJECT
public:
    HomeView(AppContext &ctx, QWidget *parent = nullptr);

    void refresh();

signals:
    void startSession(const QString &mode);  // "new" / "review"
    void wordListRequested();
    void bookManageRequested();

private:
    void start(const QString &mode);
    void openSettings();
    void openStats();

    AppContext &m_ctx;
    BookCard *m_bookCard = nullptr;
    NumberCard *m_cardNew = nullptr;
    NumberCard *m_cardReview = nullptr;
};

}  // namespace wordmem
