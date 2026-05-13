# SPEC-100 — HV Spell `max_trades_per_spell` 2 → 3

**Type**：research-driven (parameter tweak)
**Date**：2026-05-13
**Status**：APPROVED 2026-05-13 (PM)
**Owner**：Developer
**Source**：Q064 P8 (`task/q064_p8_spell_gate_review.md`) + 2nd Quant APPROVE α (RESEARCH_LOG R-20260513-04)

---

## 0. TL;DR

将 `StrategyParams.max_trades_per_spell` 从 `2` 上调至 `3`。

预期影响（19y 实证）：+4 trades / +$5,424 total / +$1,500/yr，WR 同 (90.9 → 91.9%)，**worst trade 完全不变** (-$2,016)。无 tail risk 增加。

**单行参数修改 + 三套 backtest 缓存刷新 + RESEARCH_LOG 文档化**。预计 Developer 工作量 ~30 分钟。

---

## 1. Background

### 1.1 Q064 研究路径回顾

| Phase | 工作 | Verdict |
|---|---|---|
| P1-P4 | aftermath routing 框架 | misframed trade set，结论 voided |
| P5 + Task 1 | mechanical routing verification + V3-A 真实 trade 识别 | 33 笔实际 V3-A trades，与 P1-P4 的 15 笔不同 |
| P6 | V3-A vs IC_HV normal counterfactual | IC normal +93% equal-BP，但 mechanical fallback 显示 V3-A 是 gate bypass 而非结构优势 |
| **P5 closure** | **APPROVE α — retain V3-A** | SPEC-064 V3-A 保留 |
| P7 | skip log 分析（13 windows 触发但 0 trade） | 多数被 spell gate / max_trades / concurrent 阻挡 |
| **P8** | **`max_trades_per_spell: 2 → 3` 灵敏度** | **本 SPEC 实施依据** |
| P9 | spell reset 机制全套敏感性 (12 variants) | hysteresis / no-high-reset / age_cap 全 reject；仅 P8 是 Pareto positive change |

### 1.2 P8 实证证据（详 `task/q064_p8_spell_gate_review.md`）

| 配置 | n trades | WR | Total P&L | Worst | $/BP-day |
|---|---|---|---|---|---|
| spell_max=2 (current) | 33 | 90.9% | $39,715 | **-$2,016** | 2,570 |
| **spell_max=3 (proposed)** | **37 (+4)** | **91.9% (+1pp)** | **$45,139 (+$5,424)** | **-$2,016 (unchanged)** | 2,523 (-2%) |
| spell_max=4 | 38 | 92.1% | $46,647 | -$2,016 | 2,547 |
| spell_max=∞ | 38 | 92.1% | $46,647 | -$2,016 | 2,547 |

**关键点**：
- spell_max=4 与 ∞ 输出完全相同 → 数据中没有 spell 累积超过 4 个有效信号 → 不应 over-relax
- 4 笔增量 trades **全部盈利**（avg +$1,356/trade）
- worst trade 与 baseline 完全相同 → 无 tail risk 增加
- Spell #1 vs #2 (baseline 数据) WR 几乎相同 (91.7% vs 90.9%)，不支持"晚期 trade 退化"假说 → max=3 应也不退化

### 1.3 增量 4 笔 trades 明细

| entry | exit | hold | P&L | exit reason |
|---|---|---|---|---|
| 2010-07-08 | 2010-08-10 | 33d | +$1,359 | 50pct_profit |
| 2015-09-10 | 2015-10-02 | 22d | +$1,588 | 50pct_profit |
| 2022-03-23 | 2022-04-18 | 26d | +$1,377 | 50pct_profit |
| 2025-04-29 | 2025-06-03 | 35d | +$1,100 | roll_21dte |

4/4 winners, 4 个不同年份，无聚集。

### 1.4 2nd Quant verdict (2026-05-13)

**APPROVE α** — 单独采纳 P8 max=3；不捆绑 P9 spell_age_cap=90（证据仅 1 笔交易，太薄）；reject hysteresis / no-high-reset / combos（spell reset 机制 deliberate design）。

---

## 2. The Change

### 2.1 Single-line modification

**File**: `strategy/selector.py`
**Line**: 93

```diff
@dataclass
class StrategyParams:
    ...
    spell_age_cap:        int = 30
-   max_trades_per_spell: int = 2
+   max_trades_per_spell: int = 3   # SPEC-100: P8 +4 trades / +$5.4k / 19y, worst unchanged
    ...
```

### 2.2 Add documentation comment near constant

In `strategy/selector.py` near line 93, add inline rationale (similar to SPEC-094.1 pattern):

```python
# SPEC-100 (2026-05-13): Raised from 2 to 3 per Q064 P8 evidence:
# +4 incremental trades over 19y, all winners, avg $1,356; total +$5,424;
# worst trade unchanged at -$2,016. Spell-internal trade #1 vs #2 (baseline
# data) showed no quality degradation, supporting that #3 should also hold.
# P9 (2026-05-13) confirmed other spell reset params (hysteresis, high_reset,
# age_cap) are deliberate design — do NOT change them without similar
# Quant-grade evidence.
max_trades_per_spell: int = 3
```

### 2.3 No other code changes

- `_block_hv_spell_entry` reads from `params.max_trades_per_spell` dynamically — no logic change needed
- All call sites use `params.max_trades_per_spell` not hardcoded `2`
- No test fixture changes needed (parametrized check)

---

## 3. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| **AC-100-1** | `strategy/selector.py:93` `max_trades_per_spell = 3` | `grep` confirms |
| **AC-100-2** | Full backtest reproduces P8 result | `python3 -m backtest.engine` (or equivalent) → V3-A trade count = 37 (±2), Total P&L ≈ $45,139 (±$500), worst = -$2,016 (exact) |
| **AC-100-3** | Spell #1 vs #2 vs #3 layered metrics within tolerance | 跑 `research/q064/q064_p8_spell_gate_study.py` 后查 spell layering — #3 WR ≥ 80%, avg P&L ≥ $1,000 |
| **AC-100-4** | Three backtest caches refreshed (Q041 / ES / SPX) | Per feedback memory `feedback_backtest_cache_refresh.md` — Quant lane 主动提醒 PM |
| **AC-100-5** | RESEARCH_LOG entry `R-20260513-04` already records P9 closure + P8 approval; SPEC-100 deploy 后 append "DEPLOYED" 状态 | Single-line PROJECT_STATUS update |
| **AC-100-6** | 12-month review obligation 入 standing note: 2027-05-13 用 live + 扩展数据重测 P8 增量 quality | Calendar entry / SOP doc |

---

## 4. Out of Scope

| Item | 理由 |
|---|---|
| `spell_age_cap` 30 → 90 (P9 9c) | 仅 +1 trade / $1.3k 证据太薄；2nd Quant 否决 bundle；defer 为 future optional |
| `vix_low_reset` hysteresis | P9 9a Pareto fail (-$20-25k)；deliberate design 保留 |
| `vix_high_reset` 移除 | P9 9b Pareto fail (-$16k)；deliberate design 保留 |
| `IC_HV_MAX_CONCURRENT` 调整 | 未测试，不在 P8/P9 scope |
| V3-A vs IC_HV normal 结构改动 | Q064 P5 closure (APPROVE α retain V3-A) 已决定 |
| `/sync` Telegram command (SPEC-099 future) | 独立 telegram bot scope，不属本 SPEC |

---

## 5. Risk + Monitoring

### 5.1 Known risks PM 接受

1. **n=4 incremental 小样本**：2nd Quant disclosed；用 12-month live review 缓解
2. **0/4 losers in 19y backtest**：理论上未来可能首次出现 spell #3 loser，需 monitor
3. **Crisis exposure**：长 HV spell（VIX > 25 持续 ≥ 30 天）期间 #3 trade 入场仍可能与 #2 趋势相关；P8 packet 建议 Telegram warning，**本 SPEC 不实施**（separate future enhancement）

### 5.2 Standing monitoring (post-deploy)

| 触发条件 | Quant action |
|---|---|
| 2027-05-13 (12 months) | 重跑 P8 framework with live + extended data；若 incremental WR < 70% OR 增量 net P&L 负 → revert |
| 单一 spell 内出现 #3 trade 且亏损 ≥ -$3k | 立刻发起 Quant review，考虑临时降回 max=2 |
| 连续 HV spell（VIX > 25 sustained ≥ 60d）开始 | 在 Telegram alert 前增加 PM 人工确认要求（future SPEC scope） |

---

## 6. Reversal Plan

如果 post-deploy 12-month review fail (n>=3 #3 trades 亏损 OR 增量 P&L < $0)：

```diff
- max_trades_per_spell: int = 3   # SPEC-100: P8 +4 trades / +$5.4k / 19y
+ max_trades_per_spell: int = 2   # SPEC-100 reverted YYYY-MM-DD per live evidence
```

回退是单行修改 + cache refresh，无 architectural impact。

---

## 7. Cache Refresh (Quant 主动提醒)

Per `feedback_backtest_cache_refresh.md` standing instruction：策略算法/参数改动后必须刷新三套 backtest 缓存：

1. **Q041 backtest cache** — 若有 cross-strategy 影响
2. **ES backtest cache** — 若有 cross-portfolio 影响
3. **SPX backtest cache** — **必须**（直接受影响）

Specific files (Developer 实施时确认)：
- `data/backtest_results_cache.json`
- `data/backtest_stats_cache.json`
- Any `_Q064_BT_CACHE_MEM` or similar in-memory caches

刷新方式：删除现有 cache + 重跑 → 验证 V3-A trade count = 37。

---

## 8. Deploy

1. Local test PASS（AC-100-1, AC-100-2, AC-100-3）
2. Backtest cache refresh（AC-100-4）
3. Commit + push
4. Old Air: `git pull + restart web` (per feedback_deploy_oldair.md)
5. Smoke verify: `oldair.spxstrat.app/api/aftermath/v3a_trades` 或 backtest dashboard 验证 trade count 反映新参数

---

## 9. PROJECT_STATUS.md 索引项（Planner 自助）

```
- `SPEC-100` — HV Spell `max_trades_per_spell` 2→3. **DRAFT 2026-05-13.**
  research-driven (Q064 P8 + 2nd Quant APPROVE α 2026-05-13). Single-line
  param tweak: `strategy/selector.py:93`. Expected impact: +4 V3-A trades /
  +$5,424 / 19y, WR 90.9→91.9%, worst trade unchanged -$2,016. 12-month
  monitoring obligation. AC1-AC6. P9 `spell_age_cap=90` deferred as future
  optional. — `See: task/SPEC-100.md`, `RESEARCH_LOG.md R-20260513-04`
```

---

## 10. RESEARCH_LOG 已写入 R-20260513-04 (Q064 P9 closure)，含 P8 SPEC 推荐

Developer 实施后 append 一行 deploy status：

```
- 2026-MM-DD: SPEC-100 DEPLOYED (commit hash). Backtest cache refreshed.
  Live monitor 12-month standing obligation set for 2027-05-13.
```

---

## 11. Estimated Effort

| Phase | Time |
|---|---|
| Code change (1 line + comment) | 5 min |
| Local backtest verification (AC-100-2/3) | 10 min |
| Cache refresh + verify (AC-100-4) | 10 min |
| Commit + push + deploy | 5 min |
| **Total** | **~30 min Developer + ~5 min PM oversight** |
