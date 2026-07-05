# Q087 B1 — 生产回测定价惯例审计（scoping + 首批测量，2026-07-05）

## 1. 生产惯例确认（代码真值）

- `backtest/pricer.py`: **全 strike 用 VIX/100 平坦 sigma**（文件自述 "Uses VIX as the implied volatility proxy"）；**股息率 = 0**（自述 "Dividend yield assumed zero"）
- `backtest/engine.py:169`: `entry_sigma = VIX/100`，入场、逐日 mark、出场、delta 选 strike 全部同一惯例
- 波及面：**原始 26y 矩阵验证（Sharpe 1.43）、全部策略格的 avg_pnl、Q082 的 137 笔 BCD、Q071 /ES 校准**——即全部实盘行为的回测地基

## 2. 真实链测量（25-35 DTE，2026-05-27~07-03，27 天）

**Put 侧**（已入库 `research/q085/q085_chain_skew_offsets.csv`）: d0.30 = VIX−2.0 / d0.15 = VIX+1.0 / ATM = VIX−4.3

**Call 侧**（本次新测，中位近似）:

| 腿 | 实际 IV vs VIX | 对卖方的含义 |
|---|---|---|
| c0.70（ITM，BCD 长腿） | **VIX−2.0** | 买入比模型便宜（利好 debit 结构） |
| c0.30（BCD 短腿 / BCS） | **VIX−3.6** | 卖出收入比模型少很多 |
| c0.16（IC call 短翼） | **VIX−4.5** | **IC call 侧收入被模型严重高估** |
| c0.08（IC call 长翼） | VIX−5.0 | |

## 3. 分策略一阶偏差方向（待计算量化，方向先钉死）

| 策略 | 模型偏差方向 | 机制 |
|---|---|---|
| BPS | 高估收入（~3vp 差分） | 短腿收少（−2）+ 长腿付多（+1） |
| **IC** | **高估收入，call 侧为主** | put 翼实际略富（+1 vs 模型）但 call 翼贫 4.5vp |
| BCS_HV | 高估收入（重） | c30 贫 3.6vp |
| BCD | **方向未定，需计算** | 长腿便宜 2vp（利）vs 短腿贫 3.6vp（弊）+ 90d 期限结构未测 |

## 4. 缺口与下一步

1. **期限结构缺口**: 测量只覆盖 25-35 DTE；BCD 长腿 90 DTE 需补测 80-100 DTE 桶（链里有数据，脚本扩展即可）
2. **时代外推缺口**: 27 天单月样本（VIX 15-22）；offsets 随 regime 的稳定性未知 → SPEC-116 skew monitor 已每日积累 put 侧，**建议扩展到 call 侧 + 多 DTE 桶**（小改动，并入 dev 下一批）
3. **B 阶段主工程**（分诊板后）: 统一定价库（三模式：flat/CALIB/pessimistic）→ 矩阵回测 CALIB 重跑 → 逐格 PnL/Sharpe 对比 → 喂给 P1 重审（矩阵地基/Q082/Q071）
4. **不预判结论**: VIX-flat 高估的是绝对收入；矩阵的**格间相对排序**可能稳健（偏差同向作用于同类结构）——重跑后才知道路由本身是否需要动

## 5. 附：Q084 时代复查（verdict map P2 项，已完成）

用既有 trades 切时代：2015+ 均值 -$20、2022+ +$221（n=7）、无 2024+ 样本——**近期时代不构成复活证据，Q084 kill 维持**。历史 kill 档案时代复查 1/N 完成，原裁决经受住新镜头。
