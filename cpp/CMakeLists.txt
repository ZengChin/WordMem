cmake_minimum_required(VERSION 3.21)
project(WordMem VERSION 0.4.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

if(MSVC)
    # 源码含 UTF-8 中文字面量，需强制按 UTF-8 解析
    add_compile_options(/utf-8 /W3)
endif()

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Sql TextToSpeech Test)

# ---------------------------------------------------------------- vendored miniz（zip 解压，用于 .apkg 导入）
# 单文件 amalgamation（MIT），随仓库分发，无需 vcpkg / 系统包。
add_library(miniz STATIC third_party/miniz/miniz.c)
target_include_directories(miniz PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/third_party/miniz)
if(MSVC)
    # 第三方源码，关闭其告警以免污染本项目 /W3 输出
    target_compile_options(miniz PRIVATE /W0)
    target_compile_definitions(miniz PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()
set_target_properties(miniz PROPERTIES POSITION_INDEPENDENT_CODE ON)

# ---------------------------------------------------------------- 核心库（无 UI，供测试与可执行链接）
add_library(wordmem_core STATIC
    src/core/models.cpp
    src/core/paths.cpp
    src/core/settings.cpp
    src/core/repository.cpp
    src/core/studyservice.cpp
    src/core/importers.cpp
    src/core/bookmanager.cpp
    src/core/speaker.cpp
)
target_include_directories(wordmem_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(wordmem_core PUBLIC
    Qt6::Core Qt6::Gui Qt6::Sql Qt6::TextToSpeech
    miniz
)

# ---------------------------------------------------------------- UI 库（Widgets 视图层）
add_library(wordmem_ui STATIC
    src/ui/theme.cpp
    src/ui/icons.cpp
    src/ui/widgets.cpp
    src/ui/titlebar.cpp
    src/ui/opacitypopup.cpp
    src/ui/mainwindow.cpp
    src/ui/views/homeview.cpp
    src/ui/views/studyview.cpp
    src/ui/views/spellview.cpp
    src/ui/views/wordlistview.cpp
    src/ui/views/dialogs.cpp
    src/ui/views/bookmanageview.cpp
)
target_include_directories(wordmem_ui PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(wordmem_ui PUBLIC wordmem_core Qt6::Widgets)

# ---------------------------------------------------------------- 可执行程序
# resources/resources.qrc 由 AUTORCC 编译，将内置词书嵌入到 :/data/...
add_executable(WordMem WIN32
    src/main.cpp
    resources/resources.qrc
)
target_link_libraries(WordMem PRIVATE wordmem_ui)
# 版本号单一来源：project(VERSION) -> 编译期宏，供 main.cpp 与打包脚本共用
target_compile_definitions(WordMem PRIVATE WORDMEM_VERSION="${PROJECT_VERSION}")
set_target_properties(WordMem PROPERTIES
    OUTPUT_NAME "WordMem"
    WIN32_EXECUTABLE $<IF:$<CONFIG:Debug>,FALSE,TRUE>
)

# ---------------------------------------------------------------- 单元测试（Qt Test + CTest）
enable_testing()
# 内置词书数据目录（阶段 4 由 qrc 嵌入，开发期直接指向文件系统）
set(WORDBOOK_DATA_DIR "${CMAKE_CURRENT_SOURCE_DIR}/resources/data")
configure_file(tests/testconfig.h.in ${CMAKE_CURRENT_BINARY_DIR}/testconfig.h)
foreach(t IN ITEMS test_schedule test_repository test_importers test_session)
    add_executable(${t} tests/${t}.cpp)
    target_link_libraries(${t} PRIVATE wordmem_core Qt6::Test)
    target_include_directories(${t} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
        ${CMAKE_CURRENT_BINARY_DIR}
    )
    add_test(NAME ${t} COMMAND ${t})
endforeach()
