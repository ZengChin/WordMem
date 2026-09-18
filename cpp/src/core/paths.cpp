#include "core/paths.h"

#include <QCoreApplication>
#include <QDir>

namespace wordmem {

namespace {
QString g_resourceDir = QStringLiteral(":/data");
}

QString appDataDir() {
    const QString base = QCoreApplication::instance()
                             ? QCoreApplication::applicationDirPath()
                             : QDir::currentPath();
    QDir d(base + QLatin1String("/WordMem"));
    d.mkpath(QLatin1String("."));
    return d.absolutePath();
}

QString configFile() { return appDataDir() + QLatin1String("/config.json"); }

QString databaseFile() { return appDataDir() + QLatin1String("/wordmem.db"); }

QString logDir() {
    QDir d(appDataDir() + QLatin1String("/logs"));
    d.mkpath(QLatin1String("."));
    return d.absolutePath();
}

QString resourceDataDir() { return g_resourceDir; }

void setResourceDataDir(const QString &dir) { g_resourceDir = dir; }

QString builtinRegistryFile() {
    return resourceDataDir() + QLatin1String("/book_registry.json");
}

QString builtinBookFile(const QString &filename) {
    return resourceDataDir() + QLatin1String("/") + filename;
}

QString userBooksDir() {
    QDir d(appDataDir() + QLatin1String("/books"));
    d.mkpath(QLatin1String("."));
    return d.absolutePath();
}

}  // namespace wordmem
