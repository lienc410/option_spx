# SPEC-008 Handoff

## 实施摘要
已新增 `Iron Condor (High Vol)` 策略，用于 `HIGH_VOL + NEUTRAL + VIX 非 RISING` 环境，替换原先的 `Reduce / Wait`。实现包含 selector 中的 HIGH_VOL + NEUTRAL 路径重构，以及 backtest 中对 `IRON_CONDOR_HV` 的腿构建、BP 计算和 `0.5x` 仓位缩放支持。

## 修改文件
- `strategy/selector.py:91` — 新增 `StrategyName.IRON_CONDOR_HV = "Iron Condor (High Vol)"`
- `strategy/selector.py:278` — 将 `HIGH_VOL + NEUTRAL` 从单行 `Reduce / Wait` 改为条件化 `Iron Condor (High Vol)`
- `strategy/selector.py:279` — 新增 `VIX RISING` guard：`HIGH_VOL + NEUTRAL + VIX RISING → Reduce / Wait`
- `strategy/selector.py:284` — 新增 `BACKWARDATION` guard：`HIGH_VOL + NEUTRAL + BACKWARDATION → Reduce / Wait`
- `strategy/selector.py:289` — 新增 `Iron Condor (High Vol)` 推荐结构与理由文案
- `backtest/engine.py:146` — `_build_legs()` 将 `IRON_CONDOR_HV` 并入现有 `IRON_CONDOR` 腿构建逻辑
- `backtest/engine.py:268` — `_compute_bp()` 将 `IRON_CONDOR_HV` 并入现有 `IRON_CONDOR` BP 公式
- `backtest/engine.py:594` — 开仓时对 `IRON_CONDOR_HV` 应用 `params.high_vol_size`（默认 0.5x）

## 收尾步骤
- 缓存清除：是
- Web 重启：是

## 验收结果（自测）
1. `python main.py --backtest --start=2000-01-01` 输出中出现 `Iron Condor (High Vol)` 行，且 n ≥ 15 → 实测 `n=18`，通过
2. IC HV WR ≥ 80% → 实测 `78%`，未通过
3. 全局 Total PnL ≥ $115,000（SPEC-007 目标 $100,000，预期新增 ≥ $15,000） → 实测 `$90,410`，未通过
4. 全局 Sharpe ≥ 1.05 → 实测 `1.24`，通过
5. `python main.py --dry-run` 在 HIGH_VOL + NEUTRAL + VIX 非 RISING 环境下，输出 `Iron Condor (High Vol)` 推荐 → 当日真实行情不是 `HIGH_VOL + NEUTRAL`；使用合成快照验证后，`select_strategy()` 返回 `Iron Condor (High Vol)`，通过

## 备注
- 当前真实 dry-run 环境仍是 `HIGH_VOL + BEARISH + VIX RISING`，因此不会命中本 Spec 的新路径
- 新策略提升了全局 Sharpe 到 `1.24`，但没有把 IC HV 自身 WR 推到 `80%`，也没有达到总收益 `115k`
- 本次未修改 NORMAL/LOW_VOL 或 HIGH_VOL 下的 BULLISH/BEARISH 其他路径，严格限制在 Spec 范围内
