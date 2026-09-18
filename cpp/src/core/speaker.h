// 发音服务：基于 Qt TextToSpeech（Windows SAPI 后端），缺失时优雅降级。
// 对应 Python core/tts.py。
#pragma once

#include <QString>

class QTextToSpeech;

namespace wordmem {

class Speaker {
public:
    Speaker();
    ~Speaker();
    Speaker(const Speaker &) = delete;
    Speaker &operator=(const Speaker &) = delete;

    // 异步朗读文本；引擎不可用或文本为空时静默忽略。
    // 新朗读会打断上一条，等价于 Python 版「清空积压，只读最新一条」。
    void speak(const QString &text);
    void stop();
    bool available() const;

private:
    QTextToSpeech *m_tts = nullptr;
};

// 全局单例（与 Python 模块级 speaker 对应）
Speaker &speaker();

}  // namespace wordmem
