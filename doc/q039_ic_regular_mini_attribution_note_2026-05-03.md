# Q039 IC Regular Mini Attribution Note

## 1. One-line conclusion

`Q039` is now narrow enough to keep as a research-only residual: the HC-only `IC regular` trades are primarily explained by **high-IVP `NORMAL IC` fallback / gate behavior in HC**, not by slot blocking, and not by mild threshold-boundary sensitivity that would justify starting with an IVP sweep.

## 2. Question Being Answered

After tieout #2 and tieout #3 both passed, the largest remaining HC↔MC residual stayed:

- `IC regular`: `HC 13` vs `MC 6`

This note asks:

1. Is the residual mainly a slot-blocking artifact?
2. Is it mainly an IVP threshold-boundary issue?
3. Or is it better explained by a route / fallback / gate semantic difference?

## 3. MC 6-Trade Table

| Entry date | HC relation | Entry VIX | Entry SPX | Exit reason | PnL |
|---|---:|---:|---:|---|---:|
| 2023-08-15 | MC-only | 16.46 | 4438 | 50pct_profit | +399 |
| 2023-09-20 | MC-only | 15.14 | 4402 | roll_21dte | +63 |
| 2023-10-31 | MC-only | 18.14 | 4194 | roll_21dte | -661 |
| 2024-05-03 | Shared | 13.49 | 5128 | roll_21dte | +45 |
| 2025-12-18 | Shared | 16.87 | 6775 | 50pct_profit | +624 |
| 2026-01-21 | MC-only | 16.90 | 6876 | 50pct_profit | +621 |

Immediate implication:

- only `2 / 6` MC trades are shared with HC
- MC has `4` IC regular trades that HC does not share
- HC has `11` IC regular trades that MC does not share

So the residual is real, but it is already narrow enough to inspect by route / gate behavior rather than by a broad sweep.

## 4. HC-Only 11-Trade Mini Attribution

| Entry date | ivp252 bucket | Trend state | IC slot occupied | HC route reason | Attribution bucket |
|---|---:|---|---|---|---|
| 2023-10-04 | [30,55) 48.2 | BEARISH | No | NORMAL + IV NEUTRAL + BEARISH + VIX stable -> IC | MC-missing despite valid [30,55) |
| 2023-11-03 | <30 21.9 | NEUTRAL | No | LOW_VOL + NEUTRAL -> IC | Low-IV bug candidate |
| 2024-04-12 | >=55 84.9 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |
| 2024-08-01 | >=55 94.4 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |
| 2024-09-03 | >=55 96.8 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |
| 2024-12-30 | >=55 77.7 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |
| 2025-02-21 | >=55 79.7 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |
| 2025-03-27 | >=55 74.9 | BEARISH | No | NORMAL + IV HIGH + BEARISH + VIX stable -> IC | High-IVP fallback/gate |
| 2025-11-13 | >=55 76.9 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |
| 2026-02-12 | >=55 78.5 | BEARISH | No | NORMAL + IV HIGH + BEARISH + VIX stable -> IC | High-IVP fallback/gate |
| 2026-04-08 | >=55 76.1 | NEUTRAL | No | NORMAL + IV HIGH + NEUTRAL -> IC | High-IVP fallback/gate |

## 5. Bucket Summary

| Bucket | Count | Interpretation |
|---|---:|---|
| High-IVP fallback/gate | 9/11 | Primary cause; HC still allows `NORMAL IC` fallback when `ivp252 >= 55`, while MC Gate 1 behaves more like a hard reject or alternate route |
| Low-IV bug candidate | 1/11 | `2023-11-03`; this is a HC `LOW_VOL + NEUTRAL` route and should not yet be treated as a `NORMAL` path bug |
| MC-missing despite valid [30,55) | 1/11 | `2023-10-04`; more consistent with a single-trade path / trend-state divergence than with the main IVP gate story |
| Other | 0/11 | No meaningful concentration elsewhere |
| Slot blocking | 0/11 | All HC-only 11 trades had no same-class `IC` slot occupied |

## 6. What Is Now Ruled Out

### 6.1 Not primarily slot blocking

The HC-only 11-trade pack shows:

- `IC slot occupied = No` for all `11 / 11`

So slot blocking does not explain why HC kept more `IC regular` entries.

### 6.2 Not primarily a mild threshold-boundary problem

Of the HC `IC regular` entries:

- `9 / 13` are already `ivp252 >= 55`
- `0 / 13` are in a `50~65` borderline cluster

That means this is not mainly a “threshold near 55 is too tight / too loose” problem. A first-step IVP sweep would likely remove or add trades mechanically without clarifying the real semantic difference.

## 7. Best Current Interpretation

The most compact interpretation is:

> The main residual comes from HC continuing to route some `NORMAL` high-IVP situations into `IC regular`, while MC behaves more like a hard gate or alternate-route policy in those same environments.

This is consistent with:

- `9 / 11` HC-only trades falling into the `High-IVP fallback/gate` bucket
- no slot-blocking evidence
- only `1` true valid-range `[30,55)` exception
- only `1` low-IV exception

## 8. What Should Not Happen Next

At this stage, we should **not**:

- widen this into a stronger HC↔MC parity investigation
- start with an IVP sweep
- treat the residual as evidence of a broad implementation bug

Those moves would be disproportionate to what the mini attribution already shows.

## 9. Recommended Next Step

If anything further is needed, it should stay very small:

- preserve this note as the current narrow explanation
- optionally add one small appendix later focused only on the two exceptions:
  - `2023-11-03` low-IV `LOW_VOL` IC
  - `2023-10-04` valid `[30,55)` but MC-missing

Everything else is already explained well enough for planning and sync purposes.

## 10. Recommended Status

- `Q039`: keep **open**
- classification:
  - **research only**
  - **narrow attribution sufficient**
- no upgrade to parity investigation
- no IVP sweep as first move

## 11. References

- `sync/mc_to_hc/MC Response 2026-05-02_v2.md`
- `sync/open_questions.md`
- `PROJECT_STATUS.md`
- `doc/tieout_2_2026-05-02/README.md`
- `doc/tieout_3_2026-05-02/README.md`
