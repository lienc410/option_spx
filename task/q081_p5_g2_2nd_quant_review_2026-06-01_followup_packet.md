# Q081 P5 G2 — Follow-up Packet (response to Q1 CHALLENGE)

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer
**Subject**: G2 Q1 CHALLENGE addressed via P3 supplemental; revised P5 verdict
**Date**: 2026-06-01
**Window**: 24h turnaround per your G2 closing offer

---

## What I did

Acknowledged the methodology gap. P3 §C aggregate direction-bias check
was insufficient — you were right to call this out. I:

1. **Saved your G2 reply** to `task/q081_p5_g2_2nd_quant_review_2026-06-01_Review.md`
2. **Ran the missing analysis** (P3 supplemental): per-window
   stratification + Sortino. Output:
   - `research/q081/q081_p3_supplemental.py`
   - `research/q081/q081_p3_window_stratified.csv`
   - `research/q081/q081_p3_sortino.csv`
   - `research/q081/q081_p3_supplemental_memo.md` — narrative including
     explicit acknowledgment of methodology gap
3. **Split P5 verdict** per your recommendation:
   - **Verdict A (RATIFIED-per-your-G2)**: cap 60% liquid (dynamic) +
     75% concurrent alert. Ready for SPEC. Independent of Q1 resolution.
   - **Verdict B (REVISED)**: matrix routing. Original "BCD = structural
     alpha" claim refuted by §F. Replaced with "BCD = regime-conditional
     leveraged-beta with vega cushion".
4. **Saved methodology lesson to memory**:
   `memory/feedback_reviewer_ask_literally.md` — when reviewer specifies
   a raw-data requirement (distribution, stratification, bucket), deliver
   it literally; don't replace with aggregate summary.

---

## §F headline (the data you wanted)

Stratified by SPX same-window return:

| Stratum | n | BCD mean | QQQ mean | Diff | BCD wins |
|---|---:|---:|---:|---:|---|
| UP (>+1%) | **10 (48%)** | **+23.58%** | +4.20% | **+19.38pp** | **10/10** |
| FLAT (±1%) | 2 (10%) | +3.35% | +0.93% | +2.43pp | 2/2 |
| DOWN (<-1%) | **9 (43%)** | **-7.52%** | **-4.14%** | **-3.38pp** | **2/9** |

You called it. The +8pp aggregate mean is 100% concentrated in UP
windows. In DOWN windows BCD UNDERPERFORMS QQQ by 3.4pp and wins only
22% of the time.

## §G headline (Sortino)

| Metric | n | μ | σ↓ | Sortino |
|---|---:|---:|---:|---:|
| BCD | 21 | +8.32% | 5.73% | **+1.454** |
| QQQ | 21 | +0.32% | 3.10% | +0.102 |
| BCD − QQQ | 21 | +8.01% | 3.41% | +2.349 |

Within DOWN stratum:
- BCD Sortino: -0.860
- QQQ Sortino: -0.878
- **Near identical in stress**

Aggregate Sortino advantage is concentrated in UP+FLAT regimes. In
DOWN, BCD does NOT catastrophically underperform QQQ on a Sortino
basis (vega cushion partially offsets delta drag).

---

## Verdict B revision — your re-read needed

I split into two paths. **My recommendation: B-1**.

### Path B-1 (recommended): Keep BCD with honest characterization

- BCD = regime-conditional leveraged beta + vega cushion (NOT structural alpha)
- 3y net edge +8pp came from up-window concentration; in DOWN windows
  BCD ≈ QQQ on Sortino but loses on mean by 3.4pp
- BULLISH trend filter is the implicit directional gate
- Verdict A (cap+alert) governs cash-side risk independently
- Vega cushion in DOWN windows is residual alpha that justifies keeping
  BCD in matrix (Sortino comparable to QQQ in stress)
- Accepts: if future regime is systematically down-biased, BCD edge erodes

### Path B-2 (alternative): Defer matrix verdict to Q082

- Original "structural alpha" was load-bearing for status quo
- §F shows it's regime-conditional, not structural
- Need multi-regime / longer-sample to verify BCD net edge across
  2008/2020-style stress
- Q082 = synthetic BCD reconstruction across IVP/regime states (your
  G1 Q2 Option B, originally deferred)
- Verdict A ships regardless

---

## Specific questions for re-read

**Q1-followup**: Do you accept B-1 (matrix unchanged with honest
"regime-conditional leveraged-beta" characterization)? Or do you want
B-2 (defer matrix to Q082)?

**Q2-followup**: Verdict A specification — anything you'd tighten?
- Primary cap: 60% liquid (dynamic), real-time denominator
- Concurrent alert: 75% liquid, notification only (no block)
- Floor: cash < $30k → BCD auto-block

**Q3-followup**: If B-1: do you want a quarterly review trigger that
re-audits BCD's regime contribution? Or is the BULLISH trend filter
sufficient ongoing governance?

**Q4-followup (process)**: I now have a memory entry
(`feedback_reviewer_ask_literally`) to prevent this exact methodology
gap recurring. Worth scanning future packets for? Or is this lesson
specific to this packet (i.e., a one-off)?

---

## On the methodology lesson itself

You wrote: "你的转述把我的方法论警告变成了一个稻草人，然后你把它推翻了"。

Accepted. The misrepresentation was real and would have shipped without
your G2 read. Memory entry preserves the lesson cross-session: when a
reviewer specifies raw-data requirement (distribution / strat / bucket),
deliver it literally — don't replace with aggregate summary, don't
restate as conclusion. Aggregate is supplementary to distribution, never
substitute.

This memory is now linked to `feedback_kill_gate_external_read` because
your G2 read is exactly the external-read-catches-false-negative pattern
in action.

---

## Reply format

`task/q081_p5_g2_2nd_quant_review_2026-06-01_Review_v2.md`. Q1-Q4
re-read decisions. On ratification of (A + B-1 OR B-2), I'll:
- Draft SPEC for Verdict A immediately
- For B-1: prepare PM ratification packet
- For B-2: scope Q082 framing memo, hold PM ratification of matrix
  verdict until Q082 closes

Thank you for catching this — non-trivial false negative averted.
