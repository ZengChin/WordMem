<div align="center">

# WordMem 背单词

**一款极简风格的 Windows 桌面背单词软件 —— 本地离线、开源免费、数据随身**

[![Release](https://img.shields.io/github/v/release/ZengChin/WordMem?style=flat-square)](https://github.com/ZengChin/WordMem/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![C++](https://img.shields.io/badge/C%2B%2B-17-00599C?style=flat-square&logo=c%2B%2B&logoColor=white)](https://isocpp.org/)
[![Qt](https://img.shields.io/badge/GUI-Qt%206-41CD52?style=flat-square&logo=qt&logoColor=white)](https://www.qt.io/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/ZengChin/WordMem/releases)

背单词 · 间隔重复 · SM-2 记忆算法 · 艾宾浩斯遗忘曲线 · 雅思 / CET4 / CET6 / 考研 ·
多词库切换 · 自定义导入 · 离线发音 · 便携绿色软件 · Qt6 · C++17 · SQLite

[功能特性](#功能特性) · [下载安装](#下载安装) · [快速上手](#快速上手) · [自定义词库](#自定义词库) · [开发构建](#开发构建)

</div>

---

## 简介

WordMem 是一款基于 **Qt6 (C++) + SQLite** 的桌面背单词应用，界面与交互参考主流背单词 App：
海滩色卡片式首页、沉浸式背单词页、透明模式与不透明度调节条。所有数据保存在本地，
无需注册、无需联网，词库与记忆进度随主程序目录整体迁移。

- **为谁准备**：备考雅思 / 考研等英语考试，希望有一款轻量、离线、无广告的桌面背单词工具的用户。
- **核心理念**：极简界面 + 科学复习（SM-2 间隔重复），打开即背，背完即走。

## 界面预览

<table>
  <tr>
    <td align="center"><img src="docs/images/home.png" width="240" alt="首页"><br><b>首页</b><br>词书进度与学习入口</td>
    <td align="center"><img src="docs/images/study_question.png" width="240" alt="背单词·出题"><br><b>背单词·出题</b><br>单词 + 音标 + 发音</td>
    <td align="center"><img src="docs/images/study_answer.png" width="240" alt="背单词·作答"><br><b>背单词·作答</b><br>释义 + 例句轮播</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/images/spell.png" width="240" alt="拼写练习"><br><b>拼写练习</b><br>看释义拼单词</td>
    <td align="center"><img src="docs/images/word_list.png" width="240" alt="单词列表"><br><b>单词列表</b><br>全词浏览，点行显隐</td>
    <td align="center"><img src="docs/images/settings.png" width="240" alt="设置"><br><b>设置</b><br>每组词数 / 重现间隔 / 发音</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/images/home_ghost.png" width="240" alt="隐形模式·首页"><br><b>隐形模式·首页</b><br>整窗透明，桌面透出</td>
    <td align="center"><img src="docs/images/study_ghost.png" width="240" alt="隐形模式·背单词"><br><b>隐形模式·背单词</b><br>边工作边瞄单词</td>
    <td align="center"><img src="docs/images/ghost_autohide.gif" width="240" alt="自动隐藏演示"><br><b>自动隐藏</b><br>鼠标移出仅留菜单栏</td>
  </tr>
</table>

## 功能特性

### 学习体验

- **卡片式首页**：词书进度卡片（已学 / 总数、百分比进度条），学新词 / 复习词入口与剩余词数一目了然。
- **沉浸式背单词页**
  - 出题态：大字号单词 + 音标 + 发音按钮，底部「不认识 / 已认识」。
  - 作答态：点击后展开释义与例句卡片（例句轮播：圆点指示 + 左右切换），
    按钮切换为「记错了 / 下一词」或「记住了 / 下一词」。
  - 完成态：本组小结（记住 / 需巩固），一键返回首页。
  - `Aa` 按钮循环切换单词字号，配置自动持久化。
- **拼写练习**：看中文释义与听发音，输入英文拼写，回车校验、空格提示，对错即时反馈。
- **单词列表**：当前词书全量单词虚拟化列表，默认隐藏中文，点行显隐，支持一键切换。

### 记忆算法

- **SM-2 间隔重复**：难度因子 ease + 动态间隔 1/3/6/… 天，间隔 ≥21 天视为已掌握；
  已掌握词到期后仍会周期性唤醒复习，忘记则降级重建。
- **错词重现**：答错的词每隔若干词（默认 2，可在设置调整）在组内重现，直到答对为止。

### 词库选择与导入

<table>
  <tr>
    <td align="center"><img src="docs/images/book_manage.png" width="250" alt="词书管理"><br><b>词书管理</b><br>当前词书进度 + 一键切换</td>
    <td align="center"><img src="docs/images/book_import.png" width="250" alt="导入词书"><br><b>导入词书</b><br>拖拽导入 + 推荐下载源</td>
  </tr>
</table>

- **多词库独立进度**：内置雅思 / CET4 / CET6 / 考研四本词书；每本词书的学习进度、
  复习计划相互独立，互不干扰，切换即生效。
- **一键切换词书**：首页点词书卡片右上角进入「词书」管理页，顶部展示当前词书
  （名称 / 描述 / 已学 / 待复习 / 进度条），下方按「内置词书 / 我的导入」分组列出
  全部词书，点行或「切换」按钮即可换书，当前书高亮「使用中」。
- **导入自定义词书**：点「导入词书」进入导入页，点击或拖拽文件即可，支持
  **JSON / JSONL / TXT / CSV / Anki .apkg**；格式可自动识别，`.apkg` 由内置 miniz
  解压并自动映射单词 / 音标 / 释义 / 例句字段。导入的词书归入「我的导入」，
  可单独删除（连同其学习进度）。
- **推荐下载源**：导入页内置 AnkiWeb 共享牌组、KyleBing/english-vocabulary、
  skywind3000/ECDICT 等入口，一键跳转下载词库文件。

### 窗口与外观

无边框圆角窗口，右上角依次为：

1. **透明模式**：整窗降为低不透明度但保留高亮轮廓，可再次点击还原；
2. **不透明度滑条**：弹出线性滑杆，实时调节按钮与字体不透明度，再次点击或点击外部即隐藏；
3. 窗口置顶、自动折叠（鼠标移出仅保留菜单栏）、最小化、关闭。

### 数据与离线

- **离线发音**：Qt TextToSpeech（Windows SAPI 后端）朗读，无需联网；无可用后端时自动隐藏该能力。
- **便携数据**：数据库、配置、日志全部存放在主程序同目录的 `WordMem/` 文件夹，
  整个目录拷走即完成迁移，U 盘可用。
- **内置词库**：雅思 4127 / CET4 4027 / CET6 3991 / 考研 5491 词（含音标 / 释义 / 多例句），
  经 Qt 资源系统（qrc）嵌入可执行文件，首次启动导入本地数据库；
  可在「词书」页自由切换；亦支持导入自定义词库（见[词库选择与导入](#词库选择与导入)）。

## 下载安装

前往 [**Releases**](https://github.com/ZengChin/WordMem/releases) 页面下载最新版本：

| 文件 | 说明 |
| --- | --- |
| `WordMem-x.y.z-setup.exe` | 安装包（推荐），向导式安装，自动创建快捷方式 |
| `WordMem/` 免安装目录 | 解压即用，双击 `WordMem.exe` 运行 |

> 数据存放在程序同目录的 `WordMem/` 文件夹中，卸载或迁移时直接复制该文件夹即可。

## 快速上手

从源码构建（需要 Qt 6.8+ 与 MSVC 2022，详见[开发构建](#开发构建)）：

```powershell
git clone https://github.com/ZengChin/WordMem.git
cd WordMem
powershell -ExecutionPolicy Bypass -File cpp\scripts\build_windows.ps1
```

构建完成后运行 `cpp\build\WordMem.exe`（或直接使用 `dist/` 下的免安装目录 / 安装包）。
首次启动会自动将内置词库导入 SQLite；之后每天打开软件，按首页提示
「学新词」或「复习词」即可，算法会自动安排复习节奏。

## 自定义词库

最简单的方式是在软件内导入：「词书」页 → 「导入词书」，点击或拖拽文件即可，
支持 JSON / JSONL / TXT / CSV / Anki `.apkg`（详见[词库选择与导入](#词库选择与导入)），
无需任何外部转换工具。

若要新增一本**内置**词书，把词条 JSON 放入 `cpp/resources/data/`，在
`cpp/resources/data/book_registry.json` 注册，并将该文件加入
`cpp/resources/resources.qrc`，重新构建即可随程序分发。

## 数据与配置

| 内容 | 位置 |
| --- | --- |
| 词库种子 | `cpp/resources/data/`（`book_registry.json` + 各词书 `*_words.json`，经 qrc 嵌入） |
| 用户数据 | 主程序同目录 `WordMem/`（`wordmem.db` / `config.json` / `logs/`） |

## 开发构建

### 环境依赖

- **Qt 6.8+**（组件：Core / Gui / Widgets / Sql / TextToSpeech / Test，TextToSpeech 依赖 Multimedia）
- **MSVC 2022**（Visual Studio Build Tools，含 C++ 桌面开发工作负载）
- **Inno Setup 6**（仅生成安装包时需要）

### 一键构建

`cpp/scripts/build_windows.ps1` 会自动定位 VS 与 Qt，执行 CMake + Ninja 构建、
运行单元测试、`windeployqt` 收集运行时依赖，并用 Inno Setup 生成安装包：

```powershell
# 完整流程（构建 + 测试 + 部署 + 安装包）
powershell -ExecutionPolicy Bypass -File cpp\scripts\build_windows.ps1

# 常用开关
powershell -ExecutionPolicy Bypass -File cpp\scripts\build_windows.ps1 -QtDir D:\Qt\6.8.3\msvc2022_64
powershell -ExecutionPolicy Bypass -File cpp\scripts\build_windows.ps1 -SkipTests      # 跳过测试
powershell -ExecutionPolicy Bypass -File cpp\scripts\build_windows.ps1 -SkipInstaller  # 不生成安装包
```

产物输出至 `dist/`：`WordMem/WordMem.exe`（免安装目录版）与
`WordMem-<版本>-setup.exe`（安装包）。

### 手动构建与测试

```powershell
cd cpp
cmake --preset windows-local        # 需按需修改 CMakePresets.json 中的 CMAKE_PREFIX_PATH
cmake --build --preset windows-local-release
ctest --test-dir build --output-on-failure
```

单元测试基于 **Qt Test**，覆盖记忆调度（`test_schedule`）、数据访问（`test_repository`）、
导入解析（`test_importers`）与会话快照（`test_session`）四组。

## 项目结构

```
WordMem/
├── cpp/
│   ├── CMakeLists.txt           # 构建定义（核心库 / UI 库 / 可执行 / 测试）
│   ├── CMakePresets.json        # 本地构建预设（MSVC + Ninja）
│   ├── src/
│   │   ├── main.cpp             # 组装与入口（依赖装配 / 全局异常兜底）
│   │   ├── core/
│   │   │   ├── models.*         # 领域模型与记忆调度纯函数
│   │   │   ├── paths.*          # 便携路径解析（程序同目录 WordMem/）
│   │   │   ├── settings.*       # 用户配置（JSON 持久化）
│   │   │   ├── repository.*     # SQLite 数据访问（Qt Sql）
│   │   │   ├── studyservice.*   # 学习会话编排（业务服务层）
│   │   │   ├── importers.*      # 词库导入解析（JSON/JSONL/TXT/CSV/apkg）
│   │   │   ├── bookmanager.*    # 词书注册 / 切换 / 内置词书导入
│   │   │   └── speaker.*        # 发音服务（Qt TextToSpeech）
│   │   └── ui/
│   │       ├── mainwindow.*     # 无边框主窗口（透明模式 / 置顶 / 自动隐藏）
│   │       ├── titlebar.*       # 自定义标题栏
│   │       ├── opacitypopup.*   # 线性不透明度调节条（横向滑杆弹窗）
│   │       ├── widgets.*        # 通用控件（胶囊按钮 / 卡片 / 进度条…）
│   │       ├── icons.*          # QPainter 程序化图标
│   │       ├── theme.*          # 调色板与全局样式
│   │       ├── appcontext.h     # 跨视图共享的服务上下文
│   │       └── views/           # 首页 / 学习 / 拼写 / 单词列表 / 词书管理 / 对话框
│   ├── resources/
│   │   ├── resources.qrc        # Qt 资源清单（内置词书嵌入可执行文件）
│   │   └── data/                # 词库种子 JSON（注册表 + 各词书）
│   ├── tests/                   # Qt Test 单元测试（4 组）
│   ├── third_party/miniz/       # vendored zip 解压库（.apkg 导入用，MIT）
│   └── scripts/
│       └── build_windows.ps1    # 一键构建 / 测试 / 部署 / 打包脚本
├── packaging/                   # Inno Setup 安装包配置
├── docs/images/                 # README 界面截图
└── .github/workflows/           # CI：Qt/C++ 构建 + 测试 + 打包发布
```

## 技术栈

- **界面**：Qt6 Widgets（C++17），无边框自绘窗口，QPainter 程序化图标
- **存储**：SQLite（Qt Sql 模块，QSQLITE 驱动）
- **发音**：Qt TextToSpeech（Windows SAPI 后端，离线语音）
- **导入解压**：miniz（vendored 单文件 amalgamation，MIT）
- **构建**：CMake + Ninja + MSVC，`windeployqt` 收集运行时依赖
- **打包**：Inno Setup
- **测试**：Qt Test + CTest

## License

本项目基于 [MIT License](https://opensource.org/licenses/MIT) 开源。

---

<div align="center">

如果这个项目对你有帮助，欢迎点一个 **Star** 支持一下。

也欢迎提交 [Issue](https://github.com/ZengChin/WordMem/issues) 反馈问题与建议。

</div>
