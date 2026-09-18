#include "core/bookmanager.h"

#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QSet>

#include "core/importers.h"
#include "core/paths.h"

namespace wordmem {

namespace {

// 读取资源/文件 JSON（自动去 BOM）
QJsonDocument loadJson(const QString &path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly))
        return QJsonDocument();
    QByteArray bytes = f.readAll();
    if (bytes.startsWith("\xEF\xBB\xBF"))
        bytes.remove(0, 3);
    return QJsonDocument::fromJson(bytes);
}

using Parser = std::optional<ParsedBook> (*)(const QString &, QString *);

// 显式格式名 -> parser 映射；未知格式回退自动路由
Parser parserForFormat(const QString &fmt) {
    const QString key = fmt.toLower().remove(QLatin1Char('.'));
    if (key == QLatin1String("wordmem"))
        return parseWordmemJson;
    if (key == QLatin1String("simple") || key == QLatin1String("jsonl"))
        return parseSimpleJson;
    if (key == QLatin1String("txt") || key == QLatin1String("text"))
        return parsePlainText;
    if (key == QLatin1String("csv"))
        return parseCsv;
    if (key == QLatin1String("apkg"))
        return parseApkg;
    return parseAuto;
}

}  // namespace

BookManager::BookManager(Repository &repo) : repo(repo) {}

// ------------------------------------------------------------ 内置词书
void BookManager::registerBuiltinBooks() {
    const QString registryPath = builtinRegistryFile();
    const QJsonDocument doc = loadJson(registryPath);
    if (!doc.isObject())
        return;

    QSet<QString> existing;
    const QList<Book> books = repo.listBooks();
    for (const Book &b : books)
        if (b.source == QLatin1String("builtin"))
            existing.insert(b.name);

    const QJsonArray entries =
        doc.object().value(QLatin1String("books")).toArray();
    for (const QJsonValue &v : entries) {
        const QJsonObject entry = v.toObject();
        const QString name = entry.value(QLatin1String("name")).toString();
        if (name.isEmpty() || existing.contains(name))
            continue;  // 幂等：已注册不重复写入
        const QString filename = entry.value(QLatin1String("file")).toString();
        const QString bookPath =
            filename.isEmpty() ? QString() : builtinBookFile(filename);
        const int wordCount = (!bookPath.isEmpty() && QFile::exists(bookPath))
                                  ? countWordsInJson(bookPath)
                                  : 0;
        repo.addBook(name, entry.value(QLatin1String("description")).toString(),
                     QStringLiteral("builtin"), bookPath, wordCount);
    }
}

void BookManager::ensureDefaultActive() {
    const auto activeId = repo.getActiveBookId();
    if (activeId && repo.getBookById(*activeId)) {
        ensureWordsImported(*activeId);  // 已有活动词书：确保 words 已导入
        return;
    }
    // 首次启动：从 registry 读取默认词书文件名
    QString defaultFile;
    const QJsonDocument doc = loadJson(builtinRegistryFile());
    if (doc.isObject())
        defaultFile =
            doc.object().value(QLatin1String("default_book")).toString();

    const QList<Book> builtins = listBuiltinBooks();
    for (const Book &b : builtins) {
        if (!b.filePath.isEmpty() &&
            QFileInfo(b.filePath).fileName() == defaultFile) {
            repo.setActiveBookId(b.id);
            ensureWordsImported(b.id);
            return;
        }
    }
    if (!builtins.isEmpty()) {  // 降级：取第一本内置词书
        repo.setActiveBookId(builtins.first().id);
        ensureWordsImported(builtins.first().id);
    }
}

// ------------------------------------------------------------ 切换词书
bool BookManager::switchBook(int bookId, QString *err) {
    const auto book = repo.getBookById(bookId);
    if (!book) {
        if (err)
            *err = QStringLiteral("词书不存在: id=%1").arg(bookId);
        return false;
    }
    repo.setActiveBookId(bookId);
    ensureWordsImported(bookId);
    return true;
}

// ------------------------------------------------------------ 导入 / 删除
std::optional<int> BookManager::importBook(const QString &path,
                                           const QString &fmt,
                                           const QString &name,
                                           const QString &description,
                                           QString *err) {
    std::optional<ParsedBook> parsed =
        fmt.isEmpty() ? parseAuto(path, err)
                      : parserForFormat(fmt)(path, err);
    if (!parsed) {
        if (err && err->isEmpty())
            *err = QStringLiteral("解析词书失败：%1").arg(path);
        return std::nullopt;
    }
    const ParsedBook &data = *parsed;

    const QFileInfo fi(path);
    // 词书名：优先调用方提供，否则用文件名去扩展名
    const QString bookName = name.isEmpty() ? fi.completeBaseName() : name;
    const QString bookDesc =
        description.isEmpty() ? data.description : description;

    // 复制到 user_books_dir（统一存为 WordMem JSON）
    const QString dest = userBooksDir() + QLatin1Char('/') +
                         fi.completeBaseName() + QLatin1String(".json");
    QJsonObject bookObj;
    bookObj.insert(QLatin1String("name"), bookName);
    bookObj.insert(QLatin1String("description"), bookDesc);
    QJsonObject payload;
    payload.insert(QLatin1String("book"), bookObj);
    QJsonArray wordsArr;
    for (const QJsonObject &w : data.words)
        wordsArr << w;
    payload.insert(QLatin1String("words"), wordsArr);

    QSaveFile out(dest);
    if (!out.open(QIODevice::WriteOnly)) {
        if (err)
            *err = QStringLiteral("无法写入词书文件：%1").arg(dest);
        return std::nullopt;
    }
    out.write(QJsonDocument(payload).toJson(QJsonDocument::Indented));
    if (!out.commit()) {
        if (err)
            *err = QStringLiteral("写入词书文件失败：%1").arg(dest);
        return std::nullopt;
    }

    const int bookId = repo.addBook(bookName, bookDesc,
                                    QStringLiteral("imported"), dest,
                                    int(data.words.size()));
    repo.addWords(bookId, data.words);
    return bookId;
}

bool BookManager::deleteBook(int bookId, QString *err) {
    const auto book = repo.getBookById(bookId);
    if (!book) {
        if (err)
            *err = QStringLiteral("词书不存在: id=%1").arg(bookId);
        return false;
    }
    if (book->source != QLatin1String("imported")) {
        if (err)
            *err = QStringLiteral("内置词书不可删除: %1").arg(book->name);
        return false;
    }
    // 清理 words 和 study_state，再删 books 记录
    repo.clearWordsForBook(bookId);
    repo.deleteBook(bookId);
    if (!book->filePath.isEmpty())
        QFile::remove(book->filePath);  // 删除失败不致命
    return true;
}

// ------------------------------------------------------------ 查询
QList<Book> BookManager::listBuiltinBooks() const {
    QList<Book> out;
    const QList<Book> all = repo.listBooks();
    for (const Book &b : all)
        if (b.source == QLatin1String("builtin"))
            out << b;
    return out;
}

QList<Book> BookManager::listImportedBooks() const {
    QList<Book> out;
    const QList<Book> all = repo.listBooks();
    for (const Book &b : all)
        if (b.source == QLatin1String("imported"))
            out << b;
    return out;
}

std::optional<Book> BookManager::getActiveBook() const {
    return repo.getActiveBook();
}

// ------------------------------------------------------------ 内部工具
void BookManager::ensureWordsImported(int bookId) {
    const auto book = repo.getBookById(bookId);
    if (!book || book->filePath.isEmpty())
        return;
    if (repo.countWordsInBook(bookId) > 0)
        return;  // 表中已有词：视为已导入
    if (!QFile::exists(book->filePath))
        return;
    const auto data = parseAuto(book->filePath);
    if (data && !data->words.isEmpty())
        repo.addWords(bookId, data->words);
}

int BookManager::countWordsInJson(const QString &path) {
    const QJsonDocument doc = loadJson(path);
    if (!doc.isObject())
        return 0;
    return doc.object().value(QLatin1String("words")).toArray().size();
}

}  // namespace wordmem

