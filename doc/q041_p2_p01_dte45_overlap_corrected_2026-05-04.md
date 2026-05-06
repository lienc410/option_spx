# Q041 Phase 2 — P0-1: DTE45 Overlap 修正结果

**日期：** 2026-05-04  
**范围：** SPX CC / CSP × DTE45 × Δ0.20/0.25/0.30（6 个 combo）  
**方法：** 比较 Phase-1 overlapping 与 Phase-2 non-overlapping 两版本；non-overlapping 取两种起始对齐（A/B）的平均作为保守估计  
**结论：** **DTE45 CC 确认为 overlap artifact → 淘汰；DTE45 CSP 通过均值门槛但尾部高度集中 → 降级为观察项**

---

## 一、Overlap 问题确认

- 月度 roll 间距 ≈ 28–35 天；DTE45 实际持仓期 ≈ 41–46 天
- 每个 cycle 入场时，前一个 DTE45 cycle 约有 6–18 天尚未到期
- Phase-1 每月均进入 → N=46–47；non-overlapping → N≈23–24（约减半）

**两种对齐（A/B）的必要性：**  
以 May-2022 起始（Alignment A）跳过的月份，恰好包含 Apr-2025 关税崩盘周期；以 Jun-2022 起始（Alignment B）则将其纳入。两者 Sharpe 差距极大（CSP Δ0.20：Align A = 3.22 vs Align B = −0.08），因此 P0-1 须以 A+B 平均作为保守估计。

---

## 二、核心结果对照表

### CC（覆盖式期权 — Module A 目标：Sharpe ≥ 1.33 且 MaxDD ≤ −8.96%）

| Combo | D3 Phase-1 | 我方 Overlap | Corrected A | Corrected B | **Avg A+B** |
|-------|-----------|------------|-------------|-------------|------------|
| **CC Δ0.20 DTE45** | Sh=1.48 MDD=−14% | Sh=1.33 MDD=−17% | Sh=1.53 MDD=−6% | Sh=0.85 MDD=−15% | **Sh=1.19 MDD=−15%** |
| **CC Δ0.25 DTE45** | Sh=1.46 MDD=−14% | Sh=1.34 MDD=−17% | Sh=1.64 MDD=−5% | Sh=0.82 MDD=−15% | **Sh=1.23 MDD=−15%** |
| **CC Δ0.30 DTE45** | Sh=1.47 MDD=−14% | Sh=1.33 MDD=−16% | Sh=1.73 MDD=−5% | Sh=0.77 MDD=−15% | **Sh=1.25 MDD=−15%** |

**验收判断（Avg A+B）：**
- Sharpe：1.19–1.25 < 目标 1.33 → ✗
- MaxDD：−14.9 至 −15.2% >> 上限 −8.96% → ✗
- **CC DTE45 全部 delta：FAIL（双指标均不达标）**

### CSP（现金担保卖权 — Module B 目标：Sharpe ≥ 0.83 且 BP-day ROE ≥ 4.0%）

| Combo | D3 Phase-1 | Align A | Align B | **Avg A+B** |
|-------|-----------|---------|---------|------------|
| **CSP Δ0.20 DTE45** | Sh=3.03 cum=+35% | Sh=3.22 cum=+19% | Sh=−0.08 cum=−3% | **Sh=1.57 cum=+8%** |
| **CSP Δ0.25 DTE45** | Sh=2.24 cum=+39% | Sh=2.71 cum=+23% | Sh=−0.01 cum=−2% | **Sh=1.35 cum=+11%** |
| **CSP Δ0.30 DTE45** | Sh=1.75 cum=+39% | Sh=2.65 cum=+29% | Sh=+0.04 cum=−0% | **Sh=1.34 cum=+14%** |

**验收判断（Avg A+B）：**
- Sharpe：1.34–1.57 ≥ 0.83 → ✓（均值通过）
- 但：两对齐间 Sharpe 方差极大（差距 ≥ 3.0 Sharpe 单位）→ 高度不稳定

---

## 三、关键尾部事件

**2025-02-21 入场 / 2025-04-04 到期（关税崩盘）：**
- S_entry = 6013，S_exit = 5074（跌幅 −15.6%）
- 对 CSP Δ0.20 DTE45：K = 5740，settle = 666，pnl = −$624
- 该事件落入 Alignment B 但不在 Alignment A → 导致 Align B Sharpe 接近 0

**解读：** 在 4 年样本（46 个 cycle）中，仅这一个事件足以将整个策略从高 Sharpe 变为接近零收益。这不是"偶发的几个坏月"，而是在有限样本下集中尾部风险的经典表现。

---

## 四、与 Phase-1 D3 的方法论差异说明

本轮脚本采用 **Black-Scholes delta 法**选 strike（通过 IV 反算得到 delta，选最接近目标 delta 的 strike）。D3 的原始脚本已不存在，无法直接对照。校验结果：

| 指标 | D3 Phase-1 CSP | 本轮 overlap CSP | 差异 |
|------|---------------|-----------------|------|
| N | 46 | 46 | ✓ 完全一致 |
| WR（Δ0.20 DTE45）| 93.5% | 93.5% | ✓ 完全一致 |
| Cum return | +35.2% | +13.8% | 差异较大 |
| Worst | −$145 | −$624 | 差异 4× |

WR 和 N 精确一致表明 cycle 选择相同。差异集中在损失幅度：D3 的损失更小，可能因为 D3 strike 选择逻辑不同（推测为更保守的 moneyness 或期权价格比例规则）。**CC 方向对照更接近（本轮 Sharpe 1.33 vs D3 1.46–1.48），CC 结论可信度更高。**

---

## 五、P0-1 验收结论

| Combo | 验收状态 | 理由 |
|-------|---------|------|
| **CC DTE45 全部 Δ** | **淘汰** | Avg Sharpe 1.19–1.25 < 1.33；MaxDD −15% >> −8.96%；两项均不达标 |
| **CSP DTE45 全部 Δ** | **降级为观察项** | Avg Sharpe ≥ 0.83（均值通过），但两对齐间差距 > 3.0 Sharpe 单位；单一尾事件可摧毁全年收益；不具备生产稳定性 |

**对生产候选短名单的影响：**
- SPX CSP Δ0.20 DTE30（无 overlap 污染，D3 Sharpe 0.85）— **维持现有候选地位**
- DTE45 CC/CSP — **均不进入 Phase 2 正式生产候选**

---

## 六、已知局限性

| 局限 | 说明 |
|------|------|
| 脚本方法论与 D3 不完全一致 | D3 脚本已不存在；CSP 结果与 D3 有系统差异；CC 结果较接近 |
| 仅测试两种对齐 | 若允许任意起始月份，完整分布的尾部可能更宽 |
| 4 年样本 | N≈23 per alignment，仅 1–2 个极端事件决定 Sharpe；统计置信度有限 |
| 2025 Apr 关税崩盘 | 历史上首次此类冲击；若排除，结论变好。不排除。 |

---

*文档由 Quant Researcher 生成，2026-05-04。脚本：`backtest/prototype/q041_p2_p01_dte45_overlap_corrected.py`*
