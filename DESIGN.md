# Design System — SPX Strategy · Dashboard

## Product Context
- **What this is:** Personal quantitative trading dashboard for SPX options strategy recommendation, portfolio monitoring, and per-strategy visualization
- **Who it's for:** Single sophisticated options trader (Portfolio Margin account)
- **Space/industry:** Quantitative trading / short-premium options strategies
- **Project type:** Internal tool / personal dashboard — daily decision-making surface
- **Design priority:** Action-first information hierarchy — the user opens this once a day and needs to know immediately what to do across all active strategies

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian with Editorial data hierarchy
- **Decoration level:** Minimal — typography and color do all the work; no gradients, no textures, no illustration
- **Mood:** Serious precision instrument. Not a consumer product. Data density is a feature, not a problem. The serif/mono/sans three-font system distinguishes narrative from numbers from controls — each layer has its own voice.
- **The one design risk worth keeping:** Using a serif face (Newsreader) for recommendation narratives and strategy names in a trading tool. Every Bloomberg terminal and retail broker uses all-sans. The serif adds "newspaper headline" authority to the recommendation text, reinforcing that signals are argued judgments, not random noise. The user is the only audience — no onboarding cost.

## Typography

- **Display/Hero:** `'Newsreader', Georgia, serif` — for strategy names, recommendation headlines, rationale narrative. Italic weight adds emphasis for key signal moments.
- **Body/UI:** `'DM Sans', system-ui, sans-serif` — for labels, body copy, navigation, form inputs, button text
- **Data/Numbers:** `'JetBrains Mono', 'Courier New', monospace` — for all numeric values: prices, percentages, delta, VIX levels, BP percentages, timestamps, trade IDs
- **Code:** `'JetBrains Mono'` — same as data; no separate code face needed
- **Loading:** Google Fonts — `Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400;1,6..72,600` + `JetBrains+Mono:wght@400;500;600` + `DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500`

**Rule:** Every number on screen must use `--f-mono`. Label that says "VIX" uses `--f-ui`. Value "18.4" uses `--f-mono`. Recommendation sentence uses `--f-display`.

## Language Rules

Single-user internal tool with bilingual author. Mixed Chinese/English is intentional but must follow strict positional rules to avoid the "pasted-together" feeling.

| Position | Language | Examples |
|---|---|---|
| Navigation, tabs, buttons | English | `Today's Actions`, `Refresh`, `Save` |
| Badges (state + tier) | English | `LIVE`, `PAPER`, `WARNING`, `RETIRED` |
| Chart axes, metric names, table headers | English | `ddATH%`, `Win Rate`, `BP Usage` |
| Numeric values (always mono) | N/A | `21.3%`, `$600,804` |
| Strategy descriptions, rationale notes | Chinese | 「基于 Schwab NLV 计算」 |
| Error/status messages | Chinese | 「账户数据不可用」 |
| Research narratives, strategy spec cards | Chinese | 策略细节卡 |

**DOM-level rule:** A single HTML element (`<span>`, `<div>`, `<label>`) contains exactly one **prose language**. Numeric values (`21.3%`) and **domain jargon tokens** are exempt and may appear inside either-language prose. Sentences (clauses with subject+verb) must not switch languages mid-element.

**Domain jargon exemptions** (these may appear inside Chinese prose without violating the rule):
- Tickers / instruments: `SPX`, `VIX`, `/ES`, `GOOGL`, `AMZN`, `COST`, `JPM`
- Greek / option terms: `delta`, `gamma`, `vega`, `theta`, `DTE`, `IVR`, `IVP`
- Margin / risk terms: `BP`, `NLV`, `PM`, `SPAN`, `IMR`, `notional`
- Strategy abbreviations: `CSP`, `BPS`, `IC`, `BWB`, `MA10`, `ddATH`
- Code identifiers: function/variable names in `<code>` tags

**Sentence-level violation example** (DO NOT do this):
> `Daily selector tick decides entry — 上一笔 close 后立即可入下一笔。`

This mixes an English imperative clause ("Daily selector tick decides entry") with Chinese prose ("上一笔 close 后立即可入下一笔") in the same element. The fix is to write the whole sentence in one language:
> `Selector 每日 tick 决定是否新开仓 · 上一笔 close 后立即可入下一笔` ✓ (Chinese prose with jargon `tick`, `close`)

**Badge text is always English**, even inside an otherwise Chinese-language card. Badges are semantic tokens, not prose.

**Scale (base 14px):**
- 2xs: 0.60rem (8.4px) — micro labels, badge text
- xs:  0.68rem (9.5px) — mono data values, secondary labels
- sm:  0.72rem (10.1px) — decision lines, table text
- md:  0.76rem (10.6px) — nav links, button labels
- base: 1.00rem (14px) — body text
- lg:  1.05rem (14.7px) — nav brand
- xl:  1.20rem (16.8px) — card headings
- 2xl: 1.40rem (19.6px) — section titles
- display: 1.60rem+ — page-level hero text (Newsreader)

## Color

- **Approach:** Restrained + semantic — one warm accent (gold) for primary signals; color is rare and meaningful; background family is near-black navy

**Background / Surface:**
- `--bg:         #080A13` — page background (near-black navy)
- `--surface:    #0D1020` — card background
- `--surface-hi: #131728` — elevated / hover state surface
- `--border:     #191E33` — primary border
- `--border-2:   #232A42` — secondary border / divider

**Text:**
- `--text:       #C4CEEC` — primary text (cool light)
- `--text-2:     #606880` — secondary text / muted labels
- `--text-muted: #363C52` — faintest text / placeholders

**Semantic Colors — each has bg + border tint variants:**
- `--gold:   #C9A840` / bg `rgba(201,168,64,0.07)` / border `rgba(201,168,64,0.22)` — primary accent; key recommendation, active nav, first-attention signals
- `--green:  #42CC7C` / bg `rgba(66,204,124,0.07)` / border `rgba(66,204,124,0.22)` — positive / OPEN action / profitable trade
- `--red:    #E04862` / bg `rgba(224,72,98,0.07)` / border `rgba(224,72,98,0.22)` — negative / CLOSE signal / stop triggered / loss
- `--blue:   #4888E8` / bg `rgba(72,136,232,0.07)` / border `rgba(72,136,232,0.22)` — informational / HOLD / neutral signal / backtest line
- `--orange: #E08040` / bg `rgba(224,128,64,0.07)` / border `rgba(224,128,64,0.22)` — warning / approaching threshold (2× credit stop, expiry <7d)
- `--gray-bg: rgba(96,104,128,0.08)` / `--gray-border: rgba(96,104,128,0.2)` — disabled / NO ENTRY / blocked / read-only badge

**Dark mode only:** This product has no light mode. The dark palette is canonical.

## Action State Vocabulary

Used in the Portfolio Command Center "Today's Actions" zone and per-strategy card headers. Every strategy shows one of these states.

| State | Color | Meaning |
|---|---|---|
| OPEN | `--green` | Valid entry opportunity available today |
| HOLD | `--blue` | Position open, no action needed |
| CLOSE | `--red` | Close signal: stop triggered, expiry imminent, or explicit signal |
| NO ENTRY | `--text-muted` | Entry conditions not met; no valid setup today |
| WARNING | `--orange` | Approaching critical threshold (credit stop 2×, DTE ≤7, VIX spike) |
| BLOCKED | `--text-muted` (reduced opacity) | Blocked by system rule (BP limit, trend filter, missing data) |
| REVIEW | `--gold-bg` + `--gold-border` | Paper trade / observe-only sleeve; requires manual review |

Action state badges use `--f-ui` 0.60rem, 500 weight, uppercase, letter-spacing 0.10em.

## Strategy Tier Badge Vocabulary

Distinct from Action State Vocabulary. Action states change daily (HOLD → CLOSE → WAIT). Tier badges describe the **lifecycle stage** of a strategy and rarely change. Both can appear on the same card (action state in header right, tier badge inline next to strategy name).

| Tier | CSS class | Visual | Meaning |
|---|---|---|---|
| LIVE | `badge-review` | Gold | Production strategy, real-money execution (currently only SPX) |
| RESEARCH | `badge-hold` | Blue | Active research / monitoring, no live trading (ES) |
| PAPER | `badge-obs` | Muted gray, uppercase small | Paper-trade tracking, decisions logged but not executed (Q042 Drawdown Overlay) |
| OBSERVATION | `badge-readonly` | Gray | Signal display only, no positions (Settled VIX) |
| RETIRED | `badge-unavail` | Gray italic | Archived strategy, kept for historical reference (Q041 T1) |

**CSS class reuse note:**
- `badge-hold` is also used for action state HOLD (position open, no action). Visual collision is acceptable in this single-user tool — context (where the badge appears on the card) disambiguates. If future strategies need finer distinction, introduce dedicated `badge-research` class.
- `badge-review` overlaps with watching/timeout action states. Same rationale.
- `PAPER` deliberately does NOT use orange (orange = WARNING in Action State Vocabulary). The muted `badge-obs` style is the canonical paper-trade indicator and matches the existing Q041/Q042 "Observation" badges already in production.

## Strategy Card Hierarchy

Three visual tiers for the multi-strategy portfolio layout. All cards use the same surface token, but differ in accent color, content density, and visual prominence.

**Primary — `tier-primary` (SPX, live trading)**
- Accent: `--gold-border` left-edge
- Full content: signal chips + rationale narrative + structure + position + BP impact + settling sub-panel
- Recommendation text in `--f-display` (Newsreader serif italic)
- Reserved for the single live production strategy

**Secondary — `tier-secondary` (/ES, research candidates)**
- Accent: `--orange-border` left-edge
- Medium content: action state badge + current position + 1-2 core metrics (e.g. SPAN ratio)
- Recommendation text in `--f-ui`
- For strategies that are research-stage but already parallel to primary (not buried in observation tier)

**Addon — `tier-tertiary` (overlay signals, paper sleeves, Q041 candidate list)**
- Accent: muted gray left-edge (`rgba(96,104,128,0.40)`)
- Light content: state badge + 1-2 inline signal values + link to full detail page
- Use for: Drawdown Overlay, Settled VIX, Q041 sleeve list, anything that lives "alongside" but is not the main event
- Title with tier-context badge: `Paper`, `Observation`, etc. (in `badge-obs` style)

**Visual weight ordering on homepage Today's Actions:**
Primary → Secondary → Addon(s). Research iteration sleeves (Q041 T2/T3) live in a separate section below Today's Actions, not in this hierarchy.

## Backtest Page Template (minimum requirements)

Every strategy backtest page must include these two elements in this order, before any strategy-specific content. This is a hard requirement, not a suggestion — consistency across backtest pages is the user's primary navigation aid when comparing strategies.

**1. Key metrics row** (top of page, after page tabs)

A row of cards using `.m-card` / `.metric-grid` (or local equivalent). Required for any **trade-based** strategy:

| Card | Why it matters |
|---|---|
| Total Trades | Sample size |
| Win Rate | Hit ratio |
| Avg P&L (or Expectancy) | Per-trade unit economics |
| Total P&L | Cumulative outcome |
| Max Drawdown | Worst peak-to-trough |
| Sharpe Ratio | Risk-adjusted return |
| Annualized ROE | Capital efficiency |

For **observation-only** strategies (no trades, e.g. Settled VIX) substitute:

| Card | Substitute meaning |
|---|---|
| Total Signals | Days the signal evaluated |
| Flip Rate | % of days Signal 1 ≠ Signal 2 |
| Flip Count | Absolute flip events |
| Outcome split | e.g. stable / timeout / skipped |

**2. SPX Price chart — Trade Entry / Exit overlay** (second section)

Chart title pattern: `SPX Price — <Strategy Name> Trade Entry / Exit` for trade strategies; `SPX Price — <Signal Name> Events` for observation strategies. Markers must be SPX-priced on the date the event occurred (entry/exit/flip), so user can read "what kind of SPX day was this".

**Per-underlying exception:** Strategies that trade an instrument other than SPX (Q041 T2/T3 on GOOGL/AMZN/COST/JPM) use that underlying's price chart instead — title becomes `<Symbol> Price — Trade Entry / Exit`. Same overlay style.

Below these two required elements, each backtest page may add strategy-specific analysis (waterfalls, regime breakdowns, sensitivity tables, etc.) freely.

**3. Trading Discipline section** (bottom of page, mandatory)

Every backtest page must end with a "Trading Discipline" section. Purpose: the page is a strategy advertisement — anyone (including future-you) reading the numbers needs to immediately see the rules that produced them. No rules ⇒ no actionable trust.

Required five categories, in order:

| Category | What to capture |
|---|---|
| Entry | Signal conditions, strike / delta / DTE selection, structure |
| Exit | Profit target, time-based close, stop-loss trigger |
| Sizing | Contract count, BP allocation, account-fraction cap |
| Risk | Max drawdown limits, BP gates, regime / volatility guards |
| Frequency | Cadence, max concurrent positions, blackout periods |

Plus an optional `Source` footnote with file path / line refs.

Render as a card with horizontal rows: category label (left, mono uppercase, fixed 100px column) + rule prose (right, free width). Inline `<code>` for specific values (deltas, DTEs, BP caps). Bold key thresholds within prose. Strategy-specific exceptions appear inline within the relevant row.

CSS class names: `.discipline-section` / `.discipline-card` / `.discipline-row` / `.discipline-key` / `.discipline-val` / `.discipline-footnote`. Copy the canonical CSS block when adding to a new backtest page; do not invent variants.

## Spacing

- **Base unit:** 4px
- **Density:** Compact-to-comfortable — data-dense but not cramped; 8px minimum between logical groups
- **Scale:**
  - 2xs: 2px
  - xs: 4px
  - sm: 8px
  - md: 12px
  - lg: 16px
  - xl: 24px
  - 2xl: 28px
  - 3xl: 48px

## Layout

- **Approach:** Grid-disciplined — single-column 880px max-width for all strategy pages; portfolio backtest may expand to 1100px for chart width
- **Grid:** Single column, centered, 880px max-width, 24px side padding
- **Nav:** Sticky top, 50px height, blur backdrop, `--border` bottom edge
- **Multi-page structure:**
  - `/` — Portfolio Command Center (Today's Actions + Portfolio Snapshot + account positions)
  - `/spx` — SPX strategy detail (current recommendation + backtest)
  - `/es` — /ES short put detail (signal cards + credit stop bar) [RESEARCH]
  - `/q042` — Drawdown Overlay dashboard + backtest (display name: "Drawdown Overlay"; route kept as `/q042` for stability) [PAPER]
  - `/svix` — Settled VIX dashboard + signal history [OBSERVATION]
  - `/q041` — Q041 strategy matrix (T2/T3 research iteration only)
  - `/q041/archive` — Q041 T1 retired strategy archive [RETIRED]
  - `/backtest` — SPX strategy backtest (on-demand)
  - `/portfolio-backtest` — joint J0 vs J3 BP simulation (873-day chart)
  - `/performance` — live trade performance
  - `/margin` — margin estimator + Schwab live BP
- **Border radius:** sm: 5px (buttons, badges), md: 9px (cards), lg: 12px (large panels), pill: 9999px (dots, status indicators)
- **Card spacing:** 12px margin-bottom between cards, 16px internal padding (strip), 20px internal padding (full card)

## Motion

- **Approach:** Minimal-functional — only transitions that aid comprehension; no entrance animations
- **Easing:** `ease` for color/background transitions; `ease-out` for visibility changes
- **Duration:**
  - micro: 0.10s — hover state color transitions
  - short: 0.15s — nav link, button active states
  - medium: 0.25s — panel show/hide (collapsible cards)
  - long: 0.45s — chart updates

## Navigation (multi-page)

Nav links for the multi-page portfolio architecture:

```
Portfolio  |  SPX  |  /ES  |  Drawdown Overlay  |  Settled VIX  |  Q041  |  Backtest  |  Port BT  |  Performance  |  Margin
```

Display name `Drawdown Overlay` replaces the old `Q042` label; route stays `/q042`. `Q041 T1 Archive` is reachable from the `/q041` page via inline retired-tier link, not a top-level nav item.

- Active page: `--gold` text + `--gold-bg` background
- Hover: `--text` + `--surface-hi`
- Non-active: `--text-2`
- Strategy-tier indicator: no indicator on nav items (color comes from page content)

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-07 | Keep Newsreader serif for display/narrative text | Distinguishes recommendation narrative from data; adds editorial authority unusual in trading tools but effective for daily decision use |
| 2026-05-07 | Gold as primary accent (not blue) | Blue is every broker's default; gold reads as "premium signal tier" and matches the income-harvest strategy orientation |
| 2026-05-07 | Three-font system (serif + mono + sans) | Each layer has distinct cognitive function: narrative (serif), numbers (mono), controls (sans). Unusual but functional for daily analytical use |
| 2026-05-07 | Action-first layout for Portfolio Command Center | User opens once daily; wants to know what to do, not browse strategy state. Action summary at top, strategy detail on drill-down pages |
| 2026-05-07 | Orange for secondary strategy (/ES) accent | Distinguishes /ES from primary SPX (gold) and from warning state (orange is also warning — acceptable because /ES card context makes meaning clear); avoids blue (too neutral) and red (too alarming) |
| 2026-05-07 | No light mode | Single-user internal tool; dark-only eliminates dual-palette maintenance cost with zero UX cost |
| 2026-05-10 | Bilingual rules formalized (English chrome / Chinese narrative) | Mixed language was accumulating ad-hoc; explicit positional rules let future page work stay consistent without per-page discussion |
| 2026-05-10 | Three card tiers renamed: Sleeve → Addon (`tier-tertiary`) | "Sleeve" was Q041-specific; "Addon" generalizes to overlay signals (Drawdown Overlay, Settled VIX) sitting alongside primary strategies |
| 2026-05-10 | Tier badges separate from action state badges | Action states change daily; lifecycle tier (LIVE/RESEARCH/PAPER/OBSERVATION/RETIRED) is stable. Two layers of meaning need two badge slots |
| 2026-05-10 | PAPER uses muted `badge-obs` not orange | Orange = WARNING in action state vocab; reusing it for paper-trade tier would create reading collision (Q042 card always looking like a warning) |
| 2026-05-10 | Q042 display name → "Drawdown Overlay", route unchanged | Strategy name conveys what it does; route stability avoids breaking bookmarks and reduces refactor scope |
