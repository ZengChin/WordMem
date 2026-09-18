// 应用级上下文（依赖注入容器），对应 Python ui/main_window.py 的 AppContext。
#pragma once

namespace wordmem {

class Repository;
class StudyService;
class ConfigManager;
class Speaker;
class BookManager;
struct AppConfig;

struct AppContext {
    Repository *repo = nullptr;
    StudyService *service = nullptr;
    ConfigManager *configs = nullptr;
    Speaker *speaker = nullptr;
    BookManager *books = nullptr;

    AppConfig &config() const;
};

}  // namespace wordmem
