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
- `--gray-bg: rgba(96,104,128,0.08)` / `--gray-border: rgba(96,104,128,0.2)` — disabled / WAIT / blocked / read-only badge

**Dark mode only:** This product has no light mode. The dark palette is canonical.

## Action State Vocabulary

Used in the Portfolio Command Center "Today's Actions" zone and per-strategy card headers. Every strategy shows one of these states.

| State | Color | Meaning |
|---|---|---|
| OPEN | `--green` | Valid entry opportunity available today |
| HOLD | `--blue` | Position open, no action needed |
| CLOSE | `--red` | Close signal: stop triggered, expiry imminent, or explicit signal |
| WAIT | `--text-muted` | Entry conditions not met; waiting |
| WARNING | `--orange` | Approaching critical threshold (credit stop 2×, DTE ≤7, VIX spike) |
| BLOCKED | `--text-muted` (reduced opacity) | Blocked by system rule (BP limit, trend filter, missing data) |
| REVIEW | `--gold-bg` + `--gold-border` | Paper trade / observe-only sleeve; requires manual review |

Action state badges use `--f-ui` 0.60rem, 500 weight, uppercase, letter-spacing 0.10em.

## Strategy Card Hierarchy

Three visual tiers for the multi-strategy portfolio layout. All cards use the same surface token, but differ in accent color and visual prominence.

**Primary (SPX live trading)**
- Accent: `--gold` — the main production strategy
- Border: `--border-2` with `--gold-border` left-edge accent on active state
- Full card width (880px)
- Recommendation text in `--f-display`

**Secondary (live production candidates, /ES)**
- Accent: `--orange` — production-ready but separate risk pool
- Border: `--border-2` with `--orange-border` left-edge accent
- Full card width (880px), slightly reduced heading prominence
- Recommendation text in `--f-ui` (not serif — secondary strategies don't carry the same "this is the signal" narrative weight)

**Sleeve / Observation (/Q041, read-only)**
- Accent: `--gray-border` — research / paper-trade / observe-only
- Explicit "READ ONLY" or "OBSERVATION" badge in `--text-muted`
- Can be collapsed by default; expands on click

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
  - `/` — Portfolio Command Center (Today's Actions + Portfolio Snapshot + quick nav)
  - `/spx` — SPX strategy detail (current + backtest)
  - `/es` — /ES short put detail
  - `/q041` — Q041 sleeves + paper trades + attribution
  - `/portfolio-backtest` — joint simulation + attribution charts
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
Portfolio  |  SPX  |  /ES  |  Q041  |  Backtest
```

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
