# SPX Strategy System — Strategy Status 2026-04-16
**Date: 2026-04-16 | 承接 `strategy_status_2026-04-12.md`**

*本版新增内容：*
- *DIAGONAL Gate 1（SPEC-049 ivp252 marginal zone）已通过 Fast Path 删除*
- *BPS NORMAL+BULLISH IVP≥50 gate 深度分析（Q015）— 保留，立研究方向*
- *回测基准更新（Gate 1 删除后）*

*以下章节无变更，请参阅 `strategy_status_2026-04-12.md`：*
- *§1–2：系统定位 / 历史回测基准*
- *§3：信号体系（IVP 多时间窗口）*
- *§4：SPX Credit 决策矩阵（LOW_VOL / NORMAL / HIGH_VOL / EXTREME_VOL）*
- *§5：StrategyParams（25 个字段）*
- *§6：SPX Credit 仓位 Sizing（regime decay / local_spike size-up）*
- *§7：Recommendation 字段（local_spike tag）*
- */ES Short Put 生产组件（SPEC-061）*

---

## 生产路由变更（2026-04-15~16）

### DIAGONAL Gate 1 — 已删除

**原规则**：`strategy/selector.py` 中 DIAGONAL 入场路径检查 `ivp252 ∈ [30, 50]` → REDUCE_WAIT（SPEC-049）

**删除依据**（详见 `research_notes.md` §54）：
1. 敏感性完全平坦——gate_hi 在 40~65 上遍历，Sharpe 恒为 0.41-0.43
2. 被拦 47 笔交易 Bootstrap CI [+$574, +$1,751]，**显著为正**
3. 系统净成本 -$11,146
4. 与 SPEC-056c（both-high gate 撤销）属同一模式——基于 IVP 子集的 entry gate 产生负向选择偏差

**当前状态**：`DIAGONAL_IVP252_GATE_LO/HI` 常量和 Gate 1 检查分支已从 `selector.py` 移除。Gate 2（IV=HIGH, SPEC-051）保留不动。

### BPS NORMAL+BULLISH IVP≥50 Gate — 保留

**现行规则**：`strategy/selector.py` 中 NORMAL + IV_NEUTRAL + BULLISH 路径，`iv.iv_percentile >= BPS_NNB_IVP_UPPER (50)` → REDUCE_WAIT。BPS 入场窗口 IVP ∈ [43, 50)。

**Q015 研究结论**（详见 `research_notes.md` §55）：

| 维度 | 结果 |
|------|------|
| 敏感性 | **有真实 cliff**：IVP 55→60，Sharpe 0.53→0.23（-57%） |
| Blocked 质量 | 44 笔，avg +$7，Bootstrap CI [-$601, +$1,062]，**非显著** |
| 删除代价 | Sharpe 0.49→0.22，MaxDD -$8,578→-$14,570 |
| 系统净成本 | -$6,690（主要来自 slot-occupancy 位移效应） |
| IVP vs VIX 关系 | r = -0.154（弱负相关），68% 的 IVP≥50 日 VIX < 18 |

**决策：保留 gate=50**。理由：
- Gate 1 删除时条件明确——blocked trades 显著正、敏感性平坦、删除是 Pareto 改进
- BPS gate 删除**不是** Pareto 改进——Sharpe 腰斩、MaxDD 大幅恶化

**已识别的设计缺陷**：IVP 在 NORMAL regime 里和 VIX 绝对水位弱负相关（高 IVP 对应低 VIX），gate 在 68% 的时间拦截的是 VIX<18 环境。当前 threshold 恰好保护了一个真实 Sharpe cliff，但保护机制偶然而非因果。这是 Q015 后续研究方向。

**新增常量**：`BPS_NNB_IVP_UPPER = 50`、`BPS_NNB_IVP_LOWER = 43`（原 hardcoded 值提取为 named constant，方便未来研究，功能不变）。

---

## 阈值敏感性研究方法论总结（2026-04-15~16）

本轮完成了对两类 IVP entry gate 的系统评估，确立了"解读 B"方法论：

```
对任意 entry gate 做评估：
  Phase 1 — 敏感性：±10~15 范围内遍历阈值，观察是否存在 cliff
            → 如果平坦，gate 可能无价值
            → 如果有 cliff，gate 在保护某个质量边界
  Phase 2 — 净价值：gate-on vs gate-off 全系统比较
            → blocked trades Bootstrap CI 判断被拦质量
            → slot-occupancy 位移分析判断间接效应
  Phase 3 — 绝对水位分析（如适用）：IVP vs VIX 相关性
            → 诊断 gate 的概念基础是否成立

  判断标准：
    blocked 显著正 + 敏感性平坦 → 删除（Gate 1 模式）
    blocked 非显著 + 有 cliff + Sharpe 保护真实 → 保留（BPS gate 模式）
    不做"找最佳阈值"优化
```

### 三个已确认的负向选择偏差案例

| Gate | 机制 | 结局 |
|------|------|------|
| SPEC-054 both-high gate | ivp63≥50 ∧ ivp252≥50 → block DIAGONAL | 撤销（SPEC-056c）|
| SPEC-049 Gate 1 | ivp252 ∈ [30,50] → block DIAGONAL | 撤销（Fast Path，2026-04-15）|
| BPS IVP≥50 gate | ivp ≥ 50 → block BPS in NNB | **保留**（有 Sharpe cliff，非同类问题）|

---

## 回测基准更新（Gate 1 删除后）

SPX Credit 策略基准（含全部 SPEC-048~060 + Gate 1 删除）：

| 指标 | 前版（2026-04-12） | 当前 |
|------|-----|------|
| 总 PnL (2000–2026) | $349,785 | **$361,125** |
| 总笔数 | 310 | **314** |

其余指标（年化、Sharpe、MaxDD 等）待完整重跑确认。

---

## 开放问题（截至 2026-04-16）

| 编号 | 状态 | 内容 |
|------|------|------|
| Q015 | research | BPS IVP gate 重设计：IVP 在 NORMAL regime 和 VIX 弱负相关，单维 IVP 门槛概念基础有偏差；需研究 IVP + VIX 联合 filter 或 VIX 趋势条件化 |
| Q014 | done | DIAGONAL Gate 1 撤销（已执行 Fast Path）|
| Q013 | open | /ES short put 运行时止损与持仓管理定义 |
| Q012 | open | /ES shared-BP 管理；SPEC-061 后续扩展决策 |
| Q011 | open | regime decay DIAGONAL 样本小（回测 n≈8），需真实交易验证 |
| Q010 | open | local_spike DIAGONAL 真实交易 n 计数 |
| Q002 | open | Shock active mode Phase B 验证 |
| Q003 | open | L3 Hedge v2 实盘实现 |
| Q004 | open | vix_accel_1d L4 fast-path |
| Q005 | open | 多仓 trim 精细化 |
| Q001 | blocked | SPEC-020 ablation（等待 AMP）|

**Q015 研究方向**：
1. IVP + VIX 绝对水位联合 filter（cross-tab 显示 VIX [18,20) × IVP [55,65) 是灾难区，VIX [16,18) 全 IVP 区间均为正）
2. VIX 趋势条件化（VIX RISING + IVP≥50 组 Sharpe 0.95 vs FALLING -0.09，但 RISING 样本仅 9 笔）
3. BPS slot-occupancy 架构改进（允许 NORMAL regime 双 BPS slot 从根本上消除位移伪影）

---

## 研究候选（无变更）

参见 `strategy_status_2026-04-12.md` §11（H1/H2/H3 均继续 hold）。
