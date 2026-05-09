# RESEARCH_LOG Archive — pre 2026-04

Entries archived from `RESEARCH_LOG.md` on 2026-05-09 by Planner.
These entries are from 2026-03 and earlier and are no longer in the active index.
For current entries, see `RESEARCH_LOG.md`.

---

### R-20260329-01 — BPS holding-period IVP stop losses are harmful

- Topic: BPS and BPS_HV holding-period exits based on high IVP
- Findings: both generic `IVP > threshold` exits and IVP spike exits degraded global PnL in full-history tests
- Risks / Counterarguments: individual loss cases can still look compelling, which may tempt overfitting on memorable examples
- Confidence: high
- Next Tests: focus BPS risk management research on entry filtering rather than holding-period panic exits
- Recommendation: drop
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260329-02 — Bear Call Diagonal has no useful bullish trend-flip exit

- Topic: Testing a symmetric exit rule for Bear Call Diagonal
- Findings: bullish trend signals appeared in both winners and losers, so the rule could not separate good trades from bad ones
- Risks / Counterarguments: small sample size means nuance may still exist, but current evidence does not justify a production rule
- Confidence: medium
- Next Tests: if revisited, focus on entry filters rather than holding-period trend exits
- Recommendation: drop
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-01 — BPS_HV DTE must remain well above exit threshold

- Topic: HIGH_VOL BPS_HV DTE correction
- Findings: entering at the same DTE as the roll threshold caused near-immediate exits; increasing `high_vol_dte` from 21 to 35 materially improved results
- Risks / Counterarguments: the rule is robust, but future parameter tuning should still be checked against actual effective holding days
- Confidence: high
- Next Tests: treat `DTE_entry - DTE_exit_threshold` as a required validation check for future strategy variants
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-02 — HIGH_VOL should use BPS_HV, not LEAP

- Topic: Strategy choice in HIGH_VOL environments
- Findings: replacing directional LEAP exposure with `BPS_HV` aligned the system with theta-income logic, reduced model fragility, and produced controllable risk under stressed vol
- Risks / Counterarguments: HIGH_VOL remains inherently harder to trade, so even the improved structure still needs tighter risk posture and size discipline
- Confidence: high
- Next Tests: keep the `EXTREME_VOL` hard stop and validate any future HIGH_VOL changes against stressed periods first
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-03 — IVR and IVP disagreements should defer to IVP

- Topic: Handling IV regime misclassification after extreme volatility spikes
- Findings: when `|IVR - IVP| > 15`, IVR can be distorted by old regime peaks; IVP gave more reliable current-state classification and should drive the decision with adjusted thresholds
- Risks / Counterarguments: threshold choice may still need revision if future VIX regimes differ materially from the calibration period
- Confidence: medium
- Next Tests: monitor future misclassification cases and revisit the divergence threshold only if repeated false regime calls appear
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-04 — min_hold_days and 50 percent profit target are structural, not cosmetic

- Topic: Why early profit capture still needs a minimum holding window
- Findings: the 50 percent profit target remains reasonable for premium-selling logic, but `min_hold_days = 10` is needed to prevent luck-driven 1 to 3 day exits from distorting utilization and Sharpe
- Risks / Counterarguments: fixed holding windows can occasionally delay legitimate exits, so future exceptions should only be added with strong evidence
- Confidence: medium
- Next Tests: any proposal to bypass `min_hold_days` should be validated with sequential trade behavior, not just static snapshots
- Recommendation: hold
- Related Spec: `N/A`
- See: `doc/research_notes.md`

### R-20260328-05 — SPEC-1B seven-day fast exit should stay rejected

- Topic: Evaluating a true 7-day fast exit path for DIAGONAL
- Findings: after fixing `_entry_value`, the seven-day fast-exit rule never triggered in the examined sample; the study also exposed that the previous pricing bug had artificially inflated early DIAGONAL pnl
- Risks / Counterarguments: the result depends on correct pricing logic, so future engine regressions could create misleading support for the rule again
- Confidence: high
- Next Tests: keep `_entry_value` correctness part of regression checks before reconsidering any fast-exit variant
- Recommendation: drop
- Related Spec: `SPEC-1B`
- See: `doc/research_notes.md`

### R-20260329-03 — Sequential replacement breaks naive entry-confirmation filters

- Topic: Bear Call Diagonal filter based on five consecutive bullish days
- Findings: static prototype logic suggested filtering could help, but sequential backtests showed the rule mainly delayed entry into the same regime at worse prices rather than removing bad trades
- Risks / Counterarguments: this lesson is strategy-structure dependent, but it is a strong warning against promoting static feature correlations directly into production filters
- Confidence: high
- Next Tests: for future entry filters, require sequential replacement analysis before approval
- Recommendation: drop
- Related Spec: `SPEC-005`
- See: `doc/research_notes.md`
