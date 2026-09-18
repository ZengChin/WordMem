// 应用配置：内存结构 + JSON 持久化（对应 Python config/settings.py）。
#pragma once

#include <QString>

namespace wordmem {

struct AppConfig {
    int batchSize = 20;         // 每组学习词数
    int requeueGap = 3;         // 答错重现间隔基数（实际 [gap, gap+1] 随机）
    bool autoPronounce = true;  // 出词时自动发音
    double uiOpacity = 1.0;     // 界面不透明度 0.25~1.0
    bool ghostMode = false;     // 透明模式
    bool autoHide = false;      // 鼠标移出隐藏内容区
    int fontLevel = 1;          // 单词字号档位 0/1/2

    double scale() const;
    double cycleFont();
};

class ConfigManager {
public:
    ConfigManager();
    AppConfig config;
    void load();
    void save() const;
};

}  // namespace wordmem
