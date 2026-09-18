#include "ui/theme.h"

namespace wordmem {
namespace theme {

namespace {
bool g_ghost = false;
}

QColor ghostBorder() { return QColor(88, 100, 110, 42); }

void setGhostMode(bool on) { g_ghost = on; }

bool ghostMode() { return g_ghost; }

QString rgba(const QString &hexColor, int alpha) {
    const QColor c(hexColor);
    return QStringLiteral("rgba(%1,%2,%3,%4)")
        .arg(c.red())
        .arg(c.green())
        .arg(c.blue())
        .arg(alpha);
}

QString globalQss() {
    return QStringLiteral(
        "* { font-family: \"Microsoft YaHei UI\", \"Microsoft YaHei\", sans-serif;"
        " outline: none; }\n"
        "QLabel { color: %1; background: transparent; }\n"
        "QPushButton { background: transparent; border: none; }\n"
        "QToolTip { background: rgba(47,62,70,230); color: white; border: none;"
        " padding: 4px 8px; border-radius: 4px; font-size: 12px; }\n"
        "QDialog { background: white; }\n")
        .arg(QLatin1String(INK));
}

}  // namespace theme
}  // namespace wordmem
