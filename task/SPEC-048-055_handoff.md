# SPEC-048-055 Handoff

## 修改文件
- `signals/iv_rank.py:31` — 新增 `ivp63` / `ivp252` / `regime_decay` 字段与计算逻辑
- `strategy/selector.py:151` — 新增 multi-horizon 阈值、`_compute_size_tier()`、Gate 1/2/3、BCS_HV ivp63 gate、`local_spike`
- `backtest/run_event_study.py:1` — 新增 non-overlapping event study runner
- `backtest/run_event_study_analysis.py:1` — 新增 event study analysis CLI
- `tests/test_spec_048_055.py:1` — 新增 19 个用例覆盖 048–055 验收边界与串联顺序

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：T1–T19；`tests.test_spec_048_055` 19/19；`unittest discover -s tests` 93/93
