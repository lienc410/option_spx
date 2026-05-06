# Q041 Phase 2 启动指引 — Planner 存档

**生成日期：** 2026-05-04  
**前置工作：** Q041 Phase 1 已全部完成（D1/D2/D3/D4 CONDITIONAL PASS）  
**本文目的：** 为 planner 提供 D3/D4 关键结论与 Phase 2 任务清单，不需重读原始报告即可启动规划

---

## 一、Phase 1 结论速览

| 阶段 | 结论 | 关键数字 |
|------|------|---------|
| D1 Data Sanity | PASS | 17 个标的数据完整，4 条过滤规则确立 |
| D2 BXM 复现 | PASS | BXM 复现相关 0.97，D3 门槛确立 |
| D3 Module A/B | CONDITIONAL PASS | SPX CSP Δ0.20 DTE30 Sharpe 0.85 边际过线 |
| D4 Module C | CONDITIONAL PASS | 财报铁鹰 ex-META Sharpe* 0.7–0.9 |

**Phase 1 整体：CONDITIONAL PASS — 进入 Phase 2 精细化研究**

---

## 二、生产候选短名单（已确认）

| 候选 | 配置 | Phase 1 Sharpe | 状态 |
|------|------|--------------|------|
| **SPX CSP** | Δ0.20 DTE30 | 0.85 | ✅ 进入 Phase 2 |
| **GOOGL CSP** | Δ0.20 DTE21 | 2.28 | ✅ 需更长历史验证 |
| **AMZN CSP** | Δ0.25 DTE21 | 1.50 | ✅ 需更长历史验证 |
| **COST 财报铁鹰** | T-3, w=1.0×, IC | ROE 25.6% / 15 events | ✅ 需历史延伸 |
| **JPM 财报铁鹰** | T-3, w=1.0×, IC | ROE 32.8% / 9 events | ✅ 需历史延伸 |

---

## 三、排除项目与原因（勿重测）

| 标的/配置 | 排除原因 | 结论文件 |
|---------|---------|---------|
| **META 财报 IC** | 溢价负值（−2.29%）；3 次单日 21–29% 跳动为结构性异常，不是统计异常 | D4 §5 |
| **JPM CSP** | 2023-Q1 区域银行危机集中冲击；个股 put 尾部不对称；CumRet −25–33% | D3 §2.4 |
| **DTE21 SPX CC/CSP** | Sharpe 全面不达标（CC 0.32–0.37；CSP 0.14–0.27） | D3 §1 |
| **Put Spread（财报）** | 全参数组合负收益（Sharpe* −0.5 至 −1.0）；方向性错误不适合财报双向跳动 | D4 §3 |
| **AMZN/MSFT 财报 IC** | 铁鹰累计亏损（AMZN −$10.30，MSFT −$9.77）；超大移动未被权利金覆盖 | D4 §4.3 |

---

## 四、未解决问题（Phase 2 必须处理）

**状态更新（2026-05-05 / P0-1 + P0-2 均已关闭）：**
- `SPX CC DTE45`：已淘汰
- `SPX CSP DTE45`：已降级为观察项
- `COST/JPM 财报 IC`：降级为观察候选（数据限制，接受 4 年窗口）
- `Phase 2` 主线前移到 **P1-1（IVR 入场过滤）**

### P0 — 阻塞生产的问题（全部关闭）

| # | 问题 | 原因 | 结论 |
|---|------|------|------|
| **P0-1** | DTE45 SPX CC/CSP overlap-corrected rerun | **DONE**。CC 修正后 Sharpe `1.19–1.25` + MaxDD `≈ -15%` → 淘汰；CSP 均值通过但对齐极度敏感 → 降级观察 | 关闭：`doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md` |
| **P0-2** | COST/JPM 财报铁鹰样本量极小（N=9–15）| 无法判断稳定性；需 pre-2022 历史 | **CLOSED-C**：Massive S3 pre-2022 全部 403 Forbidden（订阅边界）。接受 4 年窗口（2022–2026），COST/JPM 降级为观察候选。结论：`doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md` |

### P1 — 改善生产参数的研究

| # | 问题 | 背景 |
|---|------|------|
| **P1-1** | IVR 入场过滤 | 财报铁鹰在 IVR > 30–50% 时是否提升选择性和 ROE？（未研究）|
| **P1-2** | GOOGL/AMZN CSP 更长历史 | 当前仅 45 个 cycle（约 2022→2026）；需验证 2019–2021 熊牛周期 |
| **P1-3** | SPX CSP DTE45 观察位复核（仅在未来需要时） | 当前均值 Sharpe 通过，但 2025-04 单一尾事件导致对齐极不稳定；不进入正式候选，仅保留观察价值 |

### P2 — 理解与压测

| # | 问题 |
|---|------|
| **P2-1** | 2022 熊市期间 CSP 压测（SPX −27%）：SPX CSP DTE30 期间 MaxDD −4.6% 看似低，但需按真实 2022 月份逐周期验证 |
| **P2-2** | 年度稳健性弱（D4 发现 2024 财报溢价接近 0）：需理解为何 2024 无效，是否存在 IV regime 切换 |

---

## 五、D3 关键发现（供 planner 备查）

**什么有效：**
- SPX CSP DTE30 Δ0.20：CVaR 仅 −3.53%，胜率 83%，低尾风险，适合作为策略基础层
- GOOGL CSP Δ0.20 DTE21：Sharpe 2.28，MaxDD −4.7%，是已测试个股中风险调整最优
- 个股 CC 高收益（JPM +400%）= bull market beta + premium，不是可单独复制的 alpha

**什么不有效：**
- 所有 DTE21 combo（CC/CSP）Sharpe < 0.4，权利金太薄，频率优势无法弥补
- 金融股（JPM）CSP 受 2023 区域银行危机重创；银行板块系统性风险不能用 delta 管理

**结构性见解：**
- DTE 升高 → Sharpe 升高，但 DTE45 存在 cycle 重叠，需去重后验证是否真实改善
- 滑点假设（3%）在 COST/WMT 等流动性较低标的可能低估（实际 5–8%）

---

## 六、D4 关键发现（供 planner 备查）

**核心统计：**
- T-3 入场隐含移动溢价 t=2.67，p=0.009（1% 显著），N=113 events
- T-1 入场 p=0.076（边际，10% 水平）
- 年度不稳定：2024 溢价≈0，仅 2025 年独立显著（t=2.50）

**最强个股：**
- JPM：溢价 t=3.35（p=0.006），财报铁鹰 ROE 32.8%，胜率 77.8%
- COST：溢价 t=2.73（p=0.016），财报铁鹰 ROE 25.6%，胜率 66.7%

**META 排除逻辑（不是过拟合，是基本面过滤）：**
- 2022-10 (+28.8%), 2023-02 (+26.7%), 2024-02 (+21.7%) — 公司战略转型期引发非常规跳动
- 同一公司历史已有明确原因（重组 → Efficiency → AI 增长叙事），可作为稳定规则记录

**结构选择：**
- Iron Condor > Put Spread（财报具有双向跳动性，单腿方向策略系统性负收益）
- 推荐宽度：1.0× implied move（ROE 10.7% ex-META；0.5× ROE 相近但 Sharpe 较低）

---

## 七、Phase 2 建议优先级（2026-05-05 更新）

```
P0（全部关闭）:
  ✅ P0-1: DTE45 overlap corrected → CC 淘汰，CSP 降级
  ✅ P0-2: COST/JPM 历史延伸 → CLOSED-C，接受 4 年窗口

P1（当前主线）:
  ✅ [P1-1] IVR 入场过滤研究 → CLOSED — 弱信号，效果因标的而异
     COST：不实施过滤；JPM：IMR≥33% 可酌情用于 paper trading
     结论：`doc/q041_p2_p11_ivr_filter_2026-05-05.md`
  ✅ [P1-2] GOOGL/AMZN CSP 历史延伸 → CLOSED-C（Massive pre-2022 同样 403）
     GOOGL/AMZN 维持"正式候选边缘"（Sharpe 2.28/1.50，信号强于 COST/JPM）
     结论：`doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md`
  → [P1-3] SPX CSP DTE45 观察位复核（低优先级，仅按需）

P2（低优先级，可视情况安排）:
  ✅ [P2-1] 熊市压测细化 → DONE
     2022 年仅 1 cycle 亏损（Aug-Sep, −$114.85）；根因："IV 压缩陷阱"（反弹后 IV 低 → strike 过近）
     全年仍正收益(+$31)；MaxDD=−2.84%（单 cycle）；static filter 不可行；正确风控=仓位规模
     结论：`doc/q041_p2_p21_spx_csp_bearmarket_2026-05-05.md`
  ✅ [P2-2] IV regime 年度效应分析 → DONE
     VIX<15 = 亏损区（Q1 cum=−$10）；VIX 15–22 = 最优区（Q2 cum=+$50）
     VIX≥15 过滤：cum +9%（$94→$102），WR +4pp；2024 弱势 = 低VIX + GOOGL/AMZN超大移动
     建议：COST/JPM 财报 IC 加入 VIX≥15 入场规则
     结论：`doc/q041_p2_p22_iv_regime_2026-05-05.md`
```

**生产候选 shortlist（P1-2 关闭后最终版）：**

| 候选 | 状态 |
|------|------|
| SPX CSP Δ0.20 DTE30 | ✅ 正式候选 |
| GOOGL CSP Δ0.20 DTE21 | 🔵 正式候选边缘（Sharpe 2.28；缺 COVID 样本） |
| AMZN CSP Δ0.25 DTE21 | 🔵 正式候选边缘（Sharpe 1.50；缺 COVID 样本） |
| COST 财报 IC T-3 1.0× | 👁️ 观察候选（N=15；Sharpe 弱；缺 COVID 样本） |
| JPM 财报 IC T-3 1.0× | 👁️ 观察候选（N=9；样本极小） |

---

## 八、相关文件索引

| 文件 | 内容 |
|------|------|
| `doc/q041_d3_module_ab_backtest_2026-05-04.md` | D3 完整报告（108 个 combo 数据表）|
| `doc/q041_d4_module_c_earnings_2026-05-04.md` | D4 完整报告（1346 条事件记录分析）|
| `backtest/prototype/q041_d4_earnings_ivcrust.py` | D4 主回测脚本（含财报日历硬编码）|
| `/tmp/d3_stocks_results.pkl` | D3 个股结果 DataFrame（108 行 × 14 列）|
| `/tmp/d4_earnings_results.pkl` | D4 财报事件结果（1346 行）|
| `/tmp/tier1_px.pkl` | Tier-1 个股日线收盘价字典 |

---

*本文档由 Quant Researcher 生成，2026-05-04。*
