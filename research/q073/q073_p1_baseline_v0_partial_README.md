# Q073 P1 Baseline v0 Partial — README

> **Status: DRAFT / pre-compute snapshot.**
> **This is NOT a completed P1 deliverable.**
> Built from existing memos / cache / SPEC documents only.
> No new compute has been run.

**Date**: 2026-05-17
**File**: `q073_p1_baseline_v0_partial.csv`
**Parent**: `q073_p0_anchored_memo_2026-05-17.md`

---

## What this DRAFT shows

每个 strategy 的"已知数字" — 从 Q071/Q072/SPEC-094.1/Q064 等 prior research 抽出来。

## What's MISSING (needs full P1 compute, 2-3 days)

### 1. SPX BPS Main — 缺 26y data 严重
- 当前唯一可读数据是 `data/backtest_results_cache.json` (2025-05-13 to 2026-05-13, **1y window only**)
- 该 1y window 数字 (ann ROE 53.79%, Sharpe 5.08, Calmar 22) **完全不代表**, exceptional 单年
- **Full P1 必须重跑 SPX BPS 26y backtest** 拿 long-term mean ROE / Sharpe / MaxDD

### 2. V3-A Aftermath — standalone metrics 不适用 (per role-based 评价)
- 不应单独算 standalone ROE
- 必须以 **marginal alpha enabled** 评价: 把架构同时 with-V3A 和 without-V3A 都跑，差值 = V3-A 贡献
- 这是 P1 中复杂的 attribution 工作

### 3. Combined Portfolio (top-level)
- 不存在
- 这是 P1 最关键 deliverable: 所有 strategy daily PnL 合并 → 组合层面 ROE / MaxDD / Sharpe / crisis windows / correlation
- 必须重跑

### 4. Idle BP rolling distribution
- 当前 `/api/portfolio/summary` 显示 idle 62%, 但 snapshot 不是 distribution
- Full P1 输出: rolling 30/90/365d mean idle BP %, 5/95-tile, by-regime breakdown

### 5. Friction-adjusted ROE
- 当前所有数字是 mid-quote backtest
- SPX BPS 有部分 live data (broker P&L log), 可以算实际 friction 折损率
- HV Ladder live=0 → 必须显式 N/A
- Q042 paper 期, friction estimate 仅基于 paper mode

### 6. Cross-strategy PnL correlation matrix
- 需要每策略 daily PnL 时间序列, full architecture 26y replay 之后才能算

### 7. LOW_VOL / IVP-gate idle days quantification
- 需要 26y VIX / IVP series 数据 + count days in each idle state
- 可以从 [signals/vix_regime.py](signals/vix_regime.py) + [signals/iv_rank.py](signals/iv_rank.py) data fetch 后算

### 8. Bootstrap sig per strategy on combined architecture
- 不能简单拿单策略 bootstrap 数字
- 需要在 combined architecture 内重算 each strategy 的 marginal contribution sig

---

## Open questions for PM (校准 baseline 口径)

1. **SPX BPS 主策略 26y 历史 ROE**: PM 知不知道 historical ann ROE 大致区间 (从 RESEARCH_LOG 或老 memo)? 帮助 sanity check 1y 53.79% 是 outlier 还是新常态
2. **BOXX 4.3% baseline**: PM 是否确认 trailing 12m BOXX 实际收益就这么多, 还是有偏差?
3. **Q042 Sleeve A 9.94%**: 这是 sleeve-only 数字 (Sleeve A capital base), 不是 combined NLV 投资回报率。Combined NLV-based 数字会更小 (按 10% sleeve sizing 缩放后 ~ 1% NLV contribution). PM 需要看哪个口径?
4. **Q019 Signal 2 paper-only**: A/B 期是否要在 P1 内提前出 interim evidence summary, 还是等 6mo 完整周期?

---

## Next steps (after PM reviews this draft pack)

PM 看完 3 个 DRAFT artifact (role map / operational score / baseline v0 partial) 后, 若 role classification + missing-data list 都 OK, 启动 full P1 compute:

| Phase | 内容 | ETA |
|---|---|---|
| P1.1 | SPX BPS main 26y full backtest replay | 1 day |
| P1.2 | Q042 / V3-A / HV Ladder daily PnL 提取 + combined architecture replay | 1 day |
| P1.3 | Cross-strategy correlation + crisis window extraction + ROE bridge | 0.5 day |
| P1.4 | Idle BP distribution + IVP/LOW_VOL idle days quantification + friction adjustment | 0.5 day |
| **Total** | | **2-3 days** |
