# WordMem 背单词

极简风格的 Windows 桌面背单词软件（PySide6 + SQLite），界面与交互参考主流背单词 App：
海滩色卡片式首页、沉浸式背单词页、透明模式与线性不透明度调节条。

## 功能特性

- **首页**：词书进度卡片（已学 / 总数、百分比进度条）、学新词 / 复习词入口与剩余词数。
- **背单词页**
  - 出题态：大字号单词 + 音标 + 发音按钮；底部「不认识 / 已认识」。
  - 作答态：点击任一按钮后展开释义与例句卡片（例句轮播：圆点指示 + 左右切换）；
    按钮切换为「记错了 / 下一词」（已认识）或「记住了 / 下一词」（不认识）。
  - 完成态：本组小结（记住 / 需巩固），一键返回首页。
  - `Aa` 按钮循环切换单词字号，配置持久化。
- **记忆调度**：SM-2 间隔重复算法（难度因子 ease + 动态间隔 1/6/… 天，间隔 ≥21 天视为已掌握）；
  已掌握词到期后仍会周期性唤醒复习，忘记则降级重建。答错的词每隔若干词（默认 2，可在设置调整）
  在组内重现，直到答对为止。
- **窗口控制**：无边框圆角窗口，右上角依次为——
  1. **透明模式**：整窗降为低不透明度但保留高亮轮廓，可再次点击还原；
  2. **不透明度滑条**：弹出线性滑杆（类似进度条），实时调节按钮与字体不透明度，再次点击或点击外部即隐藏；
  3. 窗口置顶、自动折叠（鼠标移出仅保留菜单栏）、最小化、关闭。
- **发音**：Windows SAPI 离线朗读（pyttsx3），未安装时自动隐藏该能力。
- **统计 / 设置 / 词书详情**：首页左上与右上角图标进入。

## 运行

```bash
cd WordMem
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
```

开发测试：

```bash
.venv\Scripts\pip install pytest
.venv\Scripts\pytest
```

## 数据与配置

- 词库种子：`src/wordmem/resources/data/ielts_words.json`（雅思核心词汇 4127 词，含音标 / 释义 / 例句；首次启动自动导入 SQLite，检测到默认词库更换时会清空旧库重播）。
- 词库转换：`scripts/apkg_to_words.py` 可将 Anki 词库包（`.apkg`）转为上述 JSON（用法见脚本 docstring）。
- 用户数据目录：`%APPDATA%\WordMem\`（`wordmem.db` / `config.json` / `logs\`）。

## 项目结构

```
WordMem/
├── run.py                     # 开发启动入口
├── pyproject.toml             # 打包与工具配置
├── requirements.txt
├── src/wordmem/
│   ├── app.py                 # 组装与入口（日志 / 异常兜底 / 依赖装配）
│   ├── config/                # 路径解析与用户配置（JSON 持久化）
│   ├── core/
│   │   ├── models.py          # 领域模型与记忆调度纯函数
│   │   ├── repository.py      # SQLite 数据访问
│   │   ├── study_service.py   # 学习会话编排（业务服务层）
│   │   └── tts.py             # 发音服务（后台队列）
│   ├── ui/
│   │   ├── main_window.py     # 无边框主窗口（透明模式 / 置顶 / 自动隐藏）
│   │   ├── title_bar.py       # 自定义标题栏
│   │   ├── opacity_popup.py   # 线性不透明度调节条（横向滑杆弹窗）
│   │   ├── widgets.py         # 通用控件（胶囊按钮 / 卡片 / 进度条…）
│   │   ├── icons.py           # QPainter 程序化图标
│   │   ├── theme.py           # 调色板与全局样式
│   │   └── views/             # 首页 / 学习页 / 对话框
│   └── resources/data/        # 词库种子 JSON
└── tests/                     # pytest 单元测试
```
