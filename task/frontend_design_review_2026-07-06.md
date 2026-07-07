# 前端设计审计 Findings — 2026-07-06

**Reviewer**: 前端工程师（设计审计 subagent，三方 review 之一，charter: `task/FRONTEND_REVIEW_charter_2026-07-06.md`）
**范围**: `web/templates/` 全部 22 个模板 vs `DESIGN.md`（binding）+ `web/static/theme.css`（token 真值）+ house 规则（`--text-muted` ban 等）
**不在本 lane**: 策略数字/参数正确性（quant 主会话负责）；仅当展示结构导致误读时标记

**先说通过项**（全站验证过、无需修复）：
- 22/22 模板均 link `theme.css` + `theme_bootstrap.js` + `theme.js`，0 个自建 `:root` token 块 ✓
- 硬编码 hex 颜色全站仅 3 处（chart hover `#fff`，可忽略）✓
- 7 个回测页中 6 个有完整 Trading Discipline 五分类（Entry/Exit/Sizing/Risk/Frequency）✓
- page-tab 家族内部（SPX 三页 / ES 两页 / Q042 / Aftermath / Q041 / HV Ladder）各自一致 ✓
- `.discipline-val` / `.rule-val` 用 `--f-ui` 是正确的（DESIGN.md 规定 rule prose 非数字）✓

---

## Top-10 最高影响项

| # | 页面 | 问题 | 严重度 |
|---|------|------|--------|
| 1 | spx.html:1235 | **PAPER badge 用橙色** (`badge-orange`) — DESIGN.md 明文 "PAPER deliberately does NOT use orange (orange = WARNING)"，paper 仓位会被读成告警 | **high** |
| 2 | performance.html:127,354 | **PAPER badge 用金色** `.tag`（gold = LIVE tier / REVIEW 语义）— paper trade 视觉上冒充 live；且同一 `.tag` 同时用于合约数 "2x"（356 行），一个视觉 token 两种语义 | **high** |
| 3 | matrix.html:860 | **live signals 加载失败的关键 caveat 用 `--text-muted`**（house ban：PM 必读内容禁用）且是英文 status message（规则：错误/状态消息中文）— 这条 caveat 决定整页 matrix 怎么读，是全页最重要的一行字却最暗 | **high** |
| 4 | hvladder_backtest.html:268-296 | **Trading Discipline 用自造 variant**：`.rule-row/.rule-key/.rule-val` 而非规定的 `.discipline-*` 类；分类是 Entry/Size/Roll·Stop/Max Risk 四类，缺 Frequency、Exit 改名 — DESIGN.md："Copy the canonical CSS block… do not invent variants" + 五分类 mandatory | **high** |
| 5 | portfolio_home.html:1954-1987 | **NLV 状态行用 `--text-muted`**（"NLV history pending — first snapshot at 16:30 ET" / "NLV unavailable" / label "NLV"）— house 已 4+ 次重犯的 banned 用法，PM 必读的 label/status 必须 `--text-2` | **high**（规则本身 med，累犯升级） |
| 6 | portfolio_home.html:1599-1607（全站） | **Action-state 词汇漂移**：同屏同语义（今日无 setup）SPX 卡显示 `NO ENTRY`、Q041/Q042/ES 卡显示 `WAIT`；另有 `READ ONLY`/`WAITING`/`SKIPPED`/`CHANGED`/`CONFIRMED`/`CALM`（spx.html:751,760）均不在 DESIGN.md Action State Vocabulary 七态表内 | **med-high** |
| 7 | 全站 nav | **导航集不一致**：`Book` 仅 3/12 页有（portfolio_home/funds/partnership）；`/ES` 仅 es.html 自己有；partnership.html:124-132 缺 `Stress Put Ladder`；DESIGN.md §Navigation 词表（Settled VIX/Q041/Drawdown Overlay/Backtest）已与实现全面脱节 | **med-high** |
| 8 | portfolio_home.html:1093 | **nav 项带 tier 指示器**：`Stress Put Ladder <sup>RESEARCH</sup>`（橙色 sup + opacity:0.65 inline style）— DESIGN.md §Navigation 明文 "no indicator on nav items"；且 RESEARCH tier 规定色是蓝，不是橙 | **med** |
| 9 | backtest.html:1009-1040 + hvladder_backtest.html:314-323 | **必备 metric 卡缺失**：SPX 回测页缺 `Annualized ROE`（7 缺 1）；HV Ladder 回测页缺 `Win Rate`/`Avg P&L`/`Total P&L`（其余 5 个回测页齐全）— DESIGN.md 回测模板卡片清单是 hard requirement | **med** |
| 10 | es.html:272 vs hvladder.html:203 vs es_backtest.html:742 | **/ES 生命周期展示三处互相矛盾**：/es 页 hero 挂 `Secondary` tier badge + "Today's Signal" 活跃卡；hvladder 称它 "Legacy /ES view (no longer trading)"；es_backtest 内嵌 tab 称 "[archived]" — 展示结构让 PM 无法判断该策略是否还在交易（内容真值归 quant，但结构性矛盾是展示问题） | **med** |

---

## 分页明细

### portfolio_home.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| portfolio_home.html:1954,1958,1962,1987 | NLV 状态/label 行用 `--text-muted`（如 `<span style="color:var(--text-muted)">NLV history pending — first snapshot at 16:30 ET</span>`） | house ban：`--text-muted` 仅限占位符；Color §text | high | 全部改 `--text-2` |
| portfolio_home.html:1782 | 「暂无报价（盘后 / 未找到合约）」用 `--text-muted` — 边界情况（占位 vs 状态），但含 PM 需要的原因说明 | 同上 | low | 改 `--text-2` 或拆分：占位符号 muted、原因 text-2 |
| portfolio_home.html:1599,1603,1606,1879 | `NO ENTRY` vs `WAIT` vs `READ ONLY` vs `WAITING` 混用，后三者不在 Action State 词表 | Action State Vocabulary | med | 统一 `WAIT`→`NO ENTRY`；`READ ONLY`/`WAITING`/`SKIPPED` 等 2nd-signal 态要么并入词表（DESIGN.md 加一节）要么改用现有七态 |
| portfolio_home.html:1093 | nav 项 inline `<sup>RESEARCH</sup>`（橙）+ `opacity:0.65` | §Navigation "no indicator on nav items"；tier RESEARCH = blue | med | 去掉 sup 与 opacity；tier 信息留给页面内容 |
| portfolio_home.html:1091,1094 | nav label `DD Overlay` / `Sleeves` vs DESIGN.md 决定的 `Drawdown Overlay` / `Q041` | Decisions Log 2026-05-10 + §Navigation | med | 二选一：改回 DESIGN 词表，或在 DESIGN.md Decisions Log 补登 rename 决定（见"系统性"节） |
| portfolio_home.html:249,262,647,693,713,721,743 | 7 处 11px padding/margin（discouraged legacy 值） | §Spacing "11px → 12px (md)" | low | 顺手重构时归到 12px，不必专项 |
| portfolio_home.html:2 张表无 overflow-x 容器（5 列） | 窄屏可能溢出 | 可读性 | low | 列少风险小，包一层 `overflow-x:auto` 即可 |

### spx.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| spx.html:1235 | `paper_trade` → `<span class="badge badge-orange">PAPER</span>` | Tier Badge 表 + Decisions Log："PAPER uses muted badge-obs not orange" | **high** | 改 `badge-obs` 样式（muted gray） |
| spx.html:740-768 | 无 page-hero/h1（intraday bar → tabs → decision strip）；同家族 backtest.html 有 1.5rem serif 标题，matrix.html 也没有 — 三页三种头部 | §Layout 家族一致性；heading scale | med | 家族统一：要么三页都加同规格 hero，要么 backtest.html 也去掉（action-first 论据成立的话）并在 DESIGN.md 记录 |
| spx.html:751,760 | `CALM` badge（intraday monitor）不在任何 badge 词表 | Action State Vocabulary | low | 并入词表或注明 monitor 态独立域 |
| spx.html:157 | `padding: 15px 17px 14px` — 15/17 均 off-scale（17 明文 discouraged） | §Spacing | low | → 16px |
| spx.html:1233 | 持仓面板 `meta.emoji`（📋 等）做视觉图标 | §Aesthetic "no illustration"（emoji 属装饰） | low | 换 mono 字符或删；单用户容忍度高，低优先 |

### backtest.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| backtest.html:1009-1040 | metric 行 6 卡，缺 `Annualized ROE` | §Backtest Template 必备 7 卡 | med | 加第 7 卡（数据源 quant 定口径） |
| backtest.html:2522 | `Chart.defaults.color = 'var(--text-muted)'` — 全部坐标轴刻度数字取最暗 token | house ban（数字是 PM 必读）；typography Rule | med | 改 `--text-2`（其余回测页轴刻度就是 text-2，顺带解决页间不一致） |
| backtest.html:1242 | 中英句内混写：`… DTE 30 · 或 Iron Condor if trend NEUTRAL` — 中文连词接英文条件从句 | §Language DOM-level rule（sentence-level violation 例子几乎同款） | med | 整句单语言：`或 IC（trend NEUTRAL 时）` |
| backtest.html:1110-1113 | 图例 `Open — 盈利` / `Close — 亏损` 元素内混语言，且图例属 chart chrome 应英文 | §Language 表 "Chart axes…English" | low-med | `Open · Win` / `Close · Loss`（win/loss 属 jargon 亦可） |
| backtest.html:837-1007 | metric 行前插了 controls + 可折叠 params 面板 | §Backtest Template "top of page, after page tabs" | low | on-demand 页 controls 前置合理；建议 params 面板默认折叠移到 metric 行之后，或在 DESIGN.md 给 on-demand 页豁免注记 |
| backtest.html:477 | `padding: 11px 18px` off-scale | §Spacing | low | → 12px |

### matrix.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| matrix.html:860 | `Could not load live signals — matrix below shows canonical selector paths…` 用 `--text-muted` italic 0.75rem + 英文 | house ban + §Language 错误/状态消息中文 | **high** | 升为可见 banner（`--orange-bg` 或 gray notice 卡），文案中文；这是决定全页读法的 caveat |
| matrix.html:390-396 | 无 page-hero/h1，body 直接 tabs | 家族一致性（同 spx 条目） | med | 与 spx/backtest 一并统一 |
| matrix.html:404-420 | "How to read this matrix" 长段英文叙事 + ℹ️/📊 emoji | §Language 叙事中文；§Aesthetic 装饰 | low | 文案中文化（术语豁免够用）；emoji 换字符 |
| matrix.html:944,974 | Loading/空态 `--text-muted` italic | 占位符 → 合规 | — | 无需修 |

### es.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| es.html:44-45 | `.page-title { font-family: var(--f-ui); font-size: 1.80rem; }` — 全站唯一 sans 页标题 | §Typography Display/Hero = Newsreader | med | 改 `--f-display`，size 对齐家族 |
| es.html:272 | hero 挂 `Secondary` tier badge，页面呈现活跃策略（"Today's Signal"），但 hvladder.html:203 称其 "no longer trading"、es_backtest.html:742 称 "[archived]" | 展示结构矛盾（Tier Badge 语义） | med | 若已退役：hero 改 RETIRED 头 + 顶部归档 banner（参照 q041_archive.html 模式）；若未退役：修正 hvladder 措辞 — 判定归 quant/PM |
| es.html:279-281 | A5 披露行整段用 `--orange` 色 f-mono meta；关键披露但样式是"又一行 meta"，且与 hvladder 两页同一披露三种文案/排版 | 一致性；信息层级 | low-med | 三处披露统一成同一 notice 组件样式 |
| es.html:337-340 | `Deferred` badge + 英文叙事卡 | badge 词表未收录；叙事应中文 | low | 文案中文化；Deferred 收进词表或换 `badge-obs` |

### es_backtest.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| es_backtest.html:243-261 | **标记嵌套 bug**：`.page-hero` 未在 flex 块后闭合，`.page-tabs` 被包进 hero 内（261 行的 `</div>` 才闭 hero）— tabs 下间距 24px（hero margin）而非家族的 14px，语义结构错 | §Layout；4px spacing scale | med | 把 `</div>` 移到 page-tabs 之前 |
| es_backtest.html:41 | h1 1.6rem vs 家族其他页 1.7/1.8rem | heading scale | low | 见"系统性"heading 条目 |
| es_backtest.html:742-746,913 | 内嵌 "Stress Put Ladder [archived]" tab + 英文归档说明 | §Language 叙事中文 | low | 文案中文化 |

### hvladder.html / hvladder_backtest.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| hvladder_backtest.html:268-296 | Trading Discipline 自造 `.rule-*` 类、四分类（Entry/Size/Roll·Stop/Max Risk）、缺 Frequency | §Backtest Template 3 "do not invent variants" + 五分类 mandatory | **high** | 换 canonical `.discipline-*` CSS；重排为 Entry/Exit/Sizing/Risk/Frequency（cadence ≥5TD 内容已有，归入 Frequency 行即可） |
| hvladder_backtest.html:314-323 | metric 行缺 Win Rate / Avg P&L / Total P&L | §Backtest Template 必备卡 | med | 补 3 卡（数据已在 API metrics 内） |
| hvladder_backtest.html:227-230 | 图例 `入场/出场/盈/亏` 中文 chart chrome；其他回测页图例英文 | §Language "Chart axes…English"；一致性 | low-med | 改 Entry/Exit/Win/Loss |
| hvladder.html:217, hvladder_backtest.html:206 | SPEC-104 banner 用 `linear-gradient` | §Aesthetic "no gradients" | low | 平色 `--orange-bg` + border 已足够 |
| hvladder.html:222-227 | banner 内 `NO PRODUCTION EXECUTION` font-weight:800（token 外权重）+ 全英叙事 | typography 权重域；§Language | low | 700 上限；文案可保留（警示 token 论） |
| hvladder_backtest.html:252 | 按钮 `↩ 全局` 中文 | §Language buttons English | med（全站群修，见系统性） | → `↩ Reset` 或 `↩ All` |

### q041.html / q041_backtest.html / q041_archive.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| q041.html:213 | 混语句：`0 fire in observation period verifies cash-bound boundary（按 PM ratify 这是成功，非失败）` — 英文完整主谓句 + 中文括注同元素 | §Language sentence-level rule | med | 整句中文：`观察期 0 fire 即验证 cash-bound 边界…` |
| q041.html:203 | Retired badge 全 inline style 手写（重复 `badge-unavail` 样式） | Tier Badge 表规定 class 复用 | low-med | 换 `.badge-unavail`（页内定义或抽公共） |
| q041.html:297 | 按钮 `展开 +10 / +20 详情 ▾` 中文 | buttons English | med（群修） | → `Expand +10/+20 detail` |
| q041.html:201,210,218,254-257 | 大段 inline style 块（banner/卡片整段手写样式） | 一致性（ad-hoc styles fighting theme） | low | 抽 class；行为不变 |
| q041_backtest.html:962 | `RETIRED — 已被 /ES short put 替代` 用 `--text-muted` italic（PM 必读的退役说明） | house ban | med | 改 `--text-2`（RETIRED token 保留英文合规） |
| q041_archive.html:105 | `结论是 /ES 在 capital efficiency（PM SPAN vs full notional CSP）` — 术语豁免边缘内 | §Language jargon exemption | — | 可不修 |

### q042.html / q042_backtest.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| q042.html:183, q042_backtest.html:111 | h1 `Q042 DD Overlay` / `Q042 Backtest & History` — 展示名决定是 "Drawdown Overlay"，"Q042" 只该活在 route | Decisions Log 2026-05-10 | med | h1 → `Drawdown Overlay`；或 PM 正式改判并更新 DESIGN.md |
| q042_backtest.html:285 | 按钮 `↩ 全局` | buttons English | med（群修） | 同上 |
| q042_backtest.html 表 7 列无滚动容器 | 窄屏溢出风险 | 可读性 | low | 包 `overflow-x:auto` |

### aftermath.html / aftermath_backtest.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| aftermath.html:31 | `.page-meta` 用 `--f-ui` 0.70rem — 全站其余 page-meta 为 `--f-mono` 0.65-0.68rem | 一致性 | low | 对齐 f-mono |
| aftermath.html:87 | meta 行 `观察期独立surface` 缺空格、中英贴连 | §Language 排版 | low | `观察期独立 surface` |
| aftermath_backtest.html:132 | card-title `Summary · 历史 aftermath 窗口` — 标题双语拼接（表头/标题位规定英文） | §Language 表 headers English | low | `Summary · Historical Windows` 或全中文标题（该位规则二选一，建议英文） |
| aftermath_backtest.html:194 | 按钮 `↩ 全局` | buttons English | med（群修） | 同上 |
| aftermath_backtest.html:586-592 | 7 列 Historical Windows 表全 inline style + 无滚动容器 | 一致性；可读性 | low | 抽 class + `overflow-x:auto` |

### performance.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| performance.html:127-131,354 | `.tag`（gold）渲染 `PAPER` — 金 = LIVE/REVIEW 语义，paper 仓位视觉冒充 live | Tier Badge 表：PAPER = muted `badge-obs` | **high** | PAPER 用 muted gray 样式；`.tag` 保留给别的用途 |
| performance.html:357 | 同一 `.tag` 又用于合约数 `${row.contracts}x` — 一 token 两义 | badge 语义唯一性 | low-med | 合约数改无边框 mono 文本或独立 class |
| performance.html:73,123 | 卡片背景 `linear-gradient` | §Aesthetic "no gradients" | low | 平色 surface-hi |
| performance.html:109 | `padding: 11px 8px` off-scale | §Spacing | low | → 12px |

### margin.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| margin.html:469 | `— Usable BP ceiling (70%) —` 刻度标记用 `--text-muted`（解读整个 bar 图必读） | house ban | med | 改 `--text-2` |
| margin.html:224-227 | page-title 1.5rem（低于 display 档 1.6rem+）；page-sub 内数字 `$150,000` / `2%` 非 mono | §Typography scale + mono rule | low | title 对齐家族；数字包 mono span（数值本身对不对归 quant） |
| margin.html 5 张表无滚动容器 | 2-4 列，窄，实际风险低 | 可读性 | low | 可不修 |

### funds.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| funds.html:180,224,225 | 按钮 `＋ 记录减仓` / `取消` / `记录` 中文 | §Language buttons English | med（群修） | → `+ Record` / `Cancel` / `Save`；若 PM 判定基金工具整体豁免（中文域工具），在 DESIGN.md 记录豁免 |
| funds.html:334 | `action-badge` 内容是中文规则文案截断（`(f.action||'').split('｜')[0]…substring(0,16)`） | "Badge text is always English" | low-med | 同上豁免决定；或映射规则 ①-⑥ → 英文短码（R1-R6） |
| funds.html:371 | 11 列 fund-table 无 `overflow-x` 容器（880px 页最宽表） | 可读性/scroll containers | med | 包 `overflow-x:auto` |
| funds.html:119 | modal 遮罩硬编码 `rgba(0,0,0,0.55)`，light 主题下不随 `--overlay` 变 | §Theme 颜色须走 shared vars | low | → `var(--overlay)` |
| funds.html:177 | h1 `基金 清仓信号` 中文 — 全站唯一中文 h1 | 一致性（h1 位无明文规则，但 21/22 页英文） | low | 随豁免决定一起定 |

### partnership.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| partnership.html:124-132 | nav 缺 `Stress Put Ladder`（其余页都有） | nav 一致性 | med（并入 nav 群修） | 统一 nav include/宏 |
| partnership.html:259,282 | 8 列 book-table 无滚动容器 | 可读性 | low | 包 `overflow-x:auto` |
| partnership.html:226 | live-caveat `⚠ 实时值取自…未确认…` 合规（中文状态消息 + text-2）| — | — | 无需修 |

### journal.html / etrade_reauth.html / portfolio_backtest.html

| 页面 | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| journal.html | 结构、badge、mono、层级检查全部通过；仅 warmup banner 英文叙事 | §Language | low | 可不修 |
| etrade_reauth.html:112,152 vs 121,148 | 同页按钮语言混用：`↻ 重新获取链接` / `E-Trade 报错了?` 中文 vs `→ Get authorization link` 英文 | buttons English + 页内一致性 | med（群修） | 统一英文（或全中文 + DESIGN.md 豁免，但别混） |
| portfolio_backtest.html:257 | 按钮 `↩ 全局` | buttons English | med（群修） | 同上 |
| portfolio_backtest.html | 无 entry/exit 价格叠加图 — 属 Account/cross-strategy 页（BP 模拟），非 per-strategy backtest，判定不适用模板 | §Backtest Template 适用域 | — | 建议 DESIGN.md 明文注明豁免，堵住未来争议 |
| portfolio_backtest.html:99 | `padding: 11px 14px 9px` off-scale 11 | §Spacing | low | → 12px |

---

## 系统性（跨页）findings

| # | Finding | DESIGN.md 规则 | 严重度 | 建议修复 |
|---|---|---|---|---|
| S1 | **nav 无单一真值源**：12 份手拷贝 nav，集合各不相同（Book 3/12、/ES 1/12、partnership 缺一项、hvladder 项带 inline 装饰）；DESIGN.md §Navigation 词表已过时两代 | §Navigation | med-high | 抽 Jinja include/宏统一渲染；同批更新 DESIGN.md nav 词表与 Decisions Log（Sleeves/DD Overlay/Stress Put Ladder 等 rename 正式化） |
| S2 | **按钮中文群**：6 页 10 处（明细见各页）— 唯一系统性语言位违规；`↩ 全局` 一款就出现在 4 页 | §Language buttons English | med | 一批全修（或 PM 对 funds/etrade_reauth 工具页明文豁免） |
| S3 | **heading scale 漂移**：page 级标题 6 种尺寸（1.5 / 1.6 / 1.65 / 1.7 / 1.8 / 2.1rem），backtest/margin 低于 display 档下限；es.html 还错字体 | §Typography scale "display: 1.60rem+" | med | 定两档（如 portfolio 2.1 / 其余 1.7）写进 DESIGN.md，全站对齐 |
| S4 | **badge/action-state 词表失控**：词表外标签 ≥10 个（WAIT/READ ONLY/WAITING/SKIPPED/CHANGED/CONFIRMED/TIMEOUT/CALM/Deferred/N/A），且各页 badge class 命名不同（`state-badge` vs `state-pill` vs `tier-badge` vs `.tag` vs inline） | Action State + Tier Badge Vocabulary | med | DESIGN.md 词表扩一节"signal-outcome states"收编合法项，其余归一到七态；class 收敛到 badge-* 家族 |
| S5 | **gradients**：7 页 17 处 `linear-gradient`（多为 4-6% alpha 微渐变） | §Aesthetic "no gradients" | low | 二选一：全删成平色，或 DESIGN.md 把"≤8% alpha 表面渐变"列为 blessed 例外 — 别留灰色地带 |
| S6 | **英文叙事残留**：matrix helper、hvladder banner、es_backtest 归档说明、journal warmup、etrade hero 等长段英文叙事位 | §Language 叙事/状态中文 | low | 低优先批量中文化；术语豁免足够覆盖 |
| S7 | **off-scale 11px 群**（14 处，6 页） | §Spacing discouraged 表 | low | 重构顺手修，不专项 |

---

## 与 quant/dev 的交接注记

- #2/#1（PAPER 颜色）与 quant 的 SPEC-113/124 文案核对同卡片，建议 SPEC-125 同批修
- #10（/ES 生命周期矛盾）需要 quant 先给"是否退役"真值，前端才能定 hero 处理
- matrix.html:860 修复时 quant 应同步核对该 fallback 文案的内容准确性（"canonical selector paths when guardrails pass" 的口径）
- funds/etrade_reauth 语言豁免是 PM 决策项，不是工程决策
