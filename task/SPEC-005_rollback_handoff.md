# SPEC-005 Rollback Handoff

## 回滚摘要
已按要求回滚 SPEC-005 在生产代码中引入的全部改动，恢复到 SPEC-004 完成后的状态。回滚范围仅限你指定的三个文件：`signals/trend.py`、`backtest/engine.py`、`strategy/selector.py`。

## 回滚文件
- `signals/trend.py:37` — 移除 `TrendSnapshot.consecutive_bullish_days` 字段
- `signals/trend.py:47` — 恢复 `TrendSnapshot.__str__()`，不再输出 prior bullish streak
- `signals/trend.py:58` — 移除 `_count_consecutive_bullish()` 函数
- `signals/trend.py:116` — `get_current_trend()` 不再计算或传入连续 BULLISH 天数
- `backtest/engine.py:473` — 移除 `consec_bull` 计算逻辑
- `backtest/engine.py:473` — `TrendSnapshot(...)` 不再传入 `consecutive_bullish_days`
- `strategy/selector.py:322` — 移除 `LOW_VOL + BULLISH` 的 `<5d` REDUCE_WAIT 过滤
- `strategy/selector.py:428` — 移除 `NORMAL + IV LOW + BULLISH` 的 `<5d` REDUCE_WAIT 过滤

## 收尾步骤
- 缓存清除：是
- Web 重启：是

## 确认
- `signals/trend.py` 中已不存在 `consecutive_bullish_days` 字段
- `signals/trend.py` 中已不存在 `_count_consecutive_bullish()` 函数
- `backtest/engine.py` 中已不存在 `consec_bull` 计算和对应字段传递
- `strategy/selector.py` 中已移除 BCD 入场的 `<5d` 过滤，恢复为当日 `BULLISH` 即可进入原有 BCD 逻辑

## 备注
- 未执行额外回测；本次交付仅确认代码已回滚并完成缓存清理与 Web 重启
