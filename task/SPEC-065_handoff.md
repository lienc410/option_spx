# SPEC-065 Handoff

## 修改文件
- `backtest/research_views.py:66` — 新增 `_run_with_aftermath_disabled()`，并产出 `spec064_aftermath_ic_hv` view
- `web/templates/backtest.html:942` — research pill bar 追加 `SPEC-064 Aftermath` 按钮
- `tests/test_spec_062.py:41` — 扩展 research views 测试，覆盖第 4 个 view key 和 trade count/filter
- `data/research_views.json:1` — 再生 artifact，包含第 4 个 SPEC-064 view

## 收尾
- 缓存清除：否
- Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3
- 未通过：AC4, AC5, AC6, AC7, AC8, AC9 → 尚未做浏览器 / 页面人工验收

## 阻塞/备注
- 单元测试已通过：
  - `arch -arm64 venv/bin/python -m unittest tests.test_spec_062 -v`
- artifact 已再生：
  - `arch -arm64 venv/bin/python -m backtest.research_views generate`
- 本地 artifact 核对：
  - view keys = `baseline`, `q015_ivp55_marginal`, `q016_dza_recovery_bps`, `spec064_aftermath_ic_hv`
  - `spec064_aftermath_ic_hv.trades` 数量 = `32`
  - 所有 `strategy` 均为 `Iron Condor (High Vol)`
- `Trade` 当前不携带 `rationale` 字段，因此 generator 侧采用 `baseline ∖ aftermath-disabled ∧ strategy == IC_HV` 作为精确边际集合口径；实测结果与 SPEC-064 handoff 的 32 笔集合一致。
