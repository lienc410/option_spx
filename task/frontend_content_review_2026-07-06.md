# 前端 Review — Quant 内容正确性 findings（首轮，2026-07-06）

| # | 位置 | 发现 | 严重度 | 裁定依据 |
|---|---|---|---|---|
| C1 | portfolio_home.html:1760,1828 | 持仓卡 JS 硬编码 `isDebit ? 0.50 : 0.60`——BCD/debit 止盈目标显示 50%，engine 真值 60%（params.profit_target 对 credit/debit 一视同仁，engine.py:1044）。**第四个镜像**（catalog/selector/bot 之外的前端 JS），今日断言批未覆盖 | **HIGH** | engine.py:1044 |
| C2 | engine.py:1045 | exit_reason 字面量 `"50pct_profit"` 化石——实际按 0.60 触发；污染一切按 exit_reason 分组的展示/归因 | MED | 同上 |
| C3 | matrix.html:508 | 页脚免责只列 rising-VIX/backwardation/IVP 三种降级，漏 SPEC-060 无条件 wait 与 aftermath 解锁——五个已文档化分歧格（124 断言表）应上屏 | MED | 124 归因表 |
| C4 | backtest.html:1231 | 定价披露仅"BS simulation, no spread/slippage"——Q087 后 BS-flat@VIX 高估 credit 结构已是**测量事实**，26y Sharpe 1.43 裸展示无口径警示。**三方合议项**：加一行 convention 注记 +（可选）CALIB 口径可得性说明 | MED-HIGH | B1/SPEC-120 |
| C5 | 各模板 overlay 字样 | 核查为良性（图表控件 / DD-Overlay 导航）；无 SPEC-026 VIX-accel 过期宣传 | — | 清零 |
| C6 | 全站 | 三条新证据流（S2-BPS/BCD shadow/skew monitor）无展示面——可能是正确的（后台数据），但应**有意决策并记录**而非默认遗漏 | 合议 | charter #5 |

**修复建议方向（待与设计侧 findings 合并进 SPEC-125）**: C1 从 API 下发 target 比例（消灭前端常数）或断言扩展到模板 JS；C2 label 参数化；C3 页脚引用 124 归因表五格；C4 一行披露文案由三方定稿。
