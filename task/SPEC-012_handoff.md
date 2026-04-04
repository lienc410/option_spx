# SPEC-012 Handoff

## 修改文件
- `backtest/engine.py:80` — 为 `Trade` 新增 `hold_days` 与 `rom_annualized` computed property
- `backtest/engine.py:361` — 扩展 `by_strategy` 聚合，增加 `avg_rom` 与 `median_rom`

## 收尾
- 缓存清除：是　Web 重启：是

## 验收结果
- 通过：1, 2, 3, 4
- 未通过：5 → 实测 `2022-01-01` 回测中存在 `Bull Call Diagonal avg_rom=-0.147` 与 `Bear Call Spread (High Vol) avg_rom=1.134`，但当前策略集无普通 `Bear Call Spread`

## 阻塞/备注
当前 `2022-01-01` 回测的 `by_strategy` keys 为 `Bull Call Diagonal`、`Bear Call Spread (High Vol)`、`Bull Put Spread`、`Bull Put Spread (High Vol)`、`Iron Condor`、`Iron Condor (High Vol)`。
