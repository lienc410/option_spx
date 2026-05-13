# SPEC-100 — 12-Month Monitoring Calendar

Deploy date: 2026-05-13  
Review deadline: **2027-05-13**  
Owner: Quant  

---

## Standing Obligation

`max_trades_per_spell` was raised from 2 → 3 on 2026-05-13 based on 4 incremental trades
(all winners) over 19y backtest. Sample size is small (n=4). The 12-month live review below
is required to validate or revert.

---

## 2027-05-13 Review Checklist

**Trigger**: 12 months post-deploy, regardless of whether any spell #3 trade fired.

### Data
- [ ] Pull all live V3-A IC_HV trades opened 2026-05-13 onward from `data/q042_paper_trades.jsonl`
      and/or broker fills
- [ ] Identify which were spell-position #1, #2, or #3 (using spell tracking in state machine)
- [ ] Re-run Q064 P8 script (`research/q064/q064_p8_spell_gate_study.py`) with extended
      end_date to include live period

### Pass / Revert criteria

| Metric | Pass | Revert trigger |
|---|---|---|
| Spell #3 incremental WR (live only) | ≥ 70% | < 70% with n ≥ 3 |
| Spell #3 incremental net P&L (live) | ≥ $0 | net negative with n ≥ 3 |
| Backtest incremental WR (extended 19y+) | ≥ 75% | < 70% |
| Worst single spell #3 trade | > -$5,000 | ≤ -$5,000 (single trade) |

If revert triggered:
```diff
- max_trades_per_spell: int = 3   # SPEC-100
+ max_trades_per_spell: int = 2   # SPEC-100 reverted YYYY-MM-DD per live evidence
```
Single-line change + cache refresh. No architectural impact.

---

## Intra-Year Trigger Events (act immediately, don't wait for annual review)

| Trigger | Action |
|---|---|
| Spell #3 trade with loss ≥ -$3,000 | Immediate Quant review; consider temporary revert to max=2 |
| 3+ consecutive spell #3 losses | Suspend SPEC-100, revert, file Quant review ticket |
| HV spell VIX > 25 sustained ≥ 60 days | Flag to PM before next spell #3 entry (human confirm required — future SPEC scope) |

---

## Context

- Research basis: Q064 P8 (`task/q064_p8_spell_gate_review.md`)
- 2nd Quant APPROVE α: RESEARCH_LOG R-20260513-04
- The 4 incremental trades span 4 different years (2010, 2015, 2022, 2025) — no clustering
- worst trade unchanged at -$2,016 → no tail risk increase confirmed
- P9 (spell_age_cap, hysteresis, no-high-reset) all rejected; those params are deliberate design
