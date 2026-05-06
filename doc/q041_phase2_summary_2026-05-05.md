# Q041 Phase 2 研究总结

**日期：** 2026-05-05  
**状态：** Phase 2 全部任务完成（P0/P1/P2 均已关闭）  
**前置：** Phase 1 CONDITIONAL PASS（D1–D4，2026-05-04）

---

## 一、执行摘要

Phase 2 对 Phase 1 的五项候选策略进行了精细化验证，完成了 6 个研究任务（P0-1/P0-2/P1-1/P1-2/P2-1/P2-2）。主要结论：

- **SPX CSP Δ0.20 DTE30** 通过全部压测，维持**正式候选**；2022 熊市仅 1 次 cycle 亏损，全年正收益
- **GOOGL/AMZN CSP** 升级为**正式候选边缘**；Sharpe 信号强，但缺少 COVID 崩盘样本
- **COST/JPM 财报 IC** 降为**观察候选**；数据仅覆盖 4 年，缺 COVID 样本，N 极小
- **SPX CC / CSP DTE45** 确认淘汰或降级；overlap 修正后均不达标
- **数据瓶颈**：Massive S3 pre-2022 全部 403 Forbidden，无法延伸历史，影响 P0-2/P1-2

新增可执行建议：**VIX≥15 财报 IC 入场过滤规则**（cum_pnl +9%，WR +4pp）。

---

## 二、生产候选 Shortlist（Phase 2 最终版）

| 候选 | 配置 | Phase 2 状态 | Phase 1 Sharpe | 关键限制 |
|------|------|------------|--------------|---------|
| **SPX CSP** | Δ0.20 DTE30 | ✅ **正式候选** | 0.85 | 无重大限制；2022 压测通过 |
| **GOOGL CSP** | Δ0.20 DTE21 | 🔵 **正式候选边缘** | 2.28 | 缺 2019–2021 / COVID 样本 |
| **AMZN CSP** | Δ0.25 DTE21 | 🔵 **正式候选边缘** | 1.50 | 缺 2019–2021 / COVID 样本 |
| **COST 财报 IC** | T-3, 1.0×, IC | 👁️ **观察候选** | ROE 25.6% | N=15；缺 COVID；Sharpe 弱 |
| **JPM 财报 IC** | T-3, 1.0×, IC | 👁️ **观察候选** | ROE 32.8% | N=9；样本极小 |

**状态定义：**
- ✅ 正式候选：可进入 paper trading，无已知结构性风险
- 🔵 正式候选边缘：信号强，可进入 paper trading，需标注 COVID 尾部风险未验证
- 👁️ 观察候选：alpha 信号存在但置信度不足；需 ≥12 个月 paper trading 后再评估生产

---

## 三、各任务结论速览

### P0-1 — DTE45 Overlap 修正（DONE 2026-05-04）

**结论：CC DTE45 淘汰；CSP DTE45 降级为观察项**

| Combo | 修正后 Sharpe（A+B 均值） | MaxDD | 结论 |
|-------|------------------------|-------|------|
| CC DTE45 全部 Δ | 1.19–1.25 | −15% | ❌ 淘汰（Sharpe < 1.33，MaxDD >> −9%） |
| CSP DTE45 全部 Δ | 1.34–1.57 | 高度不稳定 | ⚠️ 降级（两对齐差距 >3.0 Sharpe 单位） |

根因：月度 roll 间距 ≈28 天，DTE45 持仓 ≈42 天 → Phase 1 约 50% cycle 重叠。修正后 N 减半，单一关税崩盘事件（2025-04）可将全年 Sharpe 从 3.22 打至 −0.08。

---

### P0-2 — COST/JPM 财报铁鹰历史延伸（CLOSED-C 2026-05-05）

**结论：接受 4 年窗口（2022–2026）；COST/JPM 降级为观察候选**

Massive S3 对所有 pre-2022 日期返回 `403 Forbidden`（订阅边界）。测试命令：
```bash
venv/bin/python -m research.q041.download_massive --start 2019-01-01 --end 2019-03-31 --symbols COST JPM
# 结果：64 个交易日全部 403 Forbidden
```

4 年数据现状：COST N=15（ROE 25.6%，WR 66.7%），JPM N=9（ROE 32.8%，WR 77.8%）。缺失 COVID 崩盘（2020-Q1-Q2）导致 MaxDD 估计可信度有限。

**升级条件：** ≥12 个月实盘 paper trading（≥4 个财报周期），或未来获取 pre-2022 数据。

---

### P1-1 — IMR 入场过滤（CLOSED 2026-05-05）

**结论：弱信号，效果因标的而异；不建议统一实施**

方法：事件内隐含移动百分位排名（IMR），阈值 0%/25%/33%/50%。

| 应用范围 | IMR≥33% 效果 | 建议 |
|---------|------------|------|
| **COST** | per-event pnl $1.89 → $0.93（−50%） | ❌ 不实施 |
| **JPM** | per-event pnl $1.20 → $1.99（+66%） | ✅ paper trading 阶段可选 |
| ex-META 全体 | WR 49% → 55.4%，p=0.083 | 弱信号，次要参数优化 |

根因：COST 大赢家（2024-12, +$20.66；2026-03, +$17.49）恰好发生在低 IMR 事件，过滤后被剔除。COST 财报结果由微小已实现波动驱动，与隐含移动水平无关。

---

### P1-2 — GOOGL/AMZN CSP 历史延伸（CLOSED-C 2026-05-05）

**结论：Massive pre-2022 同样 403；接受 4 年窗口；维持正式候选边缘**

GOOGL/AMZN 与 COST/JPM 面临同样数据瓶颈。关键区别：Sharpe（2.28/1.50）远高于门槛（0.83），且 4 年窗口已覆盖 2022 熊市（SPX −27%），信号可信度显著高于财报 IC。

**升级条件：** ≥12 个月 paper trading（≥3 个含波动率冲击事件）。

---

### P2-1 — SPX CSP DTE30 2022 熊市压测（DONE 2026-05-05）

**结论：2022 年仅 1 cycle 净亏损；策略维持正式候选状态**

| 时期 | N | WR% | CumPnL | Sharpe | 备注 |
|------|---|-----|--------|--------|------|
| 2022 | 5 | 80 | +$31 | 0.15 | 1 次深度击穿 |
| 2023 | 8 | 100 | +$185 | 3.33 | 完美年 |
| 2024 | 8 | 100 | +$214 | 5.76 | 完美年 |
| 2025 | 7 | 100 | +$272 | 2.89 | 含关税前兆浅穿（仍盈） |
| **全期** | **30** | **97** | **+$763** | **2.18** | **MaxDD=−2.84%** |

**关键发现 — "IV 压缩陷阱"：** 2022-08-19 cycle（唯一亏损）的根因是 7 月反弹将 IV 从 30% 压缩至 22%，导致 Δ0.20 选出 4.2% OTM 的 strike（而非正常 6–7%），9 月 −9.3% 跌幅穿透。

**风险管理结论：** Static OTM% / IV 门槛过滤不可行（会剔除 2023–2025 全部低 VIX 盈利 cycle）。正确风控 = **仓位规模**，而非入场过滤。

---

### P2-2 — IV Regime 年度效应分析（DONE 2026-05-05）

**结论：VIX<15 是财报 IC 明确亏损区；VIX≥15 过滤有效；2024 弱势为双重成因**

**VIX "Goldilocks" 非线性关系：**

| VIX 区间 | IC 表现 | 建议 |
|---------|---------|------|
| **< 15** | WR=36%，cum=**−$10**，premium≈0 | **跳过入场** |
| **15–22（最优）** | WR=56%，cum=**+$82** | 正常入场 |
| **> 22** | WR=48%，cum=+$23，realized move 偏高 | 谨慎，可考虑仓位减半 |

**VIX≥15 过滤效果：**
- 仅移除 24 个 VIX<15 事件（这 24 个事件合计 pnl = −$8.15）
- 整体 cum_pnl：$94 → **$102**（+9%），WR：49% → **53%**（+4pp）

**2024 年弱势双重根因：**
1. **低 VIX 型**：VIX<15 事件占多数 → 溢价≈0 → 轻微移动即亏损
2. **大移动型**：GOOGL +10%（AI 云加速叙事）、AMZN +8.4% → 即使 VIX 正常也突破 IC 翼展

注：VIX 与溢价线性相关 r=0.004（p=0.97），关系非单调，不能用 VIX 水平直接预测溢价高低。

---

## 四、Phase 2 新增可执行参数

基于 P2-2 发现，以下规则可纳入生产参数考量：

| 规则 | 适用策略 | 依据 | 预期改善 |
|------|---------|------|---------|
| **VIX≥15 入场过滤** | COST/JPM 财报 IC | P2-2：VIX<15 quartile cum=−$10 | cum +9%，WR +4pp |
| **VIX>22 仓位减半** | 财报 IC 通用 | P2-2：高 VIX 期 realized move 偏高 | 降低尾部损失 |
| **仓位规模控制** | SPX CSP DTE30 | P2-1：MaxDD=−2.84% 可在全年内覆盖 | 防止单 cycle 爆仓 |
| **IMR≥33% 可选** | JPM 财报 IC 仅 | P1-1：per-event +$0.79，WR +7pp | paper trading 阶段验证 |

---

## 五、Phase 2 完整任务状态

| 任务 | 日期 | 结论 | 文件 |
|------|------|------|------|
| **P0-1** DTE45 overlap 修正 | 2026-05-04 | CC 淘汰；CSP 降级为观察 | `q041_p2_p01_dte45_overlap_corrected_2026-05-04.md` |
| **P0-2** COST/JPM 历史延伸 | 2026-05-05 | CLOSED-C；接受 4 年窗口 | `q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md` |
| **P1-1** IMR 入场过滤 | 2026-05-05 | 弱信号；COST 不实施；JPM 可选 | `q041_p2_p11_ivr_filter_2026-05-05.md` |
| **P1-2** GOOGL/AMZN 历史延伸 | 2026-05-05 | CLOSED-C；正式候选边缘 | `q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md` |
| **P2-1** 2022 熊市压测 | 2026-05-05 | 1 cycle 亏损；IV 压缩陷阱；维持候选 | `q041_p2_p21_spx_csp_bearmarket_2026-05-05.md` |
| **P2-2** IV regime 分析 | 2026-05-05 | VIX<15 亏损区；VIX≥15 过滤有效 | `q041_p2_p22_iv_regime_2026-05-05.md` |
| **P1-3** SPX CSP DTE45 复核 | — | 低优先级，仅按需 | 暂不执行 |

---

## 六、遗留的已知风险

| 风险 | 影响策略 | 说明 |
|------|---------|------|
| COVID 崩盘（2020-Q1）未测试 | GOOGL/AMZN CSP；COST/JPM IC | SPX −34% 在 1 个月内完成；超出 DTE30 cycle 保护范围 |
| 2022 Jan–Apr 缺失 | SPX CSP | 数据从 2022-05-06 开始；2022-04 下跌 −8.8% 未测试 |
| pre-2022 全量数据不可得 | 全部候选 | Massive S3 403 Forbidden；除非升级订阅否则无解 |
| N 极小（COST N=15，JPM N=9） | 财报 IC | 单一事件可主导年度结果；置信度有限 |
| 大移动型个股风险 | 财报 IC | GOOGL/AMZN 可能出现 8–10% 财报移动；无法通过 VIX 预测 |

---

## 七、下一阶段建议

**Phase 2 → Paper Trading 路径：**

```
优先级 1（立即）:
  SPX CSP Δ0.20 DTE30
  → 每月第三个 Friday 入场；VIX 无最低门槛要求
  → 仓位：建议单 cycle 名义敞口 ≤ 账户总 BP 的 20%

优先级 2（可同步）:
  GOOGL CSP Δ0.20 DTE21
  AMZN CSP Δ0.25 DTE21
  → 月度 roll；观察 COVID 量级波动下的实盘行为

优先级 3（谨慎试水）:
  COST 财报 IC（T-3，1.0×）— 加 VIX≥15 过滤
  JPM 财报 IC（T-3，1.0×）— 加 VIX≥15 + IMR≥33% 过滤
  → 每季度一次；paper trading 积累 ≥4 个完整财报周期后再评估生产

暂缓:
  SPX CSP DTE45（P1-3 观察位，仅在长历史支持后重看）
```

---

## 八、文件索引

### Phase 2 新增文档

| 文件 | 内容 |
|------|------|
| `doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md` | DTE45 overlap 修正结果 |
| `doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md` | COST/JPM 4 年窗口重框 |
| `doc/q041_p2_p11_ivr_filter_2026-05-05.md` | IMR 入场过滤研究 |
| `doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md` | GOOGL/AMZN 4 年窗口重框 |
| `doc/q041_p2_p21_spx_csp_bearmarket_2026-05-05.md` | SPX CSP 2022 熊市压测 |
| `doc/q041_p2_p22_iv_regime_2026-05-05.md` | IV regime 年度效应分析 |

### Phase 1 原始文档（参考）

| 文件 | 内容 |
|------|------|
| `doc/q041_d3_module_ab_backtest_2026-05-04.md` | D3：SPX/个股 CC/CSP 108 combo |
| `doc/q041_d4_module_c_earnings_2026-05-04.md` | D4：财报铁鹰事件研究 |

### Backtest 脚本

| 脚本 | 用途 |
|------|------|
| `backtest/prototype/q041_p2_p01_dte45_overlap_corrected.py` | DTE45 overlap 修正 |
| `backtest/prototype/q041_p2_p11_ivr_filter.py` | IMR 过滤扫描 |
| `backtest/prototype/q041_p2_p21_spx_csp_bearmarket.py` | SPX CSP 熊市压测 |
| `backtest/prototype/q041_p2_p22_iv_regime.py` | IV regime 分析 |

---

*文档由 Quant Researcher 生成，2026-05-05。*
