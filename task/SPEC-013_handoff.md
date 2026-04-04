# SPEC-013 Handoff

## 修改文件
- `strategy/selector.py:70` — 新增 `bp_target_low_vol` / `bp_target_normal` / `bp_target_high_vol`，并添加 `bp_target_for_regime()`
- `backtest/engine.py:95` — `Position` 新增 `bp_target` 字段，记录入场时的 regime-aware BP target
- `backtest/engine.py:584` — 平仓时改为按 `bp_target / bp_per_contract` 计算合约数和 `exit_pnl`
- `backtest/engine.py:627` — 开仓时把 `params.bp_target_for_regime(regime)` 写入 `Position.bp_target`
- `backtest/engine.py:647` — 回测结束强平同样改为按 BP target sizing 计算

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：1, 2, 3, 4, 5, 6
