# Q041 Phase 2 — P1-2: GOOGL/AMZN CSP 历史延伸（重框结论）

**日期：** 2026-05-05  
**范围：** GOOGL CSP Δ0.20 DTE21 / AMZN CSP Δ0.25 DTE21  
**结论：** **数据不可得 → 接受 4 年窗口；维持正式候选边缘状态（强 Sharpe 信号支撑）**

---

## 一、数据可得性验证

```bash
venv/bin/python -m research.q041.download_massive --start 2019-01-01 --end 2019-03-31 --symbols GOOGL AMZN
```

结果：64 个交易日全部 `403 Forbidden`。与 P0-2 结论一致：**Massive S3 订阅边界对所有 symbol 统一生效**，pre-2022 数据不可得。

决策：同 P0-2，选 **C（接受 4 年窗口，重框结论）**。

---

## 二、现有 4 年窗口数据（D3 最终数字）

数据覆盖：**2022-05 → 2026-04**（约 45 个月度 cycle）

| 指标 | GOOGL CSP Δ0.20 DTE21 | AMZN CSP Δ0.25 DTE21 |
|------|----------------------|----------------------|
| Sharpe | **2.28** | **1.50** |
| MaxDD | −4.7% | 未记录（见 D3 报告）|
| CVaR | 低 | 低 |
| 数据来源 | `doc/q041_d3_module_ab_backtest_2026-05-04.md` |

---

## 三、与 COST/JPM 的关键差异

| 因素 | COST/JPM 财报 IC | GOOGL/AMZN CSP |
|------|----------------|----------------|
| Sharpe | 0.7–0.9（边际） | **2.28 / 1.50（显著）** |
| 4 年窗口是否含 2022 熊市 | ✅ | ✅ CSP 在 −27% 期间 MaxDD 仅 −4.7% |
| 缺失 regime | COVID + 2021 | COVID + 2021 |
| 信号强度 | 弱 | **强** |

关键判断：GOOGL CSP Sharpe 2.28 远高于门槛 0.83，即使 2019–2021 测试结果较弱，现有信号可信度已显著高于 COST/JPM。4 年窗口对 CSP 策略的覆盖质量也高于财报事件研究（2022 熊市 IS 包含在内）。

---

## 四、缺失 regime 影响评估

| 时期 | 事件 | 对 GOOGL/AMZN CSP 的潜在影响 |
|------|------|---------------------------|
| 2020-02 → 2020-04 | COVID 崩盘（SPX −34%） | CSP 短腿可能被深度突破；MaxDD 估计可能低估 |
| 2020-11 → 2021-12 | 高流动性 + 科技股超涨 | IV 环境与 2022 后不同；CSP 权利金可能更高 |
| 2019 | 基准年 | 稳定市场，CSP 应表现良好 |

**净影响判断：** COVID 崩盘是主要风险点。2022 熊市（-27%）已被包含，提供了部分尾部样本，但 COVID 性质不同（速度更快，幅度更大）。

---

## 五、GOOGL/AMZN CSP 候选状态更新

| 策略 | Phase 1 状态 | P1-2 后状态 | 备注 |
|------|------------|------------|------|
| **GOOGL CSP Δ0.20 DTE21** | CONDITIONAL PASS | **正式候选边缘** | Sharpe 2.28 >> 门槛；2022 熊市已覆盖；缺 COVID 样本 |
| **AMZN CSP Δ0.25 DTE21** | CONDITIONAL PASS | **正式候选边缘** | Sharpe 1.50 >> 门槛；同上 |

**"正式候选边缘"定义（高于 COST/JPM 的"观察候选"）：**
- 单独信号强度已超过生产门槛
- 可进入 paper trading 阶段，但需标注 COVID 尾部风险未验证
- 升级为完整正式候选的条件：12 个月 paper trading（≥3 个 bear/vol spike 事件），或未来 pre-2022 数据获取后补测

---

## 六、对 Phase 2 生产候选 shortlist 的影响（最终版）

| 候选 | 配置 | Phase 2 状态 | 备注 |
|------|------|------------|------|
| **SPX CSP** | Δ0.20 DTE30 | ✅ 正式候选 | Sharpe 0.85，无 overlap 污染，2022 熊市已验证 |
| **GOOGL CSP** | Δ0.20 DTE21 | 🔵 正式候选边缘 | Sharpe 2.28；缺 COVID 样本 |
| **AMZN CSP** | Δ0.25 DTE21 | 🔵 正式候选边缘 | Sharpe 1.50；缺 COVID 样本 |
| **COST 财报 IC** | T-3, 1.0×, IC | 👁️ 观察候选 | N=15；Sharpe 弱；缺 COVID 样本 |
| **JPM 财报 IC** | T-3, 1.0×, IC | 👁️ 观察候选 | N=9；样本极小 |

---

*文档由 Quant Researcher 生成，2026-05-05。*  
*参考文档：`doc/q041_d3_module_ab_backtest_2026-05-04.md`，`doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md`*
