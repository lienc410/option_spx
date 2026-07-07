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

**Spec/rule IDs are provenance, not names (2026-07-06).** `SPEC-104`, `B4`,
`R5/R6` and similar identifiers answer "which document ratified this", not
"what does this do". They must never LEAD a user-facing label — the primary
label says what the surface does in plain function-first English, and the
identifier demotes to a muted `.spec-ref` suffix (mono, 0.52rem, `--text-2`)
or a tooltip. Precedent: Q042 → display name "Drawdown Overlay" (2026-05-10).

| Wrong (leads with provenance) | Right (function first, provenance demoted) |
|---|---|
| `SPEC-104 Monitors` | `Governance Health Monitors <span class="spec-ref">SPEC-104</span>` |
| `SPEC-108.1 V1b Ladder (weekly Wed)` | `Entry Ladder · weekly Wed anchor <span class="spec-ref">SPEC-108.1 V1b</span>` |
| `B4 booster gate (cap 80% → 90%)` | `BP Cap Booster · benign-regime gate 80% → 90% <span class="spec-ref">B4 · SPEC-105</span>` |

Rule IDs inside prose/detail lines (`rules R5/R6`, `(R1)`) are fine as
suffixes — the test is whether a reader who forgot the spec can still tell
what the surface does from the primary label alone.

**Personal-tool page exemption (SPEC-125 D9, PM default):** `funds.html`,
`partnership.html`, `etrade_reauth.html` are Chinese-domain personal tools —
buttons/h1/badge-content may be Chinese there (e.g. 「＋ 记录减仓」「基金 清仓信号」).
The exemption is page-scoped; general strategy/backtest pages stay English-chrome.
Within an exempted page, don't MIX: pick one language per control group.

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

**Theme system:** The product supports PM-controlled dark and light themes. The
dark palette remains the historical baseline, while the warm off-white light
palette is also canonical for dashboard use. New templates must link
`web/static/theme.css`, must not define their own `:root` token block, and must
express colors through the shared CSS variables.

## Themes

Theme state is client-side only: `<html data-theme="dark|light">` plus
`localStorage["spx-theme"]`. Backend recommendation, routing, broker, and
paper-trading semantics must not depend on theme state.

Shared assets:
- `web/static/theme_bootstrap.js` sets `data-theme` before paint.
- `web/static/theme.css` owns all core color, typography, surface, and legacy
literal tokens.
- `web/static/theme.js` injects the nav toggle and exposes `themeColor()` /
  `themeRgba()` helpers for Chart.js and JS-rendered UI.

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

**Signal-outcome states (SPEC-125 D5 addendum).** Monitor/2nd-signal panels
carry domain states that are NOT daily action states. These are the legal
ones; anything else must map into the seven action states above or be added
here first:

| State | Domain | Style |
|---|---|---|
| SIGNAL | ES ladder card: entry signal live today | `badge-open` |
| ARMED / WATCHING | Settled-VIX / intraday monitor phases | `badge-warning` |
| WAITING | Settled-VIX signal-2 pending window | `badge-readonly` |
| SKIPPED / CHANGED / CONFIRMED / TIMEOUT | Settled-VIX signal-2 outcomes | gray family |
| CALM | intraday monitor: no spike/stop condition | gray family |
| READ ONLY | Q041 review-only sleeves | `badge-readonly` |
| DEFERRED | deferred research surfaces (DEFERRED.md ledger) | `badge-obs` |

`WAIT` is NOT in the vocabulary — "no valid setup today" is `NO ENTRY`
(unified sitewide in SPEC-125).

## Push Vocabulary (SPEC-126)

Telegram pushes go through `notify/gateway.py` exclusively. Contract:

| Field | Rule |
|---|---|
| category | 🔴 `ALERT` needs PM action now / 🟡 `ACTION` suggested action / 🔵 `STATE` position state / ⚪ `FYI` routine. Missing/unknown → raise |
| about 首行 | `关于新开仓` / `关于持仓 <标识>` / `系统状态` — every message self-identifies its object (kills HOLD-vs-NO ENTRY ambiguity) |
| state words | New-entry verdict pushes use Action State Vocabulary words — `NO ENTRY`, never `WAIT`/观望/free text. Strategy name may follow in parentheses |
| quiet levels | FYI/STATE default `disable_notification` (no bell); ALERT/ACTION ring |
| dedupe | `dedupe_key` sends once per ET day; only a category UPGRADE re-sends. Clearing messages (`clears=`) only follow a key that fired today, quietly |

Daily mail budget (PM-ratified): 晨报 1 (09:35) + 收盘前 digest 1 (15:55) +
event-driven ALERT/ACTION only. Routine governance/overlay evaluations fold
into the digest; paper/shadow stays event-driven and silent.

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
- **Primary scale (4px-based):**
  - 2xs: 2px
  - xs: 4px
  - sm: 8px
  - md: 12px
  - lg: 16px
  - xl: 24px
  - 2xl: 28px
  - 3xl: 48px

**Extended scale (blessed half-step values for fine layout work):**

Real templates use these enough that they earn first-class status. Use when
the strict 4px scale produces visually wrong rhythm. Do not introduce new
off-scale values without adding them here.

- 5px — nav-link inner padding, chip-row gaps (very widely used; do not "round up" to 8)
- 6px — tight inline gaps (badge gutters, chip spacing)
- 7px — table cell `padding`, half-step between 6 and 8 (used in episode/data tables)
- 9px — card / panel `padding` between sm (8) and md (12), used for compact informational panels
- 10px — card padding `top/bottom` shorthand (matches sm + 2 hairline)
- 13px — nav-link horizontal padding (also widely used)
- 14px — section / card `margin-bottom` between md (12) and lg (16), used to separate strategy cards
- 18px — section spacing between lg (16) and xl (24), used for matrix-row gaps
- 26px — page-hero top `padding` (between xl 24 and 2xl 28)

**Discouraged for new code** — these values appear in legacy templates but should not be introduced going forward; round to the nearest scale value when refactoring:
- 11px → 12px (md)
- 17 / 19 / 21 → 16 / 20 (or use 18 from extended)
- 25 / 27 → 24 / 28

If you find yourself reaching for an off-scale value not listed above, prefer the closest
4px-scale value first. Add to the extended list (with rationale) only if the strict scale
produces visibly wrong rhythm in side-by-side comparison.

## Layout

- **Approach:** Grid-disciplined — single-column 880px max-width for all strategy pages; portfolio backtest may expand to 1100px for chart width
- **Grid:** Single column, centered, 880px max-width, 24px side padding
- **Nav:** Sticky top, 50px height, blur backdrop, `--border` bottom edge
- **Multi-page structure:**
  - **Home**
    - `/` — Portfolio Command Center (Today's Actions + Portfolio Snapshot + account positions)
  - **SPX family** [LIVE — share `Strategy | Backtest | Matrix` page-tabs]
    - `/spx` — SPX strategy detail (current recommendation + Signal 2 embedded panel)
    - `/backtest` — SPX strategy backtest (on-demand)
    - `/matrix` — SPX strategy matrix (regime × IV × trend decision table)
  - **/ES family** [RESEARCH — share `Strategy | Backtest` page-tabs]
    - `/es` — /ES short put strategy detail (signal cards + credit stop bar)
    - `/es-backtest` — /ES backtest
  - **Addon: Drawdown Overlay** [PAPER — share `Dashboard | Backtest` page-tabs]
    - `/q042` — Drawdown Overlay dashboard (display name "Drawdown Overlay"; route stays `/q042` for stability)
    - `/q042/backtest` — Drawdown Overlay backtest
  - **Addon: Aftermath** [OBSERVATION — share `Dashboard | Backtest` page-tabs]
    - `/aftermath` — Aftermath window dashboard
    - `/aftermath/backtest` — Aftermath backtest
  - **Research: Q041** [Active iteration; T1 retired]
    - `/q041` — Q041 strategy matrix (T2/T3 research iteration only)
    - `/q041/backtest` — Q041 backtest (per-sleeve)
    - `/q041/archive` — Q041 T1 retired strategy archive [RETIRED]
  - **Account / cross-strategy**
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

**Single source (SPEC-125 D6):** the nav is rendered ONLY by
`web/templates/_nav.html` (`{% set nav_active = '<key>' %}{% include "_nav.html" %}`).
Pages must not carry inline `nav-links` blocks. Canonical set and labels:

```
Portfolio | SPX | /ES | DD Overlay | Aftermath | Stress Put Ladder | Sleeves | Port BT | Performance | Journal | Margin | Funds | Book
```

Label decisions (2026-07-06): `DD Overlay` (nav-width form of display name
"Drawdown Overlay" — page h1 uses the full name; route stays `/q042`);
`Sleeves` = the Q041 T2/T3 iteration page; `Book` = partnership ledger.
`Q041 T1 Archive` stays an inline retired-tier link on `/q041`, not a nav item.

- Active page: `--gold` text + `--gold-bg` background (ES family pages may use
  their orange accent for the active state — family accent exception)
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
| 2026-05-10 | Aftermath promoted to top-level addon (Phase 7); Settled VIX returned to SPX 2nd-signal panel | Spec re-check: Aftermath is the VIX-peak-falls trade (broken-wing V3-A trigger); Settled VIX is SPX morning 2nd-look. Earlier Phase 4 elevation of Settled VIX was based on a misread |
| 2026-05-10 | Backtest Page Template formalized in DESIGN.md (Phase 6) | Cross-strategy comparability requires identical structure: metric cards + SPX overlay + Trading Discipline. Was implicit; making it explicit avoids future drift |
| 2026-05-10 | Language rule clarified with domain-jargon exemption (Phase 6 audit) | Strict per-element-one-language flagged false positives on Chinese prose with embedded tickers/Greek/margin terms. Banned only sentence-level prose switches |
| 2026-05-10 | All SPX/ES family pages migrated to `.page-tab` class | Two parallel systems (`.strat-tab` inline-styled vs `.page-tab` CSS class) existed across the site; normalized to the cleaner class-based approach. matrix.html got a tab strip for the first time |
| 2026-07-06 | Nav single-sourced to `_nav.html`; labels `DD Overlay`/`Sleeves`/`Book` formalized | 12 hand-copied navs had drifted into different sets (SPEC-125 D6); short labels win on nav width, page h1 carries full display names |
| 2026-07-06 | Signal-outcome states added as a second badge vocabulary section | ≥10 out-of-vocab badges had accumulated (SPEC-125 D5); monitor/2nd-signal domain states are legal but enumerated — `WAIT` folded into `NO ENTRY` |
| 2026-07-06 | funds/partnership/etrade_reauth exempted from English-chrome rule | Personal-tool pages in Chinese domain (SPEC-125 D9, PM default exemption) |
| 2026-07-06 | Evidence streams (S2-BPS paper, BCD shadow, skew monitor) deliberately have NO display surface | SPEC-125 C6: they are background data feeds for research arbitration; PM reads the jsonl / monthly digest when needed. A dashboard surface would invite daily micro-reading of pre-registered experiments |
| 2026-07-06 | Page-title scale: two tiers — Portfolio hero 2.1rem, all other pages 1.7rem, always `--f-display` | Six drifting sizes found (SPEC-125/S3); normalize opportunistically when touching a page |
| 2026-07-06 | Unified notification gateway (SPEC-126): 4-category contract + mandatory about 首行 + 15:55 pre-close digest replaces 15:30/16:03/16:15 scheduled pushes | 8 direct-send sites had no classification/dedupe/quiet levels; PM received contradictory-looking HOLD-vs-WAIT messages and 3 overlapping late-day pushes |
| 2026-07-06 | Spec/rule IDs banned as primary UI labels — function-first names + muted `.spec-ref` suffix | PM couldn't tell what "SPEC-104 Monitors" / "SPEC-108.1 V1b Ladder" do from the label; generalizes the Q042→"Drawdown Overlay" precedent into a rule |
