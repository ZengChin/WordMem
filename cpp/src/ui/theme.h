// 主题：调色板与全局样式表（对应 Python ui/theme.py）。
#pragma once

#include <QColor>
#include <QString>

namespace wordmem {
namespace theme {

// ---- 窗口尺寸与圆角 ----
inline constexpr int WINDOW_W = 430;
inline constexpr int WINDOW_H = 560;
inline constexpr int RADIUS = 14;

// ---- 渐变背景（天空 -> 海面 -> 沙滩） ----
inline constexpr const char *SKY_TOP = "#b6c9d4";
inline constexpr const char *SKY_MID = "#c9d6d3";
inline constexpr const char *SEA_BAND = "#9db8bb";
inline constexpr const char *SAND = "#eee2c6";
inline constexpr const char *SAND_LIGHT = "#f2e9d3";

// ---- 文字与强调色 ----
inline constexpr const char *INK = "#3d5a66";         // 单词主文字（青灰）
inline constexpr const char *INK_SOFT = "#6f8590";    // 音标/次要文字
inline constexpr const char *INK_DARK = "#2f3e46";    // 例句强调
inline constexpr const char *GREEN = "#2e8b5f";       // 主操作绿（文字）
inline constexpr const char *GREEN_ICON = "#3fa26b";  // 图标绿
inline constexpr const char *GREEN_BG = "#e9f5ee";    // 绿色浅底
inline constexpr const char *ORANGE = "#c0762a";      // 警示橙（文字）
inline constexpr const char *ORANGE_ICON = "#e8963c"; // 图标橙

// ---- 半透明底色（rgba 的 alpha 分量） ----
inline constexpr int CARD_ALPHA = 165;         // 卡片底
inline constexpr int CARD_STRONG_ALPHA = 205;  // 强调卡片底
inline constexpr int PILL_ALPHA = 150;         // 胶囊按钮底
inline constexpr int TRACK_ALPHA = 130;        // 进度条轨道
inline constexpr int FILL_ALPHA = 235;         // 进度条填充

// ---- 超透明模式（由 MainWindow 同步，卡片/进度条据此重绘） ----
inline constexpr int GHOST_CARD_ALPHA = 12;   // 透明模式下卡片底色
inline constexpr int GHOST_TRACK_ALPHA = 45;  // 透明模式下进度条轨道
inline constexpr int GHOST_PILL_ALPHA = 0;    // 透明模式下按钮底色（隐形）
inline constexpr int GHOST_PILL_HOVER = 26;   // 透明模式下按钮悬停反馈
inline constexpr int GHOST_PILL_PRESSED = 42; // 透明模式下按钮按下反馈

// 边框：深灰蓝，纯白底上隐约可见
QColor ghostBorder();

// 超透明模式全局状态
void setGhostMode(bool on);
bool ghostMode();

// #rrggbb -> rgba() 字符串
QString rgba(const QString &hexColor, int alpha);

// 全局样式表
QString globalQss();

}  // namespace theme
}  // namespace wordmem
