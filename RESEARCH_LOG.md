# RESEARCH_LOG

Last Updated: 2026-04-19
Owner: Planner or PM

---

## Entries

### R-20260419-10 — Q018 Phase 1 produced two credible directions, but not a decisive remedy

- Topic: Phase 1 prototype for the `Q018` aftermath single-slot question
- Findings: Quant completed the first real prototype round and the result is more interesting than a simple “allow two slots” answer. Variant A (multi-slot aftermath replay) identified `36` blocked clusters and, under ex-post trade replay, produced about `+$47,735` total PnL with `86.1%` win rate. The gains were stronger than the earlier rough approximation suggested because `IC_HV` often reaches `50%` profit quickly in high-VIX aftermath environments. Tail losses were real but concentrated, especially `2008-09` (`-$7,968` single-trade worst case), while `2020-03` was only mildly negative and `2025-04` was actually profitable. Variant B (tightening `AFTERMATH_OFF_PEAK_PCT` from `0.05` to `0.10`) looked attractive for a different reason: it cut max drawdown by about `36%` (`-$20,464` to `-$13,187`) and improved `IC_HV` Sharpe with almost no engineering cost, while only dropping two trades. This means the two directions are not obvious substitutes: A captures more missed alpha, B reduces risk cheaply, and the best answer may even be a combination
- Risks / Counterarguments: Variant A is still materially approximate. The big missing pieces are BP ceiling, shock-engine / overlay interactions, and the fact that only one day per blocked cluster was replayed. Any of those could reduce the apparent `+$47,735`. Variant B’s drawdown improvement may also be partly path luck because the specific removed trades have not yet been stress-tested by year or bootstrap. Phase 1 therefore upgrades Q018 from a “single anecdote” to a real research branch, but it does not yet justify a DRAFT Spec
- Confidence: medium
- Next Tests: the most valuable next step is Phase 2-A — re-run the multi-slot path with BP ceiling, shock engine, and overlay constraints so the core `+$47,735` claim gets a more realistic answer. If PM prefers a cheaper / safer path, Phase 2-C can instead scan tighter aftermath thresholds first. The “multi-slot + tighter threshold” combo is also plausible, but only after the realism gap in A is narrowed
- Recommendation: continue research
- Related Question: `Q018`
- See: `sync/open_questions.md`, `doc/research_notes.md`

### R-20260419-09 — Q019 opened: the project may have a material VIX time-basis mismatch between backtest and live recommendation

- Topic: Whether using end-of-day VIX in backtests while making live recommendation decisions from opening / early-session VIX materially changes routing and gate behavior
- Findings: PM identified a structural modeling mismatch worth separate study: historical backtests and much of the research stack rely on daily close-based VIX time series, while live recommendation decisions are taken near the open, when VIX is often materially above its later close and may even mark the intraday high. If this mismatch is large enough, it could alter regime classification (`HIGH_VOL` vs `NORMAL`), `VIX_RISING` logic, IVP-like high-vol gates, and the aftermath condition used in `SPEC-064` / `Q017`. This is not yet a strategy conclusion; it is a new measurement problem
- Risks / Counterarguments: not every intraday-open/close difference matters strategically. The relevant question is not whether VIX opens above its close in general, but whether using open-based VIX would have changed actual selector outputs, blocked trades, or realized backtest path decisions in a non-trivial number of cases. Without that quantification, the issue could be either a real blind spot or just a plausible-sounding source of noise
- Confidence: medium on the importance of the question; low on the size or direction of the effect
- Next Tests: compare close-based versus open-based (or earliest available live-time) VIX inputs on historical recommendation paths, starting with high-volatility and post-spike windows; quantify how often route, gate, or aftermath outcomes would have changed
- Recommendation: research
- Related Question: `Q019`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260419-08 — `SPEC-064` shipped; the first real double-spike review surfaces a new single-slot aftermath question (`Q018`)

- Topic: Post-ship review of the first real-world double-VIX-spike case after `SPEC-064` / `SPEC-065`
- Findings: `SPEC-064` (`HIGH_VOL Aftermath IC_HV Bypass`) shipped to production and passed review, and `SPEC-065` added a durable research-view pill for the same path. The shipped artifact matches the backtest trigger set exactly enough for audit use. PM review of the real `2026-03` double-spike sequence then surfaced a new phenomenon: the first peak opened an `IC_HV` aftermath trade, but the second peak’s aftermath dates (`2026-03-31`, `2026-04-01`, `2026-04-02`) were blocked by the engine’s `_already_open` single-slot constraint even though offline selector replay says they otherwise would have routed to `IC_HV` again. This does not prove that multi-slot opening is the right remedy, but it does establish a concrete research trigger for a new question about single-slot aftermath misses
- Risks / Counterarguments: the current evidence is still only a trigger case. The missing second-peak trade could mean “allow two aftermath slots,” but it could also mean “tighten the first aftermath trigger so the slot is preserved for the later, better peak.” The historical gap between the `73` research aftermath windows and the `32` shipped `IC_HV` aftermath entries likely contains multiple causes, not just `_already_open`, and none of that has been quantified yet. Any multi-slot idea would also be a risk-structure change, not a mere routing tweak
- Confidence: medium on the phenomenon; low on the remedy
- Next Tests: if PM wants to advance `Q018`, start with a strict Phase 1 prototype comparing (A) `IC_HV` aftermath with two concurrent slots versus (B) a tighter aftermath threshold such as `off_peak >= 10%`, then compare incremental trade count, PnL / CI, Sharpe, drawdown in `2008-10` and `2020-03`, and BP utilization
- Recommendation: research
- Related Question: `Q018`
- See: `task/SPEC-064.md`, `doc/research_notes.md`

### R-20260419-07 — Q017 Phase 2 closes the ex-ante question and makes `HIGH_VOL aftermath IC_HV bypass` a credible DRAFT candidate

- Topic: Whether Q017 has a live-usable, non-hindsight recognition rule that is strong enough to support a narrow HIGH_VOL bypass design
- Findings: Phase 2 shows that the ex-ante signal is simply the aftermath condition itself: trailing-10d VIX peak `>= 28`, current VIX at least `5%` below that peak, and still below `EXTREME_VOL`. Additional filters do not help. Across the `22` `IC_HV` aftermath trades identified in Phase 1, performance is positive in every decade bucket, with only one losing trade (`2002-08-23`). Threshold scans for `peak_drop_pct` remain broadly flat and significant, which means the feature is redundant rather than discriminative. `vix_3d_roc` also fails as a better recognizer; like the current `vix_rising_5d` logic, it ends up filtering out some of the best aftermath trades. The existing `EXTREME_VOL` threshold (`VIX >= 40`) is what keeps the core `2008-10` disaster regime out of sample, so the proposed path does not need to defeat that protection to capture the observed edge
- Risks / Counterarguments: the sample is still small (`22` trades over `25` years), and the evidence is specific to `IC_HV`; it should not be generalized to `BPS_HV` or `BCS_HV`. The proposed bypass also still needs one last system-level sanity check if PM wants extra rigor, especially around the single `2002-08-23` loser and around ensuring the protection story remains intact under full selector behavior
- Confidence: medium-high
- Next Tests: if PM wants a final pre-Spec check, do a focused fast-path-style prototype that only opens the `IC_HV` path under the aftermath condition while preserving `EXTREME_VOL`, then confirm system Sharpe / PnL / drawdown stay aligned with the Phase 1 broad-gate results. Otherwise, the next step is to draft the narrow Spec
- Recommendation: enter Spec
- Related Question: `Q017`
- See: `doc/research_notes.md`

### R-20260419-06 — Q017 Phase 1 confirms the aftermath-window leak is real in strategy PnL, with `IC_HV` carrying most of the edge

- Topic: Re-testing `Q017` with real strategy PnL and event-removal robustness instead of SPX forward-return proxies
- Findings: Phase 1 materially strengthens the case for `Q017`. Three gate-lift variants all produced significantly positive aftermath-window trades using real strategy PnL: `ivp63` gate off (`n=16`, avg about `+$1,477`, CI positive), `VIX_RISING` off (`n=10`, avg about `+$2,080`, CI positive), and both gates off (`n=24`, avg about `+$1,772`, CI positive). Removing the recent `2020-03 / 2025-04 / 2026-04` V-shaped events barely changed the result because those episodes only contributed `1/24` of the relevant trade sample. The edge is overwhelmingly carried by `IC_HV` (`22/24` trades, about `+$1,841` average, `95.5%` win rate). System-level Sharpe in the broad “both gates off” variant stayed flat at about `0.41` while total PnL rose materially, so this is no longer just a proxy-level suspicion
- Risks / Counterarguments: this is still not ready for implementation. The sample is small (`24` trades over `26` years), and the strongest evidence sits in `IC_HV`, not across all HIGH_VOL structures. Ex-ante recognition is still unresolved, and `2008`-style disaster continuation has not yet been explicitly separated from the positive aftermath trades. So the result upgrades confidence that the leak is real, but not confidence that we already know the safe live rule
- Confidence: medium-high
- Next Tests: proceed to Phase 2 rather than jumping to Spec. The two most useful next steps are ex-ante recognition work (`peak_drop_pct` / faster VIX-ROC logic) and narrower gate-specific tests that preserve the finding that `IC_HV` is the main alpha carrier
- Recommendation: continue research (upgrade confidence)
- Related Question: `Q017`
- See: `doc/research_notes.md`

### R-20260419-04 — Early post-peak VIX-reversal windows are a real HIGH_VOL phenomenon, but still too ambiguous for action

- Topic: Whether the system structurally misses opportunities in the first post-peak VIX pullback window while trend is still not `BULLISH`
- Findings: Quant identified `73` aftermath windows from `2000–2026` where VIX had peaked at `>= 28` within the prior `10` days and had already retraced by at least `5%`, producing `458` wait-days with non-`BULLISH` trend. The blockade is overwhelmingly a `HIGH_VOL` problem (`441/458`, about `96%`), dominated by two filters: `HIGH_VOL + VIX_RISING` (`208` days) and `HIGH_VOL + BEARISH + ivp63>=70` (`162` days). Forward SPX returns after these blocked days are directionally positive versus baseline wait-days, but all bootstrap confidence intervals still cross zero. The event split is highly bimodal: `2008-10` strongly supports current caution, while `2020-03`, `2025-04`, and `2026-04` look like meaningful missed rebounds
- Risks / Counterarguments: this result is still too proxy-driven for implementation decisions. SPX forward return is not strategy PnL, especially under `HIGH_VOL` where vega and path matter. The averages are also heavily influenced by a few modern V-shaped reversal episodes, while `2008` remains a strong counterexample showing the current filters can be genuinely protective. Live-identifiable peak logic is also unresolved, so the apparent “post-peak” state is not yet an ex-ante trading signal
- Confidence: medium
- Next Tests: prioritize real strategy-PnL tests inside the aftermath window (`BPS_HV` / `IC_HV` / `BCS_HV`) and test whether a live-usable peak-drop metric can separate `2008`-style continuation from `2020`-style reversal. Until then, no HIGH_VOL gate change should advance toward Spec
- Recommendation: hold
- Related Question: `Q017`
- See: `doc/research_notes.md`

### R-20260419-05 — Q017 should be advanced in strict phases, not as a parallel three-tier bundle

- Topic: Planning order for the `Q017` aftermath-window research stack
- Findings: the three proposed tiers do not have equal value. `Tier 1` is the gating phase because it answers whether the apparent opportunity survives replacement of the SPX proxy with real strategy PnL and whether the result still exists after removing the recent V-shaped reversals (`2020-03`, `2025-04`, `2026-04`). Only if that phase remains directionally positive should `Tier 2` search for ex-ante recognition features such as `peak_drop_pct` or faster VIX-ROC logic. `Tier 3` is explicitly downstream because it starts asking which concrete HIGH_VOL gate to alter, which would be premature before the alpha itself is established
- Risks / Counterarguments: this sequencing may feel slower, but it is the cleanest way to avoid optimizing a gate-level fix around a proxy-driven effect. Running all tiers in parallel would create pressure to explain or patch filters before the underlying edge is confirmed
- Confidence: high
- Next Tests: Phase 1 only for now — `T1.1` real strategy PnL, then `T1.2` event-removal robustness. Reassess after that phase before authorizing Tier 2 or Tier 3
- Recommendation: hold / phase-gate
- Related Question: `Q017`
- See: `PROJECT_STATUS.md`, `sync/open_questions.md`

### R-20260419-03 — Research view tooling shipped; exposed a generator semantic trap for future Fast Path visualizations

- Topic: Making completed research artifacts (`Q015` IVP<55 marginal trades, `Q016` Dead Zone A recovery BPS trades) persistently viewable on the backtest page
- Findings: `SPEC-062` and `SPEC-063` are now effectively complete from the research-tooling side. The resulting views reproduce the known study outputs closely enough for PM review: `Q015` shows `17` marginal trades (near the original `18`; one-trade difference comes from `_trade_identity` dedupe boundary), and `Q016` shows the expected `12` recovery-context BPS trades with total `+$2,643`. During rollout, Quant found and fixed a semantic bug in the generator: using “baseline == current production” as the only comparison reference causes any already-landed Fast Path change to collapse its own marginal diff to zero. The corrected logic explicitly compares current production against the old behavior snapshot
- Risks / Counterarguments: this is an engineering / observability lesson, not a new strategy conclusion. It should not be turned into a new open question by itself. The broader rule is simply that future Fast Path visualizations need an explicit two-snapshot baseline definition when the researched behavior is already live
- Confidence: high
- Next Tests: no immediate strategy-side follow-up is required. PM may still visually inspect the SPX-timeline distribution for `Q016`, and browser-level AC checks for `SPEC-063` remain useful, but neither should block current project-state conclusions
- Recommendation: tooling complete
- Related Spec: `SPEC-062`, `SPEC-063`
- Related Question: `Q015`, `Q016`
- See: `doc/dead_zone_a_trade_visualization.html`, `doc/research_notes.md`

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
