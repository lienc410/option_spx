# SPEC-108 — Dark/Light Theme Toggle Handoff

**Date**: 2026-05-27
**Owner**: Frontend Engineer
**Status**: PM-approved Option A (full implementation, ~4-5 days)
**Source**: PM brief 2026-05-27 ("评估一下加 theme 设置的难度" → 选 A → "写个信息让 developer 做")
**Backup tag**: `pre-light-theme-2026-05-27` (commit `73c0256`) + branch `backup/pre-light-theme-2026-05-27`, both on GitHub origin

---

## Context

The dashboard is currently dark-only by design (DESIGN.md L92 says "Dark mode only. The dark palette is canonical."). PM wants a runtime toggle between the existing dark theme and a new corporate/professional light theme.

This is **not** a small swap — the codebase has accumulated technical debt around colors that the theme system needs to clean up first:

- **20 templates** each inline their own `:root {…}` token block (CSS duplicated 20×)
- **No shared stylesheet** under `web/static/` — every template inlines its own CSS
- **~800 hardcoded hex / rgba values** across templates (mostly inline `style=""` attributes in JS-rendered HTML)
- **~320 Chart.js JS color strings** that don't read CSS vars at runtime (canvas)
- **~15 chart instances** across 10 pages that need re-render on theme toggle

DESIGN.md L92 will need an explicit amendment as part of this work — adding light mode is a design-principle change, not just a feature.

---

## Scope

**In scope:**
- Extract per-template `:root` token blocks into `web/static/theme.css`
- Add light-theme overrides via `:root[data-theme="light"] { … }`
- Toggle UI (☀️/🌙 button), localStorage persistence, `<html data-theme="…">` swap
- Refactor inline `style="color:#hex"` → `var(--token)` across all templates
- Chart.js theme map + re-render hook on toggle
- DESIGN.md amendment + memory note

**Out of scope:**
- Backend changes (no `web/server.py` edits expected — themes are pure frontend state)
- New color tokens beyond what dark already has (palette is 1:1, just light-version values)
- Per-broker color identity change (gold=options / 深绿=Schwab equity / 浅绿=ETrade / 紫=ETrade positions stays; light versions must preserve the four-way distinction)
- Mobile/responsive overhaul (current desktop layout unchanged)

---

## Decisions PM still needs to make

Before Phase 2 (light palette), PM should pick:

1. **Light bg style** — three reasonable options:
   - **Pure white** `#FFFFFF` — Bloomberg Terminal reversed-out style. Maximum contrast, least warmth.
   - **Off-white warm** `#F8F6F2` — Apple / Stripe corporate report aesthetic. Easier on the eyes for long sessions.
   - **Cool gray** `#F5F7FA` — VSCode Light+ / IDE aesthetic. Sits between the other two.

2. **Default theme** when no localStorage key exists — `dark` (PM's current usage) or `light` (new viewers) or `auto` (`prefers-color-scheme`)?

3. **Cache-busting** for the new shared stylesheet — recommend `<link rel="stylesheet" href="/static/theme.css?v={{ git_sha[:7] }}">` so each deploy busts browser cache. Developer can hardcode initially.

These are 5-minute decisions but block Phase 2. Surface them at kickoff.

---

## Code audit findings (verified 2026-05-27)

```bash
# Per-template :root token blocks
$ for f in web/templates/*.html; do
    [ "$(grep -c '^  --bg:' "$f")" -gt 0 ] && echo "$f"
  done | wc -l
20

# Hardcoded color count (the cleanup workload)
$ grep -cE '#[0-9A-Fa-f]{6}|rgba?\([0-9]+,' web/templates/*.html | sort -t: -k2 -rn | head -5
web/templates/backtest.html:163       ← worst offender
web/templates/portfolio_home.html:69
web/templates/q041_backtest.html:65
web/templates/journal.html:55
web/templates/q042_backtest.html:54
```

The 29 dark tokens currently live at the top of every template:
```css
:root {
  --bg: #080A13; --surface: #0D1020; --surface-hi: #131728;
  --border: #191E33; --border-2: #232A42;
  --text: #C4CEEC; --text-2: #606880; --text-muted: #363C52;
  --gold: #C9A840; --gold-bg: rgba(201,168,64,0.07); --gold-border: rgba(201,168,64,0.22);
  --green: #42CC7C; --green-bg: rgba(66,204,124,0.07); --green-border: rgba(66,204,124,0.22);
  --red: #E04862; --red-bg: rgba(224,72,98,0.07); --red-border: rgba(224,72,98,0.22);
  --blue: #4888E8; --blue-bg: rgba(72,136,232,0.07); --blue-border: rgba(72,136,232,0.22);
  --orange: #E08040; --orange-bg: rgba(224,128,64,0.07); --orange-border: rgba(224,128,64,0.22);
  --gray-bg: rgba(96,104,128,0.08); --gray-border: rgba(96,104,128,0.2);
  --green-equity: #4a7c59;
  --f-display: 'Newsreader', Georgia, serif;
  --f-mono: 'JetBrains Mono', 'Courier New', monospace;
  --f-ui: 'DM Sans', system-ui, sans-serif;
}
```

These are identical across all 20 templates today — easy verification baseline.

---

## Implementation phases (recommended order; each = independent commit + deploy)

### Phase 1 — Extract shared `web/static/theme.css`

- Create `web/static/theme.css` containing the 29-token `:root {…}` block (verbatim copy from any current template).
- Remove the `:root {…}` block from every template (20 files).
- Each template's `<head>` adds `<link rel="stylesheet" href="{{ url_for('static', filename='theme.css') }}?v={{ APP_VERSION or '1' }}">` near the top.
- Confirm Flask serves `/static/theme.css` (default behavior with `web/static/` dir).
- **Acceptance**: every page renders identical to pre-Phase-1; no visual diff.
- **Tag for rollback**: commit `phase1-theme-extract`.

### Phase 2 — Add light palette

- Append `:root[data-theme="light"] { … 25 token overrides … }` to `theme.css`.
- Tune accent bg alpha (0.07 on dark surface looks invisible on white — try 0.10-0.15 for light bg).
- Validate per-broker accent identity stays distinguishable: gold / 深绿 (Schwab equity) / 浅绿 (E-Trade) / 紫 (E-Trade positions) all need light-mode-friendly values that keep the four-way distinction.
- **Acceptance**: manually toggle `<html data-theme="light">` in DevTools — every page must render light without overflowing white bg into JS-rendered chunks.
- **Tag for rollback**: commit `phase2-light-palette`.

### Phase 3 — Toggle UI + persistence

- Add ☀️/🌙 button in the nav (top-right, before / inside `nav-right` block). Reuse existing `.nav-link` styling shape; single-character emoji or text.
- `localStorage.getItem('theme')` on page load → set `document.documentElement.dataset.theme = …` before first paint to avoid FOUC.
- Toggle handler: flip `data-theme`, write to localStorage, then call `_themeChanged()` (Phase 5 hook).
- Initial default per PM decision (see "Decisions" above).
- **Acceptance**: AC3.
- **Tag**: commit `phase3-theme-toggle-ui`.

### Phase 4 — Inline-color cleanup (the long pole; ~3-4 commits)

- Grep target: `style="[^"]*#[0-9A-Fa-f]{6}` and `style="[^"]*rgba?\(` across templates.
- Replace each inline color with the matching CSS var. The 800+ instances split roughly:
  - Static templates (HTML attrs): ~300 — straightforward sed-replace per template
  - JS-rendered HTML strings (template literals): ~500 — manual per-case (conditionals like `color:${x ? '#aaa' : '#bbb'}` can't be machine-rewritten)
- Suggest 4 commits, one per ~5-template group, to keep diffs reviewable.
- **Acceptance**: AC4 (no remaining hex color literals in templates outside the explicit Chart.js color map).
- **Tag**: `phase4-inline-color-cleanup`.

### Phase 5 — Chart.js theme map + re-render

- Chart.js renders to canvas — CSS vars don't reach it. Need a JS color resolver.
- Create `web/templates/_chart_theme.js` (or inline if shared static is too much overhead) exposing:
  ```js
  function themeColors() {
    const cs = getComputedStyle(document.documentElement);
    return {
      gold:    cs.getPropertyValue('--gold').trim(),
      goldBg:  cs.getPropertyValue('--gold-bg').trim(),
      // … all colors a chart might use
      text:    cs.getPropertyValue('--text').trim(),
      text2:   cs.getPropertyValue('--text-2').trim(),
      grid:    cs.getPropertyValue('--border').trim(),
    };
  }
  ```
- Every chart constructor reads `themeColors()` instead of hardcoded literals.
- Register a window-level event listener `window.addEventListener('themechange', …)` that destroys + reconstructs every chart instance. Maintain a registry: `_charts.nlv`, `_charts.bp`, `_charts.regime`, etc — already exists in journal.html.
- Toggle handler (Phase 3) dispatches `window.dispatchEvent(new Event('themechange'))`.
- ~15 chart instances total across templates. **Easy to miss one — keep a checklist**:
  - `portfolio_home.html`: none (text only)
  - `spx.html`: none (text)
  - `journal.html`: nlv, bp, regime, market (4)
  - `backtest.html`: spx-chart, equity-chart, …
  - `q041_backtest.html`, `q042_backtest.html`, `hvladder_backtest.html`, `aftermath_backtest.html`, `portfolio_backtest.html`, `es_backtest.html`: each ~1-3 charts
  - `matrix.html`: none (CSS grid only)
- **Acceptance**: AC5.
- **Tag**: `phase5-chart-theme-map`.

### Phase 6 — Visual QA pass (1-2 commits for fixes)

- Walk every page × both themes:
  - Strategy cards (badges, tier colors)
  - Banners (orange partial-data, red SchwAB reauth, orange ETrade reauth)
  - Chips (booster buffer 4-tier, IVP gate sub-block, payoff_type pills, quote-freshness LIVE/RECENT/STALE/EOD)
  - Tables (zebra rows, hover, column headers)
  - Modals (overlay opacity — 0.6 black-on-light is too dark; reconsider)
  - Tooltips (chart.js default tooltip works both)
  - Charts (axis ticks, grid lines, dataset colors)
- File one commit per "issue cluster" so each fix is bisectable.
- **Acceptance**: AC6.
- **Tag(s)**: `phase6-visual-qa-NNN`.

### Phase 7 — DESIGN.md + memory amendment

- DESIGN.md L92 amend: remove "Dark mode only" claim; add a section documenting both palettes are canonical and toggle is PM-controlled.
- Add memory entry under `feedback_` summarizing the new convention: any new template MUST link `theme.css` and NOT inline a `:root` block.
- **Acceptance**: AC7.
- **Tag**: `phase7-design-docs`.

---

## Acceptance criteria

| AC | Description | Verification |
|---|---|---|
| AC1 | `web/static/theme.css` exists and contains all 29 tokens | `grep -c "^  --" web/static/theme.css` ≥ 29 |
| AC2 | All 20 templates link to `theme.css` and no longer inline `:root` token block | `grep -c "^  --bg:" web/templates/*.html` returns 0 everywhere |
| AC3 | Toggle button in nav switches `<html data-theme>` and persists in localStorage | Browser test: click toggle, refresh, theme persists |
| AC4 | No raw hex / rgba color literals in templates outside the Chart.js explicit color map | `grep -E '#[0-9A-Fa-f]{6}\|rgba?\(' web/templates/*.html` returns only `_chart_theme.js` references |
| AC5 | All chart instances re-render with correct colors on theme toggle (no chart left in old theme) | Browser test on each backtest page + journal |
| AC6 | Visual QA pass: every page renders cleanly in both themes (banners, chips, modals, tooltips, tables) | PM walkthrough |
| AC7 | DESIGN.md amended; memory note added documenting theme.css convention for future templates | Read DESIGN.md L92 area; check memory MEMORY.md index |
| AC8 | Existing tests pass — `tests.test_spec_103 + 104 + 105 + 106 + 107` | `venv/bin/python -m unittest …` |
| AC9 | Per-broker color identity preserved in light mode: gold≠Schwab-equity-green≠ETrade-green≠ETrade-purple | Visual confirm on Account Positions panel both themes |
| AC10 | No FOUC (flash of unstyled content) on page load with `data-theme` already set | Test by clearing cache + loading with stored preference |

---

## What NOT to do

- **Don't** change any backend (`web/server.py`, `strategy/`, `etrade/`, `schwab/`, `signals/`, `scripts/`, `tests/`).
- **Don't** introduce a CSS framework (Tailwind, Bootstrap). Stay with hand-rolled CSS to keep the existing aesthetic + 1 file changeable.
- **Don't** change which colors mean what semantically. Gold still = options, green still = profit, red still = loss, etc. Only the hex values change between themes.
- **Don't** rename existing CSS vars. Templates assume `--text`, `--surface`, etc. Stability is required.
- **Don't** add per-component theme overrides (e.g., separate `.partial-banner-light` class). Stick to the var-driven approach.
- **Don't** merge any phase that visually breaks a page — bisectability is the whole point of phased commits.
- **Don't** auto-flip the booster `data-theme` based on time of day, market state, or stress flag. Theme is pure user preference.

---

## Risk / known traps

| Risk | Mitigation |
|---|---|
| Inline `color:${cond ? '#aaa' : '#bbb'}` strings missed by grep | Manual scan per template in Phase 4; track count down-to-zero |
| Chart constructed before theme listener registered → wrong colors on initial load | Initialize theme BEFORE any chart constructor runs (in `<head>` script) |
| Banner alpha (0.07) too transparent on white bg → banner disappears | Phase 2 includes `[data-theme="light"]` alpha tuning (try 0.10-0.15) |
| Modal overlay `rgba(0,0,0,0.6)` over light bg = too dark | Use `var(--overlay)` token; light version `rgba(0,0,0,0.3)` |
| Per-broker color collision in light mode (Schwab green and ETrade green merge) | Test on Account Positions panel; tweak hue distance if needed |
| Browser cache serves old per-template inline CSS after Phase 1 deploy | Cache-bust query param on the `<link>` tag (recommended above) |
| Forgetting to update a new template added post-SPEC | Memory note in Phase 7 documenting "any new template MUST link theme.css" |

---

## Backup / rollback

PM created two refs at the pre-implementation HEAD (commit `73c0256`):

- **Tag** `pre-light-theme-2026-05-27` (annotated, immutable)
- **Branch** `backup/pre-light-theme-2026-05-27`

Both pushed to `origin`. To roll back fully:

```bash
git checkout main
git reset --hard pre-light-theme-2026-05-27
git push --force-with-lease origin main
# Then on oldair:
#   cd ~/SPX_strat && git fetch && git reset --hard origin/main
#   launchctl stop com.spxstrat.web; launchctl start com.spxstrat.web
```

Per-phase rollback: each phase commit gets a phase tag (`phase1-theme-extract`, etc.) so you can roll back to any phase boundary without losing earlier progress.

---

## Estimated effort

| Phase | CC+gstack | Human |
|---|---|---|
| 1. Extract theme.css | 1.5h | 4h |
| 2. Light palette design | 0.5h | 4h (PM/designer judgement) |
| 3. Toggle UI + persistence | 0.5h | 1h |
| 4. Inline color cleanup | 3-4h | 1-2 days |
| 5. Chart.js theme map | 2-3h | 1 day |
| 6. Visual QA + fixes | 2h (visual review limited from CLI) | 1 day |
| 7. DESIGN.md + memory | 0.5h | 1h |
| **Total** | **~10h** | **~4-5 days** |

Polished result (accent retuning, chart axis contrast, edge-case banners): add ~2-3 human-days on top of MVP.

---

## Quant / PM checkpoints

- **After Phase 2**: PM reviews light palette before any cleanup work happens. Cheapest place to iterate on color choice.
- **After Phase 5**: PM walks all chart-heavy pages in both themes. Catches any chart that didn't get the theme listener.
- **After Phase 6**: PM final sign-off on visual QA matrix.

PM does NOT need to review Phase 1, 3, 4, 7 — those are mechanical refactors with binary correctness (page renders or it doesn't).

---

## Files expected to change

```
NEW:
  web/static/theme.css              (29 dark tokens + 25 light overrides)
  web/static/chart_theme.js         (theme color resolver + chart re-render hook)
                                    [or inline this in templates if static dir
                                     adds too much deploy overhead]

EDIT (20 templates — each loses ~30 lines of inline :root + many inline style="" colors):
  web/templates/aftermath.html
  web/templates/aftermath_backtest.html
  web/templates/backtest.html
  web/templates/es.html
  web/templates/es_backtest.html
  web/templates/etrade_reauth.html
  web/templates/hvladder.html
  web/templates/hvladder_backtest.html
  web/templates/journal.html
  web/templates/margin.html
  web/templates/matrix.html
  web/templates/performance.html
  web/templates/portfolio_backtest.html
  web/templates/portfolio_home.html
  web/templates/q041.html
  web/templates/q041_archive.html
  web/templates/q041_backtest.html
  web/templates/q042.html
  web/templates/q042_backtest.html
  web/templates/spx.html

EDIT (docs):
  DESIGN.md                         (L92 amendment, new "Themes" section)
  ~/.claude/projects/-Users-lienchen-Documents-workspace-SPX-strat/memory/
    MEMORY.md                       (new index entry)
    feedback_theme_convention.md    (new memory: any new template must link theme.css)
```

No `web/server.py`, no `tests/`, no `scripts/`, no `strategy/`, no `etrade/`, no `schwab/`.

---

## Quant validation contact

After deploy: I'll spot-check that:
- Per-broker color identity holds in light mode on Account Positions
- IVP gate buffer chips remain readable in both themes
- Quote freshness chips (LIVE/RECENT/STALE/EOD red) keep tier-distinct contrast in light mode

If anything regresses, ping me with the page + theme and I'll triage. Backup tag is the safety net — full revert is one command.
