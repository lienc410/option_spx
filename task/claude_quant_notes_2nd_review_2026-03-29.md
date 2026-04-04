# Claude Quant Notes — 2nd Quant Strategy/Risk Suggestions

**Target files:** `strategy_status_2026-03-29.md`, `research_notes.md`  
**Source:** 2nd Quant review based on uploaded strategy state and research notes  
**Date:** 2026-03-29

## Purpose
This note is for **Claude Quant Researcher**.  
It is **not** a code patch.  
It captures the main strategy/risk conclusions and the highest-value research directions.

---

## 1. Current System — 2nd Quant Read

Current framework should be understood as:

> **timed short-vol engine with regime filters**

Not as:
- directional alpha engine
- low-risk carry engine
- robust all-weather strategy

Main return drivers appear to be:
- theta income
- implied vs realized vol spread
- skew / panic premium harvesting
- regime timing

This interpretation is consistent with the current strategy matrix and research history in the uploaded files. fileciteturn5file0L1-L70 fileciteturn5file1L1-L20

---

## 2. What Looks Correct

### A. Risk management is mostly placed at entry, not via reactive stop logic
This is the right direction for BPS / IC type structures.  
Research notes correctly show that many holding-period stop rules damage PnL because they force exits when short options are most expensive. fileciteturn5file1L21-L71 fileciteturn5file1L72-L129

### B. Strategy pruning quality is improving
Examples:
- Bear Call Diagonal removed from active matrix
- LOW IV bullish diagonal path removed from NORMAL regime
- IV LOW + BEARISH blocked for IC
These are good signs that the framework is maturing from “strategy collection” into “strategy selection.” fileciteturn5file0L6-L18 fileciteturn5file0L126-L158

### C. Margin-aware sizing is a major improvement
Moving from premium-risk sizing to BP-based sizing is directionally correct and much more realistic for PM accounts. fileciteturn5file0L82-L104 fileciteturn5file1L276-L286

---

## 3. Core 2nd Quant Concerns

### Concern 1 — The biggest unresolved risk is vol persistence, not just vol spike
Current filters already address:
- VIX rising
- backwardation
- extreme vol hard stop

That is useful, but it mostly handles entry-time danger, not how long stressed vol persists after entry.  
The deeper risk is a regime where vol stays elevated and directional pressure continues. In that case, short-vol income can be repeatedly overwhelmed.

### Concern 2 — Multi-position architecture introduces correlated exposure
After SPEC-014, portfolio risk is no longer just trade-by-trade.  
Multiple positions can now be open under the same regime logic. Even if names differ, exposure may still be one concentrated bet:
- short gamma
- short vega
- same regime timing assumption

This means BP diversification may overstate real diversification. fileciteturn5file0L87-L104 fileciteturn5file0L194-L203

### Concern 3 — Backtest quality is still materially optimistic
The status doc explicitly notes:
- sigma uses same-day VIX rather than locked entry IV
- no bid/ask spread
- no slippage
- practical performance likely around 70–80% of backtest PnL. fileciteturn5file0L107-L110 fileciteturn5file1L238-L255

This is not a small cosmetic issue. It means strategy ranking and apparent Sharpe may still be distorted.

### Concern 4 — MA50 criticism should be refined, not treated as universally valid
Important nuance:
- For credit structures, a lagging trend filter is not automatically bad
- In some cases, lag can be beneficial because it avoids chasing the first move
- SPEC-006 logic for BCS_HV is a good example of this point. fileciteturn5file1L356-L392

So the correct research question is not “is MA50 lagging?”  
It is:

> In which strategy families is lagging confirmation helpful, and in which is it harmful?

That should be treated as a strategy-class-specific question, not a universal one.

---

## 4. Highest-Value Research Directions for Claude Quant

### Priority 1 — Build a vol persistence / stressed-regime duration model
Current framework classifies regime well enough at entry, but it does not explicitly model whether high vol is likely to normalize quickly or stay elevated.

Research goal:
- estimate probability that HIGH_VOL remains HIGH for next 5–10 trading days
- use that probability as a risk throttle for short-vol structures

Candidate inputs:
- VIX level
- VIX slope
- term structure shape
- backwardation state
- recent SPX realized vol
- maybe VVIX if available later

Why this matters:
- this is likely the biggest missing state variable in the current engine
- it addresses the actual failure mode of repeated short-vol exposure in sticky stress regimes

### Priority 2 — Add a portfolio-level exposure view
Do not treat open positions as independent just because the strategy labels differ.

Research goal:
- define a simple exposure aggregation framework at strategy level
- estimate when multiple positions are effectively the same risk

Minimal conceptual version:
- classify each strategy by dominant exposure:
  - short gamma
  - short vega
  - directional downside
  - directional upside
- then evaluate aggregate concentration by regime

This is especially important after the move to multi-position architecture. fileciteturn5file0L87-L104

### Priority 3 — Re-rank strategies after applying a realism haircut
Current ranking should not rely only on raw backtest Sharpe / PnL.

Research goal:
- apply a conservative realism adjustment to each strategy family
- compare whether ranking changes after:
  - IV bias haircut
  - spread/slippage haircut
  - stress-period penalty

This matters because a strategy with slightly lower raw PnL but better implementation realism may be the better production choice.

### Priority 4 — Redefine evaluation metric away from WR / Sharpe first
For this framework, win rate is often misleading because many legs are short-vol structures with asymmetric tail behavior.

Research goal:
prioritize:
- return / max drawdown
- tail loss statistics
- regime-specific drawdown
- PnL skew / convexity signature
- ROM after realism adjustment

This is more aligned with how the system actually makes and loses money. Current docs already introduced ROM, which is a good step. fileciteturn5file0L168-L183

### Priority 5 — Strategy-family-specific trend research
Do not ask “is MA50 good?” in the abstract.

Research by family:
- BPS / BCS / IC: lagging filter may be acceptable or helpful
- debit directional structures: lagging confirmation may destroy entry quality
- diagonal structures: trend flip logic may help on one side but fail on the symmetric mirror side, as already observed in notes. fileciteturn5file1L130-L161

This should become a research principle:
> trend signal usefulness depends on payoff structure

---

## 5. Specific Warnings for Claude Quant

### Warning A
Do not reframe the system as a directional trend-following engine.  
That will lead to wrong model changes.

### Warning B
Do not assume more filters always improve results.  
Research notes already show several examples where static feature logic looked useful but failed in sequential backtests. fileciteturn5file1L329-L355

### Warning C
Do not over-read current Sharpe.  
Use it as a provisional ranking metric only.

### Warning D
The most relevant future mistakes are likely to come from:
- correlated exposure
- sticky high-vol regimes
- optimistic backtest implementation assumptions

---

## 6. Recommended Claude Quant Output Style

For the next research pass, Claude should answer in this order:

1. What is the dominant risk the current system is still not modeling?
2. Which strategy families are actually the same trade in disguise?
3. Which metrics change most after realism adjustment?
4. Which regime definitions should be expanded from static thresholds to state persistence?

This will keep follow-up work on strategy/risk truth, rather than drifting into implementation detail.

---

## 7. Final Bottom Line

The current framework has likely passed the “can this make money?” stage.  
It has not yet passed the “can this survive bad regimes without concentrated hidden exposure?” stage.

The next meaningful edge probably does not come from one more entry filter.  
It more likely comes from:
- better regime persistence modeling
- better portfolio exposure aggregation
- more realistic strategy ranking
