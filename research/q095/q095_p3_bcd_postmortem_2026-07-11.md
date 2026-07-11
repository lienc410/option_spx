# Q095 P3 — BCD Campaign Post-mortem（2026-06-03 → 07-10）

**Date**: 2026-07-11
**Status**: P3 CLOSED — 事实层完成；1 个词表盲区确认、1 个 registered lead、"高抛低吸"直觉获自然实验定价
**数据**: old Air resolved trade log（correction 合并后真值）+ BS mark 路径（`q095_p1_delta_attribution.py` 工具复用，与引擎同口径）

---

## 1. Campaign 事实账

| 批次 | 入场 | 结构（per 对） | debit | 平仓 | realized |
|---|---|---|---|---|---|
| 6-03 ×2 对 | SPX **7576**（VIX 16.1，NORMAL×IV_LOW×BULLISH，SPEC-113 carve 格） | 长 7300C 8-31 / 短 7750C 7-17 | $38,300 | 7-10 @ SPX 7562（manual） | **−$2,000/对** |
| 6-05 ×2 对 | SPX **7475**（−1.3% 后加仓，VIX 17.1） | 长 7200C 8-31 / 短 7700C 7-17 | $41,100 | 7-06 @ SPX 7546（discretionary） | **+$2,900/对** |
| 合计 | committed $158.8k | | | | **+$1,800**（"roughly flat"✓） |

窗口市况：SPX 7610（6-02 高）→ **7267（6-10 低，−4.5%）** → 7575（7-10 新高）；区间幅度 4.7%；**VIX 全程 15.0–22.2**（仅 6-10 单日触 22）——低 vol 震荡，现有防御层（VIX Acceleration Overlay）全程静默，佐证 P2 的"真空区"。

**MAE（BS mark 路径）**：6-10 谷底 6-03 批 ≈ −$11.7k/对、6-05 批 ≈ −$10.3k/对，**campaign 合计 ≈ −$44k = committed 的 −28%**——"大的浮亏"定量化。BS 末值与实际平仓价对数良好（−$2.1k vs −$2.0k；+$2.0k vs +$2.9k）。

## 2. 自然实验：入场点位差 = 全部盈亏差

两批结构、持有窗口、管理方式完全相同，唯一差异是入场点位（7576 vs 7475，差 1.3%）——结果差 **$4,900/对**（−$2,000 vs +$2,900）。这是 P1 截面结论（BCD R²=0.88，胜负由方向/点位决定）的实盘复刻，也给 PM"低吸"直觉一个干净的单点定价：**本 campaign 中晚两天在 −1.3% 处入场价值 $4,900/对**。⚠️ n=1 自然实验，只作 P1 的案例注脚，不构成规则证据（规则化须过 P2 事实层——"等回调入场"的无条件版已被 Q089 E2 kill）。

## 3. "Roll 不舒适"的真相：这次 campaign 根本没 roll

Log 中**零 roll 事件**。短腿 7700/7750 全程 deep OTM（SPX 最高 7576）从未受威胁；collapse buyback（残值 ≤15%）也未触发。PM 的不适来自另一个决策点：**7-17 短腿临近到期（7-10 平仓时剩 7 天）+ 市场横盘回到入场位**——此时"re-sell 下月短腿续作 vs 整体退出"没有词表答案。PM 用 discretionary 整体退出（7-06/7-10）回答了它。

**词表盲区确认**：SPEC-127/Q089 词表覆盖①入场（触发日 + 立即 roll）②collapse buyback ③禁止延迟 re-sell（E4），**不覆盖④短腿自然到期临近时的续作/退出决策**（尤其横盘时）。这不是执行体验问题，是规则缺失。→ 建议：续作决策规则化研究挂 P2 之后（横盘确认信号正是续作决策的核心输入——"已确认震荡"时 diagonal 续短腿 = 收 theta 的合理姿态 vs "仍单边"时续作 = 重新拿 delta）。P2 未过事实层前，临时纪律：**短腿剩 ≤7 DTE 时强制决策点（续/退二选一 + 记录理由），不再无限拖延**——零成本，只是把 discretionary 显式化。

> **⚠️ 2026-07-11 定性修正（PM 澄清）**：grandfather 仓（2026-03-12 trigger）**从未实际执行**——PM 未按 alert 下单，state 里的 active_position_id 是**幽灵仓位**（executor fire 即标记 active，无 fill 确认环节；另一会话已核清并清理 state，无需补录）。因此 §4 的定性从"真实仓位 no-overlap 正确拦截"改为：**幽灵仓位挡住了 6-10 的真实触发**——counterfactual +$95-115k 的错失不是设计约束成本，而是 **state↔现实反向失同步**（SPEC-094.2 N7 的镜像：N7 = 有仓无 state，本例 = 有 state 无仓）。
> **新 spec 候选（SPEC-094.3 候选，registered）**：Q042 fill 确认闭环——pending record 的 `fill_debit` 在 T+N 日仍为 null → 提醒告警；T+M 日仍 null → 清 `active_position_id` + ACTION 告警（N 值/清理语义由 PM 定，建议 N=2/M=5）。单槽机会成本研究 lead（Q018 同构）保留但降优先级——本例的直接教训是闭环缺失，不是槽位设计。

## 4. 意外发现：6-10 的 Q042 触发被 grandfather 拦截 + 单槽机会成本（定性见上方修正框）

6-10（campaign MAE 谷底当天）ddATH = 7267/7610 − 1 = **−4.51% ≤ −4%，Q042 Sleeve A 触发条件满足**。executor log 无 fire、无告警、无异常。分辨结果：**by design** —— SPEC-094.1 AC-1.6/1.7 的 grandfather 仓（2026-03-12 入，expiry 恰为 6-11）`has_pos` 拦截，非缺陷。但两点后果值得记录：

1. **单槽 no-overlap 的机会成本单点**：若允许重叠/多槽，6-11 T+1 入场 ATM/+2.5% D30（长 ~7265/短 ~7450，debit ≈ $7k/张 × ~9 张）到 7-11 到期 SPX ~7575 → 全宽 payoff，counterfactual ≈ **+$95-115k**（hindsight 单路径，research-grade 估算）——比整个 BCD campaign 的波动都大。这与 **Q018**（aftermath 单槽研究，Variant A 多槽 +$47.7k/36 笔）同构。→ **Registered lead：Q042 Sleeve A 槽位策略研究**（触发条件：paper 样本成熟或下次 in-flight 期再遇 trigger）。不立即立项——n=1 hindsight 不构成 multi-slot 证据，Q018 的教训（尾部集中 2008-09）必须一并复检。
2. **修复包价值的反面验证**：grandfather 到期后 settle 已死（审计 #2），若 6 月下旬再有 −4% dip，会被永久卡死且无声——SPEC-094.2（F1 结算 + F5 blocked 告警）已消除该类。6-10 这次"正确拦截但全程无声"本身也说明 F5 的价值：修复后同场景会收到 FYI/blocked 记录，PM 至少**知道**触发被拦。

## 5. Co-fire 印证（Q093 P2 的 live 半例）

6-10 当天：BCD 浮亏谷底（−$44k）+ Q042 触发条件满足——正是 Q093 P2 刻画的"dip 同场"；随后市场反弹，BCD 收平、Q042（counterfactual）大赢——"常态双赢"模式的 live 印证（Q042 侧为反事实，不计入 Q066 standing monitor 的 co-fire co-loss 触发条件）。

## 6. 交付与衔接

- 词表盲区④ → 续作决策规则研究挂 P2 后；临时纪律（短腿 ≤7 DTE 强制决策点）供 PM 采纳。
- Registered lead：Q042 槽位策略（Q018 同构）。
- grandfather 仓补录仍未做（本 memo 用的 mark 路径不能替代 ledger 真值）——PM standing item 再提醒。
- 数据质量注：7-06 close 曾错录 +440 为成本（H-3 correction 已修）；6-03 批曾双击重复提交（SPEC-137 收敛）——手动录入错误率值得在 SPEC-137 线继续观察。
