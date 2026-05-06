# Q041 Execution-Prep Packet

**日期：** 2026-05-05  
**状态：** 2nd Quant PASS — Routing B（分层 paper trading）  
**范围：** Tier 1（SPX CSP）/ Tier 2（GOOGL/AMZN CSP）/ Tier 3（COST/JPM 财报 IC）  
**目的：** 定义各候选策略的 paper trading 执行规则、仓位规模、监控指标、升级条件

---

## 一、候选分层总览

| Tier | 策略 | 路由 | 2nd Quant 状态 |
|------|------|------|--------------|
| **1** | SPX CSP Δ0.20 DTE30 | 正式 paper trading | 证据最干净，2022 压测通过 |
| **2** | GOOGL CSP Δ0.20 DTE21 | 带 tail caveat 的 paper trading | 信号强，尾部未充分验证 |
| **2** | AMZN CSP Δ0.25 DTE21 | 带 tail caveat 的 paper trading | 同上 |
| **3** | COST 财报 IC T-3 1.0× | Observe-only / 谨慎 paper trading | N=15，样本不足晋升 |
| **3** | JPM 财报 IC T-3 1.0× | Observe-only / 谨慎 paper trading | N=9，样本极小 |

**本 packet 不适用：** SPX CC DTE45（已淘汰）/ SPX CSP DTE45（观察，不在本 packet）/ META IC（结构性排除）

---

## 二、Tier 1 — SPX CSP Δ0.20 DTE30

### 2.1 策略参数

| 参数 | 值 | 备注 |
|------|-----|------|
| 标的 | SPX（S&P 500 指数期权） | 欧式，现金结算 |
| 方向 | 卖 OTM put（Cash-Secured Put） | |
| 目标 delta | −0.20（绝对值） | BS delta，入场时计算 |
| 目标 DTE | 30 天（±10 天容忍） | 寻找最近到期日 |
| 入场时机 | 每月第三个 Friday | 非重叠 roll（前一 cycle 到期后再入） |
| 权利金过滤 | close > $0.10 | 排除极度 OTM 无流动性期权 |
| 滑点假设 | 3%（单边权利金） | 历史回测一致 |
| 无风险利率 | 4.5% | |
| 平仓 | 持有至到期 | 欧式现金结算，到期自动平 |

### 2.2 入场流程

```
第三个 Friday 收盘前：
1. 查取当日 SPX close（S）
2. 找到 DTE ≈ 30 的到期日（目标：DTE = 25–40）
3. 对可用 put strikes 计算 BS delta（用 ATM IV 估算 σ）
4. 选 |delta| 最接近 0.20 的 strike = K
5. 确认 K 的 close > $0.10
6. 记录：S / K / OTM% / IV_entry / net_prem（close × 0.97）
7. 记录入场日 VIX（供监控用）
```

### 2.3 仓位规模

| 指标 | 规则 |
|------|------|
| 名义敞口（BP） | K × 100（每 1 张合约 = 现金担保的 put notional） |
| 单 cycle 上限 | 总账户可用 BP 的 **≤ 20%** |
| 叠仓 | **禁止**；必须前一 cycle 到期后才开新 cycle |
| 起步建议 | 1 张合约（paper trading 阶段验证系统，不追求收益规模） |

**当前参考数字（SPX ≈ 7230）：**
- K 估计（∼4% OTM）：约 **6,940**
- BP per contract：约 **$694,000**
- 在 Portfolio Margin 账户，实际保证金要求约 $70,000–100,000

### 2.4 退出 / 应急规则

| 场景 | 行动 |
|------|------|
| 正常到期（S_exit > K） | 权利金全收，无需操作 |
| 到期 S_exit < K | 现金结算亏损 = K − S_exit；记录并分析根因 |
| **IV 压缩陷阱警告**（持仓中 VIX < 18 且 S 较入场上涨 > 5%）| ⚠️ 下个 cycle 注意 strike 距离；不提前平仓，但记录 flag |
| 持仓中 VIX 单周上升 > 40%（如 VIX 17 → 25+）| ⚠️ 记录为潜在 adverse regime；next cycle 考虑缩小敞口 |
| 连续 2 个 cycle 亏损 | 暂停入场，升级至 PM review |

**不触发提前平仓的情形：** SPX 在持仓期间下跌但仍高于 K — 这是正常波动，不是 signal。

### 2.5 回测基准（paper trading 比对用）

| 指标 | 历史回测值（2022-05 → 2026-04） |
|------|-------------------------------|
| N | 30 cycles |
| WR | 97% |
| 平均净权利金/cycle | $31.33 |
| 平均 ROE/cycle（net_prem/K） | 0.52% |
| 年化 ROE | ~6.2% |
| MaxDD | −2.84%（单 cycle） |
| Sharpe | 2.18 |
| 2022 全年表现 | +$31（1 亏 4 赢） |

---

## 三、Tier 2 — GOOGL CSP Δ0.20 DTE21 / AMZN CSP Δ0.25 DTE21

### 3.1 策略参数

| 参数 | GOOGL CSP | AMZN CSP |
|------|-----------|----------|
| 目标 delta | −0.20 | −0.25 |
| 目标 DTE | 21 天（±7 天） | 21 天（±7 天） |
| 入场 | 每月第三个 Friday（非重叠） | 每月第三个 Friday（非重叠） |
| 权利金过滤 | close > $0.10 | close > $0.10 |
| 滑点 | 3% | 3% |
| 平仓 | 持有至到期 | 持有至到期 |

**当前参考价格：** GOOGL ≈ $385.69 / AMZN ≈ $268.26

### 3.2 仓位规模

| 规则 | 值 |
|------|-----|
| 单名上限 | 总账户可用 BP 的 **≤ 10%** |
| Tier 2 合并上限 | GOOGL + AMZN 合计 **≤ 15%** BP（不得 10+10=20%） |
| 相对于 Tier 1 | 信心级别低于 SPX CSP；若账户 BP 有压力，优先保 Tier 1 |
| 起步 | 1–2 张/名，paper trading 阶段 |

**当前参考数字：**
- GOOGL K 估计（∼5% OTM）：约 $366；BP per contract ≈ $36,600
- AMZN K 估计（∼6% OTM）：约 $252；BP per contract ≈ $25,200

### 3.3 Tail Caveat（必须写入所有下游文件）

> **GOOGL / AMZN CSP 尚未在以下 regime 验证：**
> - COVID 崩盘（2020 Q1：SPX −34% in 5 weeks）
> - 2019–2021 牛市 + 流动性膨胀期
> - 单名叙事断裂事件（AI capex 调整、监管、mega-cap repricing）
>
> **单名 CSP 的尾部不是指数 CSP 的简单缩放版。**
> 在 GOOGL / AMZN 出现 8–10% 单月移动时，DTE21 strike 可能被深度穿越。

### 3.4 监控重点

| 指标 | 预期值（回测） | 警戒线 |
|------|-------------|--------|
| WR | GOOGL 91%，AMZN 87% | 连续 3 次亏损 → PM review |
| MaxDD/cycle | GOOGL −4.7%，AMZN −11.6% | 单 cycle 超 MaxDD 的 1.5× → 记录异常 |
| 入场后 realized move | — | 若 realized_move > implied_move 的 1.5× → root cause 分析 |

---

## 四、Tier 3 — COST / JPM 财报铁鹰 IC（Observe-Only）

### 4.1 策略参数

| 参数 | COST IC | JPM IC |
|------|---------|--------|
| 结构 | Iron Condor（双边 credit spread） | Iron Condor |
| 入场 | T-3（财报日前第 3 个交易日） | T-3 |
| 到期 | 最近的财报后到期日（财报日 +1 至 +14 天） | 同左 |
| 宽度 | 1.0× ATM straddle 隐含移动 | 1.0× |
| 入场过滤 | **VIX ≥ 15**（入场日必须满足） | **VIX ≥ 15** + 可选 **IMR ≥ 33%** |
| 滑点 | 3% | 3% |
| 平仓 | 持有至到期（现金结算） | 持有至到期 |

### 4.2 入场流程（财报 IC）

```
T-3 入场日：
1. 确认 VIX ≥ 15（若 < 15，跳过本次财报）
2. 找最近的"财报后"到期日（DTE 1–14 天，覆盖财报日）
3. 计算 ATM straddle = ATM call + ATM put（close）
4. implied_move = straddle / S
5. spread_width = implied_move × S × 1.0（dollar width）
6. 卖 ATM put + 买 put @(ATM − width)
   卖 ATM call + 买 call @(ATM + width)
7. 对 JPM 可选：检查本次 implied_move 的 IMR rank（历史百分位），
   若 IMR < 33% 可选择跳过
8. 记录所有参数
```

### 4.3 仓位规模（Observe-Only 阶段）

| 规则 | 值 |
|------|-----|
| Tier 3 合并上限 | 总账户可用 BP 的 **≤ 5%**（谨慎参与，以积累样本为主） |
| 每名每季 | 1 张合约 |
| 资本预算优先级 | Tier 1 > Tier 2 > Tier 3；若 BP 不足，先缩减 Tier 3 |

**当前参考：**
- COST 预期隐含移动 ≈ 4.2% × $1,012 ≈ $42 宽度；max BP per contract ≈ $4,200（spread max loss 约 $2,000–4,200）
- JPM 预期隐含移动 ≈ 6.3% × $312 ≈ $20 宽度；BP 约 $1,500–2,000

### 4.4 Observe-Only 期的核心目标

> **积累真实财报事件样本，不追求收益最大化。**

每次财报事件必须记录：
- 入场日 VIX、implied_move、K_put、K_call
- T+1 realized_move
- 是否被击穿（S_exit < K_put 或 > K_call）
- 净 PnL
- 简短根因备注（若亏损）

**升级至正式候选的条件：** 积累 ≥ 4 个完整财报周期（≥4 个 COST + ≥4 个 JPM）且表现符合回测基准。

---

## 五、跨策略仓位预算

### 5.1 BP 优先级框架

```
Tier 1 (SPX CSP)       ≤ 20% total BP    [最高优先，不应被压缩]
Tier 2 (GOOGL+AMZN)    ≤ 15% total BP    [次优先，信心低于 Tier 1]
Tier 3 (COST+JPM IC)   ≤ 5%  total BP    [最低优先，observe-only]
─────────────────────────────────────────
总上限                  ≤ 40% total BP    [所有 Q041 策略合计]
```

### 5.2 Paper Trading 起步配置（建议）

| 策略 | 合约数 | 目的 |
|------|--------|------|
| SPX CSP DTE30 | 1 张 | 验证入场流程、记录实际 slippage |
| GOOGL CSP DTE21 | 1 张 | 同上；监控单名尾部行为 |
| AMZN CSP DTE21 | 1 张 | 同上 |
| COST IC | 1 张/季度 | 积累财报事件样本 |
| JPM IC | 1 张/季度 | 同上 |

---

## 六、Paper Trading 监控指标

### 6.1 每 Cycle 必录字段

| 字段 | 说明 |
|------|------|
| `entry_date` | 入场日期 |
| `symbol` | 标的 |
| `S_entry` | 入场时标的价格 |
| `K` / `K_put` / `K_call` | strike(s) |
| `expiry` | 到期日 |
| `act_dte` | 实际 DTE |
| `pct_otm` | K 距 S 的百分比 |
| `delta_actual` | 入场时实际 delta |
| `iv_entry` | 入场时 ATM IV |
| `vix_entry` | 入场时 VIX |
| `net_prem` | 实际收到净权利金（扣 slippage） |
| `S_exit` | 到期日标的价格 |
| `settle_cost` | 结算成本 |
| `pnl` | 净 PnL |
| `hit` | 是否被击穿（Boolean） |
| `notes` | 市场背景备注 |

### 6.2 月度检查项

- [ ] 当期 cycle 是否符合入场参数（delta、DTE、OTM%）
- [ ] 入场 VIX 水平（CSP 无最低要求；IC 需 ≥15）
- [ ] 是否存在 **IV 压缩警告**（持仓中 IV 显著下降 + 价格上涨）
- [ ] 累计 PnL vs 回测基准（偏离 > 2× 预期 std 需记录）
- [ ] Tier 1 / Tier 2 / Tier 3 各自敞口是否在预算内

### 6.3 年度回顾指标

| 指标 | Tier 1 目标 | Tier 2 参考 |
|------|------------|------------|
| WR | ≥ 85% | ≥ 80% |
| MaxDD/cycle | < −5% | < −15% |
| 年化 ROE | 4–8% | 3–10% |
| Sharpe | ≥ 1.0 | ≥ 1.0 |

---

## 七、升级 / 降级 规则

### 7.1 晋升正式生产的条件（所有 Tier）

- [ ] ≥ 12 个月 paper trading 完成
- [ ] ≥ 10 个完整 cycles（CSP）/ ≥ 4 个财报事件（IC）
- [ ] WR、MaxDD、Sharpe 均不低于回测基准的 80%
- [ ] 经历过至少 1 次 VIX > 25 的环境
- [ ] PM 批准

### 7.2 降级触发条件

| 触发 | 行动 |
|------|------|
| 连续 3 个 cycle 亏损（同一策略） | 暂停入场，升级 PM review |
| 单 cycle 亏损超历史 MaxDD 的 2× | 立即记录，root cause 分析，下一 cycle 前 PM 确认 |
| 实盘 WR 连续 6 个月低于 70%（CSP） | 重评候选资格 |
| IV regime 切换至 VIX > 40 持续 2 周 | Tier 2 主动减仓 50%；Tier 1 维持但缩规模 |

---

## 八、已知风险与强制披露

以下内容必须在所有下游文件中保持可见：

| 风险 | 适用策略 | 说明 |
|------|---------|------|
| **IV 压缩陷阱** | SPX CSP | 熊市反弹后 IV 被压缩 → Δ0.20 选出过近 strike → 再次下跌击穿（2022-08 实例） |
| **COVID 尾部未验证** | GOOGL/AMZN CSP，COST/JPM IC | SPX −34% in 5 weeks；单名可能更差；无法用现有 4 年数据估计 |
| **单名叙事断裂** | GOOGL/AMZN CSP | 财报 / AI capex / 监管事件可造成 8–10% 单月移动 |
| **财报 IC 样本极小** | COST/JPM IC | N=15/9；单一事件可主导全年；统计置信度有限 |
| **2022 Jan–Apr 缺失** | SPX CSP | 数据从 2022-05-06 开始；2022-04 下跌 −8.8% 未测试 |
| **Overlap validation 进行中** | 全部 | Stitched dataset 正式声明须等 overlap validation 完成；paper trading 不受阻 |

---

## 九、Overlap Validation 状态

Overlap validation 正在进行 20 天正式窗口（从 2026-05-04 起）。

**对本 packet 的影响：**
- **不阻塞** paper trading 入场
- **不重开** Phase 1/2 历史候选排名
- 若 M2–M5 在 20 天窗口内出现系统性不一致，可能影响 stitched dataset 使用，但不影响 Schwab chain 单源回测结论

---

## 十、文件引用

| 引用 | 文件 |
|------|------|
| Phase 2 总结 | `doc/q041_phase2_summary_2026-05-05.md` |
| 2022 熊市压测 | `doc/q041_p2_p21_spx_csp_bearmarket_2026-05-05.md` |
| IV regime 分析 | `doc/q041_p2_p22_iv_regime_2026-05-05.md` |
| IMR 过滤研究 | `doc/q041_p2_p11_ivr_filter_2026-05-05.md` |
| 2nd Quant 裁决 | `doc/q041_2nd_quant_review_feedback.md` |
| Review Packet | `task/q041_2nd_quant_review_packet_2026-05-05.md` |

---

*文档由 Quant Researcher 生成，2026-05-05。*  
*2nd Quant PASS — Routing B 确认。*
