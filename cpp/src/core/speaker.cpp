#include "core/speaker.h"

#include <QTextToSpeech>

namespace wordmem {

Speaker::Speaker() {
    // 默认构造使用平台首选引擎；Windows 上为 SAPI，缺失语音包时进入 Error 状态
    m_tts = new QTextToSpeech();
}

Speaker::~Speaker() { delete m_tts; }

bool Speaker::available() const {
    return m_tts && m_tts->state() != QTextToSpeech::Error;
}

void Speaker::speak(const QString &text) {
    if (!available() || text.isEmpty())
        return;
    m_tts->stop();  // 打断上一条，避免快速翻词时语音堆积
    m_tts->say(text);
}

void Speaker::stop() {
    if (m_tts)
        m_tts->stop();
}

Speaker &speaker() {
    static Speaker instance;
    return instance;
}

}  // namespace wordmem
