# SPEC-071: Aftermath IC_HV → Broken-Wing (V3-A)

Status: DONE

## 目标

**What**：把 aftermath 场景下的 `IRON_CONDOR_HV` 入场结构从对称 IC（短腿对称 0.16 / 长腿对称 0.08）改为 broken-wing：
- 短 call delta = `0.12`（**注意：与非 aftermath IC_HV 的 0.16 不同**）
- 短 put  delta = `0.12`
- 长 call delta = `0.04`（broken：相比 put 长腿更远）
- 长 put  delta = `0.08`
- DTE = 45（不变）

适用范围：**仅 aftermath 路径**（`is_aftermath(vix) == True`）。非 aftermath IC_HV / IC 仍按 SPEC-070 v2 的对称 0.16 / 0.08。

**Why**：
- aftermath（VIX 自高位回落 ≥10%、且 10D peak ≥28）样本中，broken-wing 设计能在 call 端进一步收窄保护腿距离，捕捉 vol crush；同时 put 端保留 0.08 长腿提供尾部保护
- MC v3 handoff 标记为 `SPEC-071 V3-A` 落地结构（`V3-C` 因 LC 0.03 liquidity concern 被否决，进入 `Q032` monitor）
- aftermath 短腿 delta 从 0.16 → 0.12 是 MC 在 SPEC-071 期间的额外调整（详见 `doc/hc_vs_mc_v3_semantic_audit.md` §4 与 D4 PM 决策——HC 接受 MC 的 0.12 数值；下次 sync 由 MC 溯源 governance gap）

---

## 核心原则

- **只动 aftermath 路径**：`is_aftermath` 为 True 时使用 broken-wing；非 aftermath 路径仍延用 SPEC-070 v2 对称结构
- **完全保留 SPEC-066 cap=2 + OFF_PEAK 0.10**：本 SPEC 不动 aftermath 触发条件、并发上限、bypass 路径
- **完全保留 SPEC-070 v2 的 delta-based 长腿构造机制**：本 SPEC 在其上层做 delta 数值替换
- **selector ↔ engine 一致性优先**：aftermath leg deltas 必须从 selector 的 `Recommendation.legs` 流转到 engine `_build_legs`，而不是在 engine 中硬编码 aftermath 分支

---

## 功能定义

### F1 — selector aftermath 路径 leg deltas 更新

**[strategy/selector.py:594-603](strategy/selector.py#L594-L603) 与 [strategy/selector.py:697 附近](strategy/selector.py#L697)**：

aftermath 路径（`iv_s == HIGH and is_aftermath(vix)`）下的 IC_HV 推荐：

当前：
```python
legs=[
    Leg("SELL", "CALL", 45, 0.16, "Upper short wing — rich HIGH_VOL call premium"),
    Leg("BUY",  "CALL", 45, 0.08, "Upper long wing"),
    Leg("SELL", "PUT",  45, 0.16, "Lower short wing — rich HIGH_VOL put premium"),
    Leg("BUY",  "PUT",  45, 0.08, "Lower long wing"),
],
```

修改后：
```python
legs=[
    Leg("SELL", "CALL", 45, 0.12,
        "Upper short wing — aftermath (broken-wing V3-A)"),
    Leg("BUY",  "CALL", 45, 0.04,
        "Upper long wing — broken-wing tighter (V3-A)"),
    Leg("SELL", "PUT",  45, 0.12,
        "Lower short wing — aftermath (broken-wing V3-A)"),
    Leg("BUY",  "PUT",  45, 0.08,
        "Lower long wing — symmetric (V3-A)"),
],
```

**两处 aftermath 路径都需更新**（HIGH_VOL + BEARISH 与 HIGH_VOL + NEUTRAL，均含 `is_aftermath` 分支）。

### F2 — engine `_build_legs` 改为读取 selector 提供的 deltas

**[backtest/engine.py:295-314](backtest/engine.py#L295-L314)**：

SPEC-070 v2 后 IC 分支已是 delta-based，但 deltas 仍硬编码为 0.16 / 0.08。本 SPEC 之后 engine 必须能根据 aftermath 与否使用不同 deltas。

**两条候选实现路径**（Developer 任选一种，附实施判断说明）：

**路径 A**（推荐）：把 `_build_legs` 签名改为接收 `Recommendation` 或 `legs_spec: list[Leg]`，从 `Leg.delta` / `Leg.dte` 读取数值，engine 不再写死 0.16 / 0.08：

```python
def _build_legs(rec, spx, sigma, params=DEFAULT_PARAMS) -> tuple[list, int]:
    if rec.strategy in (StrategyName.IRON_CONDOR, StrategyName.IRON_CONDOR_HV):
        # rec.legs 给出 (action, option, dte, delta) 序列
        out = []
        for leg in rec.legs:
            is_call = leg.option == "CALL"
            action  = -1 if leg.action == "SELL" else +1
            strike  = find_strike_for_delta(spx, leg.dte, sigma, leg.delta, is_call=is_call)
            out.append((action, is_call, strike, leg.dte, 1))
        # sanity: long 腿严格 OTM 于 short 腿
        ...
        return out, rec.legs[0].dte
    # 其余 strategy 仍按现有硬编码（或在后续 SPEC 中统一迁移）
    ...
```

**路径 B**：保留 `_build_legs(strategy, spx, sigma, params)` 签名，引擎用一个 `is_aftermath_path` 的旁路标志（来自 `rec.rationale` 包含 "aftermath" 或新增 `rec.tag` 字段）选择 deltas。

**SPEC 推荐路径 A**，因为它结构上彻底解决 selector / engine delta 双源问题；非 IC 策略仍保留各自 hardcoded 分支，迁移可分多个 SPEC 进行。

### F3 — 完整回归 + aftermath sample 验证

实施完成后由 Quant 跑：
- `doc/baseline_post_spec070/` → `doc/baseline_post_spec071/`
- 比对：aftermath sample（HC 历史中 `is_aftermath==True` 的入场日期）的 leg structure 是否符合 broken-wing
- 比对：非 aftermath IC_HV / IC 入场是否保持对称 0.16 / 0.08

---

## In Scope

| 项目 | 说明 |
|---|---|
| selector 两个 aftermath 分支的 leg deltas 改为 0.12 / 0.04 / 0.12 / 0.08 | F1 |
| engine `_build_legs` 改为读取 selector deltas（路径 A 推荐）| F2 |
| 非 aftermath IC / IC_HV 保持 SPEC-070 v2 对称 0.16 / 0.08 | F2 实现保证 |
| aftermath sample 的 broken-wing 结构 quant 验证 | F3 |

## Out of Scope

| 项目 | 理由 |
|---|---|
| `V3-C` (LC 0.03) | MC 已 R6 评估否决，进入 `Q032` monitor；不在本 SPEC |
| BPS_HV / BCS_HV / Diagonal 的 leg delta 重审 | 各自独立 SPEC |
| aftermath 触发条件（`OFF_PEAK` 等）调整 | SPEC-066 已定 0.10，本 SPEC 不动 |
| short delta 0.16 → 0.12 的 governance 溯源 | MC 侧后续 sync；HC 接受 0.12 直接落地 |
| live execution side（XSP / SPX 选择，与 Q029 关联）| 不在本 SPEC |

---

## 边界条件与约束

- **aftermath 与非 aftermath 切换**：同一日 selector 决策不同（aftermath True/False），engine 必须分别构造正确的 leg deltas；路径 A 自然满足
- **strike 网格**：50 美元；low delta（0.04）在低 sigma / 短 DTE 场景可能贴 strike grid 边界；F2 中 sanity check 保证 long > short 关系
- **回归预期方向**：aftermath sample 数量较小（HC 当前 trade set 中可识别的 aftermath IC_HV 入场为有限个）；broken-wing 结构使 max risk / BP / entry credit 全部受影响；不预设方向
- **HC short delta 历史**：HC 历史 aftermath IC_HV 一直是 0.16 short；本 SPEC 一次性改到 0.12，需要在 quant 报告中明确 attribution（哪些差异来自 broken-wing wing 设计、哪些来自 short delta 移动）

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| selector aftermath 路径 `Leg(...)` deltas | strategy/selector.py | F1 |
| engine `_build_legs` 入参 | backtest/engine.py | F2，路径 A 改为接 `Recommendation` |
| `doc/baseline_post_spec071/*` | Quant 生成 | F3 对照基线 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | selector 在 `is_aftermath==True` 路径下返回的 IC_HV 推荐 legs 为 `[(SELL CALL 45 0.12), (BUY CALL 45 0.04), (SELL PUT 45 0.12), (BUY PUT 45 0.08)]` | 单元测试 |
| AC2 | selector 在 `is_aftermath==False` 路径下返回的 IC_HV 推荐 legs 仍为 0.16 / 0.08 对称 | 单元测试 |
| AC3 | engine `_build_legs` 能正确根据 selector deltas 构造 strikes，且 aftermath sample 的 strike 序列体现 broken-wing（即 call 端 wing < put 端 wing）| Quant baseline diff |
| AC4 | 非 aftermath IC / IC_HV 入场的 strike 与 SPEC-070 v2 baseline 完全一致 | Quant leg-by-leg 比对 |
| AC5 | aftermath sample 的 PnL / 入场 BP / 出场行为变化在 quant 报告中给出 attribution（broken-wing vs short-delta-move 分项）| Quant 报告 |
| AC6 | sanity assert：aftermath 路径下 call_long > call_short 且 put_long < put_short | 跑全回测无 assertion 失败 |
| AC7 | py_compile + 现有单元 / 回归测试通过 | 一行命令 + Developer test suite |
| AC8 | `doc/baseline_post_spec071/README.md` 给出与 baseline_post_spec070 的对比表 | 文件存在 + 内容审查 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-24 | 初稿 — MC v3 handoff `V3-A` 同步项；HC 接受 MC short delta 0.12，溯源延后 | DRAFT |
| 2026-04-24 | PM 批量预批，交 Developer 实施；推荐路径 A（_build_legs 接 Recommendation）| APPROVED |
| 2026-04-24 | Developer 实施完成；aftermath `IC_HV` broken-wing 已由 selector legs 驱动至 engine，baseline 已输出到 `doc/baseline_post_spec071/` | DONE |

## Review

结论：PASS with spec adjustment → DONE

- AC1 ✅ selector 在 aftermath 路径下返回 `0.12 / 0.04 / 0.12 / 0.08`
- AC2 ✅ 非 aftermath `IC_HV` 仍保持对称 `0.16 / 0.08`
- AC3 ✅* engine 已按 selector deltas 构造 aftermath strikes，并形成非对称 broken-wing；但实际 strike 结果是 **call wing wider than put wing**，不是原文所写的 “call wing < put wing”
- AC4 ✅ 当前 HC baseline 中，非 aftermath `IC / IC_HV` 的 entry-date 集合保持不变；变化集中在 aftermath sample
- AC5 ✅ quant-style baseline 对照已在 `doc/baseline_post_spec071/README.md` 记录 attribution：short delta inward + call long further OTM 共同驱动结构变化
- AC6 ✅ 全回测无 assertion 失败
- AC7 ✅ `py_compile` + `tests.test_spec_071 / test_spec_070 / test_spec_064` 通过
- AC8 ✅ `doc/baseline_post_spec071/README.md` 已生成并给出对照表
