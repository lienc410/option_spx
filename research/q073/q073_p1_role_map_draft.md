# Q073 P1 — Strategy Role Map (DRAFT / pre-compute)

> **Status: DRAFT / pre-compute snapshot.**
> **This is NOT a completed P1 deliverable.**
> Built from existing memos, code, and prior research only.
> No new 26y replay / friction adjustment / cross-strategy correlation has been run.
> Purpose: 让 PM 早期校准 role classification 口径，避免后续 P1/P2 跑偏。
> Full P1 compute still pending (2-3 days).

**Date**: 2026-05-17
**Parent**: `q073_p0_anchored_memo_2026-05-17.md`

---

## Role Classification Framework (per 2nd Quant P0 review)

每个策略不能只按 ROE 排名。必须先分 role:

| Role | 定义 | 评价标准 |
|---|---|---|
| **Core income engine** | 日常 BP 部署 + 周期性 PnL 贡献 | Primary ROE + $/BP-day + 稳健性 |
| **Opportunistic high-vol engine** | 仅 HIGH_VOL regime 部署，平时 idle | Per-trade $/BP-day in 触发期 + 触发频率 |
| **Hedge / Convex overlay** | 在 drawdown / tail 中赚钱，平时小亏 | Stress-period PnL + tail offset, NOT standalone ROE |
| **Permission / Bypass module** | 触发后允许其他模块入场 / bypass gate, 自身可能非 standalone alpha | Marginal contribution under bypass role, NOT standalone alpha |
| **Idle cash filler** | 无信号期 BP 部署, low-risk yield filler | Risk-adjusted yield vs T-bill baseline |
| **Research / Paper candidate** | 数据不足，6mo+ A/B 期 | Live evidence accumulation rate |

---

## Current Architecture — Role Assignment

### 1. SPX BPS Main (Q041 family) — **Core income engine**

- **设计**: regime × IV signal × trend matrix → BPS / IC / Bear Call / Bull Call / Reduce-Wait
- **现状**: production daily entry decision via `/api/recommendation`
- **Role rationale**: 是组合 BP 部署的主力。绝大多数日子是这个策略在持仓。
- **P1 评价标准**: Primary ROE (annualized) + $/BP-day + WR + worst-trade + max DD on SPX BPS sub-portfolio
- **Retire candidate?** ❌ 核心 income engine, 不退役。**可调参数 (per SPEC-077 / SPEC-084 / SPEC-100), 不退役。**

### 2. V3-A Aftermath Overlay — **Permission / Bypass module** ⚠️

- **设计**: HIGH_VOL + IV HIGH + (BEARISH 或 NEUTRAL) + `is_aftermath()` → broken-wing IC HV
- **Q064 结论**: 价值在于 **aftermath-specific bypass / permission alpha**，**不是** structural broken-wing alpha
- **Role rationale**: V3-A 替换 Bear Call Spread / IC normal 推荐 → 在 aftermath window 允许进入 HIGH_VOL regime
- **P1 评价标准 (per 2nd Quant P0 review)**: **按 permission role 边际贡献评价，不按 standalone sleeve ROE**。即"如果删掉 V3-A，aftermath window 的可达 trade 数会减少多少？这些 trade 的 incremental ROE 是多少？"
- **不要错把"低 standalone PnL"当作 retire 依据**
- **Retire candidate?** ⚠️ P1 attribution 后定。**评价路径**: 按 permission alpha (marginal trades enabled) 评估，不按 sleeve ROE

### 3. HV Ladder /ES (SPEC-101) — **Opportunistic high-vol sleeve**

- **设计**: V2f chassis (49-DTE → 21-DTE roll) + G6 gate (VIX ≥ 22)
- **现状**: 直接推荐模式 (SPEC-101 paper deploy → PM 决定 manual 入场)
- **Role rationale**: 仅 VIX ≥ 22 时部署, 21% trading days occupancy。Q071 P5: 1.14% ann ROE on combined NLV, Sharpe 0.34, MaxDD -9.7%, bootstrap sig 100%
- **P1 评价标准**: 触发期 per-trade $/BP-day + total annualized contribution + 与 SPX BPS 的 overlap/non-overlap
- **Retire candidate?** ❌ 刚 deploy, 不动 (per P0 §5)

### 4. Q042 Sleeve A (dd4 lenient) — **Convex overlay** / Hedge

- **设计**: ddATH ≤ -4% (first crossing) + 30 DTE ATM/+2.5% call spread (SPEC-094.1)
- **现状**: Paper trading on old Air since 2026-05-10
- **Role rationale**: drawdown 触发 → 期待 reversal 期间赚 call spread。Sleeve 19y backtest: 9.94% ann (sleeve-only), MaxDD -19.0%, WR 74%, p=0.09
- **P1 评价标准**: Stress-period PnL + tail offset vs main sleeve。**单纯 sleeve ROE 不代表全貌**, 必须看与 SPX BPS 在 drawdown 期的 PnL correlation (反相关性 = hedge value)
- **Retire candidate?** ❌ Paper 期未结 (per P0 §5)

### 5. Q042 Sleeve B (dd15 + MA10 reclaim) — **Convex overlay** / Hedge

- **设计**: ddATH ≤ -15% (outer) + MA10 reclaim within 30 TD (inner) + 90 DTE ATM/+5% call spread
- **现状**: Paper trading
- **Role rationale**: 深度 drawdown 后 reversal 触发。n=5 (5/100% WR over 19y), thin sample
- **P1 评价标准**: Deep crisis 期的 PnL (2008/2020/2022) + 与其他 sleeve 的 stress correlation
- **Retire candidate?** ❌ Paper 期未结, 但 n=5 太薄, 建议在 P1 attribution 中显式标 "evidence-thin, treat as research-only" 而非 promotable

### 6. Q019 Signal 2 sidecar (SPEC-091) — **Research / Paper candidate**

- **设计**: Stable-VIX `|ΔVIX| < 0.5`, hourly check, 180-min timeout
- **现状**: 6mo A/B 实证期 (2026-05-09 → 2026-11-09)
- **Role rationale**: Signal 1 (现有) 与 Signal 2 (新) 并行运行收集对比数据
- **P1 评价标准**: 触发率 + timeout 率 + 与 Signal 1 的差异 + 实证 recovery rate
- **Retire candidate?** ✅ **P1 中可考虑提前退役** — 取决于 A/B 累计样本是否足以判断 Signal 2 vs Signal 1 边际价值。如 P1 评估 evidence 累积速度极慢 (期权事件低频), 可建议 PM 缩短 A/B 期或提前 close

### 7. LOW_VOL reduce-wait (default) — **Idle (no fill currently)**

- **设计**: regime = LOW_VOL (VIX < 15) → reduce_wait (no entry)
- **现状**: 当前架构无 LOW_VOL income strategy. 触发 → idle
- **Role rationale**: by-design idle period
- **P1 评价标准**: 在 26y 历史中, LOW_VOL regime 总天数 + 占总天数比例 + 期间 idle BP $ × yield gap
- **Retire candidate?** N/A (它不是策略, 是 *没有策略的状态*)
- **激进 tear-down 候选 (P2C 处理)**: 是否引入 LOW_VOL income primitive (e.g. low-delta cash-secured put / call diagonal) 来填这块 idle

### 8. IVP-gate triggered reduce-wait — **Idle (no fill, transient)**

- **设计**: NORMAL + IV NEUTRAL + BULLISH 路径下 IVP ≥ 55 → reduce_wait (no entry, BPS_NNB_IVP_UPPER block)
- **现状**: 当前正在触发 (IVP=66.5 → BPS NNB BULLISH 被 block)
- **Role rationale**: by-design idle on stressed vol regime (Q063/Q067/Q068/Q069 都 validated 不放松)
- **P1 评价标准**: IVP ≥ 55 期间总天数 + 期间 idle BP $ × yield gap + 这些天数是否真"宜避免"还是过紧
- **Retire candidate?** N/A (它是 risk gate, 不是 strategy)
- **激进 tear-down 候选 (P2C 处理)**: 是否引入"IVP > 55 时切换到不同 strategy primitive"而非 idle (e.g. 更窄 spread + 半 size)

---

## Summary Role Map

| Strategy | Role | Retire candidate? | Evaluation method |
|---|---|---|---|
| SPX BPS Main | Core income | ❌ | Sub-portfolio ROE + $/BP-day |
| V3-A Aftermath | Permission/bypass | ⚠️ P1 attribution | Marginal alpha enabled, not standalone |
| HV Ladder /ES | Opportunistic HV | ❌ | Per-trigger $/BP-day, occupancy 21% |
| Q042 Sleeve A | Convex overlay | ❌ paper | Drawdown-period PnL + tail offset |
| Q042 Sleeve B | Convex overlay | ❌ paper | Crisis PnL + correlation, n=5 thin |
| Q019 Signal 2 | Research/Paper | ✅ may end early | A/B evidence accumulation rate |
| LOW_VOL reduce-wait | (idle, no strategy) | N/A | Idle days + BP × yield gap |
| IVP-gate reduce-wait | (idle, no strategy) | N/A | Block days + BP × yield gap |

---

## Open questions for PM (校准前先看)

1. **V3-A Aftermath role**: PM 是否同意按 "permission alpha" 评价? 还是 PM 心里仍当 "structural alpha" 评价?
2. **Q019 Signal 2**: PM 是否倾向于 6mo full A/B (到 2026-11-09)? 还是如果 P1 评估 evidence 累积很慢可以提前 close?
3. **LOW_VOL / IVP-gate idle**: 这两段时间 PM 心里是 "by-design 等仓位" 还是 "可以填一些低风险东西"? 这直接影响 Lever C1 (T-bill / cash yield) 还是 C2 (option premium) 的优先级
4. **Q042 Sleeve B evidence-thin**: n=5 over 19y backtest WR=100% 看似漂亮但样本极薄。PM 是否同意 treat as "research-only" 直到 live 累积至少 3-5 笔?

---

## What this DRAFT does NOT include (need full P1 compute)

- 实际 sub-portfolio ROE per strategy (要 26y replay)
- $/BP-day per strategy (要 daily BP tracking)
- Stress-period PnL per strategy (要 crisis-window extraction)
- Cross-strategy PnL correlation matrix
- Marginal "with vs without V3-A" attribution
- Idle BP 占总 trading days 的 rolling distribution
- Friction-adjusted ROE per strategy

Full P1 deliverable: `q073_p1_baseline.csv` + `q073_p1_role_map.md` (final) + `q073_p1_roe_bridge.md` + `q073_p1_idle_attribution.md` + `q073_p1_friction.md` + `q073_p1_operational_score.md`. 2-3 days Quant compute.
