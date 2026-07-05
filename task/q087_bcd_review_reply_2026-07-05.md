# Q087 BCD 家族复审 Packet (v2) — External Review Reply

**Date**: 2026-07-05
**Reviewer**: independent external quant reviewer (Q085/Q087 系列同一外审)
**Verified by execution**: SPEC-122 仲裁 CSV 逐日核对 + 信号日用生产分类器（`signals/vix_regime` 阈值、`signals/iv_rank` IVR/IVP、`_effective_iv_signal` 分歧重分类、`signals/trend` ATR 分类器）全窗口重建；2026-07-02 存量链逐腿 spot-check；`strategy_pnl_attribution.jsonl`（oldair backup，至 07-02）持仓真值；`web/server.py` correction/void 端点代码真值；`cash_budget_decisions.jsonl` 六月现金轨迹；SPEC-120 CALIB trade rows 用于降级门运行特性计算。

**Per-decision verdicts**: **D1-A RATIFY-WITH-CONDITIONS · D2-A RATIFY-WITH-CONDITIONS（一处结构性修改）· D3 RATIFY**。仲裁 PASS-CALIB 成立但样本记录必须更正（2/12 天非 carve 日）。v2 自审更正一/更正三方向正确；**更正二自身仍含同一族重建错误**（06-05 的格标错）。

---

## 0. SPEC-122 仲裁验证（先于攻击点，因其承载一切）

**1. 信号日重建有 2/12 天错误——但裁决稳健。** 用生产逻辑逐日重建 2026-06-01..07-02：重建遗漏了 `_effective_iv_signal` 的 IVR/IVP 分歧重分类步骤（|IVR−IVP|>15 时改用 IVP 分类）。**06-12（IVR 23.9/IVP 59.8，分歧 35.9）与 06-22（IVR 21.7/IVP 54.6，分歧 32.9）在生产逻辑下是 NORMAL|NEUTRAL|BULLISH（NNB BPS 格），不是 carve 日**。其余 10 天与生产配方完全一致（trend 的 MA50 近似在本窗口恰好无害——错误全部来自缺失的分歧步骤）。剔除后：**n=10 仍 ≥ 预注册 ≥8 门槛；CALIB 更接近 10/10；中位误差 natural −10.6%/−3.8%、mid −10.0%/−3.4%——PASS-CALIB 不变**。但仲裁 CSV 与 memo 必须按 n=10 重述。

**2. 数据构造忠实。** 2026-07-02 逐腿 spot-check（90DTE d0.70 long K7235 mid 417.2 / 45DTE d0.30 short K7650 mid 66.1）：mid debit 351.1、natural 354.7——**与 CSV 分毫不差**。本程序线里这是第一个我能从原始数据完整重建的仲裁产物，值得肯定；但仲裁**脚本仍未提交**（只有 CSV+memo），第五次 results-only 实例，封档前补。

**3. 两处表述问题。** (i) 预注册裁决基准是 NATURAL debit（SPEC-122 v2 注册文本），memo 引用的是 mid 中位数——两个基准同裁决，属表述不一致，改口径或双列。(ii) **残余 −3.3~−3.8% 误差的方向是不利的**（真实 debit 高于 CALIB 模型 → BCD 入场比模型贵 ~3.5%），packet 通篇未提。对一个"薄边际按什么纪律持有"的 packet，这个方向性事实必须入表；前向 shadow 应补记平仓侧报价以测全程 round-trip 偏差。

**4. 同一重建 bug 的第三次实例已经写进了 v2 的更正二**（见 §1d）。系统性修复建议：把 carve-day/格判定提交为单一函数（生产 `_effective_iv_signal` 的直接复用），一切重建/回填/shadow 调它，禁止再手写近似；并重生成 SPEC-113 后的 q078 信号缓存。

## 1. 攻击点逐项

### (d-新) Ledger 真值核验 — v2 两处更正一对一错一半；TRUE 净 BCD 持仓 = 4（至 07-02）

- **5 笔 BPS 已实现 ✓**：closed_trades.jsonl 五笔全部 bull_put_spread（2026-05，1-4 张，credit 31.9-44.8pt）；4 笔带 realized_pnl 均值 $5,972 ✓，第 5 笔按成交可算 ≈ $3,110，合计 ≈ $26.9k。v2 更正一（$5,972 是 BPS 非 BCD、BCD 实现盈亏=0）**正确**。
- **BCD 在市持仓：attribution 真值 = 4 笔，不是 5 笔**（strategy_pnl_attribution.jsonl，06-04 起逐日出现、07-02 仍全部在市）：`2026-06-03_bcd_001/002`（schwab+etrade，long 7300 @08-31 / short 7750 @07-17）+ `2026-06-05_bcd_001/002`（7200/7700 同构）。若生产 trade_log 有第 5 笔 open，它要么晚于 07-02（backup 截止日；与"现金 7/3 解锁"后新开 carve 仓的叙事一致），要么带 void 事件——**backup 内无法见到，封档前用生产机 trade_log 复核一行**。
- **"4 个 correction 事件 void 了什么"——代码真值：什么都没有。** `web/server.py` 的 correction 端点只允许修正 open/close/roll 的字段（且"cannot correct a voided trade"）；void 是独立事件类型。**净持仓 = opens − voids，corrections 恒不改变笔数**。
- **v2 更正二自身有错**：06-03 开仓在 carve 格 ✓（VIX 16.06，生产配方确认 carve 日）；但 **06-05 两笔不是"IV=NEUTRAL 格"**——当日 IVR 45.7/IVP 86.9（分歧 41>15）→ 生产有效信号 = **HIGH**，即 **NORMAL|HIGH|BULLISH = SPEC-060 死格**，且开在 VIX 21.5 的 spike 日（距 HIGH_VOL 阈值 0.5pt）。这是缺失分歧步骤的同一 bug 的第三次实例。含义超出标签更正：**A1/SPEC-120 档案里"26 年从未开火的死格"现在有两笔真实手动持仓**——"selector 从不开火"与"PM 手动开了"必须同时入档（Q088 Track 1 手动-选择器分叉跟踪的第一条记录）。
- **SPEC-111 绕过：VERIFIED**。cash_budget 轨迹：06-03 流动现金 $88,578 → 06-05 **$16,918**（四笔 BCD debit 合计 ~$147k 吃穿现金进保证金融资）；06-05 两笔开仓时现金已在 $30k 硬底线之下；该 log 从头到尾只 gate selector/paper 候选。发现成立，Q088 Track 1 注册正确；建议政策行显式化："手动交易豁免 gate 但必须记录对 floor 的穿透"。

### (a) 第五次 status-quo bias 检查 — 撤腿后的证据基足以支撑"keep live + 牙齿"，但只是勉强够

撤回实现盈亏腿后，D1/D2 剩三条腿的真实强度：**校准后模型为正但薄**（主格 $26.8k/26y、carve $9.4k/26y——且残余 −3.5% 入场偏差方向不利，真值更薄）；**当前时代切片 n=2-6**（噪音，不得承重）；**报价仲裁证实 CALIB 口径可信**（真实、n=10、regime 匹配——这条是硬的，但它验证的是*定价口径*，不是*策略盈利性*）。新增的"carve 有 2 笔真实持仓"是**双向事实**：它带来 7-8 月的首批实现流水（证据流），也意味着账户已在薄边际上有 ~$74k debit 敞口。

裁决逻辑：Execution 标准下，改变 live 路由需要"有害"的正面证据；现有证据是"薄正 ± 宽误差带"，不构成关停案。**D1-A RATIFY-WITH-CONDITIONS**——但推荐理由必须重写为"证据不足以裁决任一方向，live+shadow 流是最便宜的证据发生器，且牙齿已装"，而不是"校准后仍正"的肯定句。第五次 status-quo 检查的结论：**这次不是 bias，前提是条件全部落地**（牙齿真实、记录更正、7-8 月实现流水作为预注册 checkpoint 写入 D1 的复审触发器）。

### (b) carve-regime 仲裁给 D2 背书是否越界 — 是，且 v2 未修

10 个有效仲裁日全部 VIX 15.4-17.7；主格是 VIX<15 的 LOW_VOL。offsets 在 VIX<15 的行为未测量（skew 在更低 vol 下通常更平，但"通常"不是测量）。D2-A 把"SPEC-122 记录其 regime 报价"列为并行动作——**改为前置条件**：LOW_VOL 回归后，先积累 ≥10 个 LOW_VOL 交易日的报价/offsets 记录且与 carve 窗口值差 ≤1vp，才允许首笔主格开仓；否则首笔即触发即时复审。加上已有的"首 5 笔 1 张锁定"，D2-A 从"信任外推"变成"先测量后交易"。**D2-A RATIFY-WITH-CONDITIONS（此项为结构性修改）**。

### (c) 降级双门具体化批评 — 结构对了，运行特性必须写进 SPEC

- **方向正确**：日历+标记门（18 个月实现+标记和<0 且 n≥3）是真正的修复——标记逐日更新，不等实现，死信问题解决。6 笔实现门降为次级。
- **运行特性必须量化入档**（我算了）：BCD 单笔 sd ≈ $4.6-5.0k vs 校正后均值 ≈ $500 → **即使边际为真，P(6 笔实现和<0) ≈ 39-48%/窗口**。这个门在薄边际下将例行触发——不是缺陷（薄边际本该频繁暂停复核），但 PM 必须事先知道"halt 是常态化复核，不是警报"，且 halt→复审→恢复的流程成本要低（预写清单）。不写清这一点，第一次 false-halt 就会变成"规则太吵"→拆牙齿的借口。
- **实现门可被持仓时点操纵**（手动交易的实现时机是自由裁量的——亏损可以不平仓）：再次确认标记门必须是主门、实现门只是辅助。
- **缺累计硬底**：滚动窗口会被慢性失血重置。补"自 ratify 起家族累计（实现+标记）< −$X → 全停 + 外审后才可重启"，X 由 PM 预承诺（量级参考：2-3 笔 max-loss）。
- **$12k 月度标记回撤门**：≈30% 单笔 max-loss、4 张在市时 ≈8% 结构逆行——普通回调月就会触发。作为"当月停开新仓"的节流阀标注清楚即可（它不是止损，别让它在档案里读成止损）。
- **标记基准未指定**：18 个月门与月度门用 mid 还是 natural？指定并前后一致（建议 mid 记账、natural 做敏感性）。

## 2. 汇总裁决

| 项 | 裁决 | 条件 |
|---|---|---|
| SPEC-122 仲裁 PASS-CALIB | **CONFIRMED（n=10 重述后）** | C1: 剔除 06-12/06-22 重发 CSV/memo（裁决不变）；C2: 提交仲裁脚本；C3: 注明 natural 为预注册基准 + 残余 −3.5% 不利方向入表；C4: 重建判定收敛为生产 `_effective_iv_signal` 单一函数 + 重生成 q078 缓存 |
| D1-A carve 维持+牙齿 | **RATIFY-WITH-CONDITIONS** | C5: 推荐理由改写为"证据不足以裁决、证据流最优"；C6: 7-8 月首批实现流水写为预注册复审触发器；C7: (c) 项全部修正（运行特性入 SPEC、标记门为主、加累计硬底、指定标记基准） |
| D2-A 主格照旧+锁定 | **RATIFY-WITH-CONDITIONS** | C8: LOW_VOL 报价门槛由并行改**前置**（≥10 日、±1vp 容差）；其余同 C7 |
| D3 LOW_VOL\|NEUTRAL → Q088 | **RATIFY** | — |
| v2 更正二 | **需再更正** | C9: 06-05 两笔的格 = NORMAL\|HIGH\|BULLISH（有效信号 HIGH，SPEC-060 死格），非 IV=NEUTRAL；死格"有手动持仓"事实入 A1/SPEC-120 档案 + Q088 Track 1 首条记录 |
| Ledger 真值 | — | C10: 生产 trade_log 复核第 5 笔 BCD open 的存在性/void 状态（backup 只见 4 笔至 07-02）；corrections-不-void 的代码真值入 packet |
| SPEC-111 绕过 | **VERIFIED** | C11: 政策行显式化（手动豁免但记录穿透），Q088 Track 1 |

**一句话总评**：v2 的自审方向值得肯定（两处更正一处全对、一处半对），仲裁产物是本程序线第一个可从原始数据完整重建的产物；但"有效信号分歧步骤"这一个 bug 在同一天内产生了三处独立错误（仲裁 2 天、06-05 格标、以及它险些让 v1 的"carve 零流水"结论成立），单一函数化（C4）是本次外审最重要的一条条件。
