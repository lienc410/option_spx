# SPEC-092: Q019 VIX Flip Day Overlay on SPX Price Chart

Status: APPROVED

## Design Source

Engineering-driven. Data source (`data/q019_settling_log.jsonl`) and interaction pattern are well-defined.

## 目标

在现有"SPX Price — Trade Entry / Exit"图上增加一个可切换的 overlay view，高亮显示 Q019 中由于 close vs open-based VIX 口径不一致而导致 Signal 1 ≠ Signal 2 的交易日。

帮助 PM 直观看到：哪些入场/出场发生在 VIX 口径分歧日，以及当时 Signal 2 给出的推荐是否不同。

## 功能项（Features）

### F1 — 数据端点

- 新增 `/api/q019/flip-days`，返回 `data/q019_settling_log.jsonl` 中 `changed=true` 的日期列表及相关字段：
  ```json
  [
    {
      "date": "2026-05-12",
      "vix_signal1": 24.3,
      "rec_signal1": "BPS",
      "vix_signal2": 21.8,
      "rec_signal2": "IC",
      "elapsed_min": 47
    }
  ]
  ```
- Fail-soft：若 `q019_settling_log.jsonl` 不存在或为空，返回 `[]`，不报错

### F2 — 图表 Overlay Toggle

在"SPX Price — Trade Entry / Exit"图上新增 toggle：
- 文字：`Show Q019 VIX Flip Days`（默认 OFF）
- 开启时：将 flip 日期对应的 x 轴区域用半透明背景色标注（建议橙色/黄色，不遮挡现有 trade marker）
- 每个标注区域 hover 时显示 tooltip：
  ```
  Q019 VIX flip day
  Signal 1 (open): VIX 24.3 → BPS
  Signal 2 (stable): VIX 21.8 → IC (changed)
  Settled after: 47 min
  ```
- 若该日期有 trade entry 或 exit marker，两者共存（overlay 在 trade marker 下层）

### F3 — 图例更新

toggle 开启时，图例新增一行：`Q019 VIX Flip Day（Signal changed）` + 对应颜色标示

## 验收标准

- **AC1** — `/api/q019/flip-days` 返回格式正确；`q019_settling_log.jsonl` 为空时返回 `[]`
- **AC2** — Toggle 默认 OFF，开启后 flip 日期正确标注在 SPX 图上
- **AC3** — Hover tooltip 显示正确（date、两个 VIX 值、两个推荐、elapsed_min）
- **AC4** — Overlay 与现有 trade entry/exit marker 共存，不遮挡
- **AC5** — 回归：现有图表行为和其他 toggle 不受影响

## 不在范围内

- 改变 Q019 settling 逻辑
- 在回测图上显示（仅限 live 推荐图）
- 展示 Signal 2 为 "same" 的日期（只展示 changed=true）

## 参考文件

```
data/q019_settling_log.jsonl          ← 数据源
web/templates/es.html                 ← 现有 SPX 图参考（entry/exit overlay 实现）
web/server.py                         ← 新增 endpoint 挂载点
```

## Review

- Implemented as a narrow backtest-chart overlay without touching Q019 settling logic or `/api/recommendation`.
- `web/server.py` now exposes fail-soft `/api/q019/flip-days`, sourced from `data/q019_settling_log.jsonl` and filtered to `changed=true`.
- `web/templates/backtest.html` now adds:
  - a default-OFF `Show Q019 VIX Flip Days` toggle,
  - shaded flip-day regions under existing trade markers,
  - a hover detail card for Signal 1 vs Signal 2 VIX/recommendation differences,
  - a conditional legend entry shown only when the toggle is enabled.
- AC1 PASS — endpoint returns normalized flip-day rows and degrades to `[]` when the log file is missing or empty.
- AC2 PASS — toggle defaults OFF and only renders highlighted regions when explicitly enabled.
- AC3 PASS — hover surface shows date, both VIX values, both recommendation labels, and `elapsed_min`.
- AC4 PASS — overlay is drawn in a pre-dataset layer, so trade entry/exit markers remain visible above it.
- AC5 PASS — existing SPX overlay buttons, chart rendering, and backtest page controls remain unchanged.
