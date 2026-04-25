# HC vs MC v3 Semantic Audit — 2026-04-24

> Owner: Quant Researcher
> 用途：在 HC 进入复现实施前，先把 HC 当前代码现状 vs `sync/mc_to_hc/MC_Handoff_2026-04-24_v3.md` 声明的 MC-side `DONE` 状态做语义级对账。
> 输出：每条 MC v3 改动在 HC 端是 `match` / `gap (real)` / `gap (premise unverified)` / `n/a`，并给出 PM 拍板建议。
> 不在范围内：直接做实施、修改生产代码、补建 HC-side Spec 文件。

---

## 1. 对账总表

| 编号 | MC v3 声称的改动 | HC 现状（代码事实）| HC 对账结论 | 是否需要 HC 复现 |
|---|---|---|---|---|
| C1 | `AFTERMATH_OFF_PEAK_PCT = 0.10` | `strategy/selector.py:172` 中已为 `0.10`（SPEC-066 落地）| **match** | 无需，已落地 |
| C2 | `IC_HV_MAX_CONCURRENT = 2` | `backtest/engine.py:931-935` 已使用 `>= IC_HV_MAX_CONCURRENT` 分支 | **match** | 无需，已落地 |
| C3 | `hv_spell_trade_count` scalar → per-strategy dict（SPEC-068）| `engine.py:687, 1015, 1117` 仍是 scalar `int`，按 HV 总数累加 | **gap (premise unverified on HC)** | 见 §2 |
| C4 | `_build_legs` IC 长腿改为 delta-based（SPEC-070 v2）| `engine.py:295-307` 仍用 `wing = max(50, round(spx*0.015/50)*50)`、`call_long = call_short + wing` 等 wing-based 构造 | **gap (real)** | 是 |
| C5 | aftermath `IC_HV` 改为 broken-wing `LC 0.04 / LP 0.08`（SPEC-071）| selector `IRON_CONDOR_HV` legs 仍为 symmetric `short 0.16 / long 0.08`（line 815-822）；且 aftermath bypass 路径未对长腿做 broken-wing 调整 | **gap (real)** | 是 |
| C6 | `BEAR_CALL_DIAGONAL` 全库清除（SPEC-073）| `engine.py:363-373`、`strategy/selector.py` 等 8 个文件仍存在 | **gap (real, low risk)** | 是，但后置 |
| C7 | artifact `open_at_end` 字段（SPEC-069）| 未核查 — 属 artifact 层，对策略语义无影响 | **gap (artifact)** | 后置 |
| C8 | frontend dual-scale 显示（SPEC-072）| `MC-side DONE`，HC 仅做 deploy + smoke | **gap (frontend)** | 后置 |

---

## 2. SPEC-068 的"前提是否在 HC 成立"分析（C3 重点）

MC v3 的 SPEC-068 立项理由（参数变更 #3）：
> "`2026-03` 双峰 HV spell aggregate 计数会超过 `max_trades_per_spell = 2`，从而阻挡 aftermath `IC_HV` 第二笔"

### 2.1 HC 端的 throttle 实际行为

`engine.py:514`（`_block_hv_spell_entry`）：
```python
if hv_spell_trade_count >= params.max_trades_per_spell:   # 2
    return True
```

`engine.py:1015`：成功开仓后才递增 `hv_spell_trade_count += 1`。

按 HC 现行代码模拟 2026-03 时间线（仅考虑 HC 单仓位 + SPEC-066 cap=2）：

| 日期 | 事件 | 入场前 count | 是否被 spell throttle 阻挡 | 是否被 `_already_open` 阻挡 | 结果 |
|---|---|---|---|---|---|
| 2026-03-09 | IC_HV #1 候选 | 0 | 否（0 < 2）| 否（仓位 0 < cap 2）| 开仓 → count=1 |
| 2026-03-10 | IC_HV #2 候选 | 1 | 否（1 < 2）| 否（仓位 1 < cap 2）| 开仓 → count=2 |
| 2026-03-31..04-02 | 假想 IC_HV #3 候选 | 2 | **是**（2 ≥ 2）| 是（cap 2 已满）| 阻挡（双重阻挡）|

→ HC 的 SPEC-066 review 已经确认 2026-03-09 / 2026-03-10 两笔均成功捕获。spell throttle 在这条历史路径上**没有形成阻挡**。

### 2.2 为什么 MC 看到了阻挡？

最可能的原因：MC 已先做了 `Q022 单仓 → 多仓引擎重构`（MC v3 line 397-405 报为 2026-04-21 完成），HC 没有这次重构。在 MC 的多仓引擎下，spell 期间可能已经存在 **并发的 `BPS_HV` / `BCS_HV` 仓位**，这些其他 HV 策略也会让 `hv_spell_trade_count` 计数累加，从而在 IC_HV 第二笔到来前 count 已 ≥ 2，触发 throttle。

→ SPEC-068 的"per-strategy dict"修复直接对应这个跨策略累加问题，但**这个问题在 HC 当前代码下不会出现**，因为 HC 的非 IC_HV HV 策略仍然单槽位、且 SPEC-066 cap=2 已经独立约束 IC_HV。

### 2.3 结论与建议

- **HC 当前没有 SPEC-068 修复的必要触发场景**
- 但 SPEC-068 的"per-strategy 计数"在语义上是更干净的实现，且与未来若 HC 也走多仓引擎路线（Q022 等价物）兼容
- 建议给 PM 的两条路：
  - **路 A（推荐）**：HC 不复现 SPEC-068。在 `RESEARCH_LOG.md` 记录"HC 未复现，因前提不成立"，并列出未来 reopen 触发条件（HC 启动多仓引擎重构时）
  - **路 B**：HC 仍复现 SPEC-068，作为防御性对齐。代价：增加一次 engine 改动 + 测试，但行为不变（在 HC 环境下 per-strategy dict 与 scalar 的输出应等价）

---

## 3. SPEC-070 v2 的"语义错配是否真实存在"分析（C4 重点）

### 3.1 HC 当前 IC_HV 长腿构造（`backtest/engine.py:295-307`）

```python
if strategy in (StrategyName.IRON_CONDOR, StrategyName.IRON_CONDOR_HV):
    dte = 45
    call_short = find_strike_for_delta(spx, dte, sigma, 0.16, is_call=True)
    put_short  = find_strike_for_delta(spx, dte, sigma, 0.16, is_call=False)
    wing       = max(50, round(spx * 0.015 / 50) * 50)   # ~1.5% width, rounded to $50
    call_long  = call_short + wing                       # ← WING-BASED
    put_long   = put_short  - wing                       # ← WING-BASED
```

→ short 是 delta 查询，long 是固定 wing 偏移。

### 3.2 HC 当前 selector 长腿语义（`strategy/selector.py:815-822`）

```python
Leg("SELL", "CALL", 45, 0.16, "Upper short wing — HIGH_VOL premium"),
Leg("BUY",  "CALL", 45, 0.08, "Upper long wing"),
Leg("SELL", "PUT",  45, 0.16, "Lower short wing — HIGH_VOL premium"),
Leg("BUY",  "PUT",  45, 0.08, "Lower long wing"),
```

→ selector 明确写 long delta = 0.08（**delta-based 意图**）。

### 3.3 实际错配案例验证（high-SPX 环境）

假设 SPX = 6000、IV 适中：
- 1.5% wing = `max(50, round(6000*0.015/50)*50) = max(50, round(1.8)*50) = max(50, 2*50) = 100` → wing = 100 点
- `call_short` 在 delta 0.16 处约 6150
- `call_long` = 6150 + 100 = 6250
- 6250 处的实际 delta（45 DTE，VIX 22）远小于 0.08（应该在 0.04 左右）
- 也就是说：**selector 写 0.08，engine 实际给到约 0.04**

低 SPX 环境（如 SPX = 3000）：wing ≈ 50 点，`call_long` 很可能比 0.08 delta 更近 ATM，反向漂移。

→ 语义错配在 HC 上**真实存在**，与 MC F003 的判断一致（这是历史遗留约定不一致，不是 SPEC-070 v1 引入）。

> **2026-04-25 post-SPEC-070 v2 实测修正**：上述 §3.3 中"wing=100 处 long-call 实际 delta ≈ 0.04"是错误估计。SPEC-070 v2 实施后基线对照显示，在 SPX=6795.99 / sigma=0.255 / DTE=45 下，真实 δ0.08 long call = `8017`、long put = `5920`，明显比旧 wing-based 的 `7772 / 6092` **更远 OTM**。这意味着旧 wing=100 baseline 对应的有效 delta 大约是 `δ0.10–0.12`（而非 0.04），方向预设写反。语义错配仍真实存在，但**误差方向与量级**与本节原写法相反；总结的修复方向（engine 用 `find_strike_for_delta(..., 0.08)`）正确，已落地 SPEC-070 v2 commit `f69b840`。

### 3.4 结论与建议

- C4 是 **HC 必须修复的语义核心错配**
- 修复方向应与 MC SPEC-070 v2 一致：engine 改用 `find_strike_for_delta(... long_d, ...)`，把 selector 的 long delta（0.08）作为权威值
- 此项必须在 SPEC-071（broken-wing 长腿 0.04 / 0.08）之前完成，否则 broken-wing 的 LP=0.08 在 HC 下仍会被 wing 覆盖
- 需要 PM 决定是否在 HC 端补建 `task/SPEC-070_v2.md`（DRAFT → APPROVED），还是 PM 直接接受 MC 的 spec 文本作为 HC canonical

### 3.5 副作用提醒

- 修 C4 会**改变所有现有 IC / IC_HV 历史回测的长腿 strike**，因此会引发一次 trade-set 全量漂移
- 这与 SPEC-066 review 的 AC4 教训一致：trade-set 恒等不应作为 AC，应改为"selector 长腿 delta 与 engine 实际 strike 一致 ≤ 1 点 grid"这类语义级 AC
- 必须先跑全引擎对照，量化 PnL / Sharpe / MaxDD / 关键日期的影响

---

## 4. SPEC-071 的"现状是否真是 symmetric"分析（C5 重点）

### 4.1 HC 当前 IC_HV 形态

selector.py:815-822 的 legs：
- short call delta `0.16`，short put delta `0.16` → **对称 short**
- long call delta `0.08`，long put delta `0.08` → **对称 long（声称值）**
- 实际 strike：受 C4 错配影响，long 是 wing 偏移 → 实际 long delta 不严格等于 0.08，但仍**双侧对称**

→ HC 当前是 symmetric IC_HV（无论以 selector 声明还是 engine 实际为准）。

### 4.2 MC SPEC-071 的目标形态

- short call `0.12`，short put `0.12`（注意 short delta 也变化：0.16 → 0.12）
- long call `0.04`，long put `0.08`（broken-wing：call 侧更远 OTM）

### 4.3 不一致点

- HC short delta 是 `0.16`，MC 目标是 `0.12` — 这是 **MC v3 文档没有显式列为参数变更条目**的一项隐含改动（MC v3 §HC 指令 2 提到 "short call/put delta 保持 0.12 不变"，暗示 MC 端 short 早已是 0.12）
- 这意味着 **MC 在某次更早的改动中已经把 IC_HV short delta 从 0.16 调到 0.12**，但 v3 handoff 没有把这条单独列出
- 这是一个**潜在文档漂移**，需 PM 关注

### 4.4 结论与建议

- C5 是 HC 必须复现的策略语义核心
- **必须先解决 C4（delta-based 长腿），SPEC-071 才有意义**
- 建议 PM 拍板：
  1. 是否接受 MC 的"short delta 0.12"作为 HC canonical（追问 MC 哪一份 spec / handoff 引入了 0.16 → 0.12）
  2. 是否要求 HC 自跑 broken-wing 全引擎对照（MC `Q028 Phase 3` 的复现），还是直接接受 MC 结论
  3. SPEC-071 在 HC 端是单独的 spec 文件，还是把 MC 的 spec 直接落到 HC

---

## 5. 编号 / 治理冲突清单

| 项 | HC canonical | MC v3 | 建议处置 |
|---|---|---|---|
| `Q020` vs `Q021` | HC `Q020` = SPEC-066 alpha 归因（distinct second-peak）| MC `Q020` = SPEC-064 AC10 measurement gap；MC `Q021` = HC 的 `Q020` 内容 | 维持 HC `Q020` 为 canonical，记 MC 别名（`open_questions.md` 已落） |
| `Q022` 多仓引擎重构 | HC 无此编号 | MC 报告 2026-04-21 完成 | 不补建 HC-side 编号；以 SPEC 文件实施为准 |
| `Q023..Q031, Q033` 等 | HC 无 | MC 全部带入 | 不回填编号，仅把**结论**沉淀进 `RESEARCH_LOG.md` |
| MC SPEC-068/069/070 v2/071/072/073 的 HC-side 状态 | HC 无对应 spec 文件 | MC 标 `DONE` | **必须 PM 决定**：是补建 HC-side spec 走 APPROVED，还是 PM 直接接受 MC spec 文本作为 HC canonical |

---

## 6. 给 PM 的拍板清单（按依赖序）

| 序 | 决策 | 选项 | 默认建议 |
|---|---|---|---|
| D1 | C4（SPEC-070 v2 delta-based 长腿）是否在 HC 复现 | (a) 复现 / (b) 不复现 | **(a) 必须复现**——HC 端语义错配真实存在 |
| D2 | C3（SPEC-068 per-strategy spell throttle）是否在 HC 复现 | (a) 复现（防御性）/ (b) 不复现，记 reopen trigger | **(b) 不复现**——HC 当前前提不成立 |
| D3 | C5（SPEC-071 broken-wing）是否在 HC 复现 | (a) 复现 / (b) 不复现 | **(a) 复现**——但必须先 D1 |
| D4 | MC SPEC-071 的"short delta 0.12（vs HC 0.16）"是否被 PM 默认接受 | (a) 接受 / (b) 追问 MC 文档漂移 | **(b) 先追问**——v3 文档未显式列出 |
| D5 | C6（SPEC-073 BEAR_CALL_DIAGONAL 清理）是否在 HC 复现 | (a) 复现 / (b) 不做 | **(a) 复现**——0 行为变化、低风险 |
| D6 | HC 是否补建 SPEC-068/070v2/071/072/073 的 HC-side spec 文件 | (a) 全补建走 APPROVED / (b) PM 直接接受 MC spec 文本 | **(a) 补建**——保持治理一致性 |
| D7 | Q019 走 A / B / C | A / B / C | PM 自决，与本对账无关 |

---

## 7. 仍未由本审计回答的问题（留给后续）

1. MC 的 `Q022` 多仓引擎重构具体改了什么、HC 是否需要等价物 — 需要 MC 提供 `Q022` 的实施 diff 摘要
2. MC 何时把 `IC_HV short delta` 从 `0.16` 改到 `0.12` — 需要 MC 给出溯源 spec / commit
3. SPEC-072 deploy 会暴露 dual-scale UI，但当 HC 还未实施 Q029 双列 reporting 约定时，UI 上显示的 `live_scaled_est` 数据来源是否一致 — 需要 MC 给 SPEC-072 deploy handoff 的 prereq 清单

---

## 8. 本次对账的可信度

- C1 / C2：高（已读到代码，与 MC v3 一致）
- C3：高（前提分析），中（实施建议——依赖 PM 对未来多仓路线的判断）
- C4：高（错配真实，量化未做）
- C5：中-高（语义现状清晰；但 short delta 0.16 vs 0.12 漂移需要 MC 追溯）
- C6 / C7 / C8：高（直接观察）
- §5 编号冲突：高
- §6 拍板建议：中（依赖 PM 治理判断，非纯技术判断）
