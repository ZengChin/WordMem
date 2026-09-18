// 词书管理视图 + 导入词书视图（主窗口内页面切换，不弹窗）。
// 对应 Python ui/views/book_manage_view.py。
#pragma once

#include <QFrame>
#include <QString>
#include <QWidget>

class QComboBox;
class QLabel;
class QLineEdit;
class QPushButton;
class QVBoxLayout;

namespace wordmem {

struct AppContext;
struct Book;
class IconButton;
class SmoothBar;

// 整行可点击的词书行（Python 版用闭包覆盖 mousePressEvent，C++ 需子类化）
class BookRowFrame : public QFrame {
    Q_OBJECT
public:
    explicit BookRowFrame(QWidget *parent = nullptr);

signals:
    void clicked();

protected:
    void mousePressEvent(QMouseEvent *event) override;
};

// 文件拖放区：点击选择、拖放文件
class FileDropZone : public QFrame {
    Q_OBJECT
public:
    explicit FileDropZone(QWidget *parent = nullptr);

    QLabel *label = nullptr;
    QLabel *hint = nullptr;

signals:
    void fileSelected(const QString &path);  // 空字符串表示点击浏览

protected:
    void mousePressEvent(QMouseEvent *event) override;
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dropEvent(QDropEvent *event) override;
};

// 词书管理页面：当前词书信息 + 内置/导入词书列表 + 导入/下载入口
class BookManageView : public QWidget {
    Q_OBJECT
public:
    BookManageView(AppContext &ctx, QWidget *parent = nullptr);

    void refresh();

signals:
    void backRequested();
    void bookSwitched();
    void importRequested();

private:
    void buildCurrentBlock();
    void buildListArea();
    void buildBottomBar();
    void refreshList();
    QLabel *sectionLabel(const QString &text);
    QFrame *bookRow(const Book &book, int activeId, bool deletable);
    void switchBook(int bookId);
    void deleteBook(int bookId);
    void openDownloadUrl();

    AppContext &m_ctx;
    QLabel *m_countLabel = nullptr;
    QLabel *m_curName = nullptr;
    QLabel *m_curDesc = nullptr;
    QLabel *m_curInfo = nullptr;
    SmoothBar *m_curBar = nullptr;
    QVBoxLayout *m_listLayout = nullptr;
    QPushButton *m_btnImport = nullptr;
};

// 导入词书页面：拖拽/选择文件 → 格式 → 名称/描述 → 推荐源 → 导入
class ImportBookView : public QWidget {
    Q_OBJECT
public:
    ImportBookView(AppContext &ctx, QWidget *parent = nullptr);

    // 进入页面时重置状态
    void reset();

signals:
    void backRequested();
    void imported();

private:
    void onFileSelected(const QString &path);
    void pickFile();
    void setFile(const QString &path);
    void updateFileZone();
    void showError(const QString &msg);
    void startImport();
    void setImporting(bool on);

    QWidget *formRow(const QString &label, QWidget *widget);
    QFrame *downloadRow(const QString &name, const QString &url,
                        const QString &desc);
    static QString inputQss();

    AppContext &m_ctx;
    QString m_filePath;
    FileDropZone *m_fileZone = nullptr;
    QComboBox *m_fmtCombo = nullptr;
    QLineEdit *m_nameEdit = nullptr;
    QLineEdit *m_descEdit = nullptr;
    QLabel *m_errorLabel = nullptr;
    QPushButton *m_btnImport = nullptr;
    IconButton *m_btnBack = nullptr;
};

}  // namespace wordmem
