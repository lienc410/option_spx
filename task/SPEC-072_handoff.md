# SPEC-072 Handoff

## 修改文件
- `web/static/spec072_helpers.js:1` — 新增 shared frontend helpers：`liveScaleFactor` / `formatDualBp` / `formatDualPnl` / `isBrokenWingIc`
- `web/templates/index.html:6` — 引入 `spec072_helpers.js`
- `web/templates/index.html:258` — 新增 broken-wing / dual-scale 样式
- `web/templates/index.html:872` — `buildLegs` 加入 broken-wing delta 高亮
- `web/templates/index.html:885` — `buildCard` 为 HIGH_VOL aftermath IC_HV recommendation 显示 dual-scale BP 与紫色 broken-wing badge
- `web/templates/backtest.html:8` — 引入 `spec072_helpers.js`
- `web/templates/backtest.html:218` — 新增 research disclaimer / dual-stack / legend note 样式
- `web/templates/backtest.html:956` — 新增 `spec064_aftermath_ic_hv` 专属 scale disclaimer
- `web/templates/backtest.html:1108` — 新增 `SPEC-071 addendum` legend 链接
- `web/templates/backtest.html:2004` — `updateResearchBanner()` 只在 `spec064_aftermath_ic_hv` 显示 scale disclaimer
- `web/templates/backtest.html:2448` — `renderTradeRows()` 在 `spec064_aftermath_ic_hv` view 的 HIGH_VOL 行显示 dual-scale P&L / premium / BP%
- `web/templates/margin.html:6` — 引入 `spec072_helpers.js`
- `web/templates/margin.html:204` — 新增 margin live dual-est 样式
- `web/templates/margin.html:642` — `loadLiveBp()` 同时读取 `/api/schwab/balances` 和 `/api/position`，在 HIGH_VOL 持仓时显示 dual-scale BP 文案

## 收尾
- 缓存清除：否
- Web 重启：否

## 验证结果
- 已确认：
  - Flask 页面渲染正常：`/`, `/backtest`, `/margin`, `/static/spec072_helpers.js` 均返回 `200`
  - `data/research_views.json` mtime 未变化
  - 仅前端文件发生变更；未修改 backend / engine / selector / artifact 文件
- 已运行：
  - `python - <<'PY' ... app.test_client() ... PY`（验证页面与 helper 脚本可加载）
  - `git diff --stat -- web/templates/index.html web/templates/backtest.html web/templates/margin.html web/static/spec072_helpers.js`
  - `stat -f '%m %N' data/research_views.json`

## 阻塞 / 备注
- 本次没有做浏览器人工 smoke test；`AC2`–`AC8` / `AC10` 仍需 Quant / PM 在浏览器中完成视觉确认
- `F5` 按 `ST3` 收窄到 `spec064_aftermath_ic_hv` 研究视图中的 HIGH_VOL 行；production view 维持单列
- `F6` 以 margin 页面 live box 的 dual-scale BP 文案实现；未引入 backend 新字段
