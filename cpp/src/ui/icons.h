// 程序化图标工厂：全部用 QPainter 绘制，避免二进制资源依赖。
// 对应 Python ui/icons.py。
#pragma once

#include <QIcon>
#include <QString>

namespace wordmem {

// 按名称/颜色生成 QIcon（带缓存）。stroke 为目标显示线宽（px）。
// 可选 name：settings chart chevron back ghost opacity pin pin_on minimize
//           close fold fold_on speaker book_new book_review alert check undo
//           arrow_right list eye minus plus upload download
QIcon icon(const QString &name, const QString &color = QStringLiteral("#5a6b72"),
           int size = 18, double stroke = 1.8);

}  // namespace wordmem
