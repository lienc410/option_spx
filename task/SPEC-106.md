# SPEC-106 — Strategy Matrix Selector-Consistency & Payoff Semantics

**Type**: UX consistency + new backend endpoint
**Date**: 2026-05-26
**Status**: **APPROVED 2026-05-26** — ready for Developer / FE engineer implementation
**Owner**: Quant Researcher (draft) → PM approval → Developer / FE engineer implementation
**Source**: PM observation 2026-05-26 + 2nd Quant verdict (`task/q076_matrix_consistency_2nd_quant_review_2026-05-26_Review.md`)
**Priority**: 中高

---

## 0. TL;DR

PM 在 `/matrix` + `/spx` dashboard 上发现两个语义问题：

1. **Matrix 显示与 selector 实际逻辑不一致** — `NORMAL + HIGH IV + BULLISH` cell 显示 "Bull Put Spread" 但 selector.py:1083-1088 (SPEC-060) 实际 return REDUCE_WAIT
2. **IV 轴语义在不同 VIX regime 下翻转** — LOW_VOL 列下低 IV 是 debit 策略的好信号；NORMAL/HIGH_VOL 列下低 IV 是 credit 策略的"premium 不够"

修法：
- **A. Selector consistency** — matrix cell 主标签 = current selector verdict（不再是历史 strategy name）
- **B. Payoff semantics labels** — 每 cell 加 `CREDIT / DEBIT / WAIT / BLOCKED / RESEARCH_ONLY` 标签
- **C. 36-cell audit** — 4 VIX regime × 3 IV × 3 trend，逐格 selector-vs-matrix tie-out
- **D. UI helper text** — 解释 IV 语义在 credit vs debit 策略下不同

**不动**：
- `strategy/selector.py` 策略逻辑（已校准）
- 历史 stats backtest cache（仅作 secondary reference 显示）
- LOW_VOL panel 拆分（不做，sub-label 已经解决问题）

---

## 1. Background

### 1.1 PM 触发观察 (2026-05-26)

PM 在 NORMAL VOL 视图 (VIX 16.9, IVP 44, BULLISH) 上看到：
- HIGH IV + BULLISH 显示 "Bull Put Spread" 但右半边 stats "NA"
- NEUTRAL IV + BULLISH 显示 "Bull Put Spread" (NOW)
- 两格 strategy name 一致但 selector 实际处理完全不同

### 1.2 selector 真值

```python
# strategy/selector.py:1083-1088 (SPEC-060)
NORMAL + HIGH IV + BULLISH → REDUCE_WAIT
"no strategy has statistically significant alpha in this cell"

# strategy/selector.py:1218-1236
NORMAL + NEUTRAL IV + BULLISH → Bull Put Spread (with IVP gate 43-55)
```

### 1.3 Issue 2 的语义翻转证据

```python
# strategy/selector.py:1162-1166
NORMAL + LOW IV + BULLISH → REDUCE_WAIT
"thin premium (IVP<40) makes Diagonal risk/reward unfavourable; wait for IV to expand"

# strategy/selector.py:1029-1051
LOW_VOL + LOW IV + BULLISH → Bull Call Diagonal
"LOW_VOL + BULLISH — theta is cheap; use 45 DTE short leg to widen collection window"
```

→ 同样 LOW IV，NORMAL 下 WAIT (premium 不够卖)，LOW_VOL 下 BCD 交易 (long leg 便宜买)。**策略 type 不同 (credit vs debit)，所以 IV 偏好相反**。

---

## 2. Scope

### 2.1 Part A — Selector consistency

Matrix cells **主标签必须 = current selector verdict**。

显示层次（每 cell）：
```
[Primary]   selector verdict (strategy name OR REDUCE_WAIT/WAIT/BLOCKED)
[Secondary] payoff_type label (CREDIT / DEBIT / WAIT)
[Tertiary]  reason (SPEC-XXX tag OR gate description)
[Reference] historical stats (WR / avg / n) — visually de-emphasized
```

如果 cell 是 gated (REDUCE_WAIT)：
- 主标签：**REDUCE_WAIT** (大字 + warning color per DESIGN.md)
- Reason：**SPEC-060: no significant alpha**
- Historical reference：可选显示 "Historical ref: Bull Put Spread" 灰色小字
- 不显示 WR/avg/n（避免误导）

### 2.2 Part B — Payoff semantics

每 cell 增加 `payoff_type` 字段（来自 selector）：

| payoff_type | 含义 | 视觉提示 |
|---|---|---|
| `CREDIT` | net-credit short premium 策略 (BPS / IC / BCS) | 金色边框 |
| `DEBIT` | net-debit long-vol 结构 (BCD / Calendar) | 紫色边框 |
| `NEUTRAL_PREMIUM` | mixed (e.g., IC with both wings) | 蓝色边框 |
| `WAIT` | REDUCE_WAIT due to gating | 灰色 + warning icon |
| `BLOCKED` | structurally blocked (HV Ladder, etc.) | 红色 + lock icon |
| `RESEARCH_ONLY` | paper-only / 0% production | 红 banner |

### 2.3 Part C — 36-cell audit

写 `scripts/matrix_consistency_audit.py`：
- 枚举 4 VIX regime × 3 IV bucket × 3 trend = 36 cells
- 对每 cell 构造合成 VixSnapshot / IVSignal / TrendSignal，调 `select_strategy()`
- 收集：selector_verdict / reason / strategy / canonical_strategy
- 输出 CSV: `data/matrix_consistency_audit_<date>.csv`

每行 schema:
```
cell_id, vix_regime, iv_bucket, trend, matrix_displayed, selector_verdict,
selector_reason, payoff_type, historical_strategy, consistent (bool)
```

AC: 全部 36 cells 必须 `consistent == True`。任何不一致 → fail。

### 2.4 Part D — UI helper text

`/matrix` 页面顶部加 collapsible info panel：

```
ℹ️ How to read the matrix

• Strategy name reflects current selector verdict (live), not historical stats.
• Payoff type labels:
    CREDIT = sell premium (needs adequate IV)
    DEBIT  = buy structure (benefits from cheap options)
    WAIT   = no statistical edge in this cell
• IV level has regime-dependent meaning:
    LOW_VOL  → low IV is favourable for debit/diagonal
    NORMAL/HIGH_VOL → low IV is unfavourable for credit
• Historical stats (WR/avg/n) are reference only. Current verdict is the trade fact.
```

### 2.5 NOT changed

- `strategy/selector.py` 任何策略逻辑
- 历史 backtest stats cache（仅显示位置和层级变化）
- LOW_VOL panel 拆分（暂不做）
- IV 轴名称（不重命名，加 helper text 即可）

---

## 3. New Backend Endpoint

### 3.1 `/api/strategy-matrix`

返回 36 cells 数组，每 cell schema：

```json
{
  "vix_regime": "NORMAL",
  "iv_bucket": "HIGH",
  "trend": "BULLISH",
  "selector_verdict": "REDUCE_WAIT",
  "strategy": null,
  "historical_reference_strategy": "Bull Put Spread",
  "reason": "SPEC-060 — no statistically significant alpha",
  "payoff_type": "WAIT",
  "wr_3y": null,
  "wr_10y": null,
  "wr_all": null,
  "avg_pnl_3y": null,
  "n_3y": null,
  "gated": true,
  "is_current_active_cell": false
}
```

`is_current_active_cell` = true 表示这是 live VIX/IV/Trend 当前指向的 cell（用于 "NOW" 高亮）。

实现：在 `web/server.py` 加 route：
- 遍历 4 × 3 × 3 = 36 组合
- 对每组合构造合成 inputs，调 `strategy.selector.select_strategy()`
- 提取 verdict + reason + payoff_type
- 历史 stats 从现有 backtest cache (q041_backtest_cache.json 等) 查
- 缓存 5 分钟（market state 5 分钟内不会大变）

### 3.2 Payoff type 计算

在 `strategy/selector.py` 增加 helper（不改主逻辑）：

```python
def get_payoff_type(strategy_name: str | None) -> str:
    if strategy_name is None:
        return "WAIT"
    if strategy_name in (
        "Bull Put Spread", "Bull Put Spread (High Vol)",
        "Iron Condor", "Iron Condor (High Vol)",
        "Bear Call Spread (High Vol)",
    ):
        return "CREDIT"
    if strategy_name in ("Bull Call Diagonal", "Calendar", "Diagonal"):
        return "DEBIT"
    if strategy_name == "Stress Put Ladder":
        return "RESEARCH_ONLY"
    return "NEUTRAL_PREMIUM"
```

---

## 4. File Changes

| File | Action |
|---|---|
| `strategy/selector.py` | EDIT — 增加 `get_payoff_type()` helper（不改主逻辑） |
| `web/server.py` | EDIT — 加 `/api/strategy-matrix` route，遍历 36 cells |
| `web/templates/matrix.html` | EDIT — 主标签改为 selector verdict；加 payoff_type sub-label；加 helper text panel |
| `web/templates/spx.html` | EDIT — recommendation card 同步显示 selector verdict + payoff_type |
| `scripts/matrix_consistency_audit.py` | NEW — 36-cell audit 脚本 |
| `data/matrix_consistency_audit_<date>.csv` | NEW (生成的) — audit 输出 |
| `tests/test_spec_106.py` | NEW — selector helper + endpoint unit test |

---

## 5. Acceptance Criteria

| AC | 描述 | Verification |
|---|---|---|
| AC-106-1 | NORMAL + HIGH IV + BULLISH cell 主标签 = "REDUCE_WAIT" (不是 "Bull Put Spread") | 浏览器 visual on oldair |
| AC-106-2 | 每个 36 cells 显示 selector_verdict + reason | curl /api/strategy-matrix \| jq \| wc -l == 36 |
| AC-106-3 | 每 cell 显示 payoff_type 标签 | DOM inspect |
| AC-106-4 | Historical stats (WR/avg/n) 视觉上 secondary（小字/灰色/位置在下方） | visual review |
| AC-106-5 | selector.py 是 source of truth — 前端不复制策略逻辑 | code review |
| AC-106-6 | 36-cell audit 输出 CSV，全部 consistent=True | python3 scripts/matrix_consistency_audit.py 不报 fail |
| AC-106-7 | LOW_VOL + LOW IV + BULLISH cell 显示 "Bull Call Diagonal" + DEBIT 标签 | visual |
| AC-106-8 | NORMAL + LOW IV + BULLISH cell 显示 REDUCE_WAIT + "thin premium" reason | visual |
| AC-106-9 | UI helper text panel 包含 IV 语义解释 | visual |
| AC-106-10 | "NOW" 高亮指向 `is_current_active_cell == true` 的 cell | live state cross-check |
| AC-106-11 | tests/test_spec_106.py PASS | pytest |
| AC-106-12 | tests/test_spec_103.py + tests/test_spec_104.py + tests/test_spec_105.py 无 regression | pytest |
| AC-106-13 | DESIGN.md 颜色语义保持一致（金/紫/深绿等） | visual + DESIGN.md cross-ref |

---

## 6. Out of Scope

| 项 | 原因 |
|---|---|
| 修改 `strategy/selector.py` 主策略逻辑 | 不动策略真值 |
| 重命名 IV 轴 | helper text 已解决，避免大改 |
| 拆 LOW_VOL panel | sub-label 已经够清楚；future enhancement |
| 重新做 backtest stats | 不动历史数据 |
| 增加新策略类型 | scope creep |
| 修改 SPEC-105 v2 booster gate | 已 deployed，无关本 SPEC |

---

## 7. Deploy

1. Developer 实施 §4 file changes
2. 跑 `python3 scripts/matrix_consistency_audit.py` 确认 36/36 consistent
3. Backtest cache 不需要 refresh（不动策略逻辑）
4. Local pytest pass
5. Commit + push
6. Old Air `git pull` + restart web (per `feedback_deploy_oldair`)
7. PM 在浏览器 visual 验收 AC-106-1 ~ AC-106-10

Smoke tests:
- `curl https://spx.portimperialventures.com/api/strategy-matrix | jq '.[] | select(.gated==true) | {vix_regime, iv_bucket, trend, selector_verdict}'`
- Visual on `/matrix` + `/spx`

---

## 8. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| selector.py `get_payoff_type` helper | ~30 min | ~1h |
| `/api/strategy-matrix` endpoint | ~1h | ~3h |
| matrix.html + spx.html UI changes | ~1.5h | ~4h |
| matrix_consistency_audit.py | ~30 min | ~1.5h |
| tests/test_spec_106.py | ~30 min | ~2h |
| AC verification + deploy | ~30 min | ~2h |
| **Total** | **~4h** | **~1.5 days** |

---

## 9. PM Approval Signature (APPROVED 2026-05-26)

- [x] Approve Part A (selector consistency)
- [x] Approve Part B (payoff semantics labels)
- [x] Approve Part C (36-cell audit)
- [x] Approve Part D (UI helper text)
- [x] Approve new `/api/strategy-matrix` endpoint
- [x] Approve out-of-scope list (§6)
- [x] Confirm not touching selector.py 策略逻辑

Quant ready for Developer / FE engineer handoff. See §10 implementation discipline.

---

## 10. Developer Handoff Notes

### Implementation discipline

> 不要在前端模板里复制 selector 的策略判断逻辑。前端必须从 `/api/strategy-matrix` 取 verdict + payoff_type，不要自己算"如果 VIX > 22 显示什么"。selector.py 是唯一真值。

### selector.py helper 注意

`get_payoff_type()` 是**纯映射**，不影响主逻辑。但要：
- 在 `select_strategy()` return 的 Recommendation dataclass 上加 `payoff_type` 字段
- 默认 fallback：未知 strategy name → `NEUTRAL_PREMIUM`

### Matrix UI 设计要点

主显示区域优先级（从大到小）：
1. selector_verdict (策略名 OR REDUCE_WAIT) — 最大字
2. payoff_type label — 中字 + 颜色边框
3. reason (SPEC tag) — 小字
4. historical_reference_strategy (灰色小字 "Historical ref: XXX")
5. WR/avg/n stats — 最小字 + 灰色（仅当 gated=false 时显示完整 stats；gated=true 时不显示，避免误导）

### Backtest stats 显示规则

- gated=false (current strategy active): 显示 3Y/10Y/All WR + avg + n（同当前）
- gated=true (REDUCE_WAIT): 隐藏 stats，只显示 "Historical ref: <strategy> (gated)"
- 这样 PM 不会被 "REDUCE_WAIT but WR 82%" 这种矛盾显示困扰

---

## 11. PROJECT_STATUS.md 索引项

```
- `SPEC-106` — Strategy Matrix Selector-Consistency & Payoff Semantics.
  **DRAFT 2026-05-26.** PM 在 dashboard 上发现 matrix cell 显示与 selector
  实际 verdict 不一致 (NORMAL+HIGH IV+BULLISH 显示 BPS 但 SPEC-060 已 gate
  REDUCE_WAIT)，同时 IV 轴语义在 LOW_VOL (debit) vs NORMAL/HIGH_VOL (credit)
  下翻转。2nd Quant 判断为 UX bug，不是 quant model bug。本 SPEC 修复：
  (A) matrix cell 主标签 = selector verdict (B) 每 cell 加 payoff_type
  label (C) 36-cell audit (D) UI helper text。新 endpoint
  /api/strategy-matrix。selector.py 是 source of truth，前端不复制策略
  逻辑。AC1-AC13。— `See: task/SPEC-106.md`
```

---

## 12. References

- `strategy/selector.py:1060-1180` — NORMAL regime 完整逻辑
- `strategy/selector.py:949-1058` — LOW_VOL regime
- `strategy/selector.py:1083-1088` — SPEC-060 NORMAL+HIGH+BULLISH gate
- `web/templates/matrix.html` — matrix 视觉模板
- `web/templates/spx.html` — recommendation card
- `task/q076_matrix_consistency_2nd_quant_review_2026-05-26_Review.md` — 2nd Quant 全文 verdict
- `~/.claude/.../memory/feedback_quant_review_location.md` — 文件位置约定
