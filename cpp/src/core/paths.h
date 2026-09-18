// 运行时路径管理：数据目录跟随主程序所在位置（对应 Python config/paths.py）。
#pragma once

#include <QString>

namespace wordmem {

QString appDataDir();
QString configFile();
QString databaseFile();
QString logDir();

// 包内资源目录（内置词书 JSON + registry）。默认 ":/data"（qrc 嵌入），
// 测试或开发可经 setResourceDataDir 指向文件系统目录。
QString resourceDataDir();
void setResourceDataDir(const QString &dir);
QString builtinRegistryFile();
QString builtinBookFile(const QString &filename);
QString userBooksDir();

}  // namespace wordmem
