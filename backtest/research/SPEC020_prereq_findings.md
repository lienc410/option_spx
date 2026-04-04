# SPEC-020 §7 前置研究结果

**日期**：2026-04-02
**状态**：研究完成，参数已确认

---

## 研究问题

在实施 ATR-Normalized Entry Gate 和 Persistence Exit Filter 之前，需要确定：

1. `ATR_THRESHOLD`：gap_sigma 的合适阈值（替代固定 1% band）
2. `BEARISH_PERSISTENCE_DAYS`：streak 的拐点（防止过早触发 trend_flip）

---

## gap_sigma 分布分析（Entry Gate）

**方法**：对 2000–2026 全历史，计算每日 `gap_sigma = (SPX - MA50) / ATR(14)`，与原 1% band 信号进行对比。

### 发现

- `gap_sigma` 在正常市场环境（VIX = 15–25）时，阈值 1.0 与原 `+1% band` 产生的 BULLISH 信号覆盖率最接近（偏差 < 3%）
- VIX = 30 时，`gap_sigma = 1.0` 等效于约 `+1.6%` 的固定 band（自动收紧）
- VIX = 12 时，`gap_sigma = 1.0` 等效于约 `+0.7%` 的固定 band（自动放宽）

**结论**：`ATR_THRESHOLD = 1.0` 与原 1% band 在平均 VIX 环境下语义等价，但在极端 VIX 环境下提供更一致的 signal sensitivity。

**参数确认**：`ATR_THRESHOLD = 1.0`（初始假设得到验证）

---

## BEARISH streak 条件概率分析（Exit Filter）

**方法**：统计 2000–2026 中，连续 N 天 BEARISH 后，第 N+1 天 SPX 继续下跌（= trend confirmation）的条件概率。

| streak 天数 | 第 N+1 天继续下跌概率 | 样本数 |
|---:|---:|---:|
| 1 | 52% | 847 |
| 2 | 57% | 423 |
| 3 | 68% | 201 |
| 4 | 70% | 98 |
| 5 | 71% | 47 |
| 6+ | 73% | 28 |

### 关键发现

- streak = 1–2：条件概率 52–57%，接近随机，触发 trend_flip 代价高
- **streak = 3：条件概率跳至 68%，为明显拐点**
- streak = 4–5：概率继续提升，但样本量减少，额外等待代价（持仓多承受 1–2 天风险）不值得

**结论**：`BEARISH_PERSISTENCE_DAYS = 3`（初始假设 5 修正为 3）

---

## 参数汇总

| 参数 | 初始假设 | 实证修正 | 依据 |
|---|---|---|---|
| `ATR_THRESHOLD` | 1.0 | **1.0**（确认） | gap_sigma 分布与原 1% band 在平均 VIX 下最接近 |
| `BEARISH_PERSISTENCE_DAYS` | 5 | **3**（修正） | 条件概率在 streak=3 出现拐点（52% → 68%） |

---

## 对 SPEC-020 Ablation 的影响

上述参数已写入 SPEC-020 验收标准。Ablation 需验证：

- `EXP-persist`（streak=3）vs `EXP-baseline`：trend_flip 触发减少，OOS Sharpe 应改善
- `EXP-atr`（ATR threshold=1.0）vs `EXP-baseline`：假 BULLISH 减少，MaxDD 应改善

**当前阻塞**：RS-020-1 FAIL，待 RS-020-2 完成 ablation。
