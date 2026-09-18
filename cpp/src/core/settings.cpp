#include "core/settings.h"

#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>

#include "core/paths.h"

namespace wordmem {

namespace {
const double kFontScales[3] = {0.85, 1.0, 1.18};
}

double AppConfig::scale() const {
    if (fontLevel >= 0 && fontLevel < 3)
        return kFontScales[fontLevel];
    return 1.0;
}

double AppConfig::cycleFont() {
    fontLevel = (fontLevel + 1) % 3;
    return scale();
}

ConfigManager::ConfigManager() { load(); }

void ConfigManager::load() {
    config = AppConfig{};
    QFile f(configFile());
    if (!f.open(QIODevice::ReadOnly))
        return;
    const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
    if (!doc.isObject())
        return;
    const QJsonObject o = doc.object();
    if (o.contains(QLatin1String("batch_size")))
        config.batchSize = o.value(QLatin1String("batch_size")).toInt(20);
    if (o.contains(QLatin1String("requeue_gap")))
        config.requeueGap = o.value(QLatin1String("requeue_gap")).toInt(3);
    if (o.contains(QLatin1String("auto_pronounce")))
        config.autoPronounce =
            o.value(QLatin1String("auto_pronounce")).toBool(true);
    if (o.contains(QLatin1String("ui_opacity")))
        config.uiOpacity = o.value(QLatin1String("ui_opacity")).toDouble(1.0);
    if (o.contains(QLatin1String("ghost_mode")))
        config.ghostMode = o.value(QLatin1String("ghost_mode")).toBool(false);
    if (o.contains(QLatin1String("auto_hide")))
        config.autoHide = o.value(QLatin1String("auto_hide")).toBool(false);
    if (o.contains(QLatin1String("font_level")))
        config.fontLevel = o.value(QLatin1String("font_level")).toInt(1);
}

void ConfigManager::save() const {
    QJsonObject o;
    o.insert(QLatin1String("batch_size"), config.batchSize);
    o.insert(QLatin1String("requeue_gap"), config.requeueGap);
    o.insert(QLatin1String("auto_pronounce"), config.autoPronounce);
    o.insert(QLatin1String("ui_opacity"), config.uiOpacity);
    o.insert(QLatin1String("ghost_mode"), config.ghostMode);
    o.insert(QLatin1String("auto_hide"), config.autoHide);
    o.insert(QLatin1String("font_level"), config.fontLevel);
    QSaveFile f(configFile());
    if (!f.open(QIODevice::WriteOnly))
        return;  // 配置写入失败不致命，保持静默
    f.write(QJsonDocument(o).toJson(QJsonDocument::Indented));
    f.commit();
}

}  // namespace wordmem
