# Tieout #2 — 2026-05-02

Window: `2023-04-29 → 2026-05-02` (HC current end)
Runner: `doc/tieout_2_2026-05-02/run_tieout2.py`
Generated: 2026-05-02 (batch 1 all closed: SPEC-074 / SPEC-077 / SPEC-078 DONE)

---

## 目的

验证 HC reproduction sprint **batch 1** 落地后是否引入意外 trade flow 变化（Q-A 自洽性），并建立 HC@PT=0.60 在 3y 窗口的新基线（Q-C）。

---

## 结果摘要

### Q-A — 自洽性检验 (HC@PT=0.50 today vs tieout #1)

| 维度 | tieout #1 (2026-04-29) | tieout #2 (2026-05-02) | delta |
|---|---|---|---|
| trades | 57 | 58 | +1 |
| total_pnl | +$73,952 | +$75,570 | +$1,618 |
| entry date match | — | 57/58 = 98.28% | — |

**Adjusted Verdict: PASS**

脚本报告 `SELF_CONSISTENT = False`（threshold 99%），但这是**假阳性**：
- 新增 entry `2026-04-30` 是因为 tieout #1 CSV 生成于 2026-04-29，当时该日数据不存在
- 57 条共有 entry 日期 100% 保留，无消失
- PnL delta +$1,618 = 该笔新 trade 的 P&L

去掉 2026-04-30 这条 date-boundary artifact，HC@PT=0.50 与 tieout #1 完全一致。
**Batch 1 未引入任何意外 trade flow 变化。**

### Q-B — HC vs MC 残余 gap（仅参考，非 PASS/FAIL）

| | tieout #1 | tieout #2 |
|---|---|---|
| HC@PT=0.50 trades | 57 | 58 |
| MC@PT=0.50 trades | 52 | 52 |
| Δ trades | +5 | +6 (+1 date) |
| HC@PT=0.50 PnL | +$73,952 | +$75,570 |
| MC@PT=0.50 PnL | +$45,922 | +$45,922 |
| Δ PnL | +$28,030 | +$29,648 |

Gap 几乎不变，完全符合预测。Batch 1 未改动 selector / IVP gate / persistence filter，
gap 结构未收敛是**预期行为**。真正的收敛要等 **batch 2 (SPEC-079/080)** 落地后的 tieout #3。

主要 gap 构成（沿用 tieout #1 per-strategy 分解）：
- IC regular: HC 13 vs MC 6 — largest delta (+7 entries, +$18k)；根因为 Q015 IVP gate 与 persistence filter 差异
- BPS: HC 15 vs MC 21 — MC side有更多 BPS（可能与 BCD comfortable top filter SPEC-079 有关）
- BCD: HC 20 vs MC 15 — HC still fires more BCD (debit-side stop tightening SPEC-080 will affect exit PnL)

### Q-C — HC@PT=0.60 新基线

| 策略 | trades | PnL |
|---|---|---|
| Bull Call Diagonal | 20 | +$38,571 |
| Iron Condor | 13 | +$19,329 |
| Bull Put Spread | 15 | +$13,538 |
| Iron Condor (High Vol) | 8 | +$6,767 |
| Bull Put Spread (High Vol) | 1 | +$1,728 |
| **Total** | **57** (2 open) | **+$79,934** |

- `open_at_end = 2`（2 trades 仍持有，未实现 PnL 未计入）
- BCD 20 vs HC@PT=0.50 的 21：少 1 笔，符合预期（PT=0.60 延迟了一笔 BCD 的退出，变为 open_at_end）

---

## 整体裁定

| 维度 | 裁定 | 说明 |
|---|---|---|
| Q-A 自洽性 | **PASS** | date-boundary artifact 解释 +1 trade / +$1,618；57 原始 entries 100% 保留 |
| Batch 1 trade flow 完整性 | **PASS** | SPEC-074 / SPEC-077 / SPEC-078 未引入意外 trade 变化 |
| Q-B HC↔MC gap 收敛 | **未收敛（预期）** | gap 不变，需 batch 2 (SPEC-079/080) 后的 tieout #3 |
| Q-C 新基线建立 | **DONE** | HC@PT=0.60 在 2023-04-29 窗口：57 trades / $79,934 |

---

## 文件

| 文件 | 说明 |
|---|---|
| `tieout2_pt050_trades.csv` | Q-A：HC@PT=0.50，58 trades |
| `tieout2_pt060_trades.csv` | Q-C：HC@PT=0.60，57 trades（2 open） |
| `tieout2_summary.json` | 机器可读汇总 |
| `run_tieout2.py` | 重现脚本 |

---

## 下一步

1. **Batch 2 启动**：SPEC-079 (BCD comfort filter) + SPEC-080 (BCD debit stop tightening + stop_mult wiring)
2. **Tieout #3**：batch 2 落地后重跑，验证 IC regular / BCD / BPS gap 是否向 MC 收敛
3. **Q020 关闭**：per assessment §5.1，等 tieout #2（现已完成）确认收敛后再关；
   本次确认 batch-1 自洽性 PASS，但 HC↔MC gap 未收敛 → Q020 **暂不关闭**，等 tieout #3
4. **Q037 / Q038 索引层**：per assessment §4，在 tieout #2 完成后补 open_questions.md 条目；现可执行
