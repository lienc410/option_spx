# SPEC-060: 三处路由修订（SPEC-059 Bootstrap 矩阵结论）

## 目标

**What**：基于 SPEC-059 bootstrap 矩阵结论，修订三处策略路由：
1. `HIGH_VOL|HIGH|BEARISH`：BCS_HV → IC_HV
2. `HIGH_VOL|NEUTRAL|BULLISH`：BPS_HV → IC_HV
3. `NORMAL|HIGH|BULLISH`：BPS → REDUCE_WAIT

**Why**：
- Change 1：IC_HV $937 ✓ vs BCS_HV $465 ✓，两者均显著，IC_HV 高出 $472；HIGH_VOL+HIGH_IV+BEARISH 时双边 premium 丰厚，IC_HV 优于单向 BCS_HV
- Change 2：BPS_HV $100（不显著）vs IC_HV n=4（LOW_N）vs IC $1,837 ✓（n=11）；IC 是 HIGH_VOL|NEUTRAL|BULLISH 唯一有统计 alpha 的策略，路由改为 IC_HV（HIGH_VOL 制式）
- Change 3：BPS avg −$299（不显著）；BCS_HV CI [$755, $1,044] 是 n=10/block=5 的 bootstrap 退化伪信号；无充分证据支持任何入场策略，选择拦截

## 实施方式

Fast Path（单文件 `strategy/selector.py`，三处独立修改，各 ≤ 10 行，无新函数）

---

## 变更 1：HIGH_VOL + BEARISH — 新增 IV=HIGH 子分支 → IC_HV

在 HIGH_VOL + BEARISH 路径，现有 BCS_HV 入场之前（VIX_RISING 和 ivp63 门之后），新增：

```python
# SPEC-060: HIGH_VOL + BEARISH + IV=HIGH → IC_HV
# Bootstrap: IC_HV $937 ✓ vs BCS_HV $465 ✓; double-sided premium dominates
if iv_s == IVSignal.HIGH:
    action = get_position_action(...)  # IC_HV
    return _build_recommendation(StrategyName.IRON_CONDOR_HV, ...)
```

IV=HIGH 条件：保持原有 VIX_RISING 门和 ivp63 门在前，仅在通过这两道门后才做 IV 信号分支。

## 变更 2：HIGH_VOL + BULLISH — 新增 IV=NEUTRAL 子分支 → IC_HV

在 HIGH_VOL + BULLISH（backwardation 和 VIX_RISING 门之后），现有 BPS_HV 入场之前，新增：

```python
# SPEC-060: HIGH_VOL + BULLISH + IV=NEUTRAL → IC_HV
# Bootstrap: IC $1,837 ✓ (n=11) vs BPS_HV $100 不显著
if iv_s == IVSignal.NEUTRAL:
    action = get_position_action(...)  # IC_HV
    return _build_recommendation(StrategyName.IRON_CONDOR_HV, ...)
```

## 变更 3：NORMAL + IV_HIGH + BULLISH — 全路径改为 REDUCE_WAIT

将现有路径（守护门 → BPS 入场）完全替换为 REDUCE_WAIT：
- 删除 BPS 入场代码块（约 20 行）
- 替换为 REDUCE_WAIT（保留 backwardation 和 VIX_RISING 两道守护门的注释逻辑，但出口统一为 REDUCE_WAIT）
- 理由：BPS avg −$299 不显著；无充分证据支持任何入场

---

## 验收标准

- AC1. HIGH_VOL + BEARISH + IV=HIGH + VIX_FLAT → IRON_CONDOR_HV
- AC2. HIGH_VOL + BEARISH + IV=HIGH + VIX_RISING → 仍返回 REDUCE_WAIT（VIX_RISING 门优先）
- AC3. HIGH_VOL + BEARISH + IV=NEUTRAL + VIX_FLAT → 仍返回 BEAR_CALL_SPREAD_HV（原路由不变）
- AC4. HIGH_VOL + BULLISH + IV=NEUTRAL + VIX_FLAT → IRON_CONDOR_HV
- AC5. HIGH_VOL + BULLISH + IV=HIGH + VIX_FLAT → 仍返回 BULL_PUT_SPREAD_HV（IV=HIGH 不在 Change 2 范围）
- AC6. NORMAL + IV_HIGH + BULLISH → REDUCE_WAIT（无论 IVP 高低）

## Review
- 结论：PASS
- Change 1（HIGH_VOL+BEARISH+IV=HIGH→IC_HV）：`selector.py` HIGH_VOL+BEARISH 路径新增 `if iv_s == IVSignal.HIGH` 子分支，位于 VIX_RISING 门和 ivp63 门之后，BCS_HV 返回之前；AC1/AC2/AC3 ✓
- Change 2（HIGH_VOL+BULLISH+IV=NEUTRAL→IC_HV）：同理在 backwardation 和 VIX_RISING 门之后，BPS_HV 返回之前插入 `if iv_s == IVSignal.NEUTRAL` 子分支；AC4/AC5 ✓
- Change 3（NORMAL+HIGH+BULLISH→REDUCE_WAIT）：删除 IVP≥50 gate 和 BPS 入场代码块（共约25行），替换为单一 REDUCE_WAIT 返回，保留 backwardation/VIX_RISING 两道守护门；AC6 IVP=30 和 IVP=65 均返回 REDUCE_WAIT ✓
- 受影响测试已更新：`test_t10_high_vol_bearish_ivp63_65_keeps_bcs_hv` → `test_t10_high_vol_bearish_iv_high_routes_ic_hv`（期望 IC_HV），`test_high_vol_bearish_stable_still_uses_bear_call_spread_hv` → `test_high_vol_bearish_iv_high_routes_iron_condor_hv`（期望 IC_HV）
- 全套测试：91/91 通过（4 个 import error 为既有 flask/依赖缺失，与本 SPEC 无关）

---

Status: DONE
