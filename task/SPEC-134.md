# SPEC-134 — Chart.js 三件套 vendor 本地化（PM 批准 2026-07-07）

**问题**: 全站 10 个图表页面从 jsdelivr CDN 现场拉 chart.js@4.4.0 + chartjs-plugin-zoom@2.0.1 + chartjs-adapter-date-fns@3.0.0（每页 3 个外域请求）——CDN 故障/断网即全灭，且与 SPEC-132.1 给 lightweight-charts 定的"vendor 本地、零外域"红线自相矛盾。

## 改动

1. 三个文件按**现用 pinned 版本**下载 vendor 至 `web/static/vendor/`（保留版本号于文件名），随附各自 LICENSE
2. 全部模板的 CDN `<script src>` 换 `url_for('static', ...)`——逐一清点（backtest / es_backtest / q041_backtest / q042_backtest / q042 / aftermath_backtest / hvladder_backtest / portfolio_backtest / performance / journal，以 grep 实际命中为准，不漏 partial/include）
3. SPEC-132.1 的零外域静态扫描断言**升级为全模板范围**（此前若 scoped spx 则扩展）——今后任何模板出现 CDN token 即测试 fail

## AC

- 零行为变更：每页图表渲染前后一致（headless 冒烟：各页 200 + 零 console 错误 + canvas 存在）
- vendored 文件字节数与 CDN 对应版本一致（下载校验记录入 commit message）
- 全模板零外域 `<script src>` 断言（含 lightweight-charts 与本批三件套）
- oldair 部署后各页自托管回源 200

## 边界

不升级 Chart.js 版本（pinned 原版本，纯搬运）；不迁移任何图表到 lightweight-charts（选择性升级另议，见 132.1 评估——等 PM 用过 Structure Map v2 再定）。
