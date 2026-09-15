# -*- coding: utf-8 -*-
"""离屏冒烟测试：无需显示窗口即可验证 UI 装配与核心交互链路。

用法：
    set QT_QPA_PLATFORM=offscreen
    python scripts/smoke_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import wordmem.app as app_mod  # noqa: E402

# 使用临时数据库，避免污染真实用户数据
_tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
app_mod._db_path = lambda: Path(_tmpdir.name) / "smoke.db"


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"SMOKE FAIL: {msg}")
    print(f"  ok - {msg}")


def main() -> None:
    app = QApplication([])
    ctx = app_mod.build_context()
    win = app_mod.MainWindow(ctx)
    win.show()

    # ---- 首页 ----
    check(win.stack.currentWidget() is win.home_view, "启动后显示首页")
    check(ctx.repo.count_words() == 4127, f"词库已播种 4127 词(实际 {ctx.repo.count_words()})")
    check(win.home_view.card_new.button.isEnabled(), "学新词按钮可用")
    check(not win.home_view.card_review.button.isEnabled(),
          "未背完一组时复习按钮禁用")

    # ---- 整卡点击触发会话 ----
    from PySide6.QtTest import QTest

    QTest.mouseClick(win.home_view.card_new, Qt.LeftButton)
    check(win.stack.currentWidget() is win.study_view, "点击整张卡片即可开始学新词")

    # 返回首页：点击胶囊按钮本身也应跳转
    sv = win.study_view
    win.stack.setCurrentWidget(win.home_view)
    QTest.mouseClick(win.home_view.card_new.button, Qt.LeftButton)
    check(win.stack.currentWidget() is win.study_view, "点击按钮本身也可跳转")
    win.stack.setCurrentWidget(win.home_view)
    win.home_view.refresh()
    win.stack.setCurrentWidget(win.study_view)  # 切回背单词页继续原流程

    # ---- 背单词页 ----
    sv = win.study_view
    first_word = sv._current_item.word.text
    check(bool(first_word), f"出题态展示单词 {first_word}")
    check(not sv.example_card.isVisible(), "出题态不显示例句")

    # 出题态点"已认识" -> 作答态：记错了 / 下一词
    sv.btn_right.click()
    check(sv._answer_mode, "点击已认识后进入作答态")
    check(sv.example_text.text() != "", "作答态展示例句")
    check(sv.btn_left.text() == "记错了" and sv.btn_left.isVisible(),
          "已认识路径下左键为记错了")
    check(sv.btn_right.text() == "下一词", "作答态右侧按钮为下一词")
    n_examples = len(sv._current_item.word.examples)
    if n_examples > 1:
        old = sv.example_text.text()
        sv.btn_next.click()
        check(sv.example_text.text() != old, "例句轮播可切换")
    sv.btn_left.click()          # 记错了 -> 判错
    check(not sv._answer_mode and sv.session.position == 2, "判分后回到出题态 2/20")

    # 出题态点"不认识" -> 作答态：仅一个按钮"下一词"
    sv.btn_left.click()
    check(sv._answer_mode, "点击不认识后进入作答态")
    check(not sv.btn_left.isVisible(), "不认识路径下没有记住了按钮")
    check(sv.btn_right.text() == "下一词", "不认识路径下仅剩下一词")
    total_before = len(sv.session.items)
    sv.btn_right.click()         # 下一词 -> 判错并在组内重排
    check(not sv._answer_mode and sv.session.position == 3, "判分后前进到第 3 词")
    check(len(sv.session.items) == total_before + 1, "答错的词在组内重排")

    # ---- 字号切换 ----
    old_level = ctx.config.font_level
    sv.btn_font.click()
    check(ctx.config.font_level != old_level, "Aa 按钮切换字号档位")

    # ---- 背景超透明模式（背景/卡片超透明，按钮/字体不变，菜单栏半透明） ----
    from wordmem.ui import theme

    win.title_bar.btn_ghost.setChecked(True)
    check(win.ctx.config.ghost_mode and theme.ghost_mode(),
          "透明模式标记已切换（背景与卡片变超透明）")
    eff = win.stack.graphicsEffect()
    opacity_before = eff.opacity() if eff is not None else 1.0
    tb_eff = win.title_bar.graphicsEffect()
    check(tb_eff is not None and abs(tb_eff.opacity() - 0.55) < 0.01,
          "透明模式下菜单栏保持半透明")
    win.title_bar.btn_ghost.setChecked(False)
    check(not win.ctx.config.ghost_mode and not theme.ghost_mode(), "退出透明模式")
    eff = win.stack.graphicsEffect()
    opacity_after = eff.opacity() if eff is not None else 1.0
    check(abs(opacity_before - opacity_after) < 1e-6, "透明模式不影响按钮与字体透明度")

    # ---- 按钮/字体不透明度（线性滑条调节） ----
    win._apply_fg_opacity(0.8)
    eff = win.stack.graphicsEffect()
    check(eff is not None and abs(eff.opacity() - 0.8) < 0.01,
          "滑条调节按钮与字体不透明度生效")
    win._apply_fg_opacity(1.0)

    from wordmem.ui.opacity_popup import OpacitySliderPopup

    dial = OpacitySliderPopup(0.6)
    dial.set_value(0.8)
    check(abs(dial.value() - 0.8) < 1e-3, "线性滑条数值联动")
    check(dial._slider.minimum() == 25 and dial._slider.maximum() == 100,
          "滑杆范围 25%~100%")

    # ---- 调节滑条弹出/隐藏（再次点击按钮即隐藏） ----
    win._show_opacity_dial()
    check(win._opacity_popup is not None and win._opacity_popup.isVisible(),
          "点击调节按钮弹出线性滑条")
    win._show_opacity_dial()
    check(win._opacity_popup is None, "再次点击调节按钮隐藏滑条")

    # ---- 弹窗装配 ----
    from wordmem.ui.views.dialogs import BookInfoDialog, SettingsDialog, StatsDialog

    check(StatsDialog(ctx, win) is not None, "统计弹窗可构建")
    check(SettingsDialog(ctx, win) is not None, "设置弹窗可构建")
    check(BookInfoDialog(ctx, win) is not None, "词书弹窗可构建")

    # ---- 窗口可拖边缩放（非固定尺寸） ----
    win.resize(500, 620)
    check(win.size().width() == 500 and win.size().height() == 620,
          "窗口大小可调节")
    check(win.minimumSize().width() == win.MIN_W, "保留了最小尺寸限制")
    check(win.MIN_W < 380 and win.MIN_H < 500, "最小宽高已缩小")

    # ---- 鼠标移出自动隐藏（内容 opacity=0，窗口原位原尺寸，仅菜单栏可见） ----
    win._auto_hide_timer.stop()  # offscreen 下 QCursor.pos() 无意义，用注入坐标测逻辑
    close_right = (win.title_bar.btn_close
                   .mapTo(win, win.title_bar.btn_close.rect().topRight()).x())
    check(close_right > win.width() - 20, "最小化/关闭按钮位于菜单栏最右侧")
    win._on_fold(True)
    check(ctx.config.auto_hide, "隐藏模式标记开启")
    before_size = win.size()
    outside = win.mapToGlobal(QPoint(win.width() // 2, win.height() + 400))
    inside = win.mapToGlobal(QPoint(win.width() // 2, win.height() // 2))
    win._check_auto_hide(outside)
    QTest.qWait(400)  # 等待淡出动画完成
    check(win._content_hidden and not win.content.isVisible()
          and win.size() == before_size, "鼠标移出窗口内容淡出隐藏且窗口尺寸不变")
    check(win.title_bar.geometry().y() == 0, "隐藏时菜单栏钉在顶部不居中")
    win._check_auto_hide(inside)
    QTest.qWait(400)  # 等待淡入动画完成
    check(not win._content_hidden and win.content.isVisible()
          and win.size() == before_size, "鼠标移回窗口任意位置淡入恢复")
    win._on_fold(False)
    check(not ctx.config.auto_hide, "隐藏模式关闭")

    # ---- 中途退出后恢复未完成的一组 ----
    sv = win.study_view
    check(sv.session.position == 3, f"退出前停在第 3 词(实际 {sv.session.position})")
    cur_id = sv._current_item.word.id
    win.stack.setCurrentWidget(win.home_view)      # 退出背单词界面
    win._start_session("new")                       # 重新进入背单词
    check(win.stack.currentWidget() is win.study_view, "重新进入背单词页")
    check(sv.session is not None and sv.session.position == 3,
          f"恢复上次未完成的一组(实际 {sv.session.position})")
    check(sv._current_item.word.id == cur_id, "恢复后仍从上次未背的词继续")

    # ---- 完成态 -> 完成页点击"开始拼写" -> 拼写页 ----
    while not sv.session.finished:
        sv._grade_and_advance(True)
    check(not sv.done_label.isHidden(), "完成态小结可见")
    check(sv.btn_right.isVisible() and sv.btn_right.text() == "开始拼写",
          "完成页提供开始拼写按钮")
    check(ctx.service.home_summary()["review_left"] == 20,
          f"背完一组后该组计入复习列表(实际 {ctx.service.home_summary()['review_left']})")
    sv.btn_right.click()
    check(win.stack.currentWidget() is win.spell_view, "点击开始拼写进入拼写页")

    # ---- 拼写页 ----
    from wordmem.ui.views.spell_view import _COLOR_CORRECT, _COLOR_WRONG

    pv = win.spell_view
    words = pv.words
    check(len(words) == 20, f"拼写词表为会话去重词(实际 {len(words)})")
    w0 = words[0]
    check(pv.meaning_label.text() != "", "拼写出题显示中文释义")
    check(pv.phonetic.text() == w0.phonetic, "拼写出题显示音标")

    # 空格提示：显示英文 2 秒后隐藏，保留用户输入
    pv.input_edit.setText("abc")
    QTest.keyClick(pv.input_edit, Qt.Key_Space)
    check(pv.feedback_label.text() == w0.text, "按空格显示英文提示")
    QTest.qWait(2100)
    check(pv.feedback_label.text() == "", "2 秒后提示自动隐藏")
    check(pv.input_edit.text() == "abc", "提示隐藏时保留用户输入")

    # 拼写错误：红字英文 1 秒后隐藏并清空输入框
    pv.input_edit.setText("wrongword")
    pv._submit()
    check(pv.feedback_label.text() == w0.text, "拼写错误显示正确英文")
    check(_COLOR_WRONG in pv.feedback_label.styleSheet(), "错误反馈为红色字体")
    QTest.qWait(1100)
    check(pv.feedback_label.text() == "", "1 秒后错误英文隐藏")
    check(pv.input_edit.text() == "", "错误隐藏后清空输入框")

    # 拼写正确：绿字显示后自动跳下一个
    pv.input_edit.setText(w0.text)
    pv._submit()
    check(pv.feedback_label.text() == w0.text, "拼写正确显示英文")
    check(_COLOR_CORRECT in pv.feedback_label.styleSheet(), "正确反馈为绿色字体")
    QTest.qWait(1100)
    check(pv.index == 1, "拼写正确后自动跳到下一个词")
    check(pv.words[pv.index].text != w0.text, "下一个词与上一个不同")

    # 全部拼完 -> 完成态 -> 返回首页
    while pv.index < len(pv.words):
        pv.input_edit.setText(pv.words[pv.index].text)
        pv._submit()
        QTest.qWait(1100)
    check(pv.done_label.isVisible(), "拼写完成态可见")
    pv.btn_finish.click()
    check(win.stack.currentWidget() is win.home_view, "拼写结束返回首页")
    learned = 20  # 组内 20 个去重单词均已完成一次学习
    check(win.home_view.card_new.number.text() == str(4127 - learned),
          f"首页剩余新词数已刷新(实际 {win.home_view.card_new.number.text()})")

    # ---- 复习入口门控：须完整背完至少一组 ----
    from datetime import date as _date
    from wordmem.core.models import STATUS_LEARNING, WordState

    check(ctx.service.home_summary()["completed_batches"] >= 1,
          "背完一组后已背组数+1")
    row = ctx.repo._conn.execute(
        "SELECT word_id FROM study_state ORDER BY word_id LIMIT 1").fetchone()
    ctx.repo.save_state(
        WordState(word_id=row["word_id"], status=STATUS_LEARNING,
                  due_date=_date.today()),
        True, _date.today())
    win.home_view.refresh()
    check(win.home_view.card_review.button.isEnabled(),
          "背完一组且有待复习词时复习入口可用")
    ctx.repo.set_meta("completed_batches", "0")
    win.home_view.refresh()
    check(not win.home_view.card_review.button.isEnabled(),
          "有待复习词但未背完一组时复习仍禁用")
    ctx.repo.set_meta("completed_batches", "1")
    win.home_view.refresh()
    check(win.home_view.card_review.button.isEnabled(),
          "背完一组后复习入口恢复可用")

    # ---- 首页词书卡列表按钮 -> 主窗口内切换到全部单词列表页 ----
    wlv = win.word_list_view
    check(win.home_view.book_card.list_btn is not None, "词书卡右上角有列表按钮")
    QTest.mouseClick(win.home_view.book_card.list_btn, Qt.LeftButton)
    check(win.stack.currentWidget() is wlv,
          "点击列表按钮在主窗口内切换到单词列表页")
    app.processEvents()
    total_words = len(wlv.list_view._words)
    check(total_words == ctx.repo.count_words() == 4127,
          f"列表加载全部单词(实际 {total_words})")
    check(len(wlv.list_view._shown) == 0, "默认不显示任何中文释义")
    check(wlv.btn_toggle.text() == "显示全部中文", "顶部按钮默认文案为显示全部中文")
    check(wlv.list_view.width() > 0 and wlv.list_view.height() >= 44,
          f"列表控件有实际渲染尺寸(宽 {wlv.list_view.width()} 高 {wlv.list_view.height()})")

    # 点击某行 -> 仅该行显示中文
    QTest.mouseClick(wlv.list_view, Qt.LeftButton, pos=QPoint(80, 22))
    check(0 in wlv.list_view._shown and len(wlv.list_view._shown) == 1,
          "点击单词行后仅该行显示中文")
    QTest.mouseClick(wlv.list_view, Qt.LeftButton, pos=QPoint(80, 22))
    check(len(wlv.list_view._shown) == 0, "再次点击同一行可隐藏中文")

    # 一键切换全部中文
    wlv.btn_toggle.click()
    check(wlv._all_shown and len(wlv.list_view._shown) == total_words,
          "切换后全部单词显示中文")
    check(wlv.btn_toggle.text() == "隐藏全部中文", "按钮文案切换为隐藏全部中文")
    wlv.btn_toggle.click()
    check(not wlv._all_shown and len(wlv.list_view._shown) == 0,
          "再次切换后全部中文隐藏")

    # 返回首页
    wlv.btn_back.click()
    check(win.stack.currentWidget() is win.home_view, "返回按钮回到首页")

    win.close()
    ctx.repo.close()
    try:
        _tmpdir.cleanup()
    except OSError:
        pass  # Windows 下句柄释放可能有延迟
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
