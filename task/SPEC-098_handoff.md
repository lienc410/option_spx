# SPEC-098 Handoff

## 修改文件

| 文件 | 改动 |
|---|---|
| `data/q042_backtest_trades.csv` | 新建；30 笔历史触发记录（`9404663`） |
| `web/server.py` | 新增 4 个端点：`/api/q042/state`（扩充）、`/api/q042/spx-history`、`/api/q042/backtest`、`/api/q042/paper`；新增路由 `/q042`、`/q042/backtest`（`0e682c7`） |
| `web/templates/q042.html` | 新建；Dashboard 页（C1-C5 + F5 caveat banner + strategy spec card） |
| `web/templates/q042_backtest.html` | 新建；Backtest 分析页（C6-C11 + 1yr/3yr/5yr/10yr/All range 按钮） |
| `web/templates/backtest.html` 等 10 个模板 | nav bar 新增 Q042 入口 |

## Commit 链（按时序）

| Commit | 内容 |
|---|---|
| `9404663` | data: add q042_backtest_trades.csv (30 historical triggers) |
| `0e682c7` | feat: SPEC-098 Q042 Dashboard + Backtest pages, 4 APIs, nav entry |
| `37f4734` | fix: q042 spx-history date format YYYY-MM-DD |
| `54c5afd` | fix: C6 chart full 19yr history + numeric index for scatter alignment |
| `155e7a2` | feat: 1yr/3yr/5yr/10yr/All range buttons for C6 SPX overlay |
| `1cb6f60` | feat: strategy spec card added to Q042 Dashboard |
| `0fe90ca` | fix: in-flight backtest positions recorded as MTM OPEN rows |

## 收尾

- 缓存清除：否（新路由无旧缓存）
- Web 重启：否（new routes picked up on next startup）
- Old Air 部署：已完成（git pull 至 `f84171a`，含全部 SPEC-098 commits）

## 验收结果

| AC | 项 | 结果 |
|---|---|---|
| AC1 | `/q042` 路由 200；nav bar Q042 入口 | ✅ |
| AC2 | `/q042/backtest` 路由 200 | ✅ |
| AC3 | C1 Sleeve 状态卡片（A/B state + ddATH% + 距触发距离）| ✅ |
| AC4 | C2 SPX + ATH 监控图（最近 252 TD）| ✅ |
| AC5 | C3 触发距离 gauge 数值正确 | ✅ |
| AC6 | C6 SPX overlay 含 30 笔 trade 的 entry/exit marker | ✅（`54c5afd` 修复 scatter 对齐）|
| AC7 | C7 累计 P&L 曲线；paper 段 fail-soft | ✅ |
| AC8 | C8 ddATH at trigger 直方图（A/B 分色）| ✅ |
| AC9 | C9 Sleeve 对比表（WR / avg P&L / worst / avg DTE held）| ✅ |
| AC10 | F5 caveat banner 可见 | ✅ |
| AC11 | `/api/q042/backtest` 返回 30 trades + summary；fail-soft | ✅（OPEN 行为 MTM 快照，summary 仅计 CLOSED；`0fe90ca`）|
| AC12 | 回归：SPX / /ES / /q041 / portfolio home 不受影响 | ✅ |

## 备注

- `data/q042_backtest_trades.csv` 中 `status=OPEN` 行为当前 in-flight 仓位的 MTM 快照（见 RESEARCH_LOG R-20260510-11）；`/api/q042/backtest` summary 排除这些行，仅统计 `CLOSED` trades，避免未实现盈亏污染 WR / avg P&L。
- `/api/q042/spx-history` 支持 `?full=1` 参数返回 2007 年至今完整历史（供 C6 全区间用）；默认返回最近 252 TD（供 C2 用）；TTL 3600s 内存缓存。
- Paper trades（`data/q042_paper_trades.jsonl`）当前为空；`/api/q042/paper` fail-soft 返回 `[]`，C7 paper 段不显示，不报错。
