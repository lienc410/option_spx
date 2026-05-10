# SPEC-097 Handoff

## 修改文件
- `research/strategies/ES_puts/backtest.py` — 为 `run_phase2_v2f()` 加入 M1 cluster throttle、stress extraction、baseline/M1 双口径 support
- `web/server.py` — 更新 `/api/es-backtest/v2f` 返回 `v2f_baseline` / `v2f_m1` / `m1_delta`，并定向清理 V2f cache
- `web/templates/es_backtest.html` — V2f tab 改为 baseline vs M1 对比，并补 M1 warning 文案
- `tests/test_spec_095.py` — 对齐 SPEC-097 后的 V2f canonical API/UI 形状与阈值

## 收尾
- 缓存清除：是（V2f memory + disk cache 定向 purge）　Web 重启：待部署

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6

## 备注
- 实测 `mode=baseline`：
  - `v2f_baseline.ann_roe_geometric ≈ 2.59%`
  - `v2f_m1.ann_roe_geometric ≈ 2.32%`
  - `v2f_m1.sharpe ≈ 0.23`
  - `v2f_baseline.stress_cluster_pct ≈ -47.57%`
  - `v2f_m1.stress_cluster_pct ≈ -44.45%`
- `stress_*` 比较采用与 Q061 prototype 一致的 relative-cadence stress extraction；主回测 baseline 仍保留现有 legacy cadence，避免改写 V2f 基础路径。
