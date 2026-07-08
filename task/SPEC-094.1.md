# SPEC-094.1 — Q042 Sleeve A 参数替换（D30 width 2.5%）

**Type**：Amendment to SPEC-094
**Date**：2026-05-10
**Owner (Quant)**：Quant Researcher
**Status**：DRAFT for Developer pickup
**Source research**：Q062 Tier 1/2/3 ([task/q062_tier1_memo](q062_tier1_memo_2026-05-10.md), [tier2](q062_tier2_memo_2026-05-10.md), [tier3](q062_tier3_memo_2026-05-10.md))

---

## 0. TL;DR

**Sleeve A** 从 `ATM/+5% vertical, 90 DTE` → `ATM/+2.5% vertical, 30 DTE`。
**Sleeve B** 不变。
**Combined cap A+B ≤ 20%** 不变。
Q062 Tier 1→2→3 三级研究路径以及 decay-weighted 分析支持此修订。

| Sleeve | SPEC-094 baseline | SPEC-094.1 修订 |
|---|---|---|
| **A** (dd4 lenient) | ATM/+5% call vertical, **90 DTE** | **ATM/+2.5% call vertical, 30 DTE** ✏️ |
| **B** (dd15 + MA10 reclaim) | ATM/+5% call vertical, 90 DTE | **不变** ✅ |

---

## 1. Background

### 1.1 Q062 研究路径

| Tier | 工作 | 结论 |
|---|---|---|
| Tier 1 | 5 candidates per sleeve sanity check | Strict pass bar FAIL，但暴露 worst-trade saturation 问题 |
| Tier 2 | 84 cells grid (3 structures × 5 widths × 6 DTEs × 2 sleeves) | Sleeve A 暴露 **D30 short-DTE alpha cluster**：ann +9.94% vs baseline +5.02% |
| Tier 3 | 4-test robustness on D30 candidates | OOS PASS (both periods)、disaster window OK、improved metrics tied、bootstrap p=0.09 marginal |
| 后续 | Pareto + decay-weighted analysis | D30/2.5% 在 6 Pareto cells 中 risk-adjusted 最优（DD -1.3pp、WR +3pp、Sharpe +0.91、maxConsecL -1）vs D30/5% |

### 1.2 D30/2.5% vs D30/5% 决策依据

D30/2.5% 在所有 risk 维度占优，AnnROE 持平：

| metric | D30/2.5% | D30/5% | 赢家 |
|---|---|---|---|
| AnnROE unweighted | +9.94% | +9.94% | tied |
| AnnROE 5y HL decay | +11.49% | +11.57% | D30/5% (+0.08pp, noise) |
| WR | 74% | 71% | **D30/2.5% (+3pp)** |
| MaxDD | -19.0% | -20.3% | **D30/2.5% (+1.3pp)** |
| Sharpe | 8.91 | 8.00 | **D30/2.5% (+0.91)** |
| maxConsecL | 2 | 3 | **D30/2.5% (-1)** |

### 1.3 Sleeve B 不动的依据

Sleeve B n=5 across 19y，所有改动候选 statistically 无法 reject baseline。Wider widths 的 decay 优势是「2008 outlier suppression」（regime selection），不是真实结构优势。Baseline 100% WR / 0% DD 是 Pareto-near-best。Sleeve B 保持 5%/90D。

### 1.4 PM 接受的 risk

- Bootstrap 差值 95% CI 仍 overlap 0（p=0.09），统计 strictly 不显著
- P(C > A) = 91%（Bayesian 强证据）→ PM 接受 9% 概率事后证明无 alpha 提升的风险
- D30 触发频率 1.81/yr（vs baseline 1.30/yr），PM 接受 alert 频率上升

---

## 2. Sleeve A 完整修订定义

### 2.1 Trigger（不变）

- 同 SPEC-094：dd4 lenient state machine
- `ddath = close / cum_max(close) − 1`（cum_max 从 2007-01-01 起）
- Armed → fire when ddath ≤ -0.04
- Disarmed → re-arm when ddath ≥ -0.02
- 触发当天 = signal_date

### 2.2 No-overlap window（改）

- SPEC-094: 90 days
- **SPEC-094.1: 30 days**
- 触发后 30 calendar 日内不再 fire（即 next signal must be ≥ T0 + 30）

### 2.3 Execution（改）

| 参数 | SPEC-094 | SPEC-094.1 |
|---|---|---|
| Long strike | ATM (signal close, round to nearest 5) | ATM (signal close, round to nearest 5) — same |
| Short strike offset | +5% | **+2.5%** ✏️ |
| Short strike | `S_signal × 1.05`, round to 5 | `S_signal × 1.025`, round to 5 |
| Expiry | signal + 90 calendar days | **signal + 30 calendar days** ✏️ |
| Entry timing | T+1 open | T+1 open — same |
| Settlement | cash-settled European | same |

### 2.4 Sizing (不变)

- 10% NLV per sleeve cap
- NLV threshold ≥ $200k

### 2.5 Combined cap (不变)

- A + B ≤ 20%
- Gate: `min(20%, max(0, 60% − main_bp%))`

### 2.6 Pricing model (term mult 自动适应)

term_mult 函数已覆盖：
- dte ≤ 45 → 1.10（**Sleeve A 现在落在此区间** at DTE 30）
- 45 < dte ≤ 120 → 1.00（**Sleeve B 仍在此区间** at DTE 90）
- dte > 120 → 0.95

无需改 pricing.py 公式，只需改 Sleeve A 的 DTE 参数。

---

## 3. 现有 in-flight Sleeve A 仓位的处理（重要）

当前有一笔 Sleeve A 仓位（per R-20260510-11）：
- signal 2026-03-12, entry 2026-03-13
- baseline 5%/90D 结构
- expiry **2026-06-10**
- MTM 当前 +7.89% account_pct

**处理决定（grandfather）**：让这笔仓位按 SPEC-094 baseline 规则 run 到 2026-06-10 expiry，**不强制平仓 / 不结构转换**。SPEC-094.1 部署后的新 Sleeve A trigger（首次 ddath re-arm 至 ≥ -2% 后再次 ≤ -4%）才用 D30/2.5% 新结构。

这避免：
- 中途换结构产生 P&L gap（baseline 卖 + D30/2.5% 买的 spread/timing cost）
- state machine 复杂化
- 实战意外（PM 当前已被告知 baseline 持仓，无需 surprise 切换）

---

## 4. Acceptance Criteria（Developer 实施）

| AC# | 描述 | Verification |
|---|---|---|
| AC-1.1 | `signals/q042_trigger.py` Sleeve A no-overlap 从 90 → 30 days | 19y backtest 重现 n=35 (±2) Sleeve A trigger |
| AC-1.2 | `strategy/q042_pricing.py` Sleeve A DTE 90→30、short offset 0.05→0.025 | 重现 ann ROE +9.94% (±0.5pp), MaxDD -19.0% (±2pp) |
| AC-1.3 | `production/q042_executor.py` Telegram alert reflects D30/2.5% structure | dry-run with TELEGRAM_BOT_TOKEN 显示 short strike ATM+2.5%, expiry 30 DTE |
| AC-1.4 | `backtest/q042_engine.py` Sleeve A 参数同步 | full backtest 重现 Sleeve A n=35 (CLOSED) wr=74% ±5pp ann=+9.94% ±0.5pp; Sleeve B 不变 n=5 |
| AC-1.5 | **Grandfather 当前 in-flight 仓位** | 当前 signal=2026-03-12 仓位保留 baseline 5%/90D 结构，state.json 已记录，run 到 2026-06-10 不动 |
| AC-1.6 | `data/q042_state.json` Sleeve A `armed` 状态 grandfather 期内冻结，不接受新 trigger | 2026-06-10 之前若 ddath 再次 ≤-4%，仍 disarmed (因 has_pos)；2026-06-10 expiry 后才接受新 D30 trigger |
| AC-1.7 | `web/server.py` `/api/q042/state` 显示当前 sleeve A 仍是 baseline 5%/90D 直到 2026-06-10 | curl test |
| AC-1.8 | `web/templates/q042.html` strategy spec card 文案更新：标注「Sleeve A: D30/+2.5% (in effect from 2026-06-11)」+ 当前 grandfather 仓位说明 | visual on oldair |
| AC-1.9 | `task/q042_manual_sop.md` 修订：新 Sleeve A 结构 SOP + grandfather 说明 | doc commit |
| AC-1.10 | RESEARCH_LOG entry R-20260510-15 (Sleeve A SPEC change) 文字 | log appended |

---

## 5. Backtest 重现 Target（AC-1.4 详细）

Reference: [research/q062/q062_tier1_structure_scan.py](../research/q062/q062_tier1_structure_scan.py) variant `S1_2.5%/D30` + [research/q062/q062_tier3_robustness.py](../research/q062/q062_tier3_robustness.py)

**Sleeve A 修订后**：
- n_closed (excluding OPEN) ≈ 35 (tolerance ±2 due to small floating-point + date edge cases)
- win_rate_pct = 74% ±5pp
- ann_ROE_pct = +9.94% ±0.5pp
- max_dd_pct = -19.0% ±2pp
- median winner account_pct: compute fresh
- median loser account_pct: compute fresh

**Sleeve B 不变**：
- n=5, wr=100%, total ≈ +41%, MaxDD = 0%

backtest engine 改动小：仅 Sleeve A 的 `_DTE_A = 30` 和 `_OTM_A = 0.025`（若代码尚不分 sleeve，需 refactor 为 per-sleeve 参数）。

---

## 6. Manual SOP 修订（task/q042_manual_sop.md）

### 6.1 Section B 修订

```diff
- Sleeve A: long ATM call / short ATM+5% call vertical, 90 DTE expiry
+ Sleeve A: long ATM call / short ATM+2.5% call vertical, 30 DTE expiry
+ (Grandfather 期: 2026-03-12 入场仓位 sticks with old 5%/90D 直到 2026-06-10 expiry)
```

### 6.2 触发频率预期更新

```
触发频率（19y empirical）：
  Sleeve A baseline (deprecated):  ≈ 1.30 alerts/yr
  Sleeve A SPEC-094.1 (new):       ≈ 1.81 alerts/yr  (+40%)
  Sleeve B:                        ≈ 0.26 alerts/yr  (unchanged)
  Total expected alerts/yr:        ≈ 2.07
```

---

## 7. Monitoring 与 Re-evaluation

### 7.1 Standing obligations（沿用 SPEC-094）

- **首次 Sleeve A live trigger 在 SPEC-094.1 生效后（VIX ≥ 22）**：Quant re-run `research/q042/q042_f4_oldair_backfill.py` 对当天 D30/2.5% chain 重新验证 broker midpoint vs model debit
- **2026-11-10 半年 review**：
  - 用 6 月 live + 6 月扩展 19y 数据重跑 Q062 Tier 3 bootstrap 差值 CI
  - 若 CI 跨过 0 reject H0：confirm Sleeve A 修订正确
  - 若 CI 仍 overlap 0：sleeve A 修订仍在 underpowered 状态，监控但不 revert
- **连续 3 笔 Sleeve A 亏损**：暂停后续入场，发起 Quant review

### 7.2 风险已 disclosed

- Bootstrap p=0.09 marginal，9% 概率事后证明 Sleeve A 修订无 alpha 提升
- alert 频率 +40%（1.30 → 1.81/yr）：PM 接受 manual execution 工作量上升
- Grandfather 期 2026-05-10 到 2026-06-10 期间，若 ddath 再次 ≤ -4%，**新 trigger 不触发**（has_pos=True 不 re-arm）；此为既有 state machine 设计，不需特殊处理

---

## 8. RESEARCH_LOG 拟写入条目（Quant 后续 append）

```
### R-20260510-15 — Q062 闭环：SPEC-094.1 Sleeve A 从 5%/90D 替换为 2.5%/30D

- Topic: Q062 三 Tier 研究 + Pareto + decay 分析后 PM 决策 dual-sleeve 不增 Sleeve C/D，仅替换 Sleeve A 参数
- Decision basis:
  - Tier 3 OOS 双期 PASS (train +0.66pp, test +10.52pp ann vs baseline)
  - Bootstrap 差值 CI 边缘（p=0.09, P(C>A)=91%）
  - Pareto: D30/2.5% 在 6 Pareto cells 中 risk-adjusted 最优
  - Decay weighting：D30/2.5% 与 D30/5% AnnROE 持平，但 D30/2.5% 在 WR/DD/Sharpe/maxConsecL 全面占优
  - Sleeve B n=5 无 statistical power，保持 baseline
- Implementation:
  - SPEC-094.1 修订仅 Sleeve A 两参数：DTE 90→30, short offset 5%→2.5%
  - Sleeve B 不动
  - Grandfather 当前 2026-03-12 仓位至 2026-06-10 expiry
  - 10 ACs (AC-1.1 to AC-1.10) covering trigger / pricing / executor / backtest / state / web / SOP
- Caveats:
  - p=0.09 仍是 marginal evidence，9% downside risk PM 已 accept
  - Alert 频率 +40%（PM 接受）
  - 2026-11-10 半年 review 时用 6 月 live + 扩展数据 reconfirm
- Artifacts: task/SPEC-094.1.md, research/q062/q062_tier1_structure_scan.py, q062_tier2_grid_scan.py, q062_tier3_robustness.py, data/q062_tier2_grid.csv
```

---

## Errata（2026-07-08，SPEC-094.2 独立审计 N8）

§2.3 表格「Expiry: signal + 30 calendar days」为初稿字面，未同步后续 R-20260510-15 修正——**真值 = entry（T+1）+ 30 calendar days（= signal+31）**；Sleeve B 同理 entry+90（= signal+91）。executor 与 walk-forward 实现均已按 entry 锚点；`production/q042_positions.py` 的 signal+90 硬编码由 SPEC-094.2 F2 修复。引用本 spec expiry 语义时以 R-20260510-15 为准。
