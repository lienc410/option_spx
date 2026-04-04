# 参数主表（PARAM_MASTER）

> 双端同步锚点。HC和MC的参数变更均以此文件为准。
> 冲突时：参数决策MC优先，代码实现HC权威。

最后完整同步：2026-04-04
HC版本：v1
MC版本：v0（待首次MC同步）

**当前推荐生产配置**：`overlay_mode=disabled`（待SPEC-020 RS-020-2完成后切换 `active`）

---

## § 1 VIX Regime 阈值

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| extreme_vix | 35.0 | — | HC | 2026-03-28 | active | baseline | VIX >= 此值 → EXTREME_VOL，暂停入场 |

---

## § 2 交易参数

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| high_vol_delta | 0.20 | — | HC | 2026-03-28 | active | baseline | HIGH_VOL BPS short leg delta |
| high_vol_dte | 35 | — | HC | 2026-03-28 | active | baseline | HIGH_VOL DTE |
| high_vol_size | 0.50 | — | HC | 2026-03-28 | active | baseline | HIGH_VOL position size（占normal比例）|
| normal_delta | 0.30 | — | HC | 2026-03-28 | active | baseline | NORMAL BPS short leg delta |
| normal_dte | 30 | — | HC | 2026-03-28 | active | baseline | NORMAL DTE |

---

## § 3 出场规则

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| profit_target | 0.50 | — | HC | 2026-03-28 | active | baseline | 达到max credit的50%时平仓 |
| stop_mult | 2.0 | — | HC | 2026-03-28 | active | baseline | stop loss = N倍credit收入 |
| min_hold_days | 10 | — | HC | 2026-03-28 | active | baseline | profit target最早触发天数 |

---

## § 4 BP利用率

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| bp_target_low_vol | 0.10 | — | HC | 2026-04-01 | active | SPEC-024 | LOW_VOL每笔BP目标（占账户）|
| bp_target_normal | 0.10 | — | HC | 2026-04-01 | active | SPEC-024 | NORMAL每笔BP目标 |
| bp_target_high_vol | 0.07 | — | HC | 2026-04-01 | active | SPEC-024 | HIGH_VOL每笔BP目标 |
| bp_ceiling_low_vol | 0.25 | — | HC | 2026-04-01 | active | SPEC-024 | LOW_VOL组合BP上限 |
| bp_ceiling_normal | 0.35 | — | HC | 2026-04-01 | active | SPEC-024 | NORMAL组合BP上限 |
| bp_ceiling_high_vol | 0.50 | — | HC | 2026-04-01 | active | SPEC-024 | HIGH_VOL组合BP上限 |
| initial_equity | 100000 | — | HC | 2026-04-01 | active | SPEC-024 | 回测初始净值 |

---

## § 5 组合规则

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| max_short_gamma_positions | 3 | — | HC | 2026-03-28 | active | SPEC-017 | 最大short-gamma仓位数 |
| spell_age_cap | 30 | — | HC | 2026-03-28 | active | SPEC-015 | Vol Spell Throttle：高波持续天数上限 |
| max_trades_per_spell | 2 | — | HC | 2026-03-28 | active | SPEC-015 | Vol Spell每次最多新增仓位数 |

---

## § 6 Shock Engine 参数（SPEC-025）

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| shock_mode | shadow | — | HC | 2026-04-01 | active | SPEC-025 | shadow=只记录；active=主动拦截 |
| shock_budget_core_normal | 0.0125 | — | HC | 2026-04-01 | active | SPEC-025 | Normal：core shock上限（占NAV）|
| shock_budget_core_hv | 0.0100 | — | HC | 2026-04-01 | active | SPEC-025 | HIGH_VOL：core shock上限 |
| shock_budget_incremental | 0.0040 | — | HC | 2026-04-01 | active | SPEC-025 | Normal：边际shock上限 |
| shock_budget_incremental_hv | 0.0030 | — | HC | 2026-04-01 | active | SPEC-025 | HIGH_VOL：边际shock上限 |
| shock_budget_bp_headroom | 0.15 | — | HC | 2026-04-01 | active | SPEC-025 | 任意regime：BP最低剩余比例 |

---

## § 7 Overlay 参数（SPEC-026）

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| overlay_mode | disabled | — | HC | 2026-04-01 | active | SPEC-026 | disabled/shadow/active；EXP-full推荐active但待RS-020-2 |
| overlay_freeze_accel | 0.15 | — | HC | 2026-04-01 | active | SPEC-026 | L1触发：3日加速度阈值 |
| overlay_freeze_vix | 30.0 | — | HC | 2026-04-01 | active | SPEC-026 | L1触发：VIX绝对值阈值 |
| overlay_trim_accel | 0.25 | — | HC | 2026-04-01 | active | SPEC-026 | L2触发：加速度（AND条件）|
| overlay_trim_shock | 0.01 | — | HC | 2026-04-01 | active | SPEC-026 | L2触发：book_core_shock（AND条件）|
| overlay_hedge_accel | 0.35 | — | HC | 2026-04-01 | active | SPEC-026 | L3触发：加速度（AND条件）|
| overlay_hedge_shock | 0.015 | — | HC | 2026-04-01 | active | SPEC-026 | L3触发：book_core_shock（AND条件）|
| overlay_emergency_vix | 40.0 | — | HC | 2026-04-01 | active | SPEC-026 | L4触发：VIX绝对值（OR条件）|
| overlay_emergency_shock | 0.025 | — | HC | 2026-04-01 | active | SPEC-026 | L4触发：book_core_shock（OR条件）|
| overlay_emergency_bp | 0.10 | — | HC | 2026-04-01 | active | SPEC-026 | L4触发：BP headroom下限（OR条件）|

---

## § 8 趋势信号参数（SPEC-020）

| 参数 | 当前值 | 上次值 | 更新环境 | 更新日期 | status | source SPEC | 说明 |
|------|--------|--------|----------|----------|--------|-------------|------|
| use_atr_trend | True | False | HC | 2026-04-02 | active | SPEC-020 | ATR-normalized entry gate（RS-020-2验证通过）|
| bearish_persistence_days | 1 | 3（实验值）| HC | 2026-04-02 | active | SPEC-020 | 1=legacy单日翻转（persistence filter RS-020-2驳回）|

---

## § 9 当前推荐生产配置

基于 SPEC-026 §35 实验结论（EXP-full 在全历史Sharpe 0.86，MaxDD -12.22%）：

| 参数 | 推荐值 | 当前代码值 | 差异说明 |
|------|--------|-----------|---------|
| overlay_mode | active | disabled | 待SPEC-020 RS-020-2完成后切换 |
| shock_mode | shadow | shadow | Phase B数据驱动决策后切换active |
| use_atr_trend | True | True | 已实施 |
| bearish_persistence_days | 1 | 1 | persistence filter驳回，保持legacy |

---

## 版本历史

| 版本 | 日期 | 环境 | 变更摘要 |
|------|------|------|----------|
| v1 | 2026-04-04 | HC | 初始化：25个参数，增加status和source SPEC字段，v3协议同步 |
