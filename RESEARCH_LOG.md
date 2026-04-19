# RESEARCH_LOG

Last Updated: 2026-04-19
Owner: Planner or PM

---

## Entries

### R-20260419-01 — `IVP < 55` passed the key OOS check and is now a credible narrow BPS improvement candidate

- Topic: Out-of-sample validation of relaxing the BPS `NORMAL + BULLISH` upper IVP gate from `IVP < 50` to `IVP < 55`
- Findings: the OOS check came back directionally clean across all three slices. Full history improves from system Sharpe `0.40` to `0.41` with about `+$18,107` more PnL; the in-sample split (`2000–2018`) keeps system Sharpe flat (`0.37` to `0.37`) with about `+$8,087`; the OOS split (`2019–2026`) also keeps system Sharpe flat (`0.48` to `0.48`) with about `+$10,020`. BPS sub-strategy Sharpe improves in every slice (`+0.03` IS, `+0.05` OOS). The marginal `IVP [50,55)` trades remain small (`n=18`) and individually non-significant, but the direction is consistent and no slice shows degradation
- Risks / Counterarguments: this is still a modest edge, not a strong alpha discovery. System Sharpe only improves by `+0.00` to `+0.01`, and the marginal-trade bootstrap CI still crosses zero. A single tail loss (`2025-02-20`, about `-$6,253`) reminds us that the new pocket is not risk-free. So the case is best understood as “safe micro-improvement with moderate confidence,” not “high-conviction new filter”
- Confidence: medium-high
- Next Tests: PM can now decide whether this is enough to promote into a narrow Spec or Fast Path. Optional extra hardening could include cross-validation or focused analysis of the `2025-02-20` tail event, but these are no longer required to justify the move from pure research into implementation candidacy
- Recommendation: near-spec / fast-path candidate
- Related Question: `Q015`
- See: `doc/research_notes.md`

### R-20260419-02 — Q015 narrow BPS gate relaxation was implemented via Fast Path

- Topic: Production follow-through on the `IVP < 55` BPS candidate after OOS validation
- Findings: Quant applied the narrow change directly in `strategy/selector.py`, raising `BPS_NNB_IVP_UPPER` from `50` to `55` and adding an inline note referencing the Q015 OOS evidence. This means the specific “BPS `IVP < 55`” path is no longer an open planning candidate; it is now active production logic via Fast Path
- Risks / Counterarguments: this does not resolve the broader IVP / IC redesign question. The implemented change is deliberately narrow and should not be misread as proof that wider IVP relaxation, IC gate changes, or VIX-joint filters are now approved. Tail-risk reminders from the OOS work still stand, especially the `2025-02-20` style loss case
- Confidence: high
- Next Tests: let normal live / retrospective monitoring accumulate under the new `55` threshold; if future research reopens IVP redesign, treat it as a new question rather than extending the meaning of this Fast Path
- Recommendation: implemented via Fast Path
- Related Question: `Q015`
- See: `strategy/selector.py`, `doc/research_notes.md`

### R-20260418-02 — Dead Zone B does not justify a recovery override; `IVP < 55` is the only near-spec candidate and still needs OOS proof

- Topic: Whether IVP-gate behavior inside VIX recovery windows supports a safe `IVP + VIX` redesign for BPS / IC routing
- Findings: recovery-window analysis shows IVP gates blocked `62` recovery-context days (`38` BPS + `24` IC), and BPS blocks were concentrated in `VIX 18–22` rather than only low-vol conditions. But gate-lifted recovery BPS still failed to show special alpha (`n=14`, avg about `-$12`, Sharpe `0.00`, CI crossing zero), so recovery context itself is not a useful override. The strongest concrete result is narrower: relaxing the BPS gate from `IVP < 50` to `IVP < 55` is the only apparent Pareto improvement, lifting system PnL from about `$359,799` to `$377,906` while keeping system Sharpe flat-to-slightly-up (`0.40` to `0.41`). Beyond `55`, the same old cliff reappears and Sharpe drops
- Risks / Counterarguments: the `IVP [50,55)` “good pocket” is still only `n=8`, so the observed Sharpe improvement may be noise rather than a durable edge. VIX-only or compound `IVP OR VIX` filters remain post-hoc and are not ready for production use. IC-side `IVP [20,50]` gate behavior was observed but not fully isolated yet, and slot sharing means the true opportunity value remains smaller than raw blocked-day counts suggest
- Confidence: high for “recovery is not a special alpha source”; medium for “`IVP < 55` is truly better rather than sample luck”
- Next Tests: OOS validation has now passed; remaining next step is PM decision on whether to promote this into a narrow Spec / Fast Path. IC gate evaluation can continue later under the same methodology, but VIX-joint-filter exploration should stay paused
- Recommendation: superseded by `R-20260419-01`
- Related Question: `Q015`
- See: `doc/research_notes.md`, `doc/strategy_status_2026-04-16.md`

### R-20260418-01 — VIX recovery-window dead zone is systemic, but still lacks “fix without Sharpe decay” evidence

- Topic: Post-spike premium-selling windows being blocked after HIGH_VOL→NORMAL transitions
- Findings: across `66` historical HIGH_VOL→NORMAL transition windows with elevated IVP, `34` lasted at least `>=3` days; `64%` (`214/336`) of candidate trading days were blocked, and `14` windows had zero entry opportunity throughout. The blockade is not a single-gate issue: Dead Zone A is a route hole (`NORMAL + HIGH + BULLISH`, from `SPEC-060 Change 3`) and accounts for `37%` (`80` days), while Dead Zone B comes from IVP gates (`BPS >= 50` plus IC `[20,50]`) and accounts for `41%` (`87` days). `VIX_RISING` safety filtering explains the remaining `22%` and still looks like reasonable protection
- Risks / Counterarguments: the original follow-up hypothesis was that Dead Zone A might hide conditional alpha inside recovery windows. That hypothesis has now failed: recovery-window `NORMAL + HIGH + BULLISH` BPS produced only `n=12`, avg `+$220`, bootstrap CI crossing zero, and did not outperform non-recovery samples. This means the “systemic dead zone” observation is still real, but Dead Zone A is not the fix path
- Confidence: high for “dead zone exists”; high for “drop Dead Zone A as an independent fix candidate”
- Next Tests: no further validation is needed for Dead Zone A. Research focus should return to Dead Zone B only: how IVP gates behave inside recovery windows, and whether any joint `IVP + VIX` redesign can recover opportunities without Sharpe decay
- Recommendation: hold
- Related Question: `Q015`
- See: `doc/research_notes.md`, `doc/strategy_status_2026-04-16.md`

### R-20260415-01 — DIAGONAL Gate 1 (`ivp252` 30–50 marginal zone) is net harmful and should be removed

- Topic: Net value of `SPEC-049` DIAGONAL Gate 1
- Findings: sensitivity analysis first showed the Gate 1 upper bound is highly robust across `40/45/50/55/60/65`, with Sharpe staying around `0.41–0.43` and all bootstrap results significant. Follow-up net-value analysis then showed the gate itself is harmful: removing Gate 1 increases DIAGONAL trades from `115` to `119`, raises DIAGONAL total PnL by about `$11,146`, and improves total system PnL by the same amount. The gate blocked `47` trades whose total PnL was `+$46,403`, with bootstrap CI significantly positive, so it is filtering out good trades rather than protecting the system
- Risks / Counterarguments: this should be treated as a rule-removal conclusion, not threshold optimization. The lesson is not “find a better number,” but “the gate has no net value under full-history validation.” As with the former both-high gate, the original rule appears to have been built on a negatively selected subset rather than a true system-wide edge
- Confidence: high
- Next Tests: keep the detailed-layer strategy snapshot aligned so Gate 1 no longer appears as current active logic; use this case as one of the confirmed negative-selection-bias examples when evaluating future integer threshold gates
- Recommendation: implemented via Fast Path
- Related Spec: `SPEC-049`
- Related Question: `Q014`, `Q015`
- See: `task/SPEC-049.md`, `doc/strategy_status_2026-04-10.md`, `strategy/selector.py`

### R-20260416-01 — BPS IVP≥50 gate is NOT the same problem as Gate 1; gate should be retained but IVP alone is a flawed filter

- Topic: Full evaluation of `NORMAL + BULLISH` `IVP >= 50` entry gate using same methodology as Gate 1
- Findings: (1) Sensitivity is NOT flat — real cliff at IVP 55→60 where Sharpe drops from 0.53 to 0.23. (2) Blocked trades are NOT significantly profitable (avg +$7, CI [-$601, +$1,062]). (3) Gate deletion would halve BPS Sharpe (0.49→0.22) and worsen MaxDD by 70%. (4) System cost of $6,690 traces to slot-occupancy displacement (6/6 explained), not quality filtering. (5) IVP and VIX are weakly negatively correlated (r=-0.154) in NNB regime; 68% of IVP≥50 blocks happen at VIX<18. The gate's “stressed vol” rationale is conceptually wrong, but it accidentally protects a real Sharpe cliff
- Risks / Counterarguments: cross-tab analysis shows VIX [18,20) × IVP [55,65) is the actual danger zone, while VIX [16,18) is safe regardless of IVP — but any compound filter (e.g. `VIX<18 OR IVP<50`) would be post-hoc optimization. IVP<55 also looks attractive (Sharpe 0.64) but sits at the sample-internal optimum, high overfit risk
- Confidence: high (for “retain gate” conclusion); medium (for IVP+VIX joint filter as research direction)
- Next Tests: accumulate live BPS trades to validate VIX×IVP cross-tab OOS; research IVP+VIX compound filter and VIX-trend conditioning; consider BPS dual-slot architecture to eliminate displacement artifact
- Recommendation: retain gate=50, research redesign via `Q015`
- Related Question: `Q015`
- See: `research_notes.md` §55, `strategy_status_2026-04-16.md`, `backtest/prototype/bps_ivp_gate_sensitivity.py`, `backtest/prototype/bps_gate_vix_vs_ivp.py`

### R-20260412-03 — `SPEC-061` 只建立了 SoMuchRanch 三层体系中的最小 Layer 2 生产 cell，主要剩余缺口是运行时风控而不是入场逻辑

- Topic: `/ES short put` 三层体系与当前测试 / 生产覆盖状态盘点
- Findings: `SPEC-061` 已把 Layer 2 的最小生产 cell 落地到单槽、`1` 张、`45 DTE`、`20 delta`、`trend filter`、`BP <= NLV 20%` 的入场路径；但 SoMuchRanch 原始三层体系中的 Layer 1（核心 SPY/VTI 持仓）与 Layer 3（BSH）在当前生产系统中仍不存在，Strategy #3（long `/ES` calls）也尚未进入研究实现。对当前最小 cell 而言，最大剩余缺口不是入场逻辑，而是运行时风控：`-300%` stop 在生产中仍是文档化规则，未实现自动触发；趋势转负后的持仓行为也未定义
- Risks / Counterarguments: 当前 `/ES` 路径是在“无 Layer 1 缓冲、无 Layer 3 对冲”的条件下独立运行；再加上止损当前缺少系统化监控，这意味着 `SPEC-061` 虽可视为 MVP 成立，但生产安全边界仍偏薄。PM 已明确：不能接受纯人工盯仓止损，最低要求是系统监控 stop 条件并触发 bot 提醒。另一方面，Layer 1 / Layer 3 缺失是有意缩 scope，而非实现遗漏，不应把所有未覆盖项都立即提升为实现需求
- Confidence: high
- Next Tests: 优先考虑一个狭窄 follow-up Spec 来补运行时止损监控、bot alert 与 post-entry 管理定义；其余 Layer 1 / Layer 3 / Strategy #3 保持 research track；低优先级测试补全包括 `/api/es/recommendation`、`live_delta=None` 分支与 SPAN 动态扩张 stress test
- Recommendation: hold
- Related Spec: `SPEC-061`
- Related Question: `Q012`, `Q013`
- See: `task/SPEC-061.md`

### R-20260412-01 — `/ES` is now the preferred ES short put production path, but shared buying power becomes the main constraint

- Topic: ES short put production-path feasibility at ~$500k account size
- Findings: live account confirmation shows `/ES` short put buying power effect is about `$20,529` per contract, making 1-contract single-slot deployment feasible at current account size; round-trip friction appears acceptable relative to collected premium; compared with XSP, `/ES` now looks structurally superior on execution quality and lot sizing
- Risks / Counterarguments: `/ES` margin is not isolated from SPX options buying power in the current account view, so ES puts and SPX Credit compete for the same BP pool; SPAN margin can also expand sharply during volatility spikes, creating simultaneous mark-to-market loss plus BP compression
- Confidence: high
- Next Tests: define a shared-BP budgeting rule for `/ES` plus SPX Credit; confirm whether standard quarterly `/ES` options differ materially from the observed EOM weekly series in margin/liquidity; if PM agrees, narrow to a minimal DRAFT Spec
- Recommendation: enter Spec
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `sync/open_questions.md`

### R-20260412-02 — current HC planning blocker is documentation drift, not Schwab access

- Topic: HC-side planning status after Schwab connectivity confirmation
- Findings: HC has already connected successfully to Schwab Developer Portal, so `Q009` should no longer be treated as the top HC blocker; the more immediate planning risk is stale or mixed indexing across `PROJECT_STATUS.md`, `RESEARCH_LOG.md`, and `sync/open_questions.md`
- Risks / Counterarguments: MC may still remain blocked on its own environment path, so this is a cross-environment status clarification rather than a full project-wide resolution
- Confidence: high
- Next Tests: keep HC and MC environment status explicitly separated in the index layer; avoid carrying MC blockers into HC priority summaries unless they block shared work
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q009`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260411-01 — ES short put trend filter looks promising, but remains research-only

- Topic: ES short put system research using SPX proxy data
- Findings: across the phased study, the trend filter consistently improved average trade outcomes and reduced drawdowns; significance became visible only after moving from a single 45 DTE slot to a multi-DTE ladder
- Risks / Counterarguments: the core results still rely on SPX proxy assumptions rather than /ES option history, and the full system mixes naked puts, leverage management, and hedges
- Confidence: medium
- Next Tests: narrow scope to one minimal production-relevant cell before any Spec work
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `research/strategies/ES_puts/spec.md`

### R-20260411-02 — Dynamic leverage for ES puts only works with a trend filter

- Topic: Interaction between VIX-based leverage sizing and trend gating
- Findings: leverage-table baseline behavior produced collapse-like drawdowns, while the filtered version materially improved bootstrap significance and contained damage; the leverage model should not be evaluated independently from the trend gate
- Risks / Counterarguments: BSH payoff assumptions materially affect tail outcomes, so Phase 3 without full hedge payoff modeling is still incomplete
- Confidence: medium
- Next Tests: treat leverage as a second-stage feature only after the single-cell trend-filter result is accepted
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `research/strategies/ES_puts/spec.md`

### R-20260411-03 — ES puts may diversify SPX Credit more than they outperform it standalone

- Topic: Portfolio-level value of the ES short put system
- Findings: the strongest late-stage result may be diversification rather than standalone return, with modeled daily return correlation versus SPX Credit near zero and BSH improving survivability once payoff is included
- Risks / Counterarguments: this conclusion depends on proxy data, hedge modeling assumptions, and a still-unresolved production scope
- Confidence: medium
- Next Tests: confirm whether diversification survives a narrower, more realistic implementation model
- Recommendation: hold
- Related Spec: `N/A`
- Related Question: `Q012`
- See: `research/strategies/ES_puts/spec.md`

### R-20260410-01 — DIAGONAL favors structured entry alpha, not generic size-up

- Topic: Recent event-study and IVP regime work around DIAGONAL entry conditions
- Findings: DIAGONAL is the only strategy with clear entry-signal alpha in recent event-study work. This research batch supported tighter DIAGONAL-specific controls and size logic, especially keeping `regime_decay` size-up limited to DIAGONAL rather than broad premium-selling strategies.
- Risks / Counterarguments: sample sizes remain small in some sub-regimes, especially regime_decay and local_spike live tracking
- Confidence: medium
- Next Tests: keep monitoring `Q011` and observed local_spike live outcomes before promoting further sizing changes
- Recommendation: hold
- Related Spec: `SPEC-048` to `SPEC-055`
- Related Question: `Q011`
- See: `doc/strategy_status_2026-04-10.md`

### R-20260410-02 — both-high tested as a DIAGONAL risk regime, but the gate was later removed

- Topic: IVP dual-horizon classification for DIAGONAL entry filtering
- Findings: both-high (`ivp63 >= 50` and `ivp252 >= 50`) tested as negative alpha in the original audit and initially motivated `SPEC-054`. However, this should now be read as a historical research result rather than current live logic, because the DIAGONAL both-high gate was later removed by `SPEC-056c`.
- Risks / Counterarguments: evidence remains directionally useful as a caution flag, but sample size was limited and proved insufficient to keep the gate in the final routing state
- Confidence: medium
- Next Tests: re-evaluate only if future live or out-of-sample evidence rebuilds the case for reinstating a both-high restriction
- Recommendation: hold
- Related Spec: `SPEC-054`, `SPEC-056c`
- Related Question: `Q011`
- See: `doc/strategy_status_2026-04-10.md`

### R-20260410-03 — local_spike began as tag-only, but later moved into DIAGONAL full size-up

- Topic: Whether local_spike should change sizing or only be tracked diagnostically
- Findings: the initial decision was to keep `local_spike` as a diagnostic tag only (`SPEC-055`). This should now be read as an intermediate step, not the final state: later strategy updates moved `local_spike` into DIAGONAL full size-up via `SPEC-055b`.
- Risks / Counterarguments: the original live-sample caution still matters, so this remains a regime worth monitoring even though the production sizing rule has already advanced
- Confidence: low
- Next Tests: monitor live outcomes under the implemented `SPEC-055b` behavior and revisit only if realized results diverge from the research expectation
- Recommendation: hold
- Related Spec: `SPEC-055`, `SPEC-055b`
- Related Question: `N/A`
- See: `doc/strategy_status_2026-04-10.md`

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
