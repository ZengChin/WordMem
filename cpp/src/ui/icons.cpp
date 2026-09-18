#include "ui/icons.h"

#include <QHash>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPixmap>
#include <QPolygonF>

namespace wordmem {

namespace {

constexpr double kSize = 64.0;  // 内部绘制分辨率，保证缩放清晰
constexpr double kMargin = 10.0;

// 还原 Python 版 _pen_of：把 NoPen 之后的画笔恢复为实线（保留颜色与线宽）
QPen solidPen(const QColor &color, double widthF) {
    QPen pen(color);
    pen.setStyle(Qt::SolidLine);
    pen.setWidthF(widthF);
    pen.setCapStyle(Qt::RoundCap);
    pen.setJoinStyle(Qt::RoundJoin);
    return pen;
}

void drawIcon(QPainter &p, const QString &name, const QColor &color) {
    const double s = kSize;
    const double m = kMargin;
    const QRectF rect(m, m, s - 2 * m, s - 2 * m);
    const QPointF center(s / 2, s / 2);
    const double strokeW = p.pen().widthF();

    if (name == QLatin1String("settings")) {  // 齿轮设置
        p.save();
        p.translate(center);
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        for (int i = 0; i < 8; ++i) {  // 8 个轮齿，45° 均布
            p.save();
            p.rotate(i * 45.0);
            p.drawRoundedRect(QRectF(-s * 0.078, -s * 0.344, s * 0.156, s * 0.078),
                              s * 0.03, s * 0.03);
            p.restore();
        }
        p.restore();
        // 齿圈：粗描边圆，与轮齿融合
        QPen ring(color);
        ring.setStyle(Qt::SolidLine);
        ring.setCapStyle(Qt::RoundCap);
        ring.setJoinStyle(Qt::RoundJoin);
        ring.setWidthF(s * 0.094);
        p.setPen(ring);
        p.setBrush(Qt::NoBrush);
        p.drawEllipse(center, s * 0.235, s * 0.235);
    } else if (name == QLatin1String("chart")) {  // 统计柱状图
        p.drawLine(QPointF(m + 4, m + 2), QPointF(m + 4, s - m - 4));
        p.drawLine(QPointF(m + 4, s - m - 4), QPointF(s - m - 2, s - m - 4));
        const double hs[3] = {0.32, 0.55, 0.80};
        for (int i = 0; i < 3; ++i) {
            const double x = s * (0.38 + 0.18 * i);
            p.drawLine(QPointF(x, s - m - 4),
                       QPointF(x, s - m - 4 - (s - 2 * m - 8) * hs[i]));
        }
    } else if (name == QLatin1String("chevron")) {
        QPainterPath path;
        path.moveTo(s * 0.38, s * 0.28);
        path.lineTo(s * 0.62, s * 0.5);
        path.lineTo(s * 0.38, s * 0.72);
        p.drawPath(path);
    } else if (name == QLatin1String("back")) {
        p.drawEllipse(rect.adjusted(2, 2, -2, -2));
        p.drawLine(QPointF(s * 0.58, s * 0.34), QPointF(s * 0.42, s * 0.5));
        p.drawLine(QPointF(s * 0.42, s * 0.5), QPointF(s * 0.58, s * 0.66));
    } else if (name == QLatin1String("ghost")) {  // 透明模式：半填充圆角方块
        p.drawRoundedRect(rect, 12, 12);
        p.save();
        p.setClipRect(QRectF(m, m, rect.width() / 2, rect.height()));
        p.setPen(Qt::NoPen);
        p.setBrush(color);
        p.drawRoundedRect(rect, 12, 12);
        p.restore();
    } else if (name == QLatin1String("opacity")) {  // 不透明度：斜分半填充圆
        p.drawEllipse(rect);
        QPainterPath path;
        path.moveTo(rect.center().x(), rect.top());
        path.arcTo(rect, 90, 180);
        path.closeSubpath();
        p.save();
        p.setPen(Qt::NoPen);
        p.setBrush(color);
        p.drawPath(path);
        p.restore();
    } else if (name == QLatin1String("pin")) {  // 置顶（未开启）：空心大头针
        p.drawRoundedRect(QRectF(s * 0.34, s * 0.18, s * 0.32, s * 0.32), 6, 6);
        p.drawLine(QPointF(s * 0.5, s * 0.50), QPointF(s * 0.5, s * 0.62));
        p.drawLine(QPointF(s * 0.36, s * 0.62), QPointF(s * 0.64, s * 0.62));
        p.drawLine(QPointF(s * 0.5, s * 0.62), QPointF(s * 0.5, s * 0.84));
    } else if (name == QLatin1String("pin_on")) {  // 置顶（开启）：针头实心填充
        p.setPen(Qt::NoPen);
        p.setBrush(color);
        p.drawRoundedRect(QRectF(s * 0.34, s * 0.18, s * 0.32, s * 0.32), 6, 6);
        p.setPen(solidPen(color, strokeW));
        p.setBrush(Qt::NoBrush);
        p.drawLine(QPointF(s * 0.5, s * 0.50), QPointF(s * 0.5, s * 0.62));
        p.drawLine(QPointF(s * 0.36, s * 0.62), QPointF(s * 0.64, s * 0.62));
        p.drawLine(QPointF(s * 0.5, s * 0.62), QPointF(s * 0.5, s * 0.84));
    } else if (name == QLatin1String("minimize")) {
        p.drawLine(QPointF(s * 0.28, s * 0.5), QPointF(s * 0.72, s * 0.5));
    } else if (name == QLatin1String("close")) {
        p.drawLine(QPointF(s * 0.32, s * 0.32), QPointF(s * 0.68, s * 0.68));
        p.drawLine(QPointF(s * 0.68, s * 0.32), QPointF(s * 0.32, s * 0.68));
    } else if (name == QLatin1String("fold")) {  // 自动隐藏（未开启）：全为描边
        p.drawRect(QRectF(s * 0.24, s * 0.26, s * 0.52, s * 0.08));
        p.drawLine(QPointF(s * 0.5, s * 0.78), QPointF(s * 0.5, s * 0.44));
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.36, s * 0.58));
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.64, s * 0.58));
    } else if (name == QLatin1String("fold_on")) {  // 自动隐藏（开启）：横条实心
        p.setPen(Qt::NoPen);
        p.setBrush(color);
        p.drawRect(QRectF(s * 0.24, s * 0.26, s * 0.52, s * 0.08));
        p.setPen(solidPen(color, strokeW));
        p.setBrush(Qt::NoBrush);
        p.drawLine(QPointF(s * 0.5, s * 0.78), QPointF(s * 0.5, s * 0.44));
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.36, s * 0.58));
        p.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.64, s * 0.58));
    } else if (name == QLatin1String("speaker")) {
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        const QPolygonF horn{QPointF(s * 0.24, s * 0.42), QPointF(s * 0.38, s * 0.42),
                             QPointF(s * 0.52, s * 0.28), QPointF(s * 0.52, s * 0.72),
                             QPointF(s * 0.38, s * 0.58), QPointF(s * 0.24, s * 0.58)};
        p.drawPolygon(horn);
        p.setPen(solidPen(color, strokeW));
        p.setBrush(Qt::NoBrush);
        p.drawArc(QRectF(s * 0.56, s * 0.36, s * 0.18, s * 0.28), -60, 120);
        p.drawArc(QRectF(s * 0.60, s * 0.28, s * 0.26, s * 0.44), -60, 120);
    } else if (name == QLatin1String("book_new")) {
        const QRectF body(m + 6, m + 10, s - 2 * m - 12, s - 2 * m - 14);
        p.drawRoundedRect(body, 6, 6);
        p.drawLine(QPointF(body.center().x(), body.top()),
                   QPointF(body.center().x(), body.bottom()));
        const double cx = s * 0.72, cy = s * 0.28;
        p.setBrush(QColor(QStringLiteral("#ffffff")));
        p.setPen(solidPen(color, strokeW));
        p.drawEllipse(QPointF(cx, cy), 10, 10);
        p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy));
        p.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5));
    } else if (name == QLatin1String("book_review")) {
        p.drawArc(QRectF(m + 2, m + 8, s - 2 * m - 4, s - 2 * m), 0, 180);
        p.drawLine(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.5, s * 0.84));
        p.drawLine(QPointF(m + 2, s * 0.5), QPointF(s * 0.5, s * 0.5));
        p.drawLine(QPointF(s - m - 2, s * 0.5), QPointF(s * 0.5, s * 0.5));
    } else if (name == QLatin1String("alert")) {  // 不认识
        p.drawEllipse(rect);
        p.drawLine(QPointF(s * 0.5, s * 0.30), QPointF(s * 0.5, s * 0.56));
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        p.drawEllipse(QPointF(s * 0.5, s * 0.68), 2.6, 2.6);
    } else if (name == QLatin1String("check")) {  // 已认识
        p.drawEllipse(rect);
        QPainterPath path;
        path.moveTo(s * 0.33, s * 0.52);
        path.lineTo(s * 0.46, s * 0.65);
        path.lineTo(s * 0.68, s * 0.38);
        p.drawPath(path);
    } else if (name == QLatin1String("undo")) {  // 记错了
        p.drawArc(QRectF(s * 0.22, s * 0.30, s * 0.56, s * 0.44), 90 * 16, 200 * 16);
        const QPolygonF arrow{QPointF(s * 0.20, s * 0.42), QPointF(s * 0.34, s * 0.40),
                              QPointF(s * 0.26, s * 0.54)};
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        p.drawPolygon(arrow);
    } else if (name == QLatin1String("arrow_right")) {
        p.drawLine(QPointF(s * 0.26, s * 0.5), QPointF(s * 0.70, s * 0.5));
        p.drawLine(QPointF(s * 0.70, s * 0.5), QPointF(s * 0.54, s * 0.34));
        p.drawLine(QPointF(s * 0.70, s * 0.5), QPointF(s * 0.54, s * 0.66));
    } else if (name == QLatin1String("list")) {  // 单词列表：三条带圆点行
        const double ys[3] = {s * 0.30, s * 0.50, s * 0.70};
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        for (double y : ys)
            p.drawEllipse(QPointF(s * 0.28, y), 2.6, 2.6);
        p.setPen(solidPen(color, strokeW));
        p.setBrush(Qt::NoBrush);
        for (double y : ys)
            p.drawLine(QPointF(s * 0.38, y), QPointF(s * 0.74, y));
    } else if (name == QLatin1String("eye")) {  // 显示/隐藏中文
        p.drawEllipse(QRectF(s * 0.16, s * 0.30, s * 0.68, s * 0.40));
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), 5, 5);
    } else if (name == QLatin1String("minus")) {  // 减少
        p.drawLine(QPointF(s * 0.30, s * 0.5), QPointF(s * 0.70, s * 0.5));
    } else if (name == QLatin1String("plus")) {  // 增加
        p.drawLine(QPointF(s * 0.30, s * 0.5), QPointF(s * 0.70, s * 0.5));
        p.drawLine(QPointF(s * 0.5, s * 0.30), QPointF(s * 0.5, s * 0.70));
    } else if (name == QLatin1String("upload")) {  // 上传：向上箭头 + 底座
        p.drawLine(QPointF(s * 0.50, s * 0.52), QPointF(s * 0.50, s * 0.24));
        p.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.36, s * 0.38));
        p.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.64, s * 0.38));
        p.drawLine(QPointF(s * 0.30, s * 0.64), QPointF(s * 0.70, s * 0.64));
    } else if (name == QLatin1String("download")) {  // 下载：向下箭头 + 底座
        p.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.50, s * 0.52));
        p.drawLine(QPointF(s * 0.50, s * 0.52), QPointF(s * 0.36, s * 0.38));
        p.drawLine(QPointF(s * 0.50, s * 0.52), QPointF(s * 0.64, s * 0.38));
        p.drawLine(QPointF(s * 0.30, s * 0.64), QPointF(s * 0.70, s * 0.64));
    } else {  // 兜底：实心圆
        p.setBrush(color);
        p.setPen(Qt::NoPen);
        p.drawEllipse(center, 8, 8);
    }
}

}  // namespace

QIcon icon(const QString &name, const QString &color, int size, double stroke) {
    struct Entry {
        QIcon icon;
    };
    static QHash<QString, Entry> cache;

    const QString key = QStringLiteral("%1|%2|%3|%4")
                            .arg(name, color)
                            .arg(size)
                            .arg(stroke);
    auto it = cache.constFind(key);
    if (it != cache.constEnd())
        return it->icon;

    QPixmap pix(size, size);
    pix.fill(Qt::transparent);
    {
        QPainter painter(&pix);
        painter.setRenderHint(QPainter::Antialiasing);
        const double k = static_cast<double>(size) / kSize;
        // 缩放后线宽仍为 stroke px
        QPen pen{QColor(color)};
        pen.setWidthF(stroke / k);
        pen.setCapStyle(Qt::RoundCap);
        pen.setJoinStyle(Qt::RoundJoin);
        painter.setPen(pen);
        painter.scale(k, k);
        drawIcon(painter, name, QColor(color));
    }
    const QIcon result(pix);
    cache.insert(key, Entry{result});
    return result;
}

}  // namespace wordmem
