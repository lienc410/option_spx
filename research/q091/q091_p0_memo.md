# Q091 P0 — Crash-Day BP 储备下限(确定性情景网格)

**Date**: 2026-07-07
**Owner**: Quant Researcher
**Status**: **RATIFIED 2026-07-07** — PM 拍板 buffer = $100k;§4 其余假设(情景网格 / gap−30% / 静态账本)按拟稿接受。**② 定稿结论:可部署 defined-risk 容量 = $337,688 − $100,000 ≈ $238k**;naked-put 子配额按 crash 占用口径(GOOGL ~$20k/张)。此数即 ④ 合成栈重仿真与 SPEC-111 §4-B 的输入。
**Trigger**: BP-utilization 重审计处置顺序 ②(PM 批准 2026-07-07);同时是 SPEC-111 复审 §4-B(T2 naked-put)的前置数据
**Data**: 2026-07-07 live 双 broker 快照(`q091_p0_snapshot.json`),情景网格无拟合、无统计推断——纯风险算术

---

## 1. 一句话结论

**今天账面 ~$1.02M 的 excess liquidity 里,约 $682k 是 crash 吸收垫的"占用中储备",
真正可部署的只有最恶劣已列情景下的 $338k(再减 PM 选的 buffer)。**
"BP headroom 56% 闲置"的正确读法:约 2/3 不闲——它是 beta 账本的 2008 保险。

## 2. 快照与网格结果

今天:Schwab equity $490.5k(实测混合 haircut 21.5%)+ E-Trade equity $545.5k(23.4%),
现金 $152.3k,期权 sleeve max loss $76.6k,合并 excess = **$1,020k**。

| 情景 | dd | β | haircut× | 合并 crash-day excess |
|---|---|---|---|---:|
| 2022 阴跌 | 25% | 1.0 | 1.0 | $677,778 |
| 2022 + haircut 1.5x | 25% | 1.0 | 1.5 | $590,302 |
| 2020 崩盘 | 34% | 1.0 | 1.5 | $528,555 |
| 2020 + β1.2 | 34% | 1.2 | 1.5 | $481,902 |
| 2008 重演 | 45% | 1.0 | 1.5 | $453,087 |
| 2008 + haircut 2x | 45% | 1.0 | 2.0 | $388,938 |
| **2008 + β1.2 + haircut 2x(最恶)** | 45% | 1.2 | 2.0 | **$337,688** |

**发现 1**:全网格 excess > 0 且余量宽——**现有账本在 2008 重演下不会被强平**,
两 broker 各自独立为正(最恶点 schwab $196k / etrade $142k),无跨 broker 救火需求。

**发现 2**:储备下限 = 今天 excess − 最恶情景 excess ≈ **$682k**。这就是"闲置 BP"
里不闲置的部分,量化了重审计 §3.2 的"BP 机会成本≈0 直到 crash"到底是多少。

**发现 3(喂 SPEC-111 §4-B)**:T2 naked put 的 crash 账单(单名隔夜 gap −30%):

| | 入场 PM 保证金 | gap−30% 保证金 | + NLV 损失 | **crash 总占用** | cash-secured 对照 |
|---|---:|---:|---:|---:|---:|
| GOOGL K≈340 | $3,380 | $11,962 (3.5x) | $8,108 | **~$20,070** | $33,800 |
| AMZN K≈230 | $2,260 | $7,964 (3.5x) | $5,381 | **~$13,345** | $22,600 |

→ 若切 PM-margin,**sizing 单位必须用 crash 总占用(~$20k/张),不是入场保证金
($3.4k/张)**——差 6 倍。即便按 crash 口径,仍比 cash-secured 省 ~40% 资源,
且吃的是富余极(BP)不是稀缺极(现金)。这给 §4-B 提供了诚实的执行规则雏形:
`naked put 张数 × crash 占用 ≤ 可部署额度的一个子配额`。

## 3. 可部署额度(等 buffer ratify 后定稿)

```
可部署 defined-risk 容量 = $337,688(最恶情景 excess) − buffer
  buffer = $100k(≈8% NLV)时 → ~$238k max-loss 容量
  buffer = $150k 时          → ~$188k
naked-put 子配额按 crash 占用计(每张 GOOGL ≈ $20k)
```

## 4. 待 PM ratify 的假设集(逐项可改,改完重跑 5 分钟)

1. **情景网格**:dd 25/34/45%、haircut escalation ×1.5/×2.0(锚:2008-Q4 与
   2020-03 broker 对集中账本普遍上调 house requirement 至 30%+)、β 1.0/1.2
2. **单名 gap −30%**(T2 naked 扩张用;GOOGL/AMZN 历史单日最差约 −16~−18%,
   −30% 为隔夜跳空保守值)
3. **buffer**:$100k / $150k / 其它
4. **静态账本假设**:crash 中不减仓(保守;实际有 fund-exit 纪律与 V1-V3 veto)

## 5. 局限(如实)

- **混合 h0 双算期权保证金**(equity haircut 里含今天期权 margin,NLV 又全额扣
  sleeve max loss)——方向保守,对下限估计安全
- **Schwab/E-Trade 各自的 house haircut 调升日程未知**,×1.5/×2.0 是历史类比
  不是合同条款;真实 crash 中 broker 可单方面更狠(这就是 buffer 的意义)
- 现金按不变处理;E-Trade margin loan 字段按 API 现值读入
- 静态网格,非路径模拟——P0 目的定下限量级,若 PM 要路径版(逐日 margin call
  时序)另立 P1

## 6. 与队列的衔接

- SPEC-111 §4-B(T2 collateral)现在有数了:等本假设集 ratify → 若 PM 选 B,
  执行规则按 §2 发现 3 的 crash-占用口径起草,走 2nd quant 外审
- ④ 合成栈重仿真:本 P0 的"可部署容量"是它的输入之一
