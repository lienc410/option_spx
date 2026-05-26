# Strategy Matrix Design Review — 2nd Quant Verdict (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-26
**Source**: PM observation on `/matrix` + `/spx` recommendation card (2026-05-26)
**Verdict**: **OPEN SPEC — Issue 1 是 bug (必须修), Issue 2 是 UX/教学问题 (一起修)**

---

## Final verdict statement

> 开一个前端 / selector-consistency SPEC，一次性解决：matrix 显示必须反映 current selector verdict；同时给每个 cell 加 payoff-type / gating reason 标签，避免 IV 轴在不同 regime 下语义混乱。这不是 quant model bug，selector 逻辑是对的。问题是 dashboard 在展示"历史最佳策略"和"当前可执行推荐"时没有分层。

---

## Issue 1 verdict — Bug, 必须修

NORMAL + IV HIGH + BULLISH 在 selector.py:1083-1088 return REDUCE_WAIT (SPEC-060)，但 matrix 显示 "Bull Put Spread"。即使右边 stats 是 NA，主标签错误就是 bug。**PM 第一眼看 strategy name，不看 stats**。

**根本要求**：Matrix 主标签必须反映 selector 当前 verdict；历史 stats 只能做 secondary reference。

**需要系统核查 36 格**（4 VIX × 3 IV × 3 trend），因为 SPEC-051/054/058/060 等多次 gate 修订可能让多个 cell 漂移。

## Issue 2 verdict — UX semantics, 也修

IV 轴在不同 regime 下语义翻转：
- NORMAL/HIGH_VOL：credit 策略需要高 IV
- LOW_VOL：debit/diagonal 策略喜欢低 IV

不是策略矛盾，是 dashboard 视觉一致但底层语义反向。**Sub-label 标 payoff_type (CREDIT/DEBIT/WAIT) 解决 80% 误解**。

三个修法选择：
- **A. 每格加 payoff-type sub-label** ← 推荐
- B. IV 轴重命名 ← 轻量做（加 helper text，不改轴名）
- C. LOW_VOL 拆 panel ← **不做**（先 sub-label，后续再考虑）

---

## SPEC 建议 scope

**SPEC-106 — Strategy Matrix Selector-Consistency & Payoff Semantics**

### Part A — Selector consistency
- Matrix cells 主标签必须 = current selector verdict
- Historical stats → secondary/reference
- Gated cells 必须显示 REDUCE_WAIT / WAIT / BLOCKED 含 SPEC tag

### Part B — Payoff semantics
- 每 cell 加 payoff_type 标签：`CREDIT / DEBIT / NEUTRAL_PREMIUM / WAIT / BLOCKED / RESEARCH_ONLY`

### Part C — Audit
- 36-cell selector-vs-matrix tie-out
- 任何 cell 主标签 ≠ selector verdict → FAIL AC

### Part D — UI copy
- Helper text 解释 IV 在 credit vs debit 策略下含义不同

---

## ACs (9 items)

| AC | 描述 |
|---|---|
| AC1 | NORMAL + HIGH IV + BULLISH 显示 REDUCE_WAIT，不是 Bull Put Spread |
| AC2 | 每个 36 cells 有 selector_verdict + reason |
| AC3 | 每个 cell 有 payoff_type 标签 |
| AC4 | Historical stats 视觉上 secondary |
| AC5 | selector.py 是 source of truth；前端不复制策略逻辑 |
| AC6 | 36-cell audit 输出生成并存档 |
| AC7 | LOW_VOL + LOW IV + BULLISH 显示 BCD + DEBIT/diagonal 标签 |
| AC8 | NORMAL + LOW IV + BULLISH 显示 REDUCE_WAIT + "thin premium" reason |
| AC9 | UI helper text 解释 IV 语义因 regime 而异 |

---

## 是否需要新 endpoint

**是**。提议 `/api/strategy-matrix` 返回每 cell：
```json
{
  "vix_regime": "NORMAL",
  "iv_bucket": "HIGH",
  "trend": "BULLISH",
  "selector_verdict": "REDUCE_WAIT",
  "strategy": null,
  "historical_reference_strategy": "Bull Put Spread",
  "reason": "SPEC-060",
  "payoff_type": "WAIT",
  "wr": null,
  "avg_pnl": null,
  "n": null,
  "gated": true
}
```

selector.py 是真值。前端只展示，不复制逻辑。

---

## 不需要研究层介入

selector.py 逻辑没有问题。需要的是 **logic tie-out**（selector actual logic vs matrix output），不是新研究。

如果 audit 发现某些 cell 的 selector 逻辑本身不清楚，再单独开 research question。

---

## 2nd Quant Sign-off

- [x] Issue 1 confirmed as bug — open SPEC
- [x] Issue 2 confirmed as UX problem — fold into same SPEC
- [x] 36-cell audit required as AC
- [x] selector.py 是 source of truth
- [x] payoff_type sub-label 是正确修法（推荐 A）
- [x] LOW_VOL panel 拆出暂不做
- [x] 优先级中高
- [x] 无需研究层介入

→ Quant proceeds to draft SPEC-106.

---

## 一句话

> Selector 是交易事实，matrix 必须服从 selector；历史 stats 只能做 reference，不能做主推荐。
