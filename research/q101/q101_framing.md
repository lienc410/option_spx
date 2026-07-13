# Q101 Framing — Aftermath 结构选择独立复审（预注册 2026-07-12 深夜）

**状态**: FRAMING（数据未碰）。触发：PM 指令"不要默认以前的研究结果完全可信，独立研究验证 broken-wing 是否最合适"。
**复审对象**: 生产 aftermath 路由（HIGH_VOL×IV_HIGH×Bearish/Neutral + is_aftermath → V3-A broken-wing IC，selector.py:813-821）。

## 0. 旧研究的三个独立性缺口（复审动机，取证完毕）

1. **n=15**：Q064 P3 仅在 15 个入场日上做结构对比——结构采纳级决策的样本量不足
2. **候选集=2**：只比了 V3-A vs BPS_HV；对称 IC_HV、BCS_HV、不交易（cash）从未在 aftermath 窗口内同台
3. **σ=VIX 平坦零 skew**（研究早于 CALIB 宪法两个月）：aftermath 是 put skew 最陡窗口；V3-A 的远端翼（δ0.04 call / δ0.08 put）正是平坦定价误差最集中处——**其胜出可能是定价假象**

## 1. 预注册设计

**窗口真值**: 生产 `is_aftermath`（直接调用生产函数，构造逐日 snapshot；探针校准：与 q064_p1_daily_flags.csv 抽样断言一致——v1.2 探针规则）。入场 = 每个 aftermath 窗口首日 + 窗口持续时出场后再入（预计 n≈90 窗口/26y，对旧研究 n=15 的量级修复）。

**候选集（离散预注册，腿全部取产码/catalog 真值）**:
| | 结构 | 腿 |
|---|---|---|
| C1 | V3-A broken-wing（现任）| SC45δ.12 / BC45δ.04 / SP45δ.12 / BP45δ.08 |
| C2 | 对称 IC_HV | catalog `iron_condor_hv` 原腿 |
| C3 | BPS_HV | SP35δ.20 / BP35δ.10 |
| C4 | BCS_HV | SC45δ.20 / BC45δ.10 |
| C5 | 不交易 | cash（合法终点，房规）|

**出场（全候选统一）**: 60% 利润目标 或 DTE≤21，先到者；到期结算兜底。BS mid 按出场日 VIX 重定价（同 Q064，两臂同模）。

**定价（本复审的核心轴）**:
- **FLAT 臂**: σ = max(VIX,10)/100 × term_mult(45→1.10)——逐字复现 Q064 口径（可比性锚）
- **SKEW 臂**: σ_leg = (VIX + off(type,δ) × S)/100 × term_mult；off 取 skew monitor 实测中位（put d30/d15 + call c16/c08，δ0.12 插值、δ0.04/0.08 沿末段斜率外推）；**斜率倍数 S ∈ {1.0, 2.0}**——1.0=平静期实测，2.0=aftermath 陡化悲观 bracket（本窗口无实测链，凭 calm 外推必须带 bracket，v1.2 未量化 caveat 禁令）
- 判定规则：**若 C1 的排名在任一定价制度下翻转，其采纳属"定价脆弱"**，处置降级

**指标包（房规全套）**: 每笔均值$/合计/最差/CVaR10/胜率 + **等 BP 口径 marginal $/BP-day**（Q064 P4 惯例：IC BP=max(翼宽)，spread BP=宽度）+ 时代切片（2008-09/2011/2020/2022/2025 簇 + 2020+，n 可见）+ MDE 分级语言。

**判定标准**: C1 为现任 → Execution 标准（挑战者须显著优才换）；但 C1 自身须在 SKEW 臂下显著优于 C5（cash）——若 aftermath 收入 edge 本身死于诚实定价，verdict = 通道暂停待真实链证据（而非换结构）。

## 2. 边界

不动 is_aftermath 窗口定义（那是 Q018/Q064 P1 的领地，本审只管结构）；不动 sizing 规则；kill/换结构类 verdict 一律外审 + PM ratify。

*修订日志: 2026-07-12 初稿（预注册锁定，数据未碰）。*
