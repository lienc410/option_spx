# SPEC-009 Handoff

## 修改文件
- `strategy/selector.py:525` — 将 `NORMAL + IV LOW + BULLISH` 从 `Bull Call Diagonal` 改为 `_reduce_wait(...)`

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：2, 3, 5
- 未通过：1 → 实测 `Bull Call Diagonal n=11` vs 目标 `≤ 10`
- 未通过：4 → 实测 `Sharpe=1.08` vs 目标 `≥ 1.18`

## 阻塞/备注
- 验收 5 的当日真实 `dry-run` 环境不是 `NORMAL + IV LOW + BULLISH`；已用合成快照调用 `select_strategy()` 验证，返回 `Reduce / Wait`
