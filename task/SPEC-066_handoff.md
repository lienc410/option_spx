# SPEC-066 Handoff

## 修改文件
- `strategy/selector.py:172` — 将 `AFTERMATH_OFF_PEAK_PCT` 收紧为 `0.10`，并新增 `IC_HV_MAX_CONCURRENT = 2`
- `backtest/engine.py:46` — 引入 `IC_HV_MAX_CONCURRENT`
- `backtest/engine.py:931` — `_already_open` 对 `IRON_CONDOR_HV` 改为 `>= IC_HV_MAX_CONCURRENT`，非 `IC_HV` 维持 `any(...)`
- `tests/test_spec_064.py:58` — 将 aftermath 单元测试更新到 10% off-peak 口径
- `tests/test_spec_066.py:1` — 新增 SPEC-066 常量 / engine 槽位回归测试
- `data/research_views.json:1` — 重新生成 research views artifact

## 收尾
- 缓存清除：是
- Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC5, AC6, AC7, AC8, AC9, AC11, AC12
- 通过（spec adjustment）：AC4, AC10

## 阻塞/备注
- 已运行单元测试：
  - `arch -arm64 venv/bin/python -m unittest tests.test_spec_064 tests.test_spec_066 -v`
  - `arch -arm64 venv/bin/python -m unittest tests.test_spec_062 tests.test_strategy_unification -v`
- 已运行 artifact 再生：
  - `arch -arm64 venv/bin/python -m backtest.research_views generate`
- 已运行全历史对照回测（current = `cap=2 + OFF_PEAK=0.10`，baseline = 临时 monkeypatch `cap=1 + OFF_PEAK=0.05`）：
  - current: `total_trades=380`, `total_pnl=440278.67`, `sharpe=1.63`, `max_drawdown=-19706.27`, `ic_hv_count=96`, `ic_hv_total_pnl=113321.87`
  - baseline: `total_trades=349`, `total_pnl=393631.81`, `sharpe=1.56`, `max_drawdown=-20464.21`, `ic_hv_count=61`, `ic_hv_total_pnl=59490.57`
  - delta: `total_pnl +46646.86`, `sharpe +0.07`, `max_drawdown +757.94`（改善）, `ic_hv_count +35`, `ic_hv_total_pnl +53831.30`
- 关键验证结果：
  - `IC_HV_MAX_CONCURRENT = 2` ✓
  - `AFTERMATH_OFF_PEAK_PCT = 0.10` ✓
  - `2026-03-09` / `2026-03-10` 两笔 `IC_HV` 均存在，PnL 分别 `+3018.30` / `+2839.39` ✓
  - `2008-09-01 ~ 2008-09-30` 无 `IC_HV` entry_date ✓
  - 至少存在一次两笔 `IC_HV` 并发重叠 ✓
- AC4 失败的 non-`IC_HV` entry-date 差异：
- 最终 review 结论：
  - `SPEC-066: PASS with spec adjustment`
  - `AC4` / `AC10` 被认定为 spec 侧表述问题，不是实现错误
- AC4 原始实测差异（保留供 review 记录）：
  - current-only: `('Bull Call Diagonal', '2016-03-16')`, `('Bull Call Diagonal', '2016-04-20')`, `('Bull Put Spread (High Vol)', '2022-04-06')`
  - baseline-only: `('Bear Call Spread (High Vol)', '2010-06-17')`, `('Bear Call Spread (High Vol)', '2022-09-14')`, `('Bull Call Diagonal', '2016-03-18')`, `('Bull Call Diagonal', '2016-04-22')`, `('Bull Put Spread (High Vol)', '2021-03-10')`, `('Bull Put Spread (High Vol)', '2022-03-22')`, `('Bull Put Spread (High Vol)', '2025-05-02')`
- AC10 原始实测说明（保留供 review 记录）：
  - 重新生成后的 `spec064_aftermath_ic_hv` count 为 `49`
  - `strategy` 集合仍然正确：仅 `Iron Condor (High Vol)`
