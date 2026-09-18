// 应用组装与入口：日志、依赖装配、主窗口启动（对应 Python app.py）。
#include <QApplication>
#include <QDateTime>
#include <QFile>
#include <QMutex>
#include <QMutexLocker>
#include <QStringConverter>
#include <QTextStream>

#include "core/bookmanager.h"
#include "core/paths.h"
#include "core/repository.h"
#include "core/settings.h"
#include "core/speaker.h"
#include "core/studyservice.h"
#include "ui/appcontext.h"
#include "ui/mainwindow.h"

namespace {

const char *kAppName = "WordMem";
// 版本号由 CMake 的 project(VERSION) 经编译期宏注入（单一来源）
#ifndef WORDMEM_VERSION
#define WORDMEM_VERSION "0.0.0"
#endif
const char *kAppVersion = WORDMEM_VERSION;

QMutex g_logMutex;

// 日志：写入 <数据目录>/logs/app.log，超过 1MB 滚动一次（保留一份 .old）
void messageHandler(QtMsgType type, const QMessageLogContext &context,
                    const QString &msg) {
    Q_UNUSED(context);
    const char *level = "INFO";
    switch (type) {
    case QtDebugMsg:
        level = "DEBUG";
        break;
    case QtInfoMsg:
        level = "INFO";
        break;
    case QtWarningMsg:
        level = "WARNING";
        break;
    case QtCriticalMsg:
        level = "CRITICAL";
        break;
    case QtFatalMsg:
        level = "FATAL";
        break;
    }
    const QString line = QStringLiteral("%1 %2 wordmem: %3\n")
                             .arg(QDateTime::currentDateTime()
                                      .toString(QStringLiteral("yyyy-MM-dd HH:mm:ss")),
                                  QLatin1String(level), msg);
    fprintf(stderr, "%s", line.toLocal8Bit().constData());
    fflush(stderr);

    QMutexLocker locker(&g_logMutex);
    const QString path = wordmem::logDir() + QLatin1String("/app.log");
    QFile log(path);
    if (log.exists() && log.size() > 1000000) {
        QFile::remove(path + QLatin1String(".old"));
        log.rename(path + QLatin1String(".old"));
        log.setFileName(path);
    }
    if (log.open(QIODevice::Append | QIODevice::Text)) {
        QTextStream out(&log);
        out.setEncoding(QStringConverter::Utf8);
        out << line;
    }
}

}  // namespace

int main(int argc, char *argv[]) {
    qInstallMessageHandler(messageHandler);

    QApplication app(argc, argv);
    app.setApplicationName(QLatin1String(kAppName));
    app.setApplicationVersion(QLatin1String(kAppVersion));
    app.setQuitOnLastWindowClosed(true);

    // 依赖装配：配置 -> 仓库 -> 词书管理 -> 服务 -> 发音
    wordmem::ConfigManager configs;
    wordmem::Repository repo(wordmem::databaseFile());
    wordmem::BookManager books(repo);
    books.registerBuiltinBooks();
    books.ensureDefaultActive();
    wordmem::StudyService service(repo, configs.config.batchSize,
                                  configs.config.requeueGap);
    wordmem::Speaker tts;
    wordmem::AppContext ctx;
    ctx.repo = &repo;
    ctx.service = &service;
    ctx.configs = &configs;
    ctx.speaker = &tts;
    ctx.books = &books;

    wordmem::MainWindow window(ctx);
    window.show();
    qInfo("%s v%s 启动完成", kAppName, kAppVersion);
    return app.exec();
}
