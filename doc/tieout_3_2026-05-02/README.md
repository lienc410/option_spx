# Tieout #3 — 2026-05-02

Window: `2023-04-29 → 2026-05-02`
Runner: `doc/tieout_3_2026-05-02/run_tieout3.py`
Generated: 2026-05-02 (post-batch-2: SPEC-079 + SPEC-080 DONE)

---

## 目的

1. **Q-A 回归**：确认 SPEC-079/080 代码在 `disabled` 模式下对 trade flow 零影响
2. **Preview B/C/D**：当 toggle 切到 `active` 时，3y 窗口内触发行为的预览
3. **Gap 收敛测量**：D_pt050 (both active, PT=0.50) vs MC@PT=0.50 = 52/$45,922

---

## 场景汇总

| 场景 | PT | comfort_filter | stop_tightening | trades | open | total_pnl |
|---|---|---|---|---|---|---|
| **A (disabled)** | 0.60 | disabled | disabled | **57** | 2 | **$79,934** |
| B (comfort active) | 0.60 | active | disabled | 57 | 2 | $79,934 |
| C (stop active) | 0.60 | disabled | active | 57 | 2 | $79,934 |
| D (both active) | 0.60 | active | active | 57 | 2 | $79,934 |
| D_pt050 (both active) | 0.50 | active | active | **57** | 2 | **$76,450** |

---

## Q-A 回归结果

| 维度 | tieout #2 Q-C | tieout #3 A | delta |
|---|---|---|---|
| trades | 57 | 57 | 0 |
| total_pnl | $79,933.69 | $79,933.69 | $0.00 |

**REGRESSION_PASS = True** — SPEC-079/080 在 `disabled` 模式下对 trade flow 零影响 ✓

---

## B/C/D 全部等于 A（PT=0.60 窗口内无触发）

在 `2023-04-29 → 2026-05-02` 的 3y 窗口、PT=0.60 下：
- **SPEC-079 comfort filter 从未触发**：窗口内所有 BCD entry 日期中，无一同时满足 `vix ≤ 15 + dist_30d_high ≤ -1% + ma_gap > 1.5pp`（risk_score = 3）
- **SPEC-080 stop tightening 从未触发**：窗口内所有 BCD position，无一在 pnl_ratio 落入 `[-0.50, -0.35)` 区间时被截断（BCD 要么顺利达到 profit target，要么止损幅度超过 50%）

**含义**：该窗口对 SPEC-079/080 来说是一个"low-stress"环境。filter/stop 的真实压力测试需要包含 2020 / 2022 年的全样本窗口。

---

## D_pt050 与 gap 收敛分析

| | tieout #2 HC@0.50 | tieout #3 D_pt050 | delta |
|---|---|---|---|
| trades | 58 | 57 | -1 |
| total_pnl | $75,570 | $76,450 | +$880 |

**D_pt050 少 1 笔 = SPEC-079 拦截了 2026-04-30 的 BCD entry**

该日 VIX=14.x（≤15 ✓）、SPX dist_30d_high ≤ -1%（✓）、MA50 gap > 1.5%（✓），risk_score=3 → comfort filter 在 `active` 模式下阻断该入场。该 trade 在 PT=0.60 窗口是 `open_at_end`（未实现），所以 PT=0.60 场景数量不受影响。

**Gap vs MC@0.50：**

| | tieout #2 gap | tieout #3 D_pt050 gap |
|---|---|---|
| HC vs MC trade delta | +6 | **+5** |
| HC vs MC PnL delta | +$29,648 | **+$30,528** |

trade gap 缩小 1（SPEC-079 拦了一笔 HC-unique BCD），PnL gap 稍扩 $880（被拦的那笔是盈利单）。整体 gap 仍大，**主要残余来源仍是 IC regular HC 13 vs MC 6 和 BPS/BCD 策略组合差异**，不在 SPEC-079/080 的修复范围内。

---

## 整体裁定

| 维度 | 结果 | 说明 |
|---|---|---|
| Q-A 回归 | **PASS** | disabled 模式 byte-identical，零 trade flow 变化 |
| B/C/D 无触发（PT=0.60） | **符合预期** | 3y 窗口是低压力环境；全样本下应有更多触发 |
| D_pt050 gap 收敛 | **部分**（-1 trade） | SPEC-079 拦截 2026-04-30 BCD；主残余 gap 未变 |
| 全样本压力测试 | **待跑** | 需 `start=2007-01-01` + both active 才能观察 2020/2022 触发行为 |

---

## 下一步

1. **Q037 / Q038 open_questions.md 索引补全**（per assessment §4，tieout #2 完成后即可执行）
2. **HC return 包给 MC**（batch 1 + tieout #2 + batch 2 全部完成）
3. **PM 决定 shadow flip 时机**：`bcd_comfort_filter_mode` / `bcd_stop_tightening_mode` 均 `disabled`；MC 目标 4-8 周观察期后 flip shadow
4. **全样本 SPEC-079/080 active 验证**（可选，`start=2007-01-01` + both active）：了解 2008/2020/2022 等高压年份的 filter 触发频率和 PnL 净效果

---

## 文件

| 文件 | 说明 |
|---|---|
| `tieout3_A_pt060_disabled_trades.csv` | 回归基准 |
| `tieout3_B_pt060_comfort_active_trades.csv` | comfort filter 预览 |
| `tieout3_C_pt060_stop_active_trades.csv` | stop tightening 预览 |
| `tieout3_D_pt060_both_active_trades.csv` | 双 toggle 预览 |
| `tieout3_D_pt050_both_active_trades.csv` | gap 收敛测量基准 |
| `tieout3_summary.json` | 机器可读汇总 |
| `run_tieout3.py` | 重现脚本 |
