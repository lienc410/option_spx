# Q071 ES Sell Put Integration Study — 2nd Quant Review (2026-05-14)

**Reviewer**: 2nd Quant
**Date**: 2026-05-14
**Source memo**: `research/q071/q071_memo_2026-05-14.md`
**Verdict**: **PASS WITH SPEC-FRAMING REVISIONS**

---

## Top-line verdict

> Q071 now satisfies the requirement of a high-level integrated ES Sell Put strategy study. It correctly uses V2f as the structural chassis and Q041 as the source of volatility-regime entry-quality hypotheses, rather than mechanically porting Q041's IVP gate. The literal Q041 IVP 43–55 window is rejected in /ES V2f context. The successful integrated design is a new **High-Vol ES Sell Put Ladder**: V2f structure gated by VIX ≥ 22, with STOP=15 retained as fail-safe. **Promote to DRAFT SPEC / paper-trading candidate**, with cautious sizing and explicit live margin monitoring.

---

## 1. Does it meet the "high-level integrated strategy study" requirement?

**Yes.** Three things done right:

1. **P0 defined decision criteria up front** — ROE improvement OR ROE-flat-with-tail-improvement, with V1/bootstrap/SPAN vetoes. Strategy-level research, not parameter tuning.
2. **P1 ran V2f entry attribution BEFORE assuming Q041 transfer** — answered "where does V2f make money" rather than "does Q041's window fit". Discovered IVP 43-55 is a net loser, VIX absolute bucket is the real signal.
3. **P3/P4/P5 tested cadence modes, STOP interaction, portfolio viability, crisis windows, BP/SPAN, bootstrap** — full strategy-design validation, not just gate PnL.

---

## 2. Core findings credibility

### 2.1 Q041 literal IVP gate rejected — CREDIBLE

`IVP 43-55` in V2f context:
- ann_roe 1.04% → 0.07% (-0.98pp)
- entry frequency: 26%
- Sharpe: 0.04

Clean rejection, avoids "Q041 used it so /ES should too" mechanical integration.

### 2.2 VIX ≥ 22 as core gate — DIRECTIONALLY SOUND

P1 attribution shows clear non-linearity:
```
VIX 15-20: avg_pnl -18.9%, total -$36k
VIX 25-30: avg_pnl +53.7%
VIX >30:   avg_pnl +72.0%
```

V2f + G6:
```
V2f_base:    ann_roe 1.04%, maxDD -33.3%, bootstrap sig 0%
V2f + G6:    ann_roe 1.14%, maxDD -9.7%,  bootstrap sig 100%
```

Not a small optimization — converts a statistically fragile high-tail rolling ladder into a low-frequency high-vol regime sell put.

---

## 3. Q041 + V2f integration framing

**Conceptual integration, not parameter integration.**

| Source | Retained | Rejected |
|---|---|---|
| /ES V2f | DTE49→21 exit, rolling ladder, STOP=15, max slots, trend/warmup, /ES execution chassis | unconditional year-round rolling exposure |
| Q041 T1 | sell put needs volatility/regime entry-quality gate; tail control must exist | literal IVP 43-55 window; SPX CSP path |

The integration is NOT:
```
V2f + Q041 IVP 43-55
```

It IS:
```
V2f chassis + Q041-style volatility-regime discipline
= High-Vol ES Sell Put Ladder
```

**SPEC naming requirement**: do NOT call it "V2f with G6 filter". Call it **`ES High-Vol Sell Put Ladder`** or **`ES HV Put Ladder`**. PM/Planner/Developer must understand this is a redefined strategy, not a V2f parameter tweak.

---

## 4. Key risk: G6 reshapes V2f, doesn't enhance it

After G6:
```
trades:           725 → 146
avg active slots: 2.57 → 0.48
slot occupancy:   86% → 21%
```

Strategy fundamentally shifts from "continuous rolling theta ladder" → "episodic high-volatility deployment".

Tail improvement is dramatic:
```
maxDD:     -33.3% → -9.7%
worst 3m:  -27.6% → -8.4%
2022:      -33.1% → -8.7%
COVID:     -23.4% → +3.1%
```

But the cost: capital is idle most of the time. Strategy must be positioned as **high-vol sell-put sleeve / opportunistic premium engine**, not a "stable ROE engine".

---

## 5. Promote decision

### SUPPORT Promote-to-SPEC-draft

Per P0 criteria, G6 satisfies Criterion B:
- Ann ROE roughly flat (+0.09pp)
- MaxDD / worst cluster improve massively (+23.6pp / +19.2pp)
- Bootstrap sig_rate 100%
- V1 pass
- Peak SPAN within ceiling

### BUT: Promote level = **DRAFT SPEC / paper-trading candidate**, NOT immediate production

Reasons:
1. G6 sample only 146 trades / 26 years (~5.6 trades/year)
2. `VIX ≥ 22` is clean but coarse absolute threshold
3. High-vol entries' live execution slippage / fill quality / margin behavior unobserved
4. /ES futures option SPAN / daily settlement operational risk untested
5. Regime-episodic strategy: live 12 months may yield very few samples

Initial deployment must be **shadow / paper / small-cell**, not full production size.

---

## 6. Required corrections to memo

### 6.1 "G6 makes STOP redundant" — INCORRECT framing

P4 shows no stop hits in G6 historical sample. **Correct language**:

> In historical G6 sample, STOP=15 did not fire. Retain as fail-safe because live high-vol paths can differ from historical sample.

NOT "operationally redundant" — instead **"unused historical safeguard"**.

### 6.2 Bootstrap sig_rate 100% claim — SOFTEN

n=146 is thin. sig_rate 100% supports paper-trading promotion, not production certainty. Memo should say:

> Bootstrap significance supports promotion to paper trading, but live sample accumulation is required due to low annual trade frequency.

Don't write it as production certainty.

### 6.3 BP / SPAN dual-quote — CLARIFY

P5 shows:
```
peak BP %NLV (Schwab PM):    39.0%
peak SPAN %NLV (est /ES):    15%
```

P0 veto written as "Peak SPAN > 30% NLV" but PM BP at 39% — must explain. SPEC needs:

```
Primary cap:        estimated /ES SPAN ≤ 30% NLV
Secondary monitor:  broker-reported BP / stress BP
```

Live dashboard must record actual broker margin.

---

## 7. Recommended SPEC content

### Strategy name
```
ES High-Vol Sell Put Ladder
```

### Entry rules
```
Enter new /ES short put ladder slot if:
- warmed (≥ WARMUP_DAYS data)
- trend_ok (BULLISH)
- VIX >= 22                         ← G6 gate
- cadence condition satisfied
- active slots < 5
- risk cap not breached
```

### Structure
```
DTE entry:    49 TD
Exit:         21 DTE
Cadence:      V2f M1 adaptive cadence
Max slots:    5
STOP_MULT:    15 (retained as fail-safe)
```

### Risk controls
```
- max estimated SPAN ≤ 30% NLV
- max active slots = 5
- STOP_MULT = 15
- no entry if VIX data missing/stale
- live margin monitor required
```

### Monitoring
```
- entry VIX
- IVP bucket (passive observation, not gating)
- active slots
- estimated SPAN
- broker margin / BP
- stop proximity
- mark-to-market drawdown
```

### Review obligation
**NOT "12 months only"** — at 5-6 trades/year, 12 months may yield insufficient samples. Use:

```
Review after 12 months AND ≥ 10 live entries,
or after 24 months if fewer than 10 entries.
```

---

## 8. Q072 — Should we test IVP 55-70 exclusion?

**NO — do not make it a blocker for current SPEC.**

G8/G9 failed strict promote criteria. Strongest finding is already G6. Additional IVP exclusion may overfit.

**Optional follow-up**:
```
Q072 (optional, post-SPEC):
Within VIX >= 22 entries only, test whether IVP 55-70
remains a disaster pocket.
```

Important framing: G8/G9 were tested **globally**. The relevant post-G6 question is:

> Among VIX ≥ 22 entries, does IVP add incremental discrimination?

Do NOT block current G6 SPEC on Q072.

---

## 9. Final reviewer answer

> **Q071 is a high-level integrated strategy study, not a filter transplant.**
>
> It correctly:
> 1. Defined goal and veto before research
> 2. Ran V2f context attribution
> 3. Rejected Q041 literal IVP window
> 4. Extracted Q041's regime-quality concept
> 5. Discovered /ES's stronger absolute VIX gate
> 6. Tested cadence, stop, portfolio viability
> 7. Provided clear promote/reject logic
>
> Required revisions are framing-level, not research-level:
>
> Don't say "Q041 IVP gate port succeeded."
> Say "Q041's volatility-regime entry-quality concept successfully transferred, manifesting in /ES as VIX ≥ 22 rather than IVP 43-55."

---

## Action items for Quant Researcher

1. Apply framing revisions to `research/q071/q071_memo_2026-05-14.md`:
   - Rename recommended config to **`ES High-Vol Sell Put Ladder`**
   - Soften "STOP redundant" → "unused historical safeguard, retained as fail-safe"
   - Soften bootstrap sig 100% claim → "supports paper-trading promotion, not production certainty"
   - Add BP-vs-SPAN dual-cap clarification
   - Refine 12-month review → "12 months AND ≥10 entries, OR 24 months"
   - Add explicit "promote to DRAFT SPEC / paper-trading candidate" language
2. Do not draft SPEC yet — PM/Planner will own SPEC-XXX. Reviewer outline above is suggestion.
3. Do not start Q072 — defer as optional post-SPEC follow-up.
