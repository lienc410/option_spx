# SPX Options Strategy — Strategy Design Status
**Date: 2026-04-10（最终版，含 SPEC-048~060）| 适用于重建系统理解的完整策略文档**

*承接 `strategy_status_2026-04-05.md`。本版（最终版）累计变更：*
- *SPEC-048~055（早版）：IVP 多窗口、DIAGONAL 三道守护门、BCS_HV ivp63 拦截、regime decay size-up 修正、local_spike tag*
- *SPEC-055b：local_spike → DIAGONAL Full size-up*
- *SPEC-056：全历史矩阵分析工具（disable_entry_gates）*
- *SPEC-056c：撤销 DIAGONAL both_high 守护门*
- *SPEC-057：强制入场矩阵回测（force_strategy）*
- *SPEC-058：NORMAL+HIGH|BEARISH/NEUTRAL IVP≥50 门撤销，允许 IC 入场*
- *SPEC-059：Block Bootstrap 置信区间工具*
- *SPEC-060：三处路由修订（IC_HV 替换 BCS_HV；IC_HV 替换 BPS_HV；NORMAL+HIGH+BULLISH → REDUCE_WAIT）*

*策略核心结构（参数、基础框架）与 strategy_status_2026-04-05.md 一致，以下重点记录本轮全部变更。*

---

## 1–2. 系统定位 / 历史回测基准（无变更）

见 `strategy_status_2026-04-05.md` §1–2。

---

## 3. 信号体系（新增 IVP 多时间窗口）

### 3.1–3.3（无变更）

见 `strategy_status_2026-04-05.md` §2.1–2.3。

### 3.4 IVP 多时间窗口字段（SPEC-048 新增）

`IVSnapshot` 新增字段：

| 字段 | 说明 |
|------|------|
| `ivp63` | 过去 63 交易日中 VIX 低于今日的百分比（0–100） |
| `ivp252` | 过去 252 交易日中 VIX 低于今日的百分比（等于原 `iv_percentile`，重命名/复用）|

**IVP 四象限分类**：

| 象限 | ivp63 | ivp252 | 含义 | 对 DIAGONAL 影响 |
|------|-------|--------|------|-----------------|
| 双低 | < 50 | < 50 | 正常低波动 | 最佳入场环境 |
| regime decay | < 50 | ≥ 50 | 长期高压，近期降温 | 正 alpha（DIAGONAL size-up，F004）|
| local spike | ≥ 50 | < 50 | 近期 vol spike，长期基准不高 | 正 alpha（n=12，谨慎，SPEC-055 tag only）|
| both-high | ≥ 50 | ≥ 50 | 近期和长期均处于高压 | 负 alpha（n=8，avg −$2,556，SPEC-054 拦截）|

**常量**：
```python
REGIME_DECAY_IVP63_MAX  = 50
REGIME_DECAY_IVP252_MIN = 50
LOCAL_SPIKE_IVP63_MIN   = 50
LOCAL_SPIKE_IVP252_MAX  = 50
```

---

## 4. 决策矩阵（更新：LOW_VOL + BULLISH 分支 / HIGH_VOL + BEARISH 分支）

### LOW_VOL + BULLISH（SPEC-049/051/054 新增三道守护门）

```
LOW_VOL + BULLISH 执行顺序：
─────────────────────────────────────────────────
  Gate 1 (SPEC-049): ivp252 ∈ [30, 50] → REDUCE_WAIT
                     (长期 vol 过渡区间，DIAGONAL 优势减弱)

  Gate 2 (SPEC-051): iv_s == HIGH → REDUCE_WAIT
                     (LOW_VOL regime 中 vol expansion 信号)

  Gate 3 (SPEC-054): ivp63 ≥ 50 AND ivp252 ≥ 50 → REDUCE_WAIT
                     (both-high，DIAGONAL 尾部风险过高)

  通过全部门 → BULL_CALL_DIAGONAL（SPX 90/45 DTE）
─────────────────────────────────────────────────
```

### HIGH_VOL + BEARISH（SPEC-052 新增门）

```
HIGH_VOL + BEARISH 执行顺序：
─────────────────────────────────────────────────
  现有门 1: backwardation → REDUCE_WAIT
  现有门 2: VIX_RISING → REDUCE_WAIT
  Gate 3 (SPEC-052): ivp63 ≥ 70 → REDUCE_WAIT
                     (VIX 63 天高位，均值回归风险最高)
  通过全部门 → BEAR_CALL_SPREAD_HV
─────────────────────────────────────────────────
```

其余决策矩阵条目（NORMAL 各分支、HIGH_VOL BULLISH/NEUTRAL、EXTREME_VOL）无变更，见 `strategy_status_2026-04-05.md` §3。

---

## 5. 策略参数（无变更）

`StrategyParams` 25 个字段不变，见 `strategy_status_2026-04-05.md` §5。

> 注：SPEC-048~055 新增的 IVP 阈值常量为 code constants，不属于 `StrategyParams`，不需要 PARAM_MASTER 更新。

---

## 6. 仓位 Sizing（SPEC-053 修正 regime decay size-up）

### 6.1 原有两档（无变更）

```
Full size  — IV favors selling AND VIX trend flat/falling
Half size  — VIX rising OR signals mixed OR HIGH_VOL regime
```

### 6.2 regime decay size-up（SPEC-048/053）

| 条件 | 策略 | 变化 |
|------|------|------|
| regime_decay = True（ivp63 < 50 AND ivp252 ≥ 50）| BULL_CALL_DIAGONAL | HALF → FULL |
| regime_decay = True | BPS / BPS_HV / BCS_HV | **无变化**（SPEC-053 修正，F004 研究驳回）|

**实验依据（F004）**：
- DIAGONAL + regime decay：Sharpe +3.56
- BPS：Sharpe −0.87 | BPS_HV：Sharpe −1.12 | BCS_HV：Sharpe −2.84

---

## 7. `Recommendation` 新增字段（SPEC-055）

```python
local_spike: bool = False
    # True 当 ivp63 ≥ 50 AND ivp252 < 50（近期 vol spike，长期基准不高）
    # 诊断 tag only，不影响 size tier，不影响策略选择
    # UI: Decision Strip 灰蓝色注释
```

**SPEC-055b 前置条件**：local_spike DIAGONAL 真实交易 n ≥ 25 笔后，PM 决定是否重评 size-up（当前 n=0，Q010 追踪）。

---

## 8. 研究工具新增（SPEC-050）

| 工具 | 位置 | 用途 |
|------|------|------|
| `run_event_study.py` | `backtest/` | Non-overlapping event study，固定持有期收益分析 |
| `run_event_study_analysis.py` | `backtest/` | Event study 统计分析（n / avg_pnl / win_rate / Sharpe）|
| `run_ivp_regime_audit.py` | `backtest/` | IVP 四象限回测（F004–F006 数据来源）|
| `run_matrix_audit.py` | `backtest/` | 策略矩阵逐格 IVP 分析（F007 数据来源）|

**关键研究结论（event study 基于 n=89）：**
- DIAGONAL 是唯一有入场信号 alpha 的策略（F002）
- IC 的 alpha 完全来自 exit timing，与入场信号无关（F003）

---

## 4. 决策矩阵变更汇总（SPEC-055b / 056c / 058 / 060）

### LOW_VOL + BULLISH（最终态）

```
LOW_VOL + BULLISH 执行顺序：
─────────────────────────────────────────────────
  Gate 1 (SPEC-049): ivp252 ∈ [30, 50] → REDUCE_WAIT
  Gate 2 (SPEC-051): iv_s == HIGH → REDUCE_WAIT
  ✗ Gate 3 (SPEC-054 → SPEC-056c 撤销): both-high 门已删除
  通过全部门 → BULL_CALL_DIAGONAL

  Size-up 规则（SPEC-048/053/055b）：
    regime_decay (ivp63 < 50 AND ivp252 ≥ 50) → FULL
    local_spike  (ivp63 ≥ 50 AND ivp252 < 50) → FULL  ← SPEC-055b 新增
    其余 → HALF
─────────────────────────────────────────────────
```

### HIGH_VOL + BEARISH（最终态，SPEC-052/060）

```
HIGH_VOL + BEARISH 执行顺序：
─────────────────────────────────────────────────
  门 1: backwardation → REDUCE_WAIT
  门 2: VIX_RISING → REDUCE_WAIT
  门 3 (SPEC-052): ivp63 ≥ 70 → REDUCE_WAIT
  IV 分支 (SPEC-060 Change 1): iv_s == HIGH → IRON_CONDOR_HV
  其余 → BEAR_CALL_SPREAD_HV
─────────────────────────────────────────────────
```

### HIGH_VOL + BULLISH（最终态，SPEC-060 Change 2）

```
HIGH_VOL + BULLISH 执行顺序：
─────────────────────────────────────────────────
  门 1: backwardation → REDUCE_WAIT
  门 2: VIX_RISING → REDUCE_WAIT
  IV 分支 (SPEC-060 Change 2): iv_s == NEUTRAL → IRON_CONDOR_HV
  其余 → BULL_PUT_SPREAD_HV
─────────────────────────────────────────────────
```

### NORMAL + IV_HIGH（最终态，SPEC-058/060）

```
NORMAL + IV_HIGH + BEARISH:
  VIX_RISING → REDUCE_WAIT
  ✗ IVP≥50 门已撤销 (SPEC-058)
  → IRON_CONDOR

NORMAL + IV_HIGH + NEUTRAL:
  VIX_RISING → REDUCE_WAIT
  ✗ IVP>50 门已撤销 (SPEC-058)
  → IRON_CONDOR

NORMAL + IV_HIGH + BULLISH:
  ✗ BPS 入场 + IVP 门全部删除 (SPEC-060 Change 3)
  → REDUCE_WAIT（无条件）
```

---

## 9. SPEC 执行状态（截至 2026-04-10，最终版）

### 已完成（DONE）

包含 `strategy_status_2026-04-05.md` 中的全部 DONE 项，加上：

| SPEC | 主题 | 状态说明 |
|------|------|---------|
| SPEC-048 | IVP Multi-Horizon Fields + Regime Decay | DONE（含 SPEC-053 修正） |
| SPEC-049 | DIAGONAL Gate: ivp252 过渡区间 | DONE |
| SPEC-050 | Non-Overlapping Event Study Tool | DONE |
| SPEC-051 | DIAGONAL Gate: IV=HIGH 拦截 | DONE |
| SPEC-052 | BCS_HV Gate: ivp63 ≥ 70 拦截 | DONE |
| SPEC-053 | Regime Decay Size-Up → DIAGONAL Only | DONE |
| SPEC-054 | DIAGONAL Gate: both-high 拦截 | DONE（后被 SPEC-056c 撤销）|
| SPEC-055 | local_spike 诊断 Tag | DONE |
| SPEC-055b | local_spike → DIAGONAL Full size-up | DONE |
| SPEC-056 | 全历史矩阵分析工具（disable_entry_gates）| DONE |
| SPEC-056c | 撤销 DIAGONAL both_high 守护门 | DONE |
| SPEC-057 | 全历史强制入场矩阵回测（force_strategy）| DONE |
| SPEC-058 | NORMAL+HIGH|BEARISH/NEUTRAL IVP≥50 门撤销 | DONE |
| SPEC-059 | Block Bootstrap 置信区间工具 | DONE |
| SPEC-060 | 三处路由修订（IC_HV×2 + REDUCE_WAIT）| DONE |

### 待实现（APPROVED）

| SPEC | 主题 | 说明 |
|------|------|------|
| SPEC-044 | Delta Deviation Display in Open Modal | web/server.py + index.html |

---

## 10. 回测基准（含全部修订，截至 2026-04-10）

| 指标 | 数值 |
|------|------|
| 年化收益率 | **8.2%** |
| 最大回撤 | **-13.1%** |
| Sharpe | **1.33** |
| Sortino | 1.05 |
| Calmar | 0.63 |
| 盈利月份 | 61.1% |
| 总笔数 | 310 |
| 胜率 | 70.3% |
| 总 PnL (2000–2026) | $349,785 |

与 Long SPY 基准（同期年化 6.1%，MaxDD ~-55%）相比：超额收益 +2.1%，风险大幅降低。

---

## 11. 开放问题（截至 2026-04-10，最终版）

| 编号 | 状态 | 内容 |
|------|------|------|
| Q009 | blocked | Schwab Developer Portal 批准等待中 |
| Q002 | open | Shock active mode 待 Phase B 验证 |
| Q010 | closed | local_spike size-up 已由 SPEC-055b 实施（无需等真实 n≥25）|
| Q011 | open | regime decay DIAGONAL 样本小（回测 n≈8），需真实交易验证 |
| Q003 | open | L3 Hedge v2 实盘实现 |
| Q004 | open | `vix_accel_1d` L4 fast-path |
| Q005 | open | 多仓 trim 精细化 |

---

## 11. 技术债 / 已知限制（无变化）

见 `strategy_status_2026-04-05.md`。
