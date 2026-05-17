# Q072 P4 — Cap Recalibration (Production-View Baseline)

**Date**: 2026-05-16
**Driver**: PM observation 2026-05-16: SPEC-103 governance panel displays SPX PM BP using account-level Schwab API maintenance margin, but Q072 P1 backtest peak 67.9% used sleeve-only BP. The two are not directly comparable.

---

## TL;DR

**维持 70% cap，但物理依据修正**：

- **原 Q072 brief 理由**（口径错配，已失效）：backtest peak 67.9%，70% 留 2pp safety
- **正确 production 口径理由**：Schwab PM call 触发线 80% → **70% = 10pp safety margin to PM call**
- **在当前 PM 持仓 baseline (Schwab equity 14.4%) 下，sleeve peak 时 production view 会到 82.3%，70% cap 历史会 bind 5 天**——cap 在真正风险时刻会工作，不是"过松"

---

## 1. 口径错配的发现

| 口径 | 来源 | 数据 | 当前值 |
|---|---|---|---|
| Sleeve-only | Q072 P1 backtest (`q072_p1_daily_flags.csv.main_bp + dd_overlay_bp`) | 19y sim | peak 67.9% |
| Production | Schwab API `schwab_maintenance_margin` | live API | 34.3% |
| **差值** | non-sleeve baseline (equity + other options 的 maintenance) | live snapshot | **14.4% of Schwab NLV** |

**Production = Sleeve + Baseline**。两个数字不在同一口径，不可直接比较。

---

## 2. 当前 PM 持仓 baseline 分解（2026-05-16 live）

| 账户 | NLV | Total maint | Sleeve 部分 | **Baseline 非 sleeve** |
|---|---|---|---|---|
| Schwab | $601,182 | $206,397 (34.3%) | $119,997 (20.0% SPX spread) | **$86,397 (14.4%)** ← equity maint |
| ETrade | $292,986 | $131,604 (44.9%) | $59,999 (20.5% options) | **$71,604 (24.4%)** ← equity maint |
| **Combined** | $894,168 | $338,001 (37.8%) | $179,996 (20.1%) | $158,001 (17.7%) |

---

## 3. Cap-bind sensitivity table (Schwab pool, 19y backtest 重测)

每 baseline 假设下，把 sleeve daily BP 加上 baseline 常量，得到 production-view daily BP，查 cap bind 天数：

| Baseline % NLV | Avg | P95 | **Peak** | days ≥ 60% | days ≥ 65% | **days ≥ 70%** | days ≥ 75% | days ≥ 80% |
|---|---|---|---|---|---|---|---|---|
| 0% (空账户) | 16.5 | 41.7 | 67.9 | 2 | 2 | **0** | 0 | 0 |
| 5% | 21.5 | 46.7 | 72.9 | 5 | 2 | **2** | 0 | 0 |
| 10% | 26.5 | 51.7 | 77.9 | 63 | 5 | **2** | 2 | 0 |
| **14.4% (current)** | **30.9** | **56.1** | **82.3** | **63** | **63** | **5** | **2** | **1** |
| 20% | 36.5 | 61.7 | 87.9 | 274 | 72 | **63** | 5 | 2 |
| 25% | 41.5 | 66.7 | 92.9 | 358 | 274 | **72** | 63 | 5 |
| 30% | 46.5 | 71.7 | 97.9 | 598 | 358 | **274** | 72 | 63 |

**19y trading day total = 4869**, so 70% cap bind:
- baseline 0%: 0% of days bind
- baseline 14.4% (current): **0.10%** of days bind (5 days)
- baseline 20%: 1.29% (63 days)
- baseline 30%: 5.63% (274 days)

---

## 4. 三个 cap 方案对比

| 方案 | Normal cap | Stress cap (R5) | 19y bind (current baseline 14.4%) | 物理意义 |
|---|---|---|---|---|
| **A. 维持 70%** ✅ | 70% | 60% | 5 days (0.10%) | 距 PM call 80% 留 10pp safety |
| B. 微紧 65% | 65% | 55% | 63 days (1.29%) | 距 PM call 留 15pp safety；更早预警 |
| C. 放宽 75% | 75% | 65% | 2 days (0.04%) | 距 PM call 留 5pp safety——太接近 |

---

## 5. 决定：维持 A (70% cap)

**理由**：

1. **物理依据清晰**：Schwab PM call 80% - 10pp safety = 70%
2. **历史 bind 频率合理**：在当前持仓 baseline 14.4% 下，19y 仅 5 天 bind（0.10%），都是 sleeve 真正 peak 时——cap 在风险时刻工作
3. **PM 之前担心"70% 偏松"是基于 sleeve-only 数据 34.3 / 70 = 49% 用量的误判**：sleeve peak 时配合 baseline 会显著推高到 82.3%
4. **Baseline 是动态测量**：governance daemon 实时读 Schwab API maintenance，PM 增减持股自动反映到 effective sleeve 可用空间——不需要手工调 cap

---

## 6. 三个附加 implication

### 6.1 R3 Combined cap 也要重审

当前 R3 = 60% combined NLV（基于 Q072 P4C.0 时的 sleeve-only 数据）。但在 production口径：
- Combined baseline = $158k / $894k = **17.7%**
- 加 sleeve combined peak (Q072 P1 combined 62.8%) → production combined peak ~80%
- **R3 = 60% 在 production口径下会经常 bind**

**建议**：R3 暂时按当前 60% 运行，运行 1 个月后看实际 binding 频率，若过度限制再调到 70%。**不在本次改动范围**。

### 6.2 PM 增持股票的 trade-off

若 PM 显著增持股票（baseline > 20%）：
- 70% cap 19y 中会 bind 63+ 天
- sleeve sizing 必须考虑 baseline——sleeve 实际可用空间 = 70% - baseline

**建议**：baseline > 25% 时重审 cap 与 sizing（如 baseline 升至 25% → 推荐 cap 提到 75% 或调整 sleeve 规模）。

### 6.3 Deferred validation (不影响当前决策)

待 Q071 HV Ladder final config lock 后做的 P4B /ES rerun + P4C.7 synthetic stress test 仍保留——它们独立于本次 cap recalibration。

---

## 7. 输出文件

```
research/q072/
├── q072_p4_cap_recalibration.py      ← sensitivity script
├── q072_p4_cap_recalibration.csv     ← 8 baseline × 5 cap candidates
└── q072_p4_cap_recalibration_2026-05-16.md  ← 本 memo
```

---

## 8. 一句话总结

> **70% cap 不是过松——是物理上对应"距 PM call 留 10pp safety margin"。之前看到的 49% 用量空间是因为 sleeve 当前没在 peak；真正 sleeve peak 时 production view 会推到 82%，cap 会自动激活保护账户。**

SPEC-103.md 已更新 cap caveat 段落。无生产配置变更，governance daemon 继续运行。
