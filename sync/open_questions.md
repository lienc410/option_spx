# 开放问题追踪（Open Questions）

> 未解决问题、阻塞项、待验证假设。双端均可更新，HC负责整合。
> 状态：`open` / `blocked` / `resolved`

最后更新：2026-05-03（Planner，记录 Q041 进入 hybrid data-alignment 阶段）

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
- **2026-04-25 进展**：
  - Phase 1（信号层归因）完成：`doc/q021_phase1_attribution_2026-04-25.md` — 同峰 back-to-back 占 SPEC-066 增量 78% 笔数 / 88% 美元
  - Phase 2（全引擎 4 变体）完成：`doc/q021_phase2_full_engine_2026-04-25.md` — V3 (distinct-cluster only) 系统 -$9,200 vs V1 (SPEC-066)；max conc IC_HV V2=6 不可用；2026-03 双峰 case 增量仅 +$111
  - 1st Quant 初步建议 `(a) 保留 SPEC-066 close Q021`
  - 2nd Quant review (`tests/q021_2nd_quant_handoff_2026-04-25.md`) CHALLENGE：证据不足以 close；要求开 Phase 3 small pack（half-size 变体 + 2018-2026 切片 + BP gap 拆解）
  - PM 2026-04-25 决策：approve Phase 3，Q021 保持 open；cluster 阈值 sweep 推迟到 Phase 4 看 Phase 3 结果再定
  - Phase 3（V_A/V_B/V_C 三变体）完成：`doc/q021_phase3_half_size_2026-04-25.md` — half-size 否决，BP crowding 假设否决（非 IC_HV PnL 跨变体严格相同 $332,681），recent slice 排序一致；1st Quant 推荐回到 (a) 保留 SPEC-066
  - PM 反问 "V_A 是不是相当于 IC_HV 直接 2× size"，追加 V_D = aftermath 首笔 2× size + 双峰可两次入场
  - **V_D 全样本 +$431,673（V_A +$403,850 的 +6.9%），Sharpe 0.45 vs 0.42，MaxDD -$9,749 vs -$10,323（更优）**；非 IC_HV PnL 仍严格相同（无 portfolio interaction 副作用）；2026-03 case +$2,589 vs V_A +$1,184
  - V_D 代价：tail risk × 2（COVID 单笔 -$3,314 vs V_A -$1,657），BP-adjusted return -2.8%，MaxConc IC_HV 升至 3
  - 2nd Quant Round 2 review (`task/q021_2nd_quant_review_handoff_2.md`) CHALLENGE V_D：marginal $/BP-day = $3.37 < V_A baseline $4.85 → leverage drag 嫌疑；要求 sizing-curve study (V_E/V_J/V_H/V_G) + 永久标准指标包
- **2026-04-26 进展**（Phase 4）：
  - PM 决策：永久 standing rule — 所有未来 strategy/spec 比较必须含完整指标包（marginal $/BP-day、worst trade、disaster window、max BP%、concurrent 2× 天数、CVaR 5%）。已存为 memory `feedback_strategy_metrics_pack.md`
  - Phase 4 6 变体 sizing-curve study 完成：`doc/q021_phase4_sizing_curve_2026-04-26.md`、prototype `backtest/prototype/q021_phase4_sizing_curve.py`
  - **关键发现**：所有 sizing-up 变体 marginal $/BP-day 全部低于 V_A baseline $4.85 — V_G $3.83 / V_D $3.37 / V_J $2.98 / V_E $2.70。**整条 sizing curve 在 [1×, 2×] 区间无 smart-edge**，V_D 的 +6.9% PnL 是 leverage drag 而非 smarter rule
  - V_J (no-overlap rule, MaxBP 28%) 与 V_E (1.5× full overlap) PnL 几乎相等（+$10K），证实 V_D 多挣的 +$17K 主要来自 distinct-cluster 同时 2× leverage
  - V_G disaster cap 是最干净 doubler（disaster +$176 vs V_D -$748），但 marginal 仍 < baseline，**保留为 future spec 候选不晋升**
  - V_H split-entry 等价于 V_A − 1 trade，无 alpha；2nd Quant 的 1×+1× 假设否决
  - **更新推荐回到 (a) 保留 SPEC-066 close Q021**：sizing curve study 否决了 V_D 的 promote 候选地位；不开 SPEC-067
- **PM 2026-05-02 最终裁定**：approve。`Q021` 正式关闭，保留 `SPEC-066` 不变，不开 `SPEC-067`
- **当前归类**：resolved / closed
- **与新主线关系**：`Q021` 现在应被视为 **rule-layer evidence base / pilot input**，而不是未来 capital-allocation 研究的父容器。其结论仍然有效：`V_D` 不是更好的 canonical rule；若未来要研究 idle BP deployment，应在新问题下按组合级资本池重新建模
- **来源**：PM 对 `2026-03` 真实 double-spike case 的语义复盘，2026-04-20

### Q036 — Idle BP Deployment / Capital Allocation：在组合级资本池下，是否应将持久闲置 BP 受控部署，以合理提高账户级 ROE
- **状态**：resolved（方向层面；HC PM 已接受 MC 侧更接近 escalate / productization-stack 的方向）
- **内容**：PM 已明确项目顶层 objective 重置为：**首要目标是合理最大化账户级 ROE**。这里的 “合理” 明确包含：控制风险暴露、避免大回撤、避免 margin stress / forced liquidation risk、避免坏 regime 下的隐藏集中。这个目标**不同于**单纯最大化 `Sharpe`、`PnL/BP-day`、或某条规则的语义纯度。由此产生一个新问题：当 baseline rule 与 baseline size 已经应用后，如果账户仍有显著 idle BP，是否应通过受控 capital-deployment overlay 来提高账户级 ROE
- **为什么这不是 `Q021` 继续延长**：`Q021` 已经足够回答 rule-layer 问题：“`V_D` / `V_G` 等 sizing-up 变体不应替代 `V_A SPEC-066` 成为新的 canonical rule”。但这并不自动回答 capital-allocation 问题：“若 baseline 长期留有可观 idle BP，而这些 BP 没有更优用法，是否应通过 overlay 部署出去？” 这两个问题的 objective function 不同，必须分开治理
- **当前 PM 边界**：
  - 顶层目标：合理最大化 account-level ROE
  - 当前 opportunity-cost baseline：`A`（若无更好用途，idle BP 可以保持闲置）
  - 建模层级：按**组合级资本池**建模，而不是单策略局部池
  - pilot use case：如需试点，可先用 `IC_HV aftermath`，但它只是试点，不预设为最终通用答案
- **需要回答的最小问题**：
  1. baseline 下 idle BP 是否真的“持久且足够大”，值得研究 overlay
  2. baseline + overlay 是否提高账户级 `ROE` / 年化 `ROE`
  3. incremental overlay 带来的 tail cost 是多少：`MaxDD`、`CVaR 5%`、disaster-window damage、peak BP%、margin-stress proxy、forced-liquidation proxy
  4. overlay 是否优于当前机会成本基线（目前为“保持 idle BP 不动”）
  5. 如果 overlay 消耗 BP，是否会 crowd out 更好的 baseline 交易
- **推荐研究 framing**：
  - 不再问：“Should `V_D` replace `V_A`?”
  - 改问：“Should the system add a controlled idle-BP deployment overlay, modeled at the combination-level capital pool, to improve reasonable account-level ROE?”
- **与 `Q021` 的关系**：
  - `Q021` 作为 rule-layer evidence base 保留
  - `IC_HV aftermath` 可作为 `Q036` 第一试点
  - 但 `Q036` 不应重新打开完整 `Q021` semantic tree，也不应把 overlay 结果误写成 `SPEC-066` 规则替换结论
- **下一步建议**：先交 Quant 做 feasibility-level 研究，不开 Spec，不改生产规则；待 Quant 给出 idle-BP persistence、ROE uplift、tail-cost、opportunity-cost 四件事的证据后，再决定是否需要 DRAFT Spec 或更高层 portfolio-allocation branch
- **2026-04-26 Quant framing 更新**：
  - 2nd Quant / Quant 当前共识：`Q036` 是 **capital-allocation** 问题，不是 `Q021` 的 rule-replacement 延长线
  - overlay 的边际经济门槛不是 `V_A` 的 `+$4.85 / BP-day`，而是 **idle baseline ≈ `$0 / BP-day`**
  - baseline BP 使用率初步判断约 `12.5%` 平均、`14%` 峰值，意味着 idle BP 结构性 `>= 86%`，因此“是否值得研究 overlay”这件事本身答案偏向 **yes**
  - 但目前仍**不能**把任何 sizing-up 变体当成已批准 overlay：因为 account-level `MaxDD`、`CVaR 5%`、disaster-window damage、margin-stress / forced-liquidation proxy 还没算
  - 也不能直接把 `Q021 Phase 4` 的数值搬过来当最终答案：一旦加入 idle-BP threshold gating，真实触发形状会变，PnL 和 tail 都会同时下降
- **当前 Quant 推荐**：
  - `Phase 1`（必须先做）：idle BP baseline measurement + regime-conditional distribution
  - `Phase 2`（仅在 Phase 1 支持时）：只测 3 个 conditional overlay 试点
    - `1.5x first-entry`
    - `2x disaster-cap`
    - `2x no-overlap`
    - 且全部要求 `idle BP threshold` 作为前置 gating
- **2026-04-26 Phase 1 实测完成**：
  - detail layer: `doc/q036_framing_and_feasibility_2026-04-26.md`
  - prototype: `backtest/prototype/q036_phase1_idle_bp_baseline.py`
  - **容量结论已答**：V_A SPEC-066 baseline 下，平均 BP 使用仅 `8.68%`，平均 idle BP `91.32%`；aftermath 日 `100%` 具备 `>= 70%` idle BP；disaster 期 idle 仍在 `86–97%`
  - 因此 `Q1`（idle BP 是否持久且足够大）答案是 **yes**
  - **新主风险发现**：aftermath 日已有 `>= 2` 个 short-gamma 仓位的比例约 `47%`（full）/ `54%`（recent），说明 overlay 的首要约束不是 deploy 容量，而是 short-gamma stacking
  - `Q2/Q3/Q4` 仍未答完：overlay 是否改善 account-level ROE、增加多少 tail cost、是否优于 idle baseline，仍需 Phase 2 才能回答
  - `Q5` 的 minimum pilot shortlist 维持不变：`Overlay-A 1.5x conditional` / `Overlay-B 2x + disaster cap` / `Overlay-C 2x + no-overlap`
- **PM 2026-04-26 决策**：批准 `Phase 2`
  - 研究范围保持窄：仅测 `Overlay-A` / `Overlay-B` / `Overlay-C`
  - `idle BP threshold gating` 继续作为所有变体的强前置门
  - 不开 `SPEC`
  - 不改生产
  - 不重开 `Q021` 语义争论
- **2026-04-26 Phase 2 完成**：
  - 三个试点都对 idle capital 给出正增量回报：
    - `Overlay-A`: `+6,780` total PnL，`+0.054pp` annualized ROE
    - `Overlay-B`: `+10,706`，`+0.088pp`
    - `Overlay-C`: `+9,364`，`+0.077pp`
  - 但三者都**还不够**支持进入 DRAFT overlay spec：
    - uplift 量级仅 `+0.05` 到 `+0.09` annualized ROE points
    - `CVaR 5%` 都从 `-4,309` 变差到 `-4,382`
    - peak system `BP%` 从 baseline `30%` 升到 `31% / 38% / 34%`
  - `Overlay-B` 的 disaster-window net 最干净（`+302`，与 baseline 持平），但 peak BP 最高
  - `Overlay-C` 的 stacking guardrail 最强（pre-existing `>= 2` short-gamma 环境命中率 `0%`），但回报略低、disaster net 不如 `B`
  - `Overlay-A` 基本可淘汰：回报最弱、disaster net 最差
  - crowd-out check 全部为 `OK`
  - idle-BP utilization 极低（仅消耗 baseline idle budget 的 `0.39%` 到 `0.46%`）
- **当前 Quant/Planner 推荐**：
  - `Q036` **不应 drop**
  - 但也**不应进入 DRAFT overlay spec discussion**
  - 如继续，只建议收缩到 `Overlay-B` 与 `Overlay-C`
- **2026-04-26 Phase 3/4 收缩更新**：
  - guardrail refinement 新增：
    - `Overlay-D_hybrid` = `Overlay-B + Overlay-C`
    - `Overlay-E_hyb80` = `Overlay-D + idle BP >= 80%`
  - 结果：`D/E` 证明 stacking 可以清零且保住 `B` 的 disaster-window net，但 uplift 被压到仅 `+0.046pp` annualized ROE；`E` 与 `D` 完全同值，说明 `80% idle gate` 在该局部是 inert
  - 再进一步的窄测试给出 **lead candidate**：
    - `Overlay-F_sglt2` = `2x` iff `idle BP >= 70%`、`VIX < 30`、且 `pre-existing short-gamma count < 2`
  - `Overlay-F` 结果：
    - total PnL `+412,855`
    - annualized ROE uplift `+0.074pp`
    - 比 `Overlay-D` 的 `+0.046pp` 明显更好
    - 接近 `Overlay-B` 的 `+0.088pp`
    - `SG>=2 = 0%`
    - disaster-window net `+301`
    - peak BP `34%`（低于 `Overlay-B` 的 `38%`）
  - 这意味着 `Q036` 首次出现了一个像样的折中点：**比 `B` 更干净，比 `D` 更不保守**
- **当前 Quant/Planner 推荐（最新）**：
  - `Q036` 仍然 **不应 drop**
  - 仍然 **不应进入 DRAFT overlay spec discussion**
  - 但如果继续，已不建议横向扩更多变体；应只围绕 `Overlay-F_sglt2` 做 very narrow confirmation：
    1. yearly attribution
    2. overlay-fire 分布（regime / VIX bucket / pre-existing short-gamma count）
    3. recent-era robustness (`2018+`)
- **PM 2026-04-26 决策（最新）**：
  - 批准继续，但只批准 `Overlay-F_sglt2` 的 final narrow confirmation
  - 不再横向扩新候选
  - 不回到 `Q021`
  - 不开启 spec discussion
  - 该轮完成后，应进入 PM decision-packet 阶段，而不是继续无界扩研究树
- **PM 2026-05-02 最终方向裁定**：
  - HC 接受 MC 侧更接近 `escalate / productization stack` 的方向
  - 这意味着：`Q036` 作为“是否继续朝产品化方向前进”的方向性问题已经收口
  - `SPEC-075 / SPEC-076` 在 HC 端不再因 canonical 分歧而 deferred；后续若推进，属于 adoption / prerequisite / implementation-planning 问题，而不是继续研究 `hold vs escalate`
  - 这**不等于**立即 productize，也**不等于**现在就开 DRAFT spec；它只表示 HC 不再把 MC 的路线当作需先争论的研究分歧
- **2026-05-03 补充**：
  - `sync/mc_to_hc/MC Response 2026-05-02_v2.md` §4 已提供 `SPEC-075 / SPEC-076` adoption 输入包，内容包括：
    - spec 全文位置
    - MC file list / patch scope
    - `overlay_f_mode` posture（`disabled / shadow / active`）
    - old runtime 影响面
    - 最小 regression / tieout 验证口径
  - 因此，`Q036` 这条线在 HC 侧当前**不再**处于“等 adoption 包”状态；剩余工作是本地化 adoption planning 与 staged rollout，而不是继续索要上游定义
- **2026-05-03 adoption-fit clarifier**：
  - Quant 当前 verdict：**needs one more Quant clarification pass**
  - 这不是重开 `Q036` 研究，也不是否定 MC adoption 包，而是要求 HC 在交给 Developer 前再把本地 acceptance / guardrail / evidence 边界写实
  - `SPEC-075` 应原样 adopt 的核心：
    - 仅 `IC_HV`
    - `idle_bp_pct >= 0.70`
    - `VIX < 30`
    - `short-gamma count < 2`
    - posture 仍为 `disabled -> shadow -> active`
  - HC 必须额外锁死的 guardrails：
    - **position-count** `short-gamma` productization 语义
    - live state 缺失 / stale 时 **fail closed**
    - disabled 下 recommendation payload 行为保持 inert
    - MC `web/html/spx_strat.html` → HC 本地真实路径映射必须写死
    - backtest / live portfolio-state builder 一致性检查
  - `SPEC-076` shadow 观察期最少必须看到：
    - trade / PnL 与 disabled 一致
    - shadow fires 与 active backtest fire count 同量级
    - 每条 would-fire 有完整 context（date / strategy / VIX / idle BP / SG count / mode / factor / rationale）
    - bot / dashboard 不把 shadow 误解释成 actual size-up
  - 该轮 clarification 现已完成，Developer 结论是：已经足够形成 **HC 本地 implementation-ready planning package**
- **2026-05-03 Developer planning update**：
  - 第一批正式文件面已固定：
    - new: `strategy/overlay.py`、`scripts/overlay_f_review_reports.py`、`doc/OVERLAY_F_REVIEW_PROTOCOL.md`、`tests/test_overlay_f_gate.py`、`tests/test_overlay_f_monitoring.py`
    - modified: `strategy/selector.py`、`backtest/engine.py`、`backtest/portfolio.py`、`web/templates/index.html`
  - 正式 file-map 已确认：
    - MC `web/html/spx_strat.html`
    - HC `web/templates/index.html`
  - 最稳妥实施顺序已固定：
    1. 075/076 共同准备 file-map / guardrails / validation package
    2. 先实现 `SPEC-075`
    3. 再实现 `SPEC-076`
    4. 统一执行 `disabled -> shadow -> active` 三层验证
  - old Air 影响面已明确：
    - `web`
    - `bot`
    - telemetry (`data/overlay_f_shadow.jsonl`, `data/overlay_f_alert_latest.txt`)
    - 最小部署需重启 `com.spxstrat.web` 与 `com.spxstrat.bot`
- **2026-05-03 Developer implementation update**：
  - `SPEC-075/076` 已在 HC 本地实现，当前 posture 固定为 `overlay_f_mode = "disabled"`
  - `SPEC-075` 已落地：
    - new: `strategy/overlay.py`
    - modified: `strategy/selector.py`, `backtest/engine.py`
    - tests: `tests/test_overlay_f_gate.py`
    - handoff: `task/SPEC-075_handoff.md`
  - `SPEC-076` 已落地：
    - modified: `strategy/overlay.py`, `strategy/selector.py`, `web/server.py`, `web/templates/index.html`
    - new: `scripts/overlay_f_review_reports.py`, `doc/OVERLAY_F_REVIEW_PROTOCOL.md`
    - tests: `tests/test_overlay_f_monitoring.py`
    - handoff: `task/SPEC-076_handoff.md`
  - 当前 guardrails / wiring 已覆盖：
    - `position-count` short-gamma 语义
    - live fail-closed
    - disabled payload inert
    - shared backtest/live portfolio-state & evaluation path
  - 本地验证已通过：
    - `tests.test_overlay_f_gate` + `tests.test_overlay_f_monitoring`: `10/10 PASS`
    - `tests.test_state_and_api` + `tests.test_bcd_filter` + `tests.test_bcd_stop` + `tests.test_engine_stop_wiring`: `36/36 PASS`
    - `compileall`: PASS
    - `main.py --dry-run`: PASS
    - 3y disabled parity spot: `57` trades / `$79,933.69`，与 tieout #3 disabled baseline 一致
  - 尚未执行：
    - commit / push
    - old Air pull
    - old Air `web` / `bot` restart
  - 当前下一步：
    - commit / push
    - old Air pull
    - old Air `web` / `bot` restart
    - first `shadow` flip
- **2026-05-03 PM 决策**：
  - PM 选择 `B`
  - 含义：本地 disabled implementation review 通过，批准进入 first old Air `shadow` rollout
  - 边界不变：
    - 仍按 `disabled -> shadow -> active`
    - 当前只批准 `shadow`
    - 不批准 `active`
  - 因此这条线的当前下一步不再是“是否批准 shadow”，而是 Developer 执行：
    - commit / push
    - old Air pull
    - 重启 `com.spxstrat.web` / `com.spxstrat.bot`
    - 启动 `shadow` 观察
- **2026-05-03 Developer shadow rollout update**：
  - first old Air `shadow` rollout 已完成
  - commit: `458231e` (`SPEC-075/076: roll Overlay-F to shadow`)
  - 已 push 到 `origin/main`
  - old Air 已执行：
    - pull latest `main`
    - `pip install -e .`
    - restart `com.spxstrat.web`
    - restart `com.spxstrat.bot`
  - 当前 runtime posture：
    - `overlay_f_mode = "shadow"`
    - 明确 **不是** `active`
  - 当前运行验证：
    - local web health `200`
    - `/api/recommendation` `200`
    - 当前 recommendation 正常返回 `Bull Put Spread`
    - no-side-effect check:
      - disabled strategy = `bull_put_spread`
      - shadow strategy = `bull_put_spread`
      - same strategy = `True`
      - shadow factor = `1.0`
      - shadow would_fire = `False`
      - shadow fail_closed = `False`
  - telemetry / artifacts 当前状态：
    - `data/` 可写
    - `data/overlay_f_shadow.jsonl` 与 `data/overlay_f_alert_latest.txt` 目前**尚不存在**
    - 这是预期行为：当前 writer 仅在 shadow/active 的 would-fire 事件出现时写盘
  - 已知限制：
    - 当前还没有真实 Overlay-F shadow event
    - 第一轮有意义的 review 需等待满足 gate 的 `IC_HV` 候选出现
- **当前归类**：resolved at direction level / shadow-live on old Air / observation pending meaningful would-fire samples
- **2026-04-26 Phase 5 final confirmation 完成**：
  - detail layer: `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
  - prototype: `backtest/prototype/q036_phase5_overlay_f_confirmation.py`
  - top line 维持：
    - baseline total PnL `+$403,850`
    - `Overlay-F` total PnL `+$412,855`
    - delta `+$9,005`
    - annualized ROE uplift `+0.074pp`
  - **yearly attribution**：
    - positive delta years `11 / 27`
    - negative delta years `4 / 27`
    - zero years `12 / 27`
    - 最大单一年份贡献为 `2022 +$1,896`，仅占 absolute yearly delta 的 `17.6%`
    - 去掉最强 `1` 年后仍有 `+$7,111`
    - 再去掉前 `2` 年（`2022`, `2008`）后仍有 `+$5,285`
    - 结论：uplift 是“稀疏但分散”的，不是靠 `1–2` 个年份撑起来
  - **overlay-fire distribution**：
    - fire count `23`
    - 全部发生在 `HIGH_VOL`
    - `VIX 20-25: 5`，`25-30: 18`
    - pre-existing short-gamma count：`0: 9`，`1: 14`，`>=2: 0`
    - mean idle BP at fire 约 `80.5%`
    - 结论：guardrail 实际触发分布与设计一致，没有在危险 stacking 区间偷偷加码
  - **recent-era robustness (`2018+`)**：
    - delta total PnL `+$4,395`
    - annualized ROE uplift `+0.040pp`
    - MaxDD 基本持平（`-9,405` vs `-9,392`）
    - `CVaR 5%` 持平（`-3,798` vs `-3,798`）
    - fire count `10`，且仍全部满足 `HIGH_VOL / SG < 2` 结构
    - 结论：recent era 仍为正，但 uplift 比全样本更薄
  - **最终研究判断**：
    - `Overlay-F_sglt2` 已完成 final narrow confirmation
    - 当前没有证据支持继续扩研究树
    - 但也还不足以自然推进到 `DRAFT overlay spec discussion`
    - 最合适的下一步已不是继续做更多 variant，而是进入 **PM decision packet**
- **2026-04-26 2nd Quant review 结果**：
  - 总 verdict：**CHALLENGE**
  - 已通过部分：framing 正确、`Overlay-F_sglt2` 作为 lead candidate 站得住、yearly attribution / disaster posture / recent slice 结论方向成立
  - 指出的不一致：`Overlay-F` gate 用 **family-deduplicated** count，framing / cleanliness metric 用 **position-count**
- **2026-04-26 3rd Quant review 结果**：
  - 总 verdict：**PASS** — ready for PM decision packet
  - 同意 framing 与 lead candidate；不应进 DRAFT spec discussion
  - 承认 recent-era uplift 偏薄、full-sample CVaR 未全面改善
- **2026-04-26 Quant Researcher 综合 verdict**：**`PASS WITH CAVEAT`**
  - 关键事实核对：Phase 5 §3 cleanliness claim (`SG>=2 = 0/23`) 是从 engine 的 **position-count** metric 算出来的（[q036_phase5_overlay_f_confirmation.py:67](backtest/prototype/q036_phase5_overlay_f_confirmation.py#L67) 读 `rows_by_date[d].short_gamma_count`，即 [engine.py:1073](backtest/engine.py#L1073) 写入的 position-count），不是从 gate 的 family-dedup metric 算出来的
  - 也就是说 cleanliness 报告用的是更严的 metric，本样本下两种口径 fire 分布完全一致 → 这是 **presentation issue, not numerical issue**
  - 2nd Quant CHALLENGE 在事实核对后偏严；3rd Quant PASS 不提语义分叉偏松；交集是 PASS WITH CAVEAT
  - 已执行最小动作：往 `task/q036_quant_review_packet_2026-04-26.md` 加 §11 Methodology Note (Post-Review Addendum)，披露 gate-vs-metric 口径分叉、本样本下 cleanliness claim 在 position-count 下也成立、productization 阶段必须把 gate 对齐到 position-count
  - **不**重跑 Phase 4 / Phase 5；**不**改 prototype；packet 可发 PM
- **PM 2026-04-26 决策（最新）**：
  - PM 选择 **`B`**
  - 含义：将 `Overlay-F_sglt2` 推进到更正式的 overlay 治理讨论 / 下一阶段 planning packet
  - **不**等于：
    - `DRAFT overlay spec discussion`
    - Developer implementation
    - live rollout
  - methodology caveat 继续保留：若未来真走向 productization，gate 必须对齐到 position-count short-gamma semantics
- **当前归类**：**formal overlay discussion approved**（含披露的 caveat；仍未进入 DRAFT spec）
- **2026-04-26 Quant 最新交付**：
  - 新增 PM-facing packet：`task/q036_pm_decision_packet_2026-04-26.md`
  - 该 packet 的 recommendation 不是 `escalate`，也不是 `drop`
  - Quant 明确建议：
    - **hold as research candidate, do not productize now**
  - 主要理由：
    - uplift 真实但偏薄（full `+0.074pp` annualized ROE；recent `+0.040pp`）
    - governance cleanliness 已足够避免 `drop`
    - 但没有 knockout 量级证据值得现在承担产品化复杂度
    - 若 `escalate`，仍需先做 gate 对齐重跑与一整层治理落地
    - 若 `hold`，主要代价是机会成本与需要明文记录 re-trigger 条件，防止 branch 变成隐性 `drop`
  - **因此当前最准确状态**：
    - 不是 `ready for DRAFT overlay spec discussion`
    - 不是 `drop`
    - 而是 **等待 PM 对 hold vs productize 的最终拍板**
- **来源**：`task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md`、PM 2026-04-26 对 objective reset 的明确回复

### Q037 — `profit_target = 0.60` broad rule audit：HC 已对齐默认值，AC3 量级差距现已解释到足够程度
- **状态**：open（de-escalated; explanation largely sufficient）
- **内容**：MC 将 `profit_target 0.50 -> 0.60` 作为 broad rule audit 的主发现，并通过 `SPEC-077` 落地。HC reproduction sprint 已完成 `SPEC-077` 代码对齐：`StrategyParams.profit_target = 0.60`、两处 `web/server.py` fallback override 同步、credit-side `params.stop_mult` wiring 已锁定。操作层面已与 MC production posture 对齐
- **HC 当前结论**：`SPEC-077` 已在 HC 端闭合为 `DONE`，但属于 **documented AC3 shortfall** 收口，而不是“全样本量级完全复现”。HC 的 full-sample rerun（`2007-01-01`，19.32y）只得到：
  - `Δ annualized ROE = +0.0856pp`
  - 远低于 MC `Q037 Phase 2A` 的 `+0.91 ~ +1.03pp`
  - 也低于 `SPEC-077 AC3` 的 `≥ +0.5pp` 阈值
- **已知候选原因**：
  1. compounding-baseline / annualized ROE 口径差异
  2. debit-side `-0.50` 硬编码（现已由 `SPEC-080` 正式闭合）
  3. HC `SPEC-056c` / MC `SPEC-054` 的永久 DIAGONAL 分歧
- **当前建议**：
  - 不回滚 `SPEC-077`
  - 不再阻塞 tieout / reproduction sprint
  - 但应将这条量级差距保留为一个明确 follow-up：在 `SPEC-080` 落地后做一次 attribution run，确认上面三条里哪一条是主因
- **2026-05-02 Quant 最新判断**：
  - 这不是 HC dashboard / `SPEC-078` 的计算 bug
  - metric 口径最多只能解释**一部分**：
    - 同一 HC full-sample ledger 下
    - `final_equity_compound / $100k` = `+0.0856pp`
    - `simple PnL / $100k / years` 也只能到 `+0.3504pp`
    - 若分母改成 `$50k`，simple 最多到 `+0.7009pp`
  - 因此若要解释 MC 的 `+0.91~+1.03pp`，必须再叠加：
    - 不同 denominator / ROE definition
    - 或不同 trade path
  - 本轮也基本排除了 `SPEC-080` / debit-side hardcode 作为当前主因：`bcd_stop_tightening_mode=disabled` 与 `active` 的 full-sample PT delta 完全相同
- **2026-05-03 Quant 更新**：
  - 现在可以确认两点：
    1. HC 不是 metric bug；`SPEC-078` 的 `final_equity_compound` 口径自洽，`+0.0856pp` 是该口径下的正确读数
    2. HC / MC 至少存在混合差异：metric 口径能把 HC 同一 ledger 的 uplift 从 `+0.0856pp` 放大到约 `+0.3504pp`，但仍到不了 MC 的 `+0.9088pp`
  - 当前最可能的剩余来源排序：
    1. sample window（MC `1999-01-01 → 2026-05-02` vs HC `2007-01-01 → today`）
    2. strategy/path mix（MC uplift 最大贡献在 `bull_put_spread`，而 HC 主正贡献来自 `Iron Condor / IC_HV`）
    3. exit reason timing（MC 的主机制是 `50pct_profit(_early)` 大量迁移到 `roll_21dte`）
  - `SPEC-080` / debit-side hardcode 现在基本不是主因：HC 已验证 `bcd_stop_tightening_mode=disabled` 与 `active` 的 full-sample PT delta 完全相同
- **当前最小下一步**：
  - 不再继续大范围 HC 盲跑
  - 若需要正式收口，只补一页窄的 attribution note：
    - HC displayed `+0.0856pp` 是 CAGR/final-equity 口径
    - same-ledger simple 口径约 `+0.3504pp`
    - 剩余到 MC `+0.9088pp` 主要由更长 sample window 与不同 path / strategy mix 解释
- **与 PM 的关系**：当前不需要 PM 再为 `SPEC-077` 是否上线拍板；需要 PM 后续决定的是，这个 ~10× 量级差距是否值得提升为独立调查问题（候选 `Q040`）
- **当前归类**：post-spec attribution open（但优先级已下降）
- **来源**：`task/SPEC-077.md`、`doc/baseline_2026-05-02/ac3_summary.json`、`sync/hc_to_mc/HC_return_2026-05-02.md`

### Q038 — `BCD comfortable top` + `BCD stop tightening` 研究弧（Path C）已在 HC 复现，并已进入 old Air shadow runtime
- **状态**：resolved（Path C reproduced; shadow deployed on old Air）
- **内容**：MC 将 `Q038` 定义为一条完整研究弧，而不只是两个彼此独立的小 spec。HC reproduction sprint 已完成：
  - `SPEC-079`：`BCD comfortable top` entry filter
  - `SPEC-080`：`BCD debit stop tightening`
  - 两者默认 toggle 都保持 `disabled`
- **HC reproduction 结果**：
  - `SPEC-079` / `SPEC-080` 都已 `DONE`
  - tieout #3 证明在 `disabled` 模式下对 trade flow **零回归**
  - 在 `PT=0.50 + both active` 的预览场景中，`2026-04-30` 的一笔 `BCD` 被 `risk_score=3` 正常拦截，证明 `SPEC-079` 逻辑已生效
- **PM / Developer 2026-05-02 结果**：
  - HC 已实际切到 `shadow`
  - old Air 已同步包含 `SPEC-079/080` 的代码并重启 `web + bot`
  - `bcd_comfort_filter_mode = "shadow"`
  - `bcd_stop_tightening_mode = "shadow"`
  - `GET /api/recommendation -> 200`，live recommendation path 正常
- **剩余含义**：
  - 后续重点转为 monitoring / observation
  - `SPEC-079` 的 shadow 现在可在 live path 上观察，日志目标为 `data/bcd_filter_shadow.jsonl`
  - `SPEC-080` 的 shadow 目前主要仍是 engine/backtest 层 wiring；old Air live path 暂不会自然产生对应的 live shadow stop 日志
  - 若未来还要扩到 `state-conditional stop` 等新方向，应以新 follow-up 形式管理，而不是把当前 shadow rollout 继续当作 open blocker
- **2026-05-03 Quant monitoring protocol**：
  - shadow 观察期的目标不是证明 alpha，而是验证：
    1. `SPEC-079` comfortable-top 条件在 live recommendation path 中是否按设计被识别
    2. shadow 是否只记录、不改变推荐、不阻断交易、不影响 bot / web
    3. 触发样本是否落在原设计想防的 BCD 风险区（低 `VIX`、从 `30d high` 回落、仍高于 `MA50`）
  - `SPEC-079` review 的最低字段：
    - `date`
    - `mode`
    - `vix`
    - `dist_30d_high_pct`
    - `ma_gap_pct`
    - `risk_score`
    - `would_block`
  - 核心判断不是“日志越多越好”，而是：
    - `would_block=true` 是否只出现在三条件全满时
    - 是否集中在预期 BCD 风险环境
    - 是否完全无 recommendation side-effect
  - `SPEC-080` 当前应明确写成：
    - **engine/backtest-observable shadow + live posture alignment**
    - 不应期待 old Air 自然产出丰富 live-side stop shadow event
  - 建议 cadence：
    - 最短 `4` 周，正常 `4–8` 周
    - 每周 fixed review 一次
    - BCD candidate 日 / 近阈值市场日做 event-driven quick check
  - 只有在观察期内：
    - 无 false positive
    - 无 runtime side-effect
    - 触发语义可解释
    - 样本足够可审查
    时，才值得让 PM 讨论 `active`
- **当前归类**：resolved for planning / in runtime shadow observation
- **来源**：`task/SPEC-079.md`、`task/SPEC-080.md`、`doc/tieout_3_2026-05-02/README.md`、`sync/hc_to_mc/HC_return_2026-05-02.md`

### Q039 — `IC regular` 残余 gap：更像 high-IVP `NORMAL IC` fallback / gate 差异，而非 slot blocking
- **状态**：open
- **内容**：在 HC reproduction sprint 的 tieout #2 / #3 之后，HC↔MC 的主残余 gap 依然明显：
  - `PT=0.50` 模式下仍约 `+5` trades / `+$30k` 量级
  - 其中最大单项始终是 `IC regular`：
    - HC `13` 笔
    - MC `6` 笔
- **为什么它现在应从 candidate 升级为 open question**：
  - 在 `SPEC-074 / 077 / 078 / 079 / 080` 全部复现后，这个 gap 仍未消失
  - 因此它已不再只是“可能会被 reproduction 自动吸收的小尾差”
  - 而是一个会实质影响 HC↔MC 收敛度的正式研究问题
- **当前最可能根因**（按 HC assessment / tieout 结果综合）：
  1. `IVP` gate sensitivity（尤其 `ivp252 >= 55` 一类路径）
  2. trend / ATR persistence 默认值或触发时机差异
  3. HC `SPEC-056c` vs MC `SPEC-054` 的永久 Gate 1 分歧对 `BCD/IC` 分布的二次影响
- **2026-05-03 Quant 更新**：
  - MC 提供的 6 笔 `IC regular` ledger 支持当前判断：
    - 这更像 high-IVP `NORMAL IC` fallback / gate 差异
    - 而不是 slot blocking
  - 关键理由：
    - MC 6 笔中只有 2 笔与 HC 共有，HC-only 有 11 笔
    - HC 13 笔中已有 `9/13` 落在 `ivp252 >= 55`
    - `0/13` 落在 `50~65` 临界区
    - `0/13` 显示为已有同类 slot occupied
  - 这说明它并不是“55 附近轻微阈值抖动”问题，先做 `IVP` sweep 价值不高
- **当前建议**：
  - 不把它当作 reproduction bug
  - 也不立刻开 spec
  - 先作为正式 research question 保留，下一步只做一个 **mini attribution table**：
    - MC 6 笔：`entry date / 是否 HC 共有 / entry VIX / entry SPX / exit reason / PnL`
    - HC-only 11 笔：`entry date / ivp252 bucket (<30, [30,55), >=55) / trend state / slot occupied / HC route reason`
    - 结论桶：`high-IVP fallback/gate / low-IV bug candidate / MC-missing despite valid [30,55) / other`
  - 只有当 mini table 显示大量 HC-only 落在 `<30` 或 `[30,55)` 仍异常缺失时，才考虑升级
- **PM 2026-05-02 定位**：
  - 保持在研究位置
  - 当前不提升成更强的 parity-investigation 主线
- **与 Q020 的关系**：
  - `Q020` 当前仍是 MC-side housekeeping / `SPEC-064 AC10` artifact count 问题
  - `Q039` 则是 tieout #2/#3 之后留下的 **HC↔MC strategy-mix gap 主问题**
- **当前归类**：research — narrow attribution only
- **来源**：`task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md`、`doc/tieout_2_2026-05-02/README.md`、`doc/tieout_3_2026-05-02/README.md`、`sync/hc_to_mc/HC_return_2026-05-02.md`

### Q029 — research/live notional parity：engine `qty = 1` 与 selector `SizeTier` 不一致
- **状态**：open
- **内容**：MC 的 `5-dim parity audit` 报告，其他维度大多是 `no issue / minor drift`，但有一个 material issue：backtest engine 在研究输出中硬编码 `qty = 1`，忽略 selector `SizeTier`。这会让部分 HIGH_VOL aftermath 研究以 `1 SPX` 记账，而 live 实际只会下 `1 XSP`，从而放大 magnitude 解读。MC 没有选择直接重写 engine，而是通过 `Q033 Option B+E` 规定以后 handoff / SPEC / RDD 一律同时给出 `research_1spx` 与 `live_scaled_est`
- **2026-04-25 更新**：`SPEC-072` 已完成 HC frontend dual-scale 落地。也就是说，reporting-layer 缓解方案现在已在 HC UI 中实现；当前仍然 open 的只剩“是否需要更深的 engine / RDD 级 live-scale 重构”，而不是双列显示本身
- **建议下一步**：HC 先复现 audit 和 dual-column reporting 规则，不要直接启动 live-scale engine 重构
- **当前归类**：ready for HC reproduction
- **来源**：`MC_Handoff_2026-04-24_v3.md`

### Q041 — Large-Cap Equity Option Income Overlay：是否值得作为独立 equity-income sleeve 进入正式研究池
- **状态**：enter research pool / Gate 0 pass with constraints / overlap validation
- **内容**：Quant 已完成正式理论评估。结论不是 `drop`，也不是近端 spec，而是：这份候选材料里存在三个可被机构化研究的模块，但当前项目在数据层面还没有通过 `Gate 0`。因此它现在应被视为一个**已进入研究池、但尚未获准分配建模带宽**的独立题目
- **已确认可研究的模块**：
  1. `mega-cap covered call overlay`
  2. `cash-secured put on a strict high-quality whitelist`
  3. `defined-risk earnings short-vol`（credit spread / protected structure，而非裸卖）
- **明确排除项**：
  - naked earnings short option
  - `RSI 99` reversal discretionary short
  - 单名股票极端事件押反转
  - 社媒式“月收租金额”口径
- **机构化定义方向**：
  - 这条线应被定义为独立的 `equity-income sleeve`
  - 不应并入当前 `SPX` 主策略代码主线
  - 与 `Q036` 的关系主要是未来账户级 capital-allocation 竞争，而不是当前研究阶段的直接依赖
- **当前最高优先级不是建模，而是 Gate 0**：
  - HC 是否能获得历史 per-name 个股期权数据
  - 最低要求：大致 `2004–2026`、覆盖 whitelist、含 options OHLC / implied vol / OI 深度
  - 若 Gate 0 FAIL：`Q041` 暂缓，不进入 Phase 1
  - 若 Gate 0 PASS：最小 Phase 1 应先做
    - `BXM / PUT / WRIT` benchmark analysis
    - covered-call-only whitelist pilot
- **2026-05-03 Gate 0 scaffold update**：
  - Quant 已完成 forward-collection scaffold：
    - `research/q041/init.py`
    - `research/q041/whitelist.py`
    - `research/q041/collect_chains.py`
    - `~/Library/LaunchAgents/com.spxstrat.q041_collect.plist`
    - `.gitignore` 已加入 `data/q041_chains/`
    - `pyproject.toml` 已加入 `pyarrow>=15`
  - 当前围栏保持干净：
    - 未触碰 `engine.py / strategy/ / signals/ / web/ / notify/ / schwab/*`
    - 仅 read-only reuse `schwab.auth` + `schwab.client._parse_chain_response / _normalize_quote`
    - 写盘只在 `data/q041_chains/{date}/`
  - Smoke test（`AAPL --force`）已通过：
    - `2462` 行（`1231 calls + 1231 puts`）
    - `20` 个到期日（`2026-05-04 → 2027-03-19`）
    - 输出 `AAPL.parquet + _underlying.parquet + _summary.json`
    - 体量估算约 `700 KB/day` 全白名单、约 `175 MB/year`
  - 但这**不等于** Gate 0 已通过：
    - 当前只说明 forward collection 可行
    - 历史 per-name options 覆盖（`~2004–2026`）仍未确认
  - 当前下一步：
    - 手动执行 `launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_collect.plist`
    - 在首个 weekday run 后检查：
      - `logs/q041_collect.log`
      - `logs/q041_collect.out.log`
      - `logs/q041_collect.err.log`
      - `data/q041_chains/YYYY-MM-DD/` 是否拿到 `10` 个 symbol parquet + `_summary.json`
- **2026-05-03 Gate 0 collector refinement update**：
  - `SPX` 问题已定位并修复：
    - 根因：Schwab API gateway body-buffer overflow；`$SPX` 行权价过密（`5-point` increment）× 大 `DTE` 窗口导致响应体超限
    - 修复：`$SPX` 单独使用 `strikeCount=100`、`DTE=180` 天
    - 结果：覆盖约 `40` 个到期日、`4159` calls，足够服务当前主策略链数据积累
  - `/ES` 已从该 whitelist 路径移除：
    - 原因：Schwab `/marketdata/v1/chains` 不支持期货期权，返回 `400 Bad Request`
    - 结论：`/ES` futures options 需要独立数据源（如 CME DataSuite 或第三方）
  - 当前 forward-collection whitelist 已更新为 `12` 个标的：
    - `10` 个 large-cap 名称
    - `SPX`
    - `QQQ`
  - 当前日规模估算：
    - 约 `45K` 行
    - 约 `800KB` parquet / day
  - 当前下一步：
    - 仍是等待首次 weekday `16:30 ET` 自动触发
    - 首跑后重点确认：
      - `10` 个个股 + `SPX` + `QQQ` 是否都成功落盘
      - `BRK/B` → `BRK_B.parquet` 是否工作正常
      - `logs/q041_collect*.log` 是否无 symbol-level 异常
  - **2026-05-03 old Air deployment update**：
    - old Air 已对齐到 `origin/main @ a112d33`
    - `pyarrow-24.0.0` 已安装
    - `Q041` collector 已作为独立 launchd job 部署：
      - `~/Library/LaunchAgents/com.spxstrat.q041_collect.plist`
      - command: `/Users/macbook/SPX_strat/venv/bin/python -m research.q041.collect_chains`
    - `Q036` posture 未变：
      - 仍是 `overlay_f_mode = "shadow"`
      - 未进入 `active`
    - `web` / `bot` 本轮未重启，原因是：
      - 本次仅涉及 research scaffold / `pyarrow` / attribution notes
      - 不涉及新的 live recommendation path 代码变更
      - 当前 runtime health 仍正常
    - manual smoke 已通过：
      - `python -m research.q041.collect_chains --symbols AAPL --force --verbose`
      - 产出 `2462` rows
      - 成功写入：
        - `data/q041_chains/2026-05-03/AAPL.parquet`
        - `data/q041_chains/2026-05-03/_underlying.parquet`
        - `data/q041_chains/2026-05-03/_summary.json`
    - launchd smoke 已通过：
      - job executed under launchd
      - runs = `1`
      - last exit code = `0`
      - weekend gate 生效，`non-trading day (Sun) — skipping`
    - 当前最重要的下一检查点：
      - 首个 weekday `16:30 ET` 自动 run
      - `12` 个 whitelist symbol 是否全部落盘
      - `BRK/B -> BRK_B.parquet`
      - `logs/q041_collect*.log` 是否无 symbol-level 错误
- **2026-05-03 Massive historical-source update**：
    - PM 已开通 `Massive.com` `Options Developer` 账户
    - 定位：一次性批量下载历史数据后取消订阅
    - 当前历史规格：
      - 深度约 `4` 年（`~2022-05` 起）
      - 覆盖美国期权市场（经 `OPRA`）
      - 含 EOD aggregates / trades / greeks / IV / OI / S3 flat files
      - 不含历史 bid/ask quotes（该项需更高计划）
    - symbol 覆盖预验证：
      - 白名单 `17/17` symbol reference PASS
      - `SPXW` PASS
      - `BRK/B` PASS
      - OHLCV aggregates PASS
    - 当前执行路径：
      - Massive 负责历史批量下载（约 `2022–2026`）
      - Schwab forward collector 自 `2026-05-03` 起继续积累新增链数据
      - 两者在 Phase 1 中拼接使用
    - 关键约束：
      - 这不是原始设想的 `2004–2026` 全历史深度
      - `/ES` 仍不在该数据路径中
      - 若未来需要历史 bid/ask 或更长深度，仍可能需要补数据源
    - 当前 Gate 0 结论：
      - **PASS WITH CONSTRAINTS**
      - 可以开始历史下载和本地转换
      - 但未来所有 Phase 1 结果都必须显式注明数据窗口与 quote-depth 约束
- **2026-05-03 data-alignment note update**：
  - `doc/q041_data_alignment_note_2026-05-03.md` 已写入，当前总判断是：
    - **`ready to collect and align`**
    - 但 Phase 1 前必须先完成 Massive 历史段与 Schwab 近期段的 schema / overlap / tolerance 对齐
  - 当前正式拼接方向：
    - Massive = 历史 canonical
    - Schwab = 近期 canonical
    - overlap = 校验窗口，不双重入库
  - 当前最关键的新约束不是 symbol mapping，而是字段缺口：
    - Massive `day_aggs` 历史段 **无 Greeks / IV / OI**
    - Schwab 当前 forward parquet **也没有 IV**
    - 这意味着“hybrid path 可拼接”并不等于“Phase 1 已具备完整 IV-sensitive 建模数据”
  - 当前认定：
    - 历史段可先用 OHLCV / close / volume 进入受限研究
    - 但若后续建模依赖历史 delta / IV / OI，则仍需额外数据补充或明确降级方案
  - 当前建议并行动作：
    - Developer：执行 Massive 历史批量下载与本地转换（见 `SPEC-081`）
    - Quant：确认 Schwab raw chain response 中是否存在 IV / full Greeks 字段但当前未被采集（见 `SPEC-082`）
    - 在这两步完成前：
      - `Q041` 仍然不是 Phase 1 回测开跑状态
      - 更准确说是：**Gate 0 pass with constraints / alignment phase**
  - **2026-05-03 overlap validation protocol update**：
    - `doc/q041_overlap_validation_protocol_2026-05-03.md` 已写入
    - Quant 当前正式建议不是“边下载边零散 spot check”，而是：
      - **20 个交易日正式校验**
      - **10 天修正与复验缓冲**
    - 不选 `10–15` 个交易日：
      - 不足以覆盖月度 rollover 边界
      - 也不足以覆盖较低频标的（如 `ASML / TSM / PANW`）
    - 不直接把 `30` 天全部用于纯观察：
      - 需要留出后 `10` 天处理校验中暴露出的 schema / field / naming 问题
    - 当前 overlap 期间最关键的持续指标是：
      - `symbol / expiry / strike` 命中率
      - `price` 偏差
      - `volume` rank correlation
      - 以及 `IV / Greeks / OI` 完整率与 `SPX / SPXW`、`BRK/B` 稳定性
    - Quant 已明确把差异分成两类：
      - **可吸收**：
        - volume 点值偏差（用 rank 不用点值）
        - `price <= 2%`
        - Massive 历史段 `Greeks / IV / OI = null`
        - 稀疏标的零行日
        - Massive `T+1` 延迟
      - **阻止 stitching**：
        - `symbol match < 85%`
        - `price > 5%`
        - `expiry / strike` key 解析错误
        - `IV` 单位混淆未修正
        - `SPX / SPXW` 行数偏差 `> 20%`
    - 修正顺序也已固定：
      - `symbol normalization`
      - `date / timestamp`
      - `price field mapping`
      - `IV` 单位口径
      - `missingness handling`
      - `canonical source priority`
    - 30 天结束时，PM 的唯一判断依据应是：
      - **逐标的 Reconciliation Report / Table**
      - 所有 checklist 条件全部通过，Phase 1 才可入场
    - 当前最合理的节奏：
      - `SPEC-081/082` 产物一旦可用，立即启动 overlap 计时
      - 目标在 `2026-05-30` 左右提交 Reconciliation Report 给 PM
  - **2026-05-03 SPEC-082 implementation update**：
    - Developer 已本地实现 `SPEC-082`：
      - `schwab/client.py` 的 `_parse_chain_response` 现在保留：
        - `iv`
        - full Greeks
        - `expiry_type`
        - `open/high/low/close`
        - `last`
      - `research/q041/collect_chains.py` 已把这些列追加到 forward parquet schema
      - 本地 readback 已确认 `AAPL` / `SPX` parquet 中存在新增列
    - 当前实现层面是成功的，但 live-data validation **尚未完全通过**：
      - `iv` 原始值出现：
        - `iv_min = -999.0`
        - `iv_max = 629.206`
      - `expiry_type` 在 `AAPL` 上返回的是 `['S', 'W']`，不是原先预期的 `['M', 'W']`
    - 当前最合理解释不是“实现失败”，而是：
      - Schwab 原始字段语义仍需 Quant 解释
      - `-999` 很可能是缺失 / sentinel
      - `S/W/M` 的含义需要按 Schwab 语义重新定义，而不是按原假设硬套
    - 因此：
      - `SPEC-082` 可以视为 **implemented locally**
      - 但 `Q041` 数据口径仍处在 **alignment / semantic cleanup** 阶段
      - 在 Quant 对 IV / `expiry_type` 做完语义确认前，不应把这些字段直接当作 Phase 1 canonical 输入
  - **2026-05-03 SPEC-081 / 082 review closure update**：
    - Quant 已 review 两个 spec，当前结论：
      - `SPEC-081` = **PASS / DONE**
      - `SPEC-082` = **PASS / DONE**
    - `SPEC-082` 的 code path 被确认是对的；先前的 AC3 / AC4 不通过，不是实现 bug，而是 spec 假设错了
    - Quant 已通过 Fast Path 执行最小清洗：
      - `collect_chains.py` 中对 Schwab `iv <= 0`（含 `-999.0` sentinel）改为 `null`
    - Schwab `expiry_type` 的正式口径现改为：
      - `W = Weekly`
      - `S = Standard monthly`
      - `Q = Quarterly`
      - `M = End-of-month`（少见）
    - 因此后续：
      - overlap validation protocol
      - reconciliation scripts
      - summary/report templates
      都应使用 `S` 来识别常规月度到期，而不再沿用早先的 `M/W` 假设
    - 这也意味着：
      - `Q041` 不再处于“collector / schema build-out”主状态
      - 当前正式进入 **overlap validation** 阶段
      - 剩余 blocker 是 reconciliation，不是 `SPEC-081/082` 实现能力
- **2026-05-03 runtime-alignment note**：
  - `Q036` posture 本轮未变化：
    - old Air 仍是 `overlay_f_mode = "shadow"`
    - 当前 recommendation 仍显示 `overlay_factor = 1.0`
    - `overlay_would_fire = False`
  - 本轮未重启 `web` / `bot`，原因是：
    - `a112d33` 仅引入 research scaffold、`pyarrow` 和 attribution notes
    - 不涉及新的 live recommendation/runtime code path
    - 当前 runtime health 正常
- **当前归类**：research only（research pool admitted; modeling blocked on data feasibility）
- **来源**：`research/strategies/Large-Cap Equity Option Income Overlay/Large-Cap Equity Option Income Overlay.md`；Quant 评估，2026-05-03

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
