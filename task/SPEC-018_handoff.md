# SPEC-018 Handoff

## 修改文件
- `backtest/engine.py:344` — 为 `compute_metrics` 增加 `calmar`、`cvar5`、`cvar10`、`skew`、`kurt`，并补空列表零值边界
- `backtest/engine.py:729` — 回测主流程继续复用扩展后的 metrics 输出
- `notify/telegram_bot.py:280` — backtest Telegram 摘要增加 Calmar、CVaR 5%、Skew
- `tests/test_spec_018_metrics.py:1` — 新增 SPEC-018 回归测试，覆盖新增字段、空列表边界、bot 摘要输出

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：1, 2, 3, 4

