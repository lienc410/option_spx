# SPEC-006 Handoff

## 实施摘要
已在 `HIGH_VOL + BEARISH` 路径中新增 `Bear Call Spread (High Vol)` 策略。当 VIX 仍在 `RISING` 时继续返回 `Reduce / Wait`；当 VIX 非 `RISING` 时，进入 45 DTE、`SELL CALL δ0.20 / BUY CALL δ0.10` 的高波动 Bear Call Spread。回测引擎已同步支持新策略的腿构建、BP 计算与 0.5x 仓位缩放。

## 修改文件
- `strategy/selector.py:87` — 新增 `StrategyName.BEAR_CALL_SPREAD_HV = "Bear Call Spread (High Vol)"`
- `strategy/selector.py:243` — 重构 `HIGH_VOL` 分支，新增 `BEARISH` 下的 BCS HV 路径，并保留 `VIX RISING → REDUCE_WAIT`
- `strategy/selector.py:277` — 为 `HIGH_VOL + NEUTRAL` 明确返回 `Reduce / Wait`
- `backtest/engine.py:178` — 在 `_build_legs()` 中新增 BCS HV 的 45 DTE call credit spread 构建逻辑
- `backtest/engine.py:256` — 在 `_compute_bp()` 中将 BCS HV 纳入与 BPS 相同的 defined-risk BP 公式
- `backtest/engine.py:594` — 开仓时对 BCS HV 应用 `params.high_vol_size`（默认 0.5x）

## 收尾步骤
- 缓存清除：是
- Web 重启：是

## 验收结果（自测）
1. `python main.py --backtest --start=2000-01-01` 输出中出现 `Bear Call Spread (High Vol)` 行，且 n ≥ 20 → 实测 `n=72`，通过
2. BCS HV WR ≥ 70% → 实测 `82%`，通过
3. 全局 Total PnL ≥ $78,000（SPEC-004 后基准 $70,017，预期新增 ≥ $8,000） → 实测 `$78,738`，通过
4. 全局 Sharpe ≥ 1.20 → 实测 `0.95`，未通过
5. `python main.py --dry-run` 在当前信号为 HIGH_VOL + BEARISH + VIX 非 RISING 时，输出 `Bear Call Spread (High Vol)` 推荐（若当日信号不符合，用合成快照验证） → 当日真实行情为 `HIGH_VOL + BEARISH + VIX RISING`，dry-run 正确返回 `Reduce / Wait`；使用合成快照验证后，`select_strategy()` 返回 `Bear Call Spread (High Vol)`，通过

## 备注
- 当前真实市场条件为 `HIGH_VOL + BEARISH + VIX RISING`，因此 dry-run 没有直接命中新策略；这与 Spec 预期一致
- 全量回测命令使用 `arch -arm64 venv/bin/python main.py --backtest --start=2000-01-01`
- 新策略显著提升了总收益，但没有把全局 Sharpe 推高到 `1.20`；是否接受该 tradeoff 需由 PM / Claude 决定
