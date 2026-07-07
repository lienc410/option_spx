# SPEC-129 — 手动入场信息鸿沟修复批（BPS 复审产物，PM 批准 2026-07-07）

**来源**: task/BPS_live_review_2026-07-07.md 改进项 ①②③。主题一句话：**把"系统知道但 PM 看不见"的三样东西放进 PM 的操作路径**——门的原因、推荐的腿、风险的绝对值。全部"提示不拦"，不新增任何拦截。

## 1. Advisory 附原因文本（改进①，最小改动）

`web/server.py:_manual_open_governance_advisory`：routed==reduce_wait 或路由不符时，FYI 正文附上生产 selector 的 reason 文本（`get_recommendation()` 返回对象已含 reason，如 "NORMAL + IV NEUTRAL + BULLISH but IVP=62 ≥ 55 — stressed vol environment…"）。5 月实证：PM 把 IVP 55 当退出信号用，说明不知道它是入场门——原因文本是教学面。

**AC-1**: 单测——IVP 否决日 fixture → FYI 正文含 "IVP=" 与阈值字样；仍走 gateway FYI 类，不升级类别。

## 2. Entry 表单预填当日推荐腿（改进②）

交易录入表单（SPEC-034 UI）加载时从当日推荐 payload 预填：strategy 对应的 strikes（推荐卡已算好的具体行权价）、width、DTE、expiry。用户改动任一预填字段 → 该字段高亮 + 提交时自动在 note 追加 `deviated: <field>=<actual> (rec <value>)`。当日路由为 wait/无推荐 → 不预填，表单顶部显示 wait 横幅（含 reason，同①），照常可提交（提示不拦）。

5 月实证：短腿三笔全贴 δ0.30，长腿三笔全买太远（δ0.09-0.12 vs 0.15）——默认值锚定专治这种单向 drift。

**AC-2**: (a) 推荐可用日表单预填且与推荐 API 数值一致（非 mock 冒烟：对 live 推荐 payload 断言字段透传）；(b) 偏离字段的 auto-note 落入 ledger open 事件；(c) wait 日无预填 + 横幅含 reason + 提交路径不受阻。

## 3. Entry 表单风险行（改进③）

表单实时显示三个绝对值（今日尺度原则，禁止只报比例）：
- **本单 max loss $**：credit 结构 =(width−credit)×100×n；debit 结构 =debit×100×n
- **同家族并发 max loss $**：本单 + 现有 open 同 strategy 家族仓位合计
- **占流动现金 %**：分母 `get_current_liquid_cash()`（cash_budget_governance 现成函数；不可用时该行显示 n/a，不阻塞）

5 月实证：5/14 单日加 $154k、5/14+5/15 并发 ~$197k，当时无人看见这个数。

**AC-3**: fixture 三值与手算脚本一致（测试向量脚本生成）；NaN/Inf 不入 JSON（strict-JSON 断言）；现金源不可用时 fail-soft。

## 房规

UI 改动先读 DESIGN.md；theme.css vars；可读内容禁 --text-muted（用 --text-2）；推送一律走 notify/gateway；ledger append-only。

## 边界

不改 selector/门逻辑；不新增拦截；credit 并发 cap 是否设规则 = DEFERRED #20（PM 治理决定，不在本 SPEC）。
