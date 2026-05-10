# Q055 — Naked Put Strategy Slot Competition Protocol & Execution

**生成日期：** 2026-05-10
**生成者：** Quant Researcher
**触发：** PM 2026-05-09 决策 — Q041 T1 SPX CSP 与 /ES V2c 正式合并为单一 naked put 策略槽，竞争后留一个
**状态：** 协议已设计、执行已完成、推荐已给出 — 等 PM 最终确认

---

## 1. 候选

| 标签 | 实现 | Window | Pricing | Account |
|------|------|--------|---------|---------|
| **A** | /ES V2c — true rolling weekly ladder, entry=49 trading-day DTE, exit@21, STOP_MULT=8.0, profit=10% | 2000–2026 | BS-flat (VIX as sigma) | $500k |
| **B** | SPX CSP T1 — single slot, Δ0.20, DTE30 (calendar), hold-to-expiry | 2000–2026 | BS-flat (VIX as sigma) | $500k |

**同口径声明：** 两者均使用 26 年 SPX + VIX 合成数据，几何 Ann ROE 定义，BP-trading-day 资本效率口径，相同 $500k 账户假设。

---

## 2. 协议设计

### 2.1 处理 ladder 结构性差异的方式

PM 指令："SPX CSP 在 $500k 下无法形成 ladder 是结构性约束，不应被协议设计绕过。"

**采纳方式：**

- **主评分用 account-level**（生产现实）：A 的 ladder 优势是真实可部署的 alpha，不被规避
- **辅助报告 per-contract $/year**（结构盲）：让 PM 看到剥离 ladder 后的纯策略效率
- **辅助报告 $/BP-year**（资本效率）：判断如果未来账户尺寸允许 SPX CSP 自身 ladder，谁会更值得移植

### 2.2 三层评分

**Tier 1 — Vetos（任一不通过即淘汰）**

| 编号 | 条件 | 阈值依据 |
|------|------|---------|
| V1 | Worst single trade ≤ 15% NLV | broker/PM 自我应激阈值；超过会触发非自愿减仓行为，破坏统计假设 |
| V2 | 几何 Ann ROE > 0% | 26 年下连正收益都做不到的策略不应进入生产 |
| V3 | Bootstrap CI 下界（block=250）> -1.0% Ann | 排除"明显无 alpha"的候选；不要求显著为正（两者皆 borderline） |

**Tier 2 — Primary（account-level，赢 2/3 即获胜）**

| 编号 | 指标 | 含义 |
|------|------|------|
| P1 | 几何 Ann ROE | 账户层产出，PM top-level objective |
| P2 | $/BP-year | 资本效率，是否值得占用 BP |
| P3 | Worst trade % NLV | 单笔尾部纪律 |

**Tier 3 — Secondary（informational，只作为 tie-breaker）**

| 编号 | 指标 |
|------|------|
| S1 | Annualised Sharpe |
| S2 | Win Rate |
| S3 | CVaR 5% / NLV |
| S4 | Account MDD |
| S5 | $/contract/year（结构盲） |

### 2.3 显式排除的判据

- **不用绝对 worst trade $**：会被 ladder 规模影响
- **不用 trade count**：trade 频率不同，指标层面已被 trades_per_year 反映
- **不用对 Q041 P2-1 的 3.8 年子样本** ：会失去 2008/2018/2020 等关键尾事件

---

## 3. 执行结果

### 3.1 基础参数（验证同口径）

| | A: /ES V2c | B: SPX CSP T1 |
|---|------------|--------------|
| Trades total | 1,310 | 315 |
| Trades per year | 49.8 | 12.0 |
| Concurrent contracts (avg) | **5.6** | **1.0** |
| BP deployed avg | $114,800 | $50,000 |

### 3.2 Tier 1 Vetos

| Veto | A | B |
|------|---|---|
| V1: Worst trade $ | -$54,804 | **-$89,962** |
| V1: Worst trade % NLV | **-10.96%** ✅ | **-17.99%** ❌ |
| V1 决议 | **PASS** | **FAIL** |
| V2: Ann ROE geometric | +1.28% ✅ | +0.44% ✅ |
| V3: Bootstrap CI lo Ann % | -0.60% ✅ | -0.24% ✅ |

**B 在 V1 失败**：2020-02 COVID 单 cycle 损失 -$89,962 = 账户 -17.99%，超过 -15% NLV 阈值。

### 3.3 Tier 2 Primary（即使 B 不被 V1 veto，仍要算）

| 指标 | A | B | Winner |
|------|---|---|--------|
| P1: 几何 Ann ROE | **+1.28%** | +0.44% | **A** |
| P2: $/BP-year | **6.61%** | 4.67% | **A** |
| P3: Worst % NLV | **-10.96%** | -17.99% | **A** |

**Tier 2: A 胜 3/3。**

### 3.4 Tier 3 Secondary

| 指标 | A | B | 备注 |
|------|---|---|------|
| S1: Sharpe (annualised) | **0.20** | 0.11 | A 占优 |
| S2: Win Rate | 77.4% | **88.3%** | B 占优（CSP 结构特征）|
| S3: CVaR 5% / NLV | -3.77% | **-3.58%** | B 略好 |
| S4: Account MDD | -32.7% | **-17.9%** | B 占优（少 trade，低累计 DD 暴露）|
| S5: $/contract/year（结构盲）| $1,354 | **$2,333** | B 占优（单 contract 效率更高）|

**Tier 3 不影响 verdict（已由 V1 + Tier 2 决定），但保留信息透明：**

- B 在 single-position-strategy efficiency（per-contract）上更优
- B 的 account MDD 较小，部分原因是 trade 数少（315 vs 1310），暴露窗口少
- B 的 WR 高是 CSP 结构特征（少数大事件主导损失），不构成相对 A 的 alpha 优势

---

## 4. Verdict

### **A 胜出**

**两条独立路径都指向 A：**

1. **B 在 Tier 1 V1（worst trade % NLV）上 FAIL** — 2020 单 cycle -17.99% NLV 超过 -15% 阈值，触发协议排除
2. **即使放宽 V1 阈值到 -20%，A 仍在 Tier 2 全胜 3/3**：账户 ROE 高 2.9×、资本效率高 41%、worst trade % NLV 一半

### Veto 阈值敏感性（透明披露）

| V1 阈值 | A 状态 | B 状态 | 决定路径 |
|---------|--------|--------|---------|
| **-15% NLV (默认)** | PASS | **FAIL** | B 被淘汰 |
| -18% NLV | PASS | PASS | Tier 2: A 胜 3/3 |
| -20% NLV | PASS | PASS | Tier 2: A 胜 3/3 |

无论 V1 阈值如何宽松，**A 都在 Tier 2 全胜**。所以这个 verdict 对 V1 阈值选择不敏感。

---

## 5. 结构性约束的诚实披露

按 PM 要求如实呈现 ladder 约束的影响：

**A 的 alpha 优势 (+0.84pp Ann ROE) 由两部分组成：**

| 来源 | 估计贡献 |
|------|---------|
| Ladder 结构性优势（5.6× 并发 vs 1×） | ~主要部分 |
| Per-BP 资本效率（6.61% vs 4.67%）| ~次要部分 |

**Per-contract $/year 显示 B 单合约更高效**（$2,333 vs $1,354），但：

- 这是结构盲口径
- B 在 $500k 下无法部署多于 1 张
- A 的 vehicle 选择允许 5.6× BP 周转
- **A 的 ladder 优势是真实的可部署 alpha，不是协议偏见的产物**

**对未来账户尺寸增长的含义：**

如果账户尺寸增长到 $2M+ 允许 SPX CSP 自身 ladder：
- B per-contract 更高 → 5 槽 SPX CSP ladder 可能 alpha = 0.44% × 5.6 ≈ 2.5% account ROE
- 这会反超 A 的 +1.28%
- 但**需在那时重新做这个比较**，不是现在的决策依据

---

## 6. 推荐

**A: /ES V2c 留任，B: SPX CSP T1 淘汰。**

理由（1-2 句）：

> B 在 -15% NLV worst-trade veto 上失败（2020-02 COVID 单 cycle -18% NLV），且即使放宽 veto，A 在所有三项 Tier 2 主指标上全胜（账户 ROE 2.9× / 资本效率 +41% / 尾部纪律一半）。A 的优势来自 vehicle 容许 5.6× ladder 部署 + per-BP 资本效率更高的双重叠加，是 $500k 账户的真实可部署 alpha。

---

## 7. 附加 caveats

1. **A 的 V2c 升级仍未进 SPEC**——本次 verdict 只决定"naked put 槽位归属于 /ES"，是否把当前 fixed-slot 替换为 V2c true ladder 是独立的 PM 决定（Q041 T1 治理审查归档已建议升级）
2. **两者都是 BS-flat 合成结果**，BS 系统性低估 OTM put premium ~2-3%；这个 bias 对 A 和 B 同向，不影响相对排序
3. **A 的 V2 / V2c bootstrap 显著性是 borderline**——75% 的种子下显著，CI 下界 +0.08% Ann ROE。生产时应作为 "alive-with-conditions" 推进，paper-trading 阶段需密切监控
4. **B 的研究路径不被关闭**——本 verdict 仅决定 naked put 槽位归属。Q041 关于 GOOGL/AMZN/COST/JPM 的研究保持原 status

---

## 8. 后续动作

| 项 | 责任方 | 时机 |
|---|-------|------|
| Q041 T1 SPX CSP T1 paper-trading 计划正式撤销 | PM | 收到本 verdict 后 |
| /ES V2c true ladder + STOP=8 SPEC 草案 | Quant Researcher | PM 批准升级路径后 |
| PROJECT_STATUS.md 反映 naked put 槽位归属 = /ES | Planner | sediment 阶段 |
| RESEARCH_LOG.md 增加 Q055 竞争协议条目 | Planner | sediment 阶段 |

---

## 9. 源材料

| 文件 | 内容 |
|------|------|
| `backtest/prototype/q055_naked_put_competition.py` | 竞争协议执行脚本 |
| `/tmp/q055_competition_results.pkl` | 全部指标数据 + verdict |
| `task/q041_t1_es_governance_review_archive_2026-05-09.md` | 上一轮治理审查归档（前置依据）|
| `/tmp/q041_es_v2_validation.pkl` | V2c 数据来源 |
| `/tmp/q041_es_full_window_bs.pkl` | SPX CSP 数据来源 |

---

*由 Quant Researcher 生成，2026-05-10。*
