# SPEC-005 Handoff

## 实施摘要
已为 Bull Call Diagonal 新增“入场日前连续 BULLISH ≥ 5 个交易日”的前置过滤。实现覆盖 `signals/trend.py` 的 streak 计算与 `TrendSnapshot` 字段扩展、`backtest/engine.py` 的回测快照注入，以及 `strategy/selector.py` 中 LOW_VOL + BULLISH、NORMAL + IV LOW + BULLISH 两个 BCD 入场点的 REDUCE_WAIT 过滤。

## 修改文件
- `signals/trend.py:37` — 为 `TrendSnapshot` 新增 `consecutive_bullish_days` 字段，默认值为 `0`
- `signals/trend.py:68` — 新增 `_count_consecutive_bullish(df)`，按 Spec 要求统计“入场日前、不含当天”的连续 BULLISH 天数
- `signals/trend.py:134` — 在 `get_current_trend()` 中计算并写入 `consecutive_bullish_days`
- `backtest/engine.py:473` — 在回测主循环里基于 `spx_window` 计算 prior bullish streak，并传入 `TrendSnapshot`
- `strategy/selector.py:322` — 为 `LOW_VOL + BULLISH` 的 BCD 入口增加 `<5d` 过滤，返回 `Reduce / Wait`
- `strategy/selector.py:434` — 为 `NORMAL + IV LOW + BULLISH` 的 BCD 入口增加 `<5d` 过滤，返回 `Reduce / Wait`

## 收尾步骤
- 缓存清除：是
- Web 重启：是

## 验收结果（自测）
1. `python main.py --backtest --start=2000-01-01` 输出中 BCD 笔数 ≤ 50（当前 89，预期约 39） → 实测 `Bull Call Diagonal n=77`，未通过
2. BCD WR ≥ 52%（当前 46%） → 实测 `52%`，通过
3. 全局 Total PnL 仍 ≥ $60,000（BCD 贡献减少，但整体不应大幅倒退） → 实测 `$58,299`，未通过
4. 全局 Sharpe ≥ 1.10 → 实测 `0.77`，未通过
5. `python main.py --dry-run` 在 BULLISH 天数不足时输出含 "wait for confirmed uptrend" 的 REDUCE_WAIT → 当日真实行情未触发该分支；使用合成快照调用 `select_strategy()` 验证，返回 `Reduce / Wait`，且理由文本包含 `wait for confirmed uptrend`，功能通过

## 备注
- 全量回测命令使用 `arch -arm64 venv/bin/python main.py --backtest --start=2000-01-01`；当前虚拟环境中的 `numpy/pandas` 需以 `arm64` 方式运行
- 首次回测失败是因为 `backtest/engine.py` 缺少 `MA_LONG` 导入，已补上最小修复后重新执行
- 该实现严格按 Spec 的“连续 ≥5d”门槛落地，但按当前回测结果，验收标准中的全局收益与 Sharpe 阈值未达成，建议后续由 PM / Claude 决定是否调整阈值或继续迭代过滤逻辑
