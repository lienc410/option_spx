# Open Questions Archive

Questions archived from `sync/open_questions.md` on 2026-05-09 by Planner.
These questions have status `resolved` or `CLOSED` and are no longer in the active open-questions file.
Archived: Q012, Q017, Q018, Q045, Q049, Q051, Q052.

---

### Q012 — `/ES` short put 生产路径与共用 BP 管理
- **状态**：resolved
- **内容**：ES short put 的生产路径评估已有实质更新。`/ES` 账户权限已确认可用，实测 buying power effect 约为 `$20,529 / 合约`，`$500k` 账户可支持单槽 `1` 张、较高 VIX 下可提升至 `1–2` 张；相较之下，XSP 虽解决 lot size 问题，但 spread 成本更可能侵蚀统计显著性，因此 `/ES` 现已成为优先路径
- **关键风险**：`/ES` 与 SPX Credit 共用同一 options buying power 池，而非独立池；同时 `/ES` 的 SPAN margin 会在高波动期动态扩张，可能形成“亏损扩大 + BP 占用上升”的双重压力
- **当前状态补充**：`SPEC-061` 已完成最小 Layer 2 production cell，但该实现仍是无 Layer 1 缓冲、无 Layer 3 对冲的独立 `/ES` MVP
- **2026-05-08 补充**：homepage / portfolio surface 的 PM-aware margin breakdown 已经落地，当前 operational proxy 口径是：SPX spread BP 近似 `width × 100 × contracts`（max-loss proxy），equity PM haircut 近似 `15%`；Schwab API 可用的是账户级 maintenance total，而不是 per-position PM 细分。这个 proxy 已足够支持前端 truthfulness 与组合层 BP 观察，但**不等于** shared-BP 风险问题已彻底解决
- **Phase A 结果（SPAN 扩张模型）**：
  - 新开仓 `/ES` SPAN：`VIX 19 -> $20,529`，`VIX 30 -> $33,853`，`VIX 40 -> $46,541`，`VIX 60 -> $73,367`
  - 持仓 10 天后压力更大：`VIX 30 -> $46,107`，`VIX 40 -> $70,533`，`VIX 60 -> $117,456`
  - 推荐的入场前 stress buffer：
    - `VIX < 22`：静态 `$20,529`
    - `VIX 22–30`：`1.3x`
    - `VIX 30–40`：`1.6x`
    - `VIX > 40`：`2.0x`
  - 推荐的入场后 SPAN 校正：
    - `VIX < 22`：不校正
    - `VIX 22–30`：`1.4x`
    - `VIX > 30`：`1.8x`
- **Phase B 结果（并发竞争频率）**：
  - `/ES` bullish 天数占比 `62.1%`
  - SPX Credit 开仓天数占比 `71.9%`
  - collision 天数 `39.1%`（约 `1,901` 天 / `98` 天每年）
  - collision 中 BP 超 cap 比例 `27.1%`
  - regime 分层：
    - `LOW_VOL (VIX < 15)`：cap breach `0%`
    - `NORMAL (VIX 15–25)`：cap breach `21.1%`
    - `HIGH_VOL (VIX 25–35)`：cap breach `100%`
    - `EXTREME_VOL (VIX > 35)`：cap breach `100%`
- **Phase C 结果（架构对比）**：
  - `Arch-1` 简单叠加、`Arch-2` 动态预算、`Arch-3` regime-gated 三种治理架构，对账户层 ROE 的影响都几乎为零（约 `±0.01pp`）
  - `/ES` 当前 `1` 合约规模在 `$500k` 账户里只占 `~4%` NLV，太小，不值得为它引入复杂治理框架
  - 真正可见且重要的问题不是“谁优先开仓”，而是 **SPAN 扩张的后验可见性**
  - `82 / 158` 笔模型交易出现 `>1.5x` 的 SPAN 扩张，最大 `6.74x`（约 `$138k`，`27%` NLV）；这说明当前阶段首先需要监控，而不是 allocator
- **修正后的整合结论**：
  - 当前 `1` 合约规模下，不建议实现完整 shared-BP governance framework
  - 当前最合理的下一步是：**窄范围 SPAN 后验可见性 / monitoring spec**
    - 当 `/ES` 有活跃 live 仓位时，前端显示：
      1. 入场时静态 SPAN 估算
      2. 当前估算 stressed SPAN
      3. 两者比值
  - 若未来 `/ES` 扩大至 `3–5+` 合约，再重开完整动态预算 / regime-priority 治理框架
- **当前归类**：research-driven clarification complete；**ready only for narrow monitoring-spec**
- **保留 caveat**：
  - Phase B 使用的是 SPX Credit proxy model，不是最终 canonical engine path
  - 首笔真实 `/ES` live 仓位仍应用于校准 stressed-SPAN 可见性与 real Schwab behavior
- **2026-05-08 Quant alignment audit 补充（现已大部分实现）**：
  - `/ES` stop 语义现已统一为 **`3.0x credit`**。这与 `SPEC-061` 的 `-300% credit` 定义和 `SPEC-086` 的 bot `TRIGGER >= 3.0x` 一致；旧的 `4.0x` backtest 结果现在应视为历史乐观口径，而不是 production-equivalent truth
  - sizing mismatch 现已按 **production single-contract execution** 收口：生产比较路径固定为 `1` 张 `/ES`，不再让 BP%-mode sizing 默认伪装成 production truth。后续若再跑 BP%-mode sensitivity，必须显式标注隐含 contract assumption
  - 新增 `strategy/es_params.py`（`EsShortPutParams`）作为 `/ES` 参数单一真值层，当前已接入 backtest / bot / server-side BP-limit 用法
  - `high_vol_dte` 若从 server-side hardcoded `21` 收敛到 `StrategyParams` 默认 `35`，方向上是正确的单一真值修复，但仍应在下一次回测对比中确认 HIGH_VOL auto-search 行为与预期一致
- **最终结论**：当前 live 规模下（`1` contract / `$500k` 账户），shared-BP allocator / gating / priority framework 是过度设计。正确实施目标已收成 stressed-SPAN 可见性，并已通过 `SPEC-088 DONE` 落地。该问题在当前规模下已闭合；若未来 `/ES` 扩张至 `3–5+` contracts，再改由 `Q050` 重开全局 shared-BP 治理。
- **来源**：Claude 研究更新 2026-04-12

### Q017 — VIX 顶峰回落早期窗口：HIGH_VOL 分支是否结构性错过机会
- **状态**：resolved
- **内容**：Quant 新研究显示，这不是偶发案例：`2000–2026` 共识别出 `73` 个 `aftermath` 窗口（过去 `10` 日内 VIX 峰值 `>=28`，当前已回落 `>=5%`），对应 `458` 个 trend 非 `BULLISH` 的 wait 日。阻挡几乎全部发生在 `HIGH_VOL` 路由内部（`441/458 = 96%`），其中最大来源是 `HIGH_VOL + VIX_RISING` (`208` 日) 和 `HIGH_VOL + BEARISH + ivp63>=70` (`162` 日)。问题定位因此不在 `Q015/Q016` 覆盖的 `NORMAL` cells，而在 `HIGH_VOL` 早期回落阶段
- **Phase 1 更新**：真实策略 PnL 已显著增强了证据。三种 gate-lift 变体在 aftermath 窗口里的新增交易 CI 全部显著为正；其中最关键的双 gate-off 版本给出 `24` 笔新增交易、avg 约 `+$1,772`、win rate 约 `95.8%`，且系统级 Sharpe 严格不退化。去掉 `2020-03 / 2025-04 / 2026-04` 三个现代 V 型反转事件后，结论几乎不变，说明现象并不依赖最近几次事件。alpha 主要集中在 `IC_HV`，而不是 `BPS_HV / BCS_HV`
- **Phase 2 更新**：ex-ante 识别问题已基本收束。`aftermath` 条件本身就是 live 可计算、非后见之明的规则；`peak_drop_pct` 和 `vix_3d_roc` 都没有额外判别力，反而会削弱信号。真正的灾难保护来自现有 `EXTREME_VOL (VIX >= 40)` 硬门槛，因此当前最小实现单元无需推翻 `2008` 保护结构
- **当前最小候选**：只在 `HIGH_VOL`、`trend ∈ {BEARISH, NEUTRAL}`、`IV = HIGH` 且满足 aftermath 条件时，为 `IC_HV` 路径跳过 `VIX_RISING` 与 `ivp63>=70` 两个 gate；`BPS_HV` / `BCS_HV` 不在范围内，`EXTREME_VOL` 继续完整保留
- **依赖**：PM 可直接决定是否进入 DRAFT Spec；若希望再严谨一步，可先做一个更窄的 Phase 3 sanity check，但这已不再是进入 DRAFT 的硬前置
- **当前归类**：implemented via `SPEC-064`
- **来源**：Q017 研究输出，2026-04-19；`SPEC-064` shipped 2026-04-19

### Q018 — HIGH_VOL aftermath 单槽位约束在 double-spike 事件中是否错过第二峰
- **状态**：resolved into `SPEC-066`（2026-04-20，DONE）
- **内容**：`SPEC-064` 上线后的第一次真实 `double VIX spike` 复盘（`2026-03`）显示，第一峰触发了 `2026-03-09` 的 `IC_HV` aftermath 开仓，但第二峰回落期间的 `2026-03-31 / 2026-04-01 / 2026-04-02` 三天，selector 离线重跑本应再次路由到 `IC_HV aftermath`，却被 engine `_already_open` 的单槽位约束阻挡。第一笔仓位直到 `2026-04-08` 才以 `50pct_profit` 平仓，届时 regime 已回 `NORMAL`，第二峰窗口整体错过
- **关键不确定性**：这不自动等于"应放开多槽位"。替代解释同样成立：也许应收紧第一次 aftermath 开仓条件（例如 `off_peak >= 10%`），为第二峰保留 slot，而不是允许并发两笔 `IC_HV`

#### Phase 1 Prototype 结果（2026-04-19）

Prototype 文件：
- [backtest/prototype/q018_phase1_multi_slot.py](backtest/prototype/q018_phase1_multi_slot.py) — 变体 A blocked-cluster 扫描 + 变体 B 全回测
- [backtest/prototype/q018_phase1_cluster_replay.py](backtest/prototype/q018_phase1_cluster_replay.py) — 变体 A ex-post 逐笔模拟（替换原 `$1,023` 近似）

**变体 A（多槽位，post-hoc approximation + ex-post replay）**
- `27` 年历史中识别出 `36` 个 blocked clusters（每年约 `1.33` 次），其中 `4` 个落在灾难窗口（`2008` GFC / `2020` COVID / `2025` 关税 ×2）
- Sanity check：`2026-03-10..2026-04-07` 的 cluster 准确复现 PM 原始观察
- ex-post 用 `_build_legs / _current_value` 重放全部 `36` 次"假想第二槽位"进场（同样的 `IC_HV` 腿、`50pct_profit / -2× stop / 21 DTE roll`）：
  - 总净 PnL = **+$47,735**（胜率 `31/36 = 86.1%`，远高于 baseline `71.5%`）
  - 盈利总和 +$68,014，亏损总和 -$20,279
  - 非灾难 `32` 笔净 +$52,790
  - 灾难 `4` 笔净 -$5,055（`2008-09 -$7,968` 最重、`2020-03 -$2,259`、`2025-04 ×2 +$3,260 / +$1,912`）
- 尾部风险集中在 `2008-09` 单笔，`2020-03` 仅轻微负，`2025` 关税两笔都盈利——说明灾难不全等于亏损

**变体 B（`AFTERMATH_OFF_PEAK_PCT 0.05 → 0.10`，full backtest）**
- 系统级：n `-2`、total `+$8,142`、Sharpe `+0.01`（基本中性）
- `IC_HV` 子集：n `-2`、total `+$6,912`、Sharpe `0.40 → 0.50`（`+0.10`）
- **最大回撤：`-$20,464 → -$13,187`（减少 `36%`）**

**关键发现对比**
| 维度 | 变体 A（多槽位） | 变体 B（收紧阈值） |
|---|---|---|
| 实现成本 | 改 engine `_already_open` 逻辑 | 改一个常数 |
| PnL | 逐笔模拟 `+$47,735` | `+$8,142` |
| 尾部风险 | `2008-09 -$7,968` 单笔、灾难净 `-$5,055` | `MaxDD -36%` |
| 胜率 | `86.1%` | 与 baseline 相近 |

**Phase 1 approximation 限制**（变体 A）
- 未建模 BP ceiling（第二槽位可能被 BP 限额阻止）
- 未建模 shock engine / overlay（`2008-09` 深跌里 overlay 可能先触发强平）
- 未建模 regime 中途切换的 re-routing
- 每 cluster 仅用首日进场；真实 engine 可能在 cluster 内任一天进场
- 样本稀疏：`2008` 级尾部事件 `27` 年内仅 `1` 次

**研究结果反转初步直觉**
- Phase 1a 基于 `$1,023/cluster` 近似时，数据偏向变体 B（多开在灾难窗口"必然放大亏损"）
- Phase 1b 精确重放后，变体 A 的实际净值 `+$47,735` 明显超过近似上限 `$36,828`，灾难窗口 `2/4` 仍赚钱，单一毁灭性案例仅 `2008-09`
- 结论：两条路径都有可取之处，**不能仅凭 Phase 1 做最终决策**

#### Phase 2 Prototype 结果（2026-04-20）

Prototype 文件：
- [backtest/prototype/q018_phase2a_full_engine.py](backtest/prototype/q018_phase2a_full_engine.py) — 变体 A 全 engine（BP + shock + overlay 全部就位，IC_HV `cap=2`）
- [backtest/prototype/q018_phase2b_combo.py](backtest/prototype/q018_phase2b_combo.py) — A + B 组合对比（cap=2 + OFF_PEAK 0.10）
- [backtest/prototype/q018_phase2c_unlimited.py](backtest/prototype/q018_phase2c_unlimited.py) — IC_HV 完全不限个数、仅 BP gate
- [backtest/prototype/q018_phase2d_cap_sweep.py](backtest/prototype/q018_phase2d_cap_sweep.py) — cap 扫描 `{1, 2, 3, 4, 5, 7}` × B filter

**Phase 2-A — 变体 A 全 engine 复核（`cap=2`，无 B）**
- 系统级：n `+34`、total `+$24,676`、Sharpe `-0.02`
- **MaxDD：`-$20,464 → -$29,356`（恶化 `43%`）**
- Phase 1b 的 `+$47,735` 上限下调到现实的 `+$24,676`：`36` 个 cluster 中实际仅 `24` 个开仓（BP 挡了 `12` 个），另 `2` 笔 baseline IC_HV 被多槽位挤掉
- 灾难窗口：`2008-09` 第二槽 `-$7,574` stop，与 Phase 1b 预测几乎一致，shock / overlay 未能救场
- **2026-03 trigger case 开仓 `+$2,839`**，PM 原始问题解决

**Phase 2-B — 四象限对比（baseline / A / B / A+B，`cap=2`）**
| Variant | n | Total PnL | Sharpe | MaxDD |
|---|---|---|---|---|
| baseline | 347 | +$393K | 0.40 | -$20,464 |
| A (`cap=2`) | 381 | +$418K | 0.38 | -$29,356 |
| B (`0.10`) | 345 | +$402K | 0.41 | **-$13,187（-36%）** |
| **A+B (`cap=2`)** | 378 | **+$440K** | **0.42** | -$19,706（+4%）|

A+B 同时拿到 `+$47K`、Sharpe `+0.02`、MaxDD 几乎持平——**远优于单 A 或单 B**。A+B 在灾难窗口只剩 `5` 笔（`2020 COVID ×2`、`2025 Tariff ×3`），`2008-09` 被 B 彻底过滤。

**Phase 2-C — IC_HV 无上限（只靠 BP）**
- 数学上限：`bp_target 7%` / ceiling `50%` → 最多 `7` 槽
- 无 B 的无限制版本：`+$54K`、MaxDD **`-$40,723`（恶化 `99%`）**，`2008-09` 开了 `3` 笔全部 stop，合计 `-$22K`
- 加 B 的无限制版本：`+$81K`、Sharpe `0.43`、MaxDD `-$25K`（恶化 `24%`）
- 关键观察：加 B 后 `2008` 全部被过滤，BP 约束仍然有意义，但 slot 集中度风险显性化

**Phase 2-D — cap sweep {1, 2, 3, 4, 5, 7} + B**
| Cap | n | Total PnL | Sharpe | MaxDD | PnL/$DD |
|---|---|---|---|---|---|
| 1+B | 345 | +$401.6K | 0.41 | **-$13.2K** | **30.46** |
| **2+B** | **378** | **+$440.1K** | **0.42** | **-$19.7K** | **22.33** |
| 3+B | 391 | +$445.3K | 0.41 | -$27.3K | 16.33（严格支配）|
| 4+B | 398 | +$458.3K | 0.42 | -$27.8K | 16.51 |
| 5+B | 402 | +$467.2K | 0.43 | -$25.4K | 18.38 |
| 7+B | 406 | +$474.6K | 0.43 | -$25.4K | 18.67 |

**边际分析**：
- `1→2`: `+$38.5K` PnL for `+$6.5K` DD → **$5.91 per $DD**（值得）
- `2→3`: `+$5.2K` PnL for `+$7.6K` DD → **$0.69 per $DD**（非常不值）
- `3→4`: `+$13K` PnL for `+$487` DD → `$26.67`（反弹）
- `4→5` / `5→7`: DD 持平或改善，$earned/$DD 趋于无穷

**2026-03 double-spike**：cap=2 就完整捕捉 `2026-03-09` + `2026-03-10` 两笔（`+$5,858`），更高 cap 对此场景零增益

**灾难窗口**：所有 cap ≥ 2 的灾难交易数 / PnL **完全一致**（`5` 笔、`-$4,720`）——额外 slot 从未被灾难触发

#### PM 选定最终方案（2026-04-20）

**`cap=2 + B`** = IC_HV 最多 `2` 笔并发 + `AFTERMATH_OFF_PEAK_PCT = 0.10`

选择理由：
1. 2026-03 PM 原触发 case 完整解决
2. `+$47K` 系统 PnL、Sharpe `+0.02`，MaxDD 几乎持平（`+4%`）
3. `cap=3` 被严格支配，`cap≥3` 的边际收益（共 `+$34K`）需承受 `+$6K` 以上 MaxDD 恶化，历史样本稀疏、泛化性存疑
4. `cap=2` 的集中度上限明确（最多 `14%` BP 锁在同策略），operational risk 可控

- **当前归类**：done via `SPEC-066`
- **收口说明**：最终 review 结论为 `PASS with spec adjustment -> DONE`。Developer 无需补改代码；`AC4` 被修正为逻辑级约束，`AC10` 的 artifact count 预期区间从 `[33,40]` 校正为 `[45,55]`，实测 `49` 正确
- **来源**：`SPEC-064` post-ship real-world review，2026-04-19 → 2026-04-20 Phase 2 完成；`SPEC-066` 于 2026-04-20 review 通过并 DONE

### Q045 — Account-Level ROE Optimization Across Strategy Matrix：联合 bp_target lift（取代分散的单策略优化）

- **状态**：resolved via `SPEC-084 DONE` and live on old Air
- **触发**：PM 在 Q044 Tier 2 完成后观察到"我们在按策略一个一个做 ROE 优化，不理想"——piecemeal 方法漏掉了 cross-strategy 联合效应
- **核心发现**：
  - **Phase 1 baseline mapping** 揭示系统结构性被低利用：avg BP 仅 11.09%，17% 交易日完全空仓，61% 单策略
  - **Phase 2C joint optimum (J3)**：`bp_target_normal=0.15` + `bp_target_high_vol=0.14`
    - 3y AnnROE: 16.27% → 22.39% (+6.12pp)
    - **19y AnnROE: 11.94% → 17.41% (+5.48pp)**
    - **Sharpe IMPROVES**: 1.78 → 1.83
    - 6 个策略全部正贡献
    - Peak BP 43%（HIGH_VOL ceiling 50% 内）
    - NORMAL/HIGH_VOL 完美可加（interaction = 0.000pp）
  - **风险量级**：worst trade -5.6% → -8.8% account（1.57x scaling），CVaR 5% 同比例
- **取代关系**：
  - **Q044 (BPS-only)**：完全被取代——Q044 是 Q045 NORMAL 维度的子集
  - **Q036 Overlay-F**：部分被取代——Overlay-F 全样本仅 +0.074pp，Q045 HIGH_VOL 维度同样本 +1.96pp（26 倍）；Q036 selectivity 仍可作为 tail safety 保留 shadow
  - **Q041 attribution / visualization path**：互补——填补剩余 ~19pp idle BP 的多样化轴；经 `Q046` 明确提升为 post-`Q045` 的 primary deployment-efficiency mechanism axis
- **Spec 范围（如 PM 批准）**：
  - `bp_target_normal`: 0.10 → 0.15
  - `bp_target_low_vol`: 0.10 → 0.15
  - `bp_target_high_vol`: 0.07 → 0.14
  - `_size_rule()` 文字: "≤ 3% / 1.5%" → "≤ 4.5% / 2.25%"
  - 风险声明：worst trade 可达 -8.8% 账户
- **当前决策结果**：
  - `SPEC-084` 已实施并通过 implementation review
  - old Air live runtime 已部署新默认值：`bp_target_low_vol/normal/high_vol = 0.15 / 0.15 / 0.14`
  - live surface 已验证：`/api/recommendation` 正常、`_size_rule()` 显示 `4.5% / 2.25%`、`/api/position/open-draft` 的 `bp_target_pct = 15.0`、`HIGH_VOL` helper = `14.0`
  - runtime 注记：old Air 本次通过 cherry-pick 接入 `SPEC-084`，原因是该仓库当前存在 pre-existing local-only commit，未处于 fast-forward clean 状态
  - 单 Spec 路线成立；未拆两阶段
  - Q036 维持 `shadow` / deprioritize
  - Q044 维持 superseded / closed
- **后续仅保留两项收尾**：
  - 若 PM 需要，再讨论 rollout / observation 是否作为独立 follow-up，而非重开 `SPEC-084`
  - 旧 Gate 1 测试债务（`test_spec_048_055` / `test_spec_056`）可单独做 maintenance cleanup
- **参考备忘**：`task/q045_pm_decision_packet_2026-05-06.md`，`task/SPEC-084.md`

### Q049 — Multi-Sleeve Read-Only Recommendation & Visualization Surface（由 Q048 收口出的窄实施方向）

- **状态**：resolved via `SPEC-085 DONE`
- **触发**：在 `Q048` 架构规划与 Quant 治理 scope-down 后，PM 选择以“可视化回测 + attribution artifact”作为主要替代路径，取代原先笨重的长周期 paper-trading 依赖；同时不希望直接进入 unified routing 或 live write-path merge。
- **当前 DRAFT 方向**：
  - read-only `sleeve_candidates[]`
  - 最小 portfolio summary surface
  - 最小 attribution / visualization artifact
- **明确要解决的问题**：
  1. `Q041` Tier 1 / Tier 2 候选如何在 live 数据上前向展示，而不自动开仓
  2. 如何在一个只读 summary 里同时看到 SPX live rail 与 Q041 paper rail
  3. 如何给 post-`SPEC-084` 的 deployment-efficiency 问题一个最小可观察接口（idle-day capture / BP-fill / worst-day overlap）
- **明确排除**：
  - 不做 unified portfolio routing
  - 不改 `current_position.json` 写路径
  - 不自动写 `q041_paper_trades.jsonl`
  - 不做 broker write
  - 不做 full multi-asset simulator
- **Tier 路径语义（当前共识）**：
  - Tier 1：以 read-only candidate + accepted attribution artifact 支撑，不额外要求通用 forward-tracking 观察期
  - Tier 2：若未来 PM 单独提出单名 fill/slippage realism 问题，再作为窄 follow-up 处理；不是当前默认 gate
  - Tier 3：review-only forward log
- **当前归类**：implemented platform support item / 不是大重构
- **当前共识**：
  - Quant fidelity review：`PASS with specific boundary edits`
  - Developer feasibility review：`feasible with boundary edits`
  - PM：已批准 `SPEC-085`
  - PM：已接受 `data/q041_portfolio_attribution_latest.json` 作为 `SPEC-085 F3` 正式输入
  - PM：不再要求 `4–6` 周 live signal forward-tracking，也不恢复原 12-month paper-trading 路线
  - Developer：`SPEC-085` 已实施完成（`Status: DONE`）
- **参考备忘**：`task/SPEC-085.md`

### Q051 — `/ES` honest-parameter 口径下是否仍有可恢复的 performance edge
- **状态**：resolved
- **内容**：近期 `/ES` 线已经完成了一轮重要的语义收敛：`stop_mult = 3.0x credit`、production-comparable sizing 固定为 `1` 合约、参数统一到 `strategy/es_params.py`。在这个更诚实的口径下，当前 `/es-backtest` 页展示的最小 cell（`45 DTE / Δ0.20 / trend filter ON`）表现接近 `Sharpe 0.00 / ROE 轻微负值`。Planner 直接复核当前 backtest 路径后，判断这个差结果方向上是真实的，而不是单纯 UI 漂移
- **关键澄清**：这首先否定的是**当前最小 cell**，不等于直接否定原始 `/ES` 研究的完整 thesis。原始 `research/strategies/ES_puts` 研究包含更大的结构假设：trend filter、DTE ladder、VIX leverage framing、以及更高层的 multi-layer intuition，而不是只有一个 `45d Δ0.20` 单槽位
- **最终研究结论**：**original thesis still alive but current cell is the wrong implementation**
  - 当前 `1` 合约 production 路径与原始 thesis 所需的完整结构（动态 VIX leverage + BSH + 多槽 theta 引擎）不是同一个策略
  - 因此当前路径应重新定位为：
    - live data collection cell
    - visibility / monitoring cell
    - runtime semantics calibration cell
  - BSH 的经济性被正式量化为**规模依赖**：`1` 合约 × `5` 槽的 theta 收益不足以覆盖 BSH 年成本，说明 BSH 只在动态杠杆放大后才有意义
  - `STOP = 3.0 / 3.5 / 4.0` 与 `2` 合约诊断都没有恢复统计显著性；问题不是一个小参数，而是当前诚实规模下的结构性高方差
- **与其他条目的关系**：
  - `Q012` = 当前规模下的 `/ES` 监控 / stressed-SPAN 可见性
  - `Q050` = 更长期 portfolio-level shared-BP governance
  - `Q051` = 只讨论 `/ES` 这条线在更诚实参数口径下还有没有值得 salvage 的 alpha / implementation shape
- **full-thesis rerun 结果**：
  - 在完整体系下，thesis **得到验证**
  - `P4 + BSH` 在 `STOP = 3.5x` 与 `4.0x` 下都得到正显著 bootstrap CI
  - `STOP = 3.0x` 仍处于边界状态，但并不推翻 full-system thesis
  - 当前 `1` 合约路径与完整 thesis 仍应视为两条不同的东西：前者是 live-data / visibility cell，后者才是可验证的 full-system hypothesis
  - BSH 只在动态杠杆规模下才有经济性；在当前 `1` 合约规模下仍不成立
- **最终结论**：完整 `/ES` thesis 在 full-system 形态下得到统计支持，但它是 **scale-dependent** 的；在当前 `$500k` 账户下，production-plausible 的保守 recalibration 无法恢复 significance。故当前 `1` contract 路径应重新定位为 live-data / visibility / operational-calibration cell，而不是主动 ROE 引擎。`Q051` 至此闭合，不再继续这条 thesis 线的主动救援。
- **后续路由**：未来若还要研究 `/ES`，不再回到 `Q051`，而是转入 `Q052` 作为新的结构性 redesign 分支。
- **来源**：Planner 收口 2026-05-08；详见 `doc/q051_es_performance_salvage_seed_memo_2026-05-08.md`

### Q052 — `/ES` defensive redesign after closure of the original thesis line
- **状态**：open
- **内容**：这是在 `Q012/Q051` 正式闭合之后新开的未来研究分支。目标不是继续修补原 thesis，而是研究三个新的 `/ES` 方向：
  1. 对 `/ES` 整体走势做技术判断，在进入明显下跌区间时更早触发离场，而不是被动等待 `3x/4x` stop
  2. 在该技术判断框架下，优先研究向更低 strike / 更远 DTE 的 roll-down / roll-out 管理
  3. 研究极远 OTM、长期限的裸 put 结构（例如指数 `7000` 时卖 `3500` strike、半年期限的 put）是否构成与原 thesis 不同的风险收益分布
- **定位**：这不是 `Q012/Q051` 的延续，而是一个新的 `/ES` redesign branch。当前优先级低于 `Q041`，不进入当前 implementation queue。
- **下一决策**：若 PM 未来要重开 `/ES` 研究，应先从这三个方向中选一个最窄问题作为 Quant 下一单元，而不是把三者混成一个大包。
- **来源**：PM follow-up idea + Planner 收口 2026-05-08；详见 `doc/q052_es_defensive_redesign_seed_memo_2026-05-08.md`
