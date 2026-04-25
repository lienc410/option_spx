# 开放问题追踪（Open Questions）

> 未解决问题、阻塞项、待验证假设。双端均可更新，HC负责整合。
> 状态：`open` / `blocked` / `resolved`

最后更新：2026-04-24（Planner，接收通过 MC 审核的 `MC_Handoff_2026-04-24_v3`，新增 HC 复现队列）

---

## 当前优先阻塞

### Q009 — Schwab Developer Portal 批准等待中
- **状态**：blocked
- **内容**：该项保留为 **MC 侧系统状态**。HC 已成功连接 Schwab Developer Portal，因此它不是当前 HC planner 主线 blocker；但若 MC 侧环境仍未完成批准，则 SPEC-035 AC1/3/4/5 live Greeks 联调在 MC 侧仍受阻
- **阻塞下游**：live position Greeks enrichment（SPEC-035）
- **备注**：后续索引层若从 HC 视角总结 blocker，应避免直接把 Q009 写成 HC 当前 blocker
- **来源**：MC Handoff 2026-04-10；HC 状态修正 2026-04-12

### Q001 — SPEC-020 RS-020-2 ablation 未完成
- **状态**：blocked
- **内容**：RS-020-1 FAIL（信号逻辑15/15通过，但 `run_backtest` 缺少 toggle 参数，ablation AC7–AC10无法验证）；AMP 负责修复 `run_backtest` toggle 并完整实现 `run_trend_ablation.py`（4路ablation + regime breakdown + OOS路径）
- **依赖**：RS-020-2 由 AMP 实施，HC不应假设其已提交或通过
- **阻塞下游**：overlay_mode 切换为 active；SPEC-020 → DONE
- **注意**：`bearish_persistence_days` 实际值为3（signals/trend.py L33），HC不得自行修改
- **来源**：MC Handoff 2026-04-04

### Q002 — Shock Active Mode 生产切换决策（Phase B）
- **状态**：open
- **内容**：SPEC-027 Phase A shadow analysis 已完成；Phase B A/B 测试需数据驱动决策：active mode 是否满足 AC B1–B4（trade count 下降 ≤10%，PnL 下降 ≤8%，MaxDD/CVaR 不劣化）
- **依赖**：Phase B 回测结果
- **来源**：SPEC-027，research_notes §36

---

## 策略设计待解决

### Q012 — `/ES` short put 生产路径与共用 BP 管理
- **状态**：open
- **内容**：ES short put 的生产路径评估已有实质更新。`/ES` 账户权限已确认可用，实测 buying power effect 约为 `$20,529 / 合约`，`$500k` 账户可支持单槽 `1` 张、较高 VIX 下可提升至 `1–2` 张；相较之下，XSP 虽解决 lot size 问题，但 spread 成本更可能侵蚀统计显著性，因此 `/ES` 现已成为优先路径
- **关键风险**：`/ES` 与 SPX Credit 共用同一 options buying power 池，而非独立池；同时 `/ES` 的 SPAN margin 会在高波动期动态扩张，可能形成“亏损扩大 + BP 占用上升”的双重压力
- **当前状态补充**：`SPEC-061` 已完成最小 Layer 2 production cell，但该实现仍是无 Layer 1 缓冲、无 Layer 3 对冲的独立 `/ES` MVP
- **下一决策**：shared-BP 口径是否需要进一步细化，以及 `/ES` 生产路径是否需要进入下一轮 follow-up Spec（见 `Q013`）
- **当前归类**：post-SPEC-061 follow-up pending
- **来源**：Claude 研究更新 2026-04-12

### Q013 — `/ES` short put 运行时止损与持仓管理定义
- **状态**：open
- **内容**：`SPEC-061` 已完成 `/ES` minimal production cell 的入场路径，但 `-300%` stop 当前仍主要是 catalog / review 层面的文档化规则，生产中没有自动触发执行；同时，趋势转负后的现有持仓行为也未定义。PM 已明确：**不能接受纯人工盯仓止损**；最少要求是系统监控该 stop 条件，并在触发时由 bot 发出提醒
- **依赖**：应收缩成一个新的 follow-up Spec，只补运行时风控与 post-entry 管理；最小可接受范围应至少覆盖 stop 监控与 bot alert，不把 Layer 1 / Layer 3 / leverage 一起带入
- **当前归类**：ready for DRAFT Spec
- **来源**：`SPEC-061` review + `/ES` 三层体系覆盖盘点，2026-04-12

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

### Q019 — backtest 的收盘口径 VIX 与 live recommendation 的开盘 / 早盘 VIX 口径是否存在系统性偏差
- **状态**：open
- **内容**：当前大量研究与回测默认使用按交易日收盘口径构建的 VIX 时间序列，但 live recommendation 的真实决策发生在开盘附近；而 VIX 在很多波动事件日会在开盘前或刚开盘时达到当日高点，随后回落。这意味着 backtest 使用 close-based VIX，可能低估 live 决策时实际面对的恐慌水位，进而影响：
  - `HIGH_VOL` vs `NORMAL` regime 切换
  - `VIX_RISING` 判定
  - `ivp63` / 其他高波 gate 的触发频率
  - `Q017 / SPEC-064` aftermath 条件是否在 live 中更早或更晚触发
- **关键问题**：需要研究的不是“VIX 开盘通常高于收盘”这一一般事实，而是：如果历史推荐与回测改用 open-based（或最接近 live 决策时点的）VIX 口径，selector 的实际输出会有多少次发生变化？这些变化集中在什么 regime / filter / strategy 上？是否足以改变我们对某些研究结论或 live miss 的解释？
- **MC 2026-04-24 新证据**：MC Phase 1 已用 `BBG OHLC` 跑完 `27` 年测量，报告：
  - aftermath 层 `4.63%` flip
  - regime 层 `9.71%` flip
  - trend 层 `31.54%` flip
  - aftermath `319` 个 flip 中，`179` 个为 `close=False / open=True`，`140` 个相反
- **当前 PM 状态**：MC handoff 明确写为 `decision deferred`；有 `A / B / C` 三个后续路径，但 PM 尚未拍板，HC 不应自行把这份证据解释为“必须改 live”或“必须重跑既有 spec”
- **建议下一步**：如 PM 批准，先做一个窄研究原型
  - baseline：现有 close-based VIX 口径
  - variant：open-based 或 earliest-available live-time VIX 口径
  - 输出：route 变化次数、gate 变化次数、aftermath 变化次数、受影响 trade 数、主要集中在哪些日期 / regime / strategy
- **当前归类**：research only
- **来源**：PM 新增研究问题，2026-04-19

### Q020 — MC `backtest_select` 简化导致 `SPEC-064 AC10` artifact count 偏少
- **状态**：open
- **内容**：MC 报告其 `backtest_select` pipeline 的简化路径会让 `SPEC-064` 的 aftermath research view artifact count 比预期偏少，触发 `AC10` 计数区间的偏移。HC 端 artifact 计数（`49`）已是当前 canonical 数据；本项追踪的是 MC 端简化的回填决策
- **HC 影响**：暂无直接代码影响；监控 MC 后续是否要求 HC 同步调整
- **当前归类**：MC-side housekeeping
- **来源**：`MC_Handoff_2026-04-24_v3.md`、`MC_Response_2026-04-25_v2.md` §4

### Q021 — `Q018 / SPEC-066` 的 aftermath 多槽位语义是否设错：应抓第二峰回落，而不是 back-to-back 连抓两次
- **状态**：open
- **历史编号**：HC 自 2026-04-20 起原记为 `Q020`；2026-04-25 PM 接受 MC 编号约定后改为 `Q021`，与 MC handoff / response 对齐
- **内容**：PM 在复盘 `2026-03` 的 double-spike 真实案例时指出，当前 `SPEC-066` 的 `cap=2 + B` 逻辑虽然成功捕捉了两笔 `IC_HV`（`2026-03-09` 与 `2026-03-10`），但这两笔是紧邻的 back-to-back 开仓，而不是“第一峰后的机会未完成、第二个峰值形成后再抓第二次回落”。若策略设计的真正意图是后者，那么 `Q018` 研究与 `SPEC-066` 的收益中，可能混入了语义错误的 alpha
- **关键问题**：需要区分三件事：
  1. `cap=2 + B` 的增量收益里，有多少来自同一峰后的紧邻 back-to-back `IC_HV`
  2. 有多少来自真正的 distinct-second-peak aftermath 机会
  3. 如果要求“第二笔必须对应新峰或至少满足 re-arm 语义”，当前 `SPEC-066` 的 `+$47K / Sharpe +0.02` 还剩多少
- **为什么这不是直接回滚**：目前这只是语义与归因问题，不是已证实的实现错误。`SPEC-066` 仍可能在总量上有效，只是研究目标可能定义得过宽。应先做归因研究，再决定是：
  - 保留 `SPEC-066`
  - 收紧为“distinct-second-peak only”
  - 或推翻并重做 aftermath 多槽位逻辑
- **建议最小 Phase 1**：
  - 将 `SPEC-066` 新增的 `IC_HV` 交易拆成：
    - 同峰 back-to-back
    - distinct-second-peak
    - 其他
  - 对比各自的 trade count / total PnL / avg / Sharpe / MaxDD 贡献
  - 同时构造一个对照变体：`single-slot + re-arm only after new peak`
- **当前归类**：research only
- **来源**：PM 对 `2026-03` 真实 double-spike case 的语义复盘，2026-04-20

### Q029 — research/live notional parity：engine `qty = 1` 与 selector `SizeTier` 不一致
- **状态**：open
- **内容**：MC 的 `5-dim parity audit` 报告，其他维度大多是 `no issue / minor drift`，但有一个 material issue：backtest engine 在研究输出中硬编码 `qty = 1`，忽略 selector `SizeTier`。这会让部分 HIGH_VOL aftermath 研究以 `1 SPX` 记账，而 live 实际只会下 `1 XSP`，从而放大 magnitude 解读。MC 没有选择直接重写 engine，而是通过 `Q033 Option B+E` 规定以后 handoff / SPEC / RDD 一律同时给出 `research_1spx` 与 `live_scaled_est`
- **建议下一步**：HC 先复现 audit 和 dual-column reporting 规则，不要直接启动 live-scale engine 重构
- **当前归类**：ready for HC reproduction
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q032 — aftermath broken-wing `V3-C (LC = 0.03)` 是否值得替换当前 `V3-A`
- **状态**：open（monitoring）
- **内容**：MC 已将 aftermath broken-wing 的当前落地形态定为 `V3-A = LC 0.04 + LP 0.08`，`DTE = 45` 不变；`V3-C = LC 0.03` 没有被直接否决，但因为 liquidity concern 被降级为 monitor-and-revisit 候选
- **触发条件**：先积累前 `5–10` 笔 live aftermath；只有当 `V3-A` 的 worst-case 表现满足预期，且 `LC = 0.03` 的流动性观察也可接受时，才重新打开升级评估
- **当前归类**：monitoring only
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q034 — strike rounding `/5 grid` 与 engine 整数 round 的精度漂移
- **状态**：open（低优先级）
- **内容**：MC 提醒当前 engine strike rounding 仍是整数 round，而 live 执行在部分腿上是 `/5` grid；理论上会带来最多 `±2.5` 点的精度漂移。MC 认为这只在 precision execution matching 的场景下才 material，不是当前主线
- **当前归类**：optional / low priority
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q035 — future live-scale backtest engine / RDD
- **状态**：open（长期）
- **内容**：若项目未来希望 backtest engine 直接输出 live-scale 数字，而不是由 `research scale × live_factor` 换算，则需要单独的 live-scale engine architecture / RDD 分支。MC 明确建议暂缓，不要把它作为当前 sync 后的默认下一步
- **当前归类**：long-term / defer by default
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q003 — L3 Hedge 实盘实现（v2）
- **状态**：open
- **内容**：当前 v1 中 L3 实际执行与 L2 相同（全平仓位）；真正的 long put spread hedge 待立新SPEC并验证
- **当前归类**：waiting on dependency / priority decision
- **建议**：ChatGPT review 推荐优先推进
- **来源**：SPEC-026，research_notes §35

### Q004 — `vix_accel_1d` L4 fast-path（COVID类极速崩溃）
- **状态**：open
- **内容**：3日窗口在COVID类5日内极速崩溃中有滞后；`vix_accel_1d` fast-path 可提升响应，但需backtest验证避免日内噪声误触发
- **当前归类**：research only
- **来源**：SPEC-026，research_notes §35

### Q005 — 多仓 trim 精细化
- **状态**：open（中期）
- **内容**：当前 L2/L4 触发时全平所有仓位；多仓扩展后可改为按 shock 贡献排序优先关闭最高风险仓位，提高资本效率
- **依赖**：多仓引擎
- **当前归类**：waiting on dependency
- **来源**：research_notes §35

---

## 信号研究待验证

### Q006 — ADX 辅助确认
- **状态**：open（低优先级）
- **内容**：若 SPEC-020 OOS 期仍有 >20% 误触发，考虑 ADX 作为辅助确认信号
- **依赖**：SPEC-020 RS-020-2 OOS 结果
- **来源**：SPEC-020 §39

### Q007 — Vol Persistence Model（senior quant review §5.2）
- **状态**：open（中期，P3）
- **内容**：高波持续性模型，目前 spell_age_cap 为固定参数，可改为数据驱动
- **来源**：research_notes §5.2

### Q008 — ATR v2（Bloomberg H/L版）
- **状态**：open（低优先级，P5）
- **内容**：当前 ATR 用收盘价差分近似（无需 H/L 数据）；v2 升级到真实 ATR 需 Bloomberg H/L 数据
- **来源**：SPEC-020

---

## DIAGONAL 样本追踪

### Q011 — regime decay DIAGONAL 样本验证
- **状态**：open
- **内容**：DIAGONAL ivp252 ≥ 50 且 ivp63 < 50 区间（regime decay）：n=8，Sharpe +3.56；样本偏小，需真实交易验证后才能确认 SPEC-053 的 DIAGONAL size-up 有效性
- **依赖**：真实交易数据积累
- **来源**：MC Handoff 2026-04-10（新增）

---

## 已解决（存档）

| 编号 | 问题 | 结论 | 解决日期 |
|------|------|------|---------|
| — | Daily portfolio metrics vs trade-level 哪个作为主指标 | Daily portfolio 作为主决策依据，trade-level 保留用于策略族ROM排名 | 2026-04-01 |
| — | Overlay L2 AND还是OR条件 | AND：防止VIX正常上升但组合风险可控时误触 | 2026-04-01 |
| — | book_core_shock 信号路径（freeze触发后的缺陷）| 每日独立计算，不依赖入场路径 | 2026-04-01 |
| — | ATR阈值选择（1.0 vs 其他）| 1.0，gap_sigma分布与原+1%band最接近 | 2026-04-02 |
| Q010 | local_spike DIAGONAL 真实交易 n 计数 | `SPEC-055b` 已实施，`local_spike` 已进入 DIAGONAL full size-up；不再作为前置 open question 追踪 | 2026-04-10 |
| Q014 | 撤销 DIAGONAL Gate 1（`SPEC-049` ivp252 marginal zone） | Quant 已通过 Fast Path 在 `strategy/selector.py` 删除 Gate 1 分支；当前生产逻辑仅保留 Gate 2（`IV=HIGH`）及其余 LOW_VOL + BULLISH 有效规则 | 2026-04-15 |
| Q016 | VIX recovery window dead zone（Dead Zone A 独立方向） | 条件 alpha 验证失败：recovery context 内 `NORMAL + HIGH + BULLISH` BPS 不显著，`SPEC-060 Change 3` 应保持 `REDUCE_WAIT`；后续研究并回 `Q015` / Dead Zone B | 2026-04-18 |
| Q015 | BPS `NORMAL + BULLISH` IVP gate 窄幅放宽（`50 -> 55`） | OOS 验证通过后，Quant 已通过 Fast Path 将 `BPS_NNB_IVP_UPPER` 从 `50` 提高到 `55`；该窄变更已不是 open question，未来若继续研究更广泛 IVP / IC redesign，应作为新问题处理 | 2026-04-19 |
