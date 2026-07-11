# SPEC-139 — 可选池小批清扫（PM 批准 2026-07-11，Opus）

三件独立小活,一批扫清。F6 裸 except 全面扩展**不做**(PM 采纳 Quant 建议:已覆盖资金流关键路径,余为有意 fail-soft,边际近零)。

## 1. Gateway send-ledger（DEFERRED #22）

**缺口**: `notify/gateway.py` 只在 dedupe/clear 时 log,成功发送零日志;`event_push._send` 只累加 `push_stats.json` 计数(sent/fallback/failed),不记**每条**的分类/about/key → SPEC-126 完整验收无法溯源"每天 ~7 条无 key 静默件是谁"。

**修**: `event_push._send` 成功发送后追加一行到 `logs/push_ledger.jsonl`(strict-JSON,保留最近 14 日,与 push_stats 同 rotation): `{ts, category, about, title_head(前40字), dedupe_key(或 null), quiet, fallback}`。gateway `push()` 把 category/about/dedupe_key 透传给 `_send`(现在 `_send` 只收 text,需加可选 meta 参数,不破坏既有 caller)。

**AC**: 发一条走 gateway → ledger 有对应行且字段齐;无 key 件也记(key=null);SPEC-130 guard 未过时零 ledger 行(禁发即禁记);rotation 保留 14 日;既有 `_send(text)` 裸调用向后兼容(meta 全 optional)。

## 2. Google Fonts 自托管

**缺口**: 22 个模板从 `fonts.googleapis.com`/`fonts.gstatic.com` 拉三家字体(Newsreader/JetBrains Mono/DM Sans)——全站最后的外域依赖,断网/CDN 故障时字体降级到系统 fallback。与 SPEC-134(Chart.js 自托管)、SPEC-132.1(lightweight-charts vendored)确立的"零外域"姿态不一致。

**修**: 下载三家字体的 woff2(按 DESIGN.md §Typography 精确字重: Newsreader ital+400/600 opsz 6..72、JetBrains Mono 400/500/600、DM Sans 300/400/500 opsz 9..40)vendor 至 `web/static/fonts/`;`theme.css` 加 `@font-face`(font-display:swap 保留);删除 22 模板的 `<link href="fonts.g...">` 与 preconnect(单源到 theme.css)。

**AC**: 全模板零 `fonts.google`/`gstatic` 引用(静态扫描,同 SPEC-134 断言扩展);woff2 字节校验记 commit;三家字体三字重 headless 渲染确认(Newsreader 斜体 recommendation 叙事、JetBrains Mono 数字、DM Sans UI 均正确上屏);双主题;License(SIL OFL)随附 `web/static/fonts/*.LICENSE`。

## 3. Lane B 历史回放落盘

**缺口**: Decision Trace 30 日切换目前 Lane A 有历史(recommendation_log 存档),但 **Lane B(持仓动作)未存档**——回放历史日时 Lane B 空。`web/server.py:6496` 已如实标注此缺口。

**修**: 每日 trace 生成时(晨报路径 `append_recommendation_event` 同处),把当日 Lane B 的 `short_leg_actions`(每个 open 仓的 21-DTE/collapse/profit-target/止损锚触发器读数)一并存进 recommendation_log 行的扩展字段;`/api/decision-trace?date=` 回放历史日时读该字段渲染 Lane B(无字段的旧行如实标"该日 Lane B 未存档"降级,不伪造)。

**AC**: 今日 trace 落盘含 lane_b 快照;历史回放读到有字段的行渲染 Lane B、无字段行标注降级(不空白不伪造);strict-JSON;Lane A/C/D 回放零回归;字段纯附加(recommendation_log 既有字段逐字节不变)。

## 交付约束

worktree 隔离;推分支 `spec-139` 不碰 main 不部署;每件独立 commit;全量 pytest 零新增失败;Quant 合并验收(gateway ledger 实发一条看落盘 + 字体 browse 实看 + Lane B 回放实测)后统一部署。回报附字体渲染截图路径。
