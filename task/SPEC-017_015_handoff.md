# SPEC-017_015 Handoff

## 修改文件
- `strategy/catalog.py:7` — 为 `StrategyDescriptor` 增加 `short_gamma`、`short_vega`、`delta_sign`，并补齐 6 个活跃策略与 `reduce_wait` 的 Greek metadata
- `strategy/selector.py:48` — 为 `StrategyParams` 增加 `max_short_gamma_positions`、`spell_age_cap`、`max_trades_per_spell`
- `backtest/engine.py:50` — 新增合成 IC / short-gamma / HIGH_VOL spell 的辅助常量与 helper
- `backtest/engine.py:572` — 在回测主循环中加入 HIGH_VOL spell 状态追踪
- `backtest/engine.py:643` — 为信号历史补充 `strategy_key` 与 `hv_spell_age`
- `backtest/engine.py:747` — 在入场条件中加入 synthetic IC block、short-gamma 上限、spell throttle
- `tests/test_specs_017_015.py:1` — 新增 SPEC-017 / SPEC-015 单元测试，覆盖 catalog 字段、block 逻辑、spell reset、no-op 配置

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：1, 2, 4, 5, 6
- 通过：SPEC-015 #1, #2, #3, #4, #5, #6

## 阻塞/备注
- SPEC-017 的“BPS_HV 与 BCS_HV 不出现于同一时间点的 positions 列表”在当前 engine 顺序下本来就满足：引擎先平仓再开新仓，因此同日换仓不会形成真实并发。新增 synthetic IC block 主要是把这条风险约束显式化，并为未来更复杂的多仓入场逻辑保留保护网。
- 2022 对拍结果：
  - `all_off`: 62 trades, Sharpe `0.90`
  - `017_on_only`: 62 trades, Sharpe `0.90`
  - `015_on_only`: 56 trades, Sharpe `0.97`
  - `both_on`: 56 trades, Sharpe `0.97`
  - 结论：当前样本里实际改善主要来自 SPEC-015 的 sticky-spell throttle，SPEC-017 在现有 engine 时序下没有额外改变已实现结果。

