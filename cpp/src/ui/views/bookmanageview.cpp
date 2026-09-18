#include "ui/views/bookmanageview.h"

#include <QApplication>
#include <QComboBox>
#include <QDesktopServices>
#include <QDragEnterEvent>
#include <QDropEvent>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QMimeData>
#include <QPushButton>
#include <QScrollArea>
#include <QUrl>
#include <QVBoxLayout>

#include "core/bookmanager.h"
#include "core/models.h"
#include "core/repository.h"
#include "core/studyservice.h"
#include "ui/appcontext.h"
#include "ui/icons.h"
#include "ui/theme.h"
#include "ui/views/wordlistview.h"
#include "ui/widgets.h"

namespace wordmem {

namespace {

// 格式下拉项：显示文本 + 传给 BookManager 的 fmt 值（空串表示自动识别）
const struct {
    const char *label;
    const char *fmt;
} kFormatOptions[] = {
    {"自动识别", ""},
    {"WordMem JSON", "wordmem"},
    {"简单 JSON", "simple"},
    {"JSONL", "jsonl"},
    {"TXT", "txt"},
    {"CSV", "csv"},
    {"Anki .apkg", "apkg"},
};
constexpr int kFormatCount = int(sizeof(kFormatOptions) / sizeof(kFormatOptions[0]));

// 推荐词库下载源：名称 / 链接 / 简介
const struct {
    const char *name;
    const char *url;
    const char *desc;
} kDownloadSources[] = {
    {"AnkiWeb 共享牌组", "https://ankiweb.net/shared/decks?search=english",
     "海量 .apkg 牌组，导入时自动识别字段"},
    {"KyleBing/english-vocabulary",
     "https://github.com/KyleBing/english-vocabulary",
     "含 CET4/CET6/考研，TXT/JSON 格式"},
    {"skywind3000/ECDICT", "https://github.com/skywind3000/ECDICT",
     "77 万词条 CSV，含音标释义"},
    {"mahavivo/english-wordlists",
     "https://github.com/mahavivo/english-wordlists", "多种分类词库"},
};
constexpr int kSourceCount =
    int(sizeof(kDownloadSources) / sizeof(kDownloadSources[0]));

}  // namespace

// ============================================================ BookRowFrame
BookRowFrame::BookRowFrame(QWidget *parent) : QFrame(parent) {}

void BookRowFrame::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton)
        emit clicked();
    QFrame::mousePressEvent(event);
}

// ============================================================ FileDropZone
FileDropZone::FileDropZone(QWidget *parent) : QFrame(parent) {
    setAcceptDrops(true);
    setCursor(Qt::PointingHandCursor);
    setFixedHeight(72);
    setObjectName(QStringLiteral("fileZone"));

    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(0, 0, 0, 0);
    lay->setSpacing(2);

    label = new QLabel(QStringLiteral("点击选择或拖拽文件到此处"), this);
    label->setAlignment(Qt::AlignCenter);
    label->setAttribute(Qt::WA_TransparentForMouseEvents, true);

    hint = new QLabel(QStringLiteral("支持 JSON / JSONL / TXT / CSV / apkg"), this);
    hint->setAlignment(Qt::AlignCenter);
    hint->setAttribute(Qt::WA_TransparentForMouseEvents, true);

    lay->addStretch(1);
    lay->addWidget(label);
    lay->addWidget(hint);
    lay->addStretch(1);
}

void FileDropZone::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton)
        emit fileSelected(QString());
    QFrame::mousePressEvent(event);
}

void FileDropZone::dragEnterEvent(QDragEnterEvent *event) {
    if (event->mimeData()->hasUrls())
        event->acceptProposedAction();
}

void FileDropZone::dropEvent(QDropEvent *event) {
    const QList<QUrl> urls = event->mimeData()->urls();
    if (!urls.isEmpty())
        emit fileSelected(urls.first().toLocalFile());
}

// ============================================================ BookManageView
BookManageView::BookManageView(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(2, 2, 2, 4);
    lay->setSpacing(8);

    // ---- 顶栏 ----
    auto *head = new QHBoxLayout;
    auto *btnBack = new IconButton(QStringLiteral("back"),
                                   QStringLiteral("#5a6b72"), 34, 19,
                                   QStringLiteral("返回首页"), false, false, this);
    auto *title = new QLabel(QStringLiteral("词书"), this);
    title->setStyleSheet(QStringLiteral("color:%1; font-size:16px; font-weight:600;")
                             .arg(QLatin1String(theme::INK_DARK)));
    m_countLabel = new QLabel(this);
    m_countLabel->setStyleSheet(QStringLiteral("color:%1; font-size:13px;")
                                    .arg(QLatin1String(theme::INK_SOFT)));
    head->addWidget(btnBack);
    head->addSpacing(6);
    head->addWidget(title);
    head->addWidget(m_countLabel);
    head->addStretch(1);
    lay->addLayout(head);

    buildCurrentBlock();
    buildListArea();
    buildBottomBar();

    connect(btnBack, &QAbstractButton::clicked, this,
            &BookManageView::backRequested);
    connect(m_btnImport, &QPushButton::clicked, this,
            &BookManageView::importRequested);

    refreshList();
}

void BookManageView::buildCurrentBlock() {
    auto *block = new QFrame(this);
    block->setObjectName(QStringLiteral("curBlock"));
    // 用 #curBlock 而非 QFrame 选择器：QLabel 也是 QFrame 子类，
    // 类型选择器会级联给内部文字标签加上边框，形成多余的线框
    block->setStyleSheet(QStringLiteral(
                             "#curBlock { background:%1; border-radius:10px;"
                             " border:1px solid #cfe5d8; }")
                             .arg(QLatin1String(theme::GREEN_BG)));
    auto *lay = new QVBoxLayout(block);
    lay->setContentsMargins(14, 10, 14, 10);
    lay->setSpacing(3);

    m_curName = new QLabel(block);
    m_curName->setStyleSheet(QStringLiteral("color:%1; font-size:15px;"
                                            " font-weight:600;")
                                 .arg(QLatin1String(theme::GREEN)));
    m_curDesc = new QLabel(block);
    m_curDesc->setWordWrap(true);
    m_curDesc->setStyleSheet(QStringLiteral("color:%1; font-size:12px;")
                                 .arg(QLatin1String(theme::INK)));
    m_curInfo = new QLabel(block);
    m_curInfo->setStyleSheet(QStringLiteral("color:%1; font-size:11px;")
                                 .arg(QLatin1String(theme::INK_SOFT)));
    m_curBar = new SmoothBar(false, QLatin1String(theme::GREEN_ICON), block);
    m_curBar->setFixedHeight(14);
    lay->addWidget(m_curName);
    lay->addWidget(m_curDesc);
    lay->addWidget(m_curInfo);
    lay->addWidget(m_curBar);
    static_cast<QVBoxLayout *>(layout())->addWidget(block);
}

void BookManageView::buildListArea() {
    auto *scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setStyleSheet(scrollAreaQss());
    auto *container = new QWidget;
    m_listLayout = new QVBoxLayout(container);
    m_listLayout->setContentsMargins(0, 0, 0, 0);
    m_listLayout->setSpacing(7);
    m_listLayout->addStretch(1);
    scroll->setWidget(container);
    static_cast<QVBoxLayout *>(layout())->addWidget(scroll, 1);
}

void BookManageView::buildBottomBar() {
    auto *bar = new QHBoxLayout;
    bar->setSpacing(8);
    m_btnImport = new QPushButton(QStringLiteral(" 导入词书"), this);
    m_btnImport->setCursor(Qt::PointingHandCursor);
    m_btnImport->setFixedHeight(34);
    m_btnImport->setIcon(icon(QStringLiteral("upload"),
                              QLatin1String(theme::GREEN), 15));
    m_btnImport->setStyleSheet(QStringLiteral(
                                   "QPushButton { color:%1; border:1px solid #cfe5d8;"
                                   " border-radius:17px; padding:0 16px;"
                                   " font-size:13px; background:transparent; }"
                                   "QPushButton:hover { background:%2; }")
                                   .arg(QLatin1String(theme::GREEN),
                                        QLatin1String(theme::GREEN_BG)));

    auto *btnDownload = new QPushButton(QStringLiteral(" 下载更多"), this);
    btnDownload->setCursor(Qt::PointingHandCursor);
    btnDownload->setFixedHeight(34);
    btnDownload->setIcon(icon(QStringLiteral("download"),
                              QLatin1String(theme::INK_SOFT), 15));
    btnDownload->setStyleSheet(QStringLiteral(
        "QPushButton { color:%1; border:1px solid #dbe3e6;"
        " border-radius:17px; padding:0 16px; font-size:13px;"
        " background:transparent; }"
        "QPushButton:hover { background:#f4f7f8; }")
                                   .arg(QLatin1String(theme::INK_SOFT)));
    connect(btnDownload, &QPushButton::clicked, this,
            &BookManageView::openDownloadUrl);

    bar->addWidget(m_btnImport);
    bar->addStretch(1);
    bar->addWidget(btnDownload);
    static_cast<QVBoxLayout *>(layout())->addLayout(bar);
}

void BookManageView::refresh() { refreshList(); }

void BookManageView::refreshList() {
    // 重建当前词书信息 + 词书列表
    const auto book = m_ctx.books->getActiveBook();
    const HomeSummary summary = m_ctx.service->homeSummary();
    m_curName->setText(book ? book->name : QStringLiteral("（无词书）"));
    m_curDesc->setText((book && !book->description.isEmpty())
                           ? book->description
                           : QStringLiteral("暂无描述"));
    m_curInfo->setText(QStringLiteral("共 %1 词 · 已学 %2 · 待复习 %3")
                           .arg(summary.total)
                           .arg(summary.learned)
                           .arg(summary.reviewLeft));
    m_curBar->setFraction(static_cast<double>(summary.learned) /
                          qMax(1, summary.total));

    // 清空列表区（保留末尾的 stretch）
    while (m_listLayout->count() > 1) {
        QLayoutItem *item = m_listLayout->takeAt(0);
        if (QWidget *w = item->widget())
            w->deleteLater();
        delete item;
    }

    const int activeId = book ? book->id : -1;
    int count = 0;

    // 内置词书分组
    const QList<Book> builtins = m_ctx.books->listBuiltinBooks();
    if (!builtins.isEmpty()) {
        count += builtins.size();
        m_listLayout->insertWidget(m_listLayout->count() - 1,
                                   sectionLabel(QStringLiteral("内置词书")));
        for (const Book &b : builtins)
            m_listLayout->insertWidget(m_listLayout->count() - 1,
                                       bookRow(b, activeId, false));
    }

    // 用户导入词书分组
    const QList<Book> imported = m_ctx.books->listImportedBooks();
    if (!imported.isEmpty()) {
        count += imported.size();
        m_listLayout->insertWidget(m_listLayout->count() - 1,
                                   sectionLabel(QStringLiteral("我的导入")));
        for (const Book &b : imported)
            m_listLayout->insertWidget(m_listLayout->count() - 1,
                                       bookRow(b, activeId, true));
    }

    m_countLabel->setText(QStringLiteral("共 %1 本").arg(count));
}

QLabel *BookManageView::sectionLabel(const QString &text) {
    auto *lab = new QLabel(text, this);
    lab->setStyleSheet(QStringLiteral("color:%1; font-size:11px; font-weight:600;"
                                      " padding:8px 2px 4px 2px;")
                           .arg(QLatin1String(theme::INK_SOFT)));
    return lab;
}

QFrame *BookManageView::bookRow(const Book &book, int activeId, bool deletable) {
    // 单行词书：名称 + 词数 + 切换/状态 + 可选删除，整行可点击切换
    const bool isActive = (book.id == activeId);
    auto *row = new BookRowFrame;
    row->setObjectName(QStringLiteral("bookRow"));

    if (isActive) {
        row->setStyleSheet(QStringLiteral(
                               "#bookRow { background:%1; border-radius:8px;"
                               " border:1px solid %2; }")
                               .arg(QLatin1String(theme::GREEN_BG),
                                    QLatin1String(theme::GREEN_ICON)));
    } else {
        row->setCursor(Qt::PointingHandCursor);
        row->setStyleSheet(QStringLiteral(
            "#bookRow { background:#f4f7f8; border-radius:8px;"
            " border:1px solid transparent; }"
            "#bookRow:hover { background:#edf2f3; border-color:#dbe3e6; }"));
        connect(row, &BookRowFrame::clicked, this,
                [this, id = book.id] { switchBook(id); });
    }

    auto *lay = new QHBoxLayout(row);
    lay->setContentsMargins(12, 8, 10, 8);
    lay->setSpacing(10);

    auto *name = new QLabel(book.name, row);
    name->setStyleSheet(QStringLiteral("color:%1; font-size:13px; font-weight:%2;")
                            .arg(QLatin1String(isActive ? theme::INK_DARK
                                                        : theme::INK))
                            .arg(isActive ? 600 : 400));
    lay->addWidget(name, 1);

    auto *count = new QLabel(QStringLiteral("%1 词").arg(book.wordCount), row);
    count->setStyleSheet(QStringLiteral("color:%1; font-size:11px;")
                             .arg(QLatin1String(theme::INK_SOFT)));
    lay->addWidget(count);

    if (isActive) {
        auto *tag = new QLabel(QStringLiteral("使用中"), row);
        tag->setStyleSheet(QStringLiteral(
            "color:%1; font-size:11px; font-weight:600; padding:2px 8px;"
            " border:1px solid #cfe5d8; border-radius:10px; background:white;")
                               .arg(QLatin1String(theme::GREEN)));
        lay->addWidget(tag);
    } else {
        auto *btn = new QPushButton(QStringLiteral("切换"), row);
        btn->setCursor(Qt::PointingHandCursor);
        btn->setFixedHeight(26);
        btn->setStyleSheet(QStringLiteral(
                               "QPushButton { color:%1; border:1px solid #cfe5d8;"
                               " border-radius:13px; padding:0 12px;"
                               " font-size:12px; background:white; }"
                               "QPushButton:hover { background:%2;"
                               " border-color:%3; }")
                               .arg(QLatin1String(theme::GREEN),
                                    QLatin1String(theme::GREEN_BG),
                                    QLatin1String(theme::GREEN_ICON)));
        connect(btn, &QPushButton::clicked, this,
                [this, id = book.id] { switchBook(id); });
        lay->addWidget(btn);
    }

    if (deletable && !isActive) {
        auto *delBtn = new IconButton(QStringLiteral("close"),
                                      QStringLiteral("#b03a3a"), 22, 11,
                                      QStringLiteral("删除词书"), false, false, row);
        connect(delBtn, &QAbstractButton::clicked, this,
                [this, id = book.id] { deleteBook(id); });
        lay->addWidget(delBtn);
    }
    return row;
}

void BookManageView::switchBook(int bookId) {
    if (!m_ctx.repo->getBookById(bookId))
        return;
    m_ctx.books->switchBook(bookId);
    refreshList();
    emit bookSwitched();
}

void BookManageView::deleteBook(int bookId) {
    const auto book = m_ctx.repo->getBookById(bookId);
    if (!book)
        return;
    const auto ret = QMessageBox::question(
        this, QStringLiteral("删除词书"),
        QStringLiteral("确定删除导入词书《%1》？\n词书及其学习进度将被清除，不可恢复。")
            .arg(book->name),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
    if (ret != QMessageBox::Yes)
        return;
    QString err;
    if (!m_ctx.books->deleteBook(bookId, &err)) {
        QMessageBox::warning(this, QStringLiteral("无法删除"), err);
        return;
    }
    refreshList();
    emit bookSwitched();
}

void BookManageView::openDownloadUrl() {
    QDesktopServices::openUrl(
        QUrl(QStringLiteral("https://github.com/KyleBing/english-vocabulary")));
}

// ============================================================ ImportBookView
ImportBookView::ImportBookView(AppContext &ctx, QWidget *parent)
    : QWidget(parent), m_ctx(ctx) {
    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(2, 2, 2, 4);
    lay->setSpacing(8);

    // ---- 顶栏 ----
    auto *head = new QHBoxLayout;
    m_btnBack = new IconButton(QStringLiteral("back"), QStringLiteral("#5a6b72"), 34,
                               19, QStringLiteral("返回词书管理"), false, false,
                               this);
    auto *title = new QLabel(QStringLiteral("导入词书"), this);
    title->setStyleSheet(QStringLiteral("color:%1; font-size:16px; font-weight:600;")
                             .arg(QLatin1String(theme::INK_DARK)));
    head->addWidget(m_btnBack);
    head->addSpacing(6);
    head->addWidget(title);
    head->addStretch(1);
    lay->addLayout(head);

    // ---- 滚动内容区 ----
    auto *scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setStyleSheet(scrollAreaQss());
    auto *container = new QWidget;
    auto *cl = new QVBoxLayout(container);
    cl->setContentsMargins(0, 0, 0, 0);
    cl->setSpacing(8);

    // 文件拖放区
    m_fileZone = new FileDropZone(container);
    connect(m_fileZone, &FileDropZone::fileSelected, this,
            &ImportBookView::onFileSelected);
    cl->addWidget(m_fileZone);

    // 表单
    m_fmtCombo = new QComboBox(container);
    for (int i = 0; i < kFormatCount; ++i)
        m_fmtCombo->addItem(QLatin1String(kFormatOptions[i].label));
    cl->addWidget(formRow(QStringLiteral("格式"), m_fmtCombo));

    m_nameEdit = new QLineEdit(container);
    m_nameEdit->setPlaceholderText(QStringLiteral("留空则用文件名"));
    cl->addWidget(formRow(QStringLiteral("名称"), m_nameEdit));

    m_descEdit = new QLineEdit(container);
    m_descEdit->setPlaceholderText(QStringLiteral("可选"));
    cl->addWidget(formRow(QStringLiteral("描述"), m_descEdit));

    // 推荐下载源
    auto *cap = new QLabel(QStringLiteral("推荐词库下载"), container);
    cap->setStyleSheet(QStringLiteral("color:%1; font-size:12px;"
                                      " padding:6px 2px 4px 2px;")
                           .arg(QLatin1String(theme::INK_SOFT)));
    cl->addWidget(cap);
    for (int i = 0; i < kSourceCount; ++i)
        cl->addWidget(downloadRow(QLatin1String(kDownloadSources[i].name),
                                  QLatin1String(kDownloadSources[i].url),
                                  QLatin1String(kDownloadSources[i].desc)));

    cl->addStretch(1);
    scroll->setWidget(container);
    lay->addWidget(scroll, 1);

    // ---- 底部：错误提示 + 导入按钮 ----
    m_errorLabel = new QLabel(this);
    m_errorLabel->setStyleSheet(QStringLiteral(
        "color:#b03a3a; font-size:12px; padding:2px 2px;"));
    m_errorLabel->setWordWrap(true);
    m_errorLabel->setVisible(false);
    lay->addWidget(m_errorLabel);

    m_btnImport = new QPushButton(QStringLiteral("导入"), this);
    m_btnImport->setCursor(Qt::PointingHandCursor);
    m_btnImport->setFixedHeight(38);
    m_btnImport->setStyleSheet(QStringLiteral(
        "QPushButton { color:white; background:%1; border-radius:19px;"
        " font-size:14px; font-weight:600; }"
        "QPushButton:hover { background:%2; }"
        "QPushButton:disabled { background:#c9d6d3; }")
                                   .arg(QLatin1String(theme::GREEN),
                                        QLatin1String(theme::GREEN_ICON)));
    connect(m_btnImport, &QPushButton::clicked, this, &ImportBookView::startImport);
    lay->addWidget(m_btnImport);

    connect(m_btnBack, &QAbstractButton::clicked, this,
            &ImportBookView::backRequested);

    updateFileZone();
}

// -------------------------------------------------- 表单构件
QWidget *ImportBookView::formRow(const QString &label, QWidget *widget) {
    auto *row = new QWidget(widget->parentWidget());
    row->setStyleSheet(QStringLiteral("background: transparent;"));
    auto *lay = new QHBoxLayout(row);
    lay->setContentsMargins(0, 0, 0, 0);
    lay->setSpacing(8);
    auto *lab = new QLabel(label, row);
    lab->setFixedWidth(38);
    lab->setStyleSheet(QStringLiteral("color:%1; font-size:13px;"
                                      " background:transparent; border:none;")
                           .arg(QLatin1String(theme::INK_SOFT)));
    lay->addWidget(lab);
    widget->setFixedHeight(34);
    widget->setStyleSheet(inputQss());
    lay->addWidget(widget, 1);
    return row;
}

QString ImportBookView::inputQss() {
    return QStringLiteral(
        "QLineEdit, QComboBox { background:white; border:1px solid #dbe3e6;"
        " border-radius:8px; padding:0 10px; color:#2f3e46; font-size:13px; }"
        "QLineEdit:focus, QComboBox:focus { border:1px solid #3fa26b; }"
        "QComboBox::drop-down { border:none; width:20px; }"
        "QComboBox QAbstractItemView { background:white;"
        " border:1px solid #dbe3e6; border-radius:4px;"
        " selection-background-color:#e9f5ee; }");
}

QFrame *ImportBookView::downloadRow(const QString &name, const QString &url,
                                    const QString &desc) {
    auto *row = new QFrame;
    row->setObjectName(QStringLiteral("dlRow"));
    row->setStyleSheet(QStringLiteral(
                           "#dlRow { background:#f4f7f8; border-radius:8px;"
                           " border:1px solid transparent; }"
                           "#dlRow:hover { background:%1;"
                           " border-color:#cfe5d8; }")
                           .arg(QLatin1String(theme::GREEN_BG)));
    auto *lay = new QHBoxLayout(row);
    lay->setContentsMargins(12, 7, 12, 7);
    lay->setSpacing(8);

    auto *text = new QVBoxLayout;
    text->setSpacing(1);
    auto *title = new QLabel(QStringLiteral("<a href=\"%1\""
                                            " style=\"color:#2e8b5f;"
                                            "text-decoration:none\">%2</a>")
                                 .arg(url, name),
                             row);
    title->setOpenExternalLinks(true);
    title->setTextInteractionFlags(Qt::TextBrowserInteraction);
    title->setStyleSheet(QStringLiteral("color:%1; font-size:13px;"
                                        " background:transparent; border:none;")
                             .arg(QLatin1String(theme::GREEN)));
    auto *sub = new QLabel(desc, row);
    sub->setStyleSheet(QStringLiteral("color:%1; font-size:11px;"
                                      " background:transparent; border:none;")
                           .arg(QLatin1String(theme::INK_SOFT)));
    text->addWidget(title);
    text->addWidget(sub);
    lay->addLayout(text, 1);

    auto *arrow = new QLabel(QStringLiteral("↗"), row);
    arrow->setStyleSheet(QStringLiteral("color:%1; font-size:14px;"
                                        " background:transparent; border:none;")
                             .arg(QLatin1String(theme::INK_SOFT)));
    lay->addWidget(arrow);
    return row;
}

// -------------------------------------------------- 文件选择
void ImportBookView::onFileSelected(const QString &path) {
    if (path.isEmpty())
        pickFile();
    else
        setFile(path);
}

void ImportBookView::pickFile() {
    const QString path = QFileDialog::getOpenFileName(
        this, QStringLiteral("选择词书文件"), QString(),
        QStringLiteral("词书文件 (*.json *.jsonl *.txt *.csv *.apkg)"));
    if (!path.isEmpty())
        setFile(path);
}

void ImportBookView::setFile(const QString &path) {
    m_filePath = path;
    if (m_nameEdit->text().trimmed().isEmpty())
        m_nameEdit->setText(QFileInfo(path).completeBaseName());
    updateFileZone();
}

void ImportBookView::updateFileZone() {
    if (!m_filePath.isEmpty()) {
        m_fileZone->label->setText(QFileInfo(m_filePath).fileName());
        m_fileZone->label->setStyleSheet(QStringLiteral(
            "color:%1; font-size:13px; font-weight:600;"
            " background:transparent; border:none;")
                                             .arg(QLatin1String(theme::GREEN)));
        m_fileZone->hint->setText(QStringLiteral("点击重新选择"));
        m_fileZone->hint->setStyleSheet(QStringLiteral(
            "color:%1; font-size:11px; background:transparent; border:none;")
                                            .arg(QLatin1String(theme::INK_SOFT)));
        m_fileZone->setStyleSheet(QStringLiteral(
                                      "#fileZone { background: %1;"
                                      " border: 2px solid %2;"
                                      " border-radius: 10px; }"
                                      "#fileZone:hover { border-color: %3; }")
                                      .arg(QLatin1String(theme::GREEN_BG),
                                           QLatin1String(theme::GREEN_ICON),
                                           QLatin1String(theme::GREEN)));
    } else {
        m_fileZone->label->setText(QStringLiteral("点击选择或拖拽文件到此处"));
        m_fileZone->label->setStyleSheet(QStringLiteral(
            "color:%1; font-size:13px; background:transparent; border:none;")
                                             .arg(QLatin1String(theme::INK_SOFT)));
        m_fileZone->hint->setText(
            QStringLiteral("支持 JSON / JSONL / TXT / CSV / apkg"));
        m_fileZone->hint->setStyleSheet(QStringLiteral(
            "color:%1; font-size:11px; background:transparent; border:none;")
                                            .arg(QLatin1String(theme::INK_SOFT)));
        m_fileZone->setStyleSheet(QStringLiteral(
            "#fileZone { background: #f8fafb; border: 2px dashed #c9d6d3;"
            " border-radius: 10px; }"
            "#fileZone:hover { border-color: %1; background: %2; }")
                                      .arg(QLatin1String(theme::GREEN_ICON),
                                           QLatin1String(theme::GREEN_BG)));
    }
}

// -------------------------------------------------- 导入逻辑
void ImportBookView::reset() {
    m_filePath.clear();
    m_nameEdit->clear();
    m_descEdit->clear();
    m_fmtCombo->setCurrentIndex(0);
    m_errorLabel->setVisible(false);
    updateFileZone();
}

void ImportBookView::showError(const QString &msg) {
    m_errorLabel->setText(msg);
    m_errorLabel->setVisible(true);
}

void ImportBookView::startImport() {
    const QString path = m_filePath;
    if (path.isEmpty()) {
        showError(QStringLiteral("请先选择要导入的词书文件。"));
        return;
    }
    if (!QFileInfo::exists(path)) {
        showError(QStringLiteral("找不到文件：%1").arg(path));
        return;
    }

    m_errorLabel->setVisible(false);
    const int idx = m_fmtCombo->currentIndex();
    const QString fmt = (idx >= 0 && idx < kFormatCount)
                            ? QLatin1String(kFormatOptions[idx].fmt)
                            : QString();
    const QString name = m_nameEdit->text().trimmed();
    const QString description = m_descEdit->text().trimmed();

    setImporting(true);
    QApplication::processEvents();

    QString err;
    const auto bookId = m_ctx.books->importBook(path, fmt, name, description, &err);
    setImporting(false);
    if (bookId)
        emit imported();
    else
        showError(err.isEmpty() ? QStringLiteral("导入失败：%1").arg(path) : err);
}

void ImportBookView::setImporting(bool on) {
    m_btnImport->setEnabled(!on);
    m_btnBack->setEnabled(!on);
    m_btnImport->setText(on ? QStringLiteral("导入中…")
                            : QStringLiteral("导入"));
    m_fileZone->setEnabled(!on);
    m_fmtCombo->setEnabled(!on);
    m_nameEdit->setEnabled(!on);
    m_descEdit->setEnabled(!on);
}

}  // namespace wordmem
