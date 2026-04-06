# SPEC-031_032 Handoff

## 修改文件
- `web/server.py:19` — `/api/backtest/stats` 新增 `avg_pnl`，并加 schema version 让旧磁盘缓存失效
- `web/templates/index.html:96` — Dashboard 新增 Decision Strip、Risk Flag Bar、Historical Edge、Position days_held / DTE estimate
- `web/templates/matrix.html:212` — Matrix stats 行新增 `avg_pnl` 正负着色展示
- `web/templates/backtest.html:490` — Grid Search 新增 OOS warning，Backtest 新增 Annual P&L by Year chart
- `strategy/selector.py:174` — `Recommendation` 新增 `canonical_strategy`、`re_enable_hint`、`overlay_mode`、`shock_mode`
- `strategy/selector.py:317` — guardrail `REDUCE_WAIT` 路径补 canonical strategy 和 re-enable hint
- `tests/test_state_and_api.py:68` — 新增 recommendation 新字段与 backtest stats `avg_pnl` API 回归
- `tests/test_strategy_unification.py:78` — 新增 backwardation / VIX-rising canonical + hint 回归

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：SPEC-031#1,#2,#3,#4,#6（模板/API 代码路径已落地，后端 stats/recommendation 回归通过）
- 通过：SPEC-032#5,#6（`/api/recommendation` 新字段存在；EXTREME/BACKWARDATION/VIX RISING 主 guardrail 路径已填 canonical/hint）
- 未通过：SPEC-031#5,#7；SPEC-032#1,#2,#3,#4,#7 → 未做浏览器端手工验收，仅完成模板代码与 Python/API 层回归

## 阻塞/备注
- `venv/bin/python -m unittest discover -s tests -v` → 30/30 通过
- `venv/bin/python -m compileall web strategy tests` 通过
- 因为 `web/server.py` 的 stats schema 扩展为 `avg_pnl`，已运行的 web 进程若仍持有旧内存 cache，需要重启 `com.spxstrat.web` 才能确保页面拿到新 payload
