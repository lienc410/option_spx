# SPEC-014 Handoff

## 修改文件
- `strategy/selector.py:77` — 新增 `bp_ceiling_low_vol` / `bp_ceiling_normal` / `bp_ceiling_high_vol`
- `strategy/selector.py:83` — 新增 `bp_ceiling_for_regime()`，方法体内 `from signals.vix_regime import Regime`
- `backtest/engine.py:457` — 单仓 `position` 改为多仓 `positions: list[Position] = []`
- `backtest/engine.py:532` — 持仓管理改为 `for position in list(positions):` 逐仓评估并出场
- `backtest/engine.py:615` — 入场条件改为 `BP ceiling + dedup` 检查
- `backtest/engine.py:654` — 回测结束强平改为遍历全部未平仓仓位

## 收尾
- 缓存清除：是
- Web 重启：是

## 验收结果
- 1 通过：`StrategyParams` 具有 `bp_ceiling_low_vol=0.25`、`bp_ceiling_normal=0.35`、`bp_ceiling_high_vol=0.50`
- 2 通过：`bp_ceiling_for_regime()` 实测返回 `LOW_VOL=0.25`、`NORMAL=0.35`、`HIGH_VOL=0.50`
- 3 通过：`run_backtest(start_date="2024-01-01")` 正常完成，无异常
- 4 通过：`2024-01-01` 回测总 trades 从修改前单仓基线 `23` 增至修改后 `30`
- 5 通过：instrumented replay 未发现任何时点 `sum(p.bp_target for p in positions)` 超过当日 `bp_ceiling_for_regime(regime)`；违规数 `0`
- 6 通过：instrumented replay 未发现 `positions` 中同时出现两个相同 `StrategyName`；违规数 `0`
- 7 通过：instrumented replay 显示回测结束前仍有 `1` 个未平仓仓位，`run_backtest()` 输出中对应 `exit_reason="end_of_backtest"` 记录数为 `1`
