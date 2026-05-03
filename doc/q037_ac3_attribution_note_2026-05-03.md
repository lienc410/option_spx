# Q037 AC3 Attribution Note

## 1. One-line conclusion

HC `SPEC-077` AC3 magnitude gap is **not** caused by a dashboard / metric bug.

The remaining HC vs MC difference is best explained as a **mixed effect** of:

1. metric / denominator semantics
2. sample-window difference
3. strategy / path composition difference

This is now explained **well enough for planning**, even if not fully numerically closed.

---

## 2. Question Being Answered

MC reports `Q037 Phase 2A` uplift around:

- `+0.91 ~ +1.03pp annualized ROE`

HC full-sample rerun for `SPEC-077` reports:

- `+0.0856pp annualized ROE`

This note asks:

- Is the HC result a bug?
- If not, what are the smallest plausible drivers of the remaining gap?

---

## 3. What Is Now Ruled Out

### 3.1 Not a HC dashboard / `SPEC-078` bug

HC `annualized_roe` metric is internally consistent:

- `SPEC-078` closed DONE
- server-side `annualized_roe` is authoritative
- JS fallback parity is verified
- HC `+0.0856pp` is the correct reading under HC’s current `final_equity_compound` interpretation

### 3.2 Not currently driven by `SPEC-080` / BCD debit-stop wiring

HC ran:

- `bcd_stop_tightening_mode = disabled`
- `bcd_stop_tightening_mode = active`

on the same full-sample `PT 0.50 -> 0.60` comparison, and the delta was unchanged.

So debit-side stop hardcode is no longer the main live candidate for the AC3 magnitude gap.

---

## 4. Metric-Layer Explanation

Using the same HC full-sample ledger:

- HC displayed / current canonical metric:
  - `final_equity_compound / $100k = +0.0856pp`
- Recomputed in MC-style simple annual ROE:
  - `simple PnL / $100k / years = +0.3504pp`

Interpretation:

- metric semantics explain a **material part** of the gap
- but they do **not** explain the full jump to MC’s `+0.9088pp`

So the gap is **not** “just accounting,” but accounting is a real component.

---

## 5. Sample-Window Explanation

HC full-sample window:

- `2007-01-01 -> today`
- about `19.32y`

MC full-sample window:

- `1999-01-01 -> 2026-05-02`
- `26.3217y`

Meaning:

- MC includes an extra `1999–2007` block
- that block contains:
  - dot-com / post-dot-com stress
  - more high-vol / stress-regime conditions
- those are exactly the kinds of environments where:
  - delaying exit from `50pct_profit(_early)` into `roll_21dte`
  - can matter more

Interpretation:

- sample window is likely the **largest remaining source** of the magnitude difference

---

## 6. Path / Strategy-Mix Explanation

MC by-strategy attribution shows the largest uplift contribution in:

- `bull_put_spread`: `+3,456`

HC path decomposition, by contrast, shows the main positive contribution concentrated in:

- `Iron Condor`
- `Iron Condor (High Vol)`

Interpretation:

- HC and MC are not realizing the same `PT sensitivity` through the same strategy mix
- this is consistent with known permanent path differences, including:
  - `SPEC-056c` vs `SPEC-054`
  - selector-tree composition drift
  - route mix differences across `BPS / BCD / IC` sleeves

This supports a **true path difference** component, not just a metric-definition issue.

---

## 7. Exit-Reason Mechanism

MC’s own explanation is:

- many trades that would previously exit via:
  - `50pct_profit`
  - `50pct_profit_early`
- are instead held to:
  - `roll_21dte`

MC numbers indicate:

- `roll_21dte` count increases by `+52`
- and that migration is the main source of the observed uplift

HC direction is similar, but magnitude is smaller.

Interpretation:

- exit-timing mechanism is aligned directionally
- but the **scale** of the benefit differs due to the combined effects above:
  - metric
  - sample
  - path mix

---

## 8. Minimal Final Interpretation

The most compact interpretation is:

> HC’s `+0.0856pp` is the correct CAGR-style / final-equity-compound reading for the HC path.  
> Re-expressing the same ledger in MC-style simple annual ROE raises the uplift to about `+0.3504pp`, but still not to MC’s `+0.9088pp`.  
> The remaining difference is therefore best explained by MC’s longer sample window plus different strategy/path composition, not by a HC metric bug.

---

## 9. What This Means Operationally

### 9.1 What we should stop doing

- stop treating AC3 as an unexplained HC failure
- stop blind rerunning large HC backtests hoping the gap disappears
- stop treating `SPEC-080` as the main current explanation

### 9.2 What remains worth preserving

- preserve a short documented note that:
  - HC number is correct in its own metric frame
  - MC number is on a different effective economics frame
  - comparison is directionally aligned, not numerically identical

---

## 10. Recommended Status

- `Q037`: keep **open**, but **de-escalate**
- classify as:
  - **post-spec attribution**
  - **explained enough for planning**
- no immediate need for a broader investigation unless MC later wants tighter numeric parity

---

## 11. References

- `task/SPEC-077.md`
- `doc/baseline_2026-05-02/ac3_summary.json`
- `sync/mc_to_hc/MC Response 2026-05-02_v2.md`
- `sync/open_questions.md`
- `PROJECT_STATUS.md`
