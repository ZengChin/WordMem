// 词书管理服务：内置词书注册、活动词书切换、外部词书导入与删除。
// 对应 Python core/book_manager.py。
#pragma once

#include <QString>
#include <optional>

#include "core/models.h"
#include "core/repository.h"

namespace wordmem {

class BookManager {
public:
    explicit BookManager(Repository &repo);

    // ------------------------------------------------------------ 内置词书
    void registerBuiltinBooks();  // 幂等：按 name 去重
    void ensureDefaultActive();   // 首次启动设默认词书并导入其 words

    // ------------------------------------------------------------ 切换
    bool switchBook(int bookId, QString *err = nullptr);

    // ------------------------------------------------------------ 导入 / 删除
    // fmt: wordmem/simple/jsonl/txt/text/csv/apkg，空则按扩展名自动路由
    std::optional<int> importBook(const QString &path,
                                  const QString &fmt = QString(),
                                  const QString &name = QString(),
                                  const QString &description = QString(),
                                  QString *err = nullptr);
    bool deleteBook(int bookId, QString *err = nullptr);  // 仅 imported 可删

    // ------------------------------------------------------------ 查询
    QList<Book> listBuiltinBooks() const;
    QList<Book> listImportedBooks() const;
    std::optional<Book> getActiveBook() const;

    Repository &repo;

private:
    void ensureWordsImported(int bookId);
    static int countWordsInJson(const QString &path);
};

}  // namespace wordmem
