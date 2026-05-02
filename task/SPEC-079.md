# SPEC-079: BCD Comfortable Top Entry Filter (`bcd_comfort_filter_mode`)

Status: DONE (2026-05-02; F1-F6 全部交付 + AC1-AC8 PASS)

## 目标

**What**：为 Bull Call Diagonal (BCD) 入场加一个 "comfortable top" 过滤层。当市场处于 VIX 极低、SPX 已从近期高点小幅回落、同时仍高于 MA50 的组合态（risk_score = 3）时，将 BCD 入场切换为 `REDUCE_WAIT`，避免在历史上 BCD 亏损最大的入场环境里开仓。

**Why**：
- Q038 walk-forward 验证：`1999–2018` IS 学到的过滤规则，在 `2024–2025` 的 3 个 OOS BCD 大亏事件上完全命中（10/10）
- MC `SPEC-079 DONE`（2026-04-29）；HC 需复现
- 该 filter 与 `SPEC-080` (BCD stop tightening) 共同组成 PM 选定的 **Path C**；二者依赖关系需同步落地，但 toggle 独立
- v1 有两个 blocking bug（numpy bool JSON 序列化静默失败 + log call 架构错位）；HC 应直接跳过 v1，按 v2 实现

---

## 核心原则

- **toggle 默认 `disabled`**：HC 端 PM 决定何时 flip 到 `shadow` 再到 `active`；不允许 Developer 私自设为 active
- **shadow 模式**：filter 检查但不阻断入场，所有 would-be block 写入 `data/bcd_filter_shadow.jsonl`；用于 PM 观察期
- **active 模式**：filter 检查 + 真实阻断，返回 `REDUCE_WAIT`
- **不改动 risk_score 阈值**：三条件 VIX ≤ 15 / dist_30d_high ≤ -1% / ma_gap_pct > 1.5pp 来自 Q038 research，不允许 post-hoc 调整

---

## 功能定义

### F1 — `TrendSnapshot` 增加 30 日高点距离字段

**[signals/trend.py](signals/trend.py)**：

```python
@dataclass
class TrendSnapshot:
    ...
    spx_30d_high:      Optional[float] = None   # trailing 30-day SPX high
    dist_30d_high_pct: Optional[float] = None   # (spx - spx_30d_high) / spx_30d_high, signed
```

在 `engine.py` 中构建 `TrendSnapshot` 的地方（每个 backtest 日期），增加计算：
```python
spx_30d_high = float(spx_window.iloc[-30:].max()) if len(spx_window) >= 30 else None
dist_30d_high_pct = (spx - spx_30d_high) / spx_30d_high if spx_30d_high else None
```

同样在 `scripts/export_backtest_trade_detail.py` 的 `_entry_recommendation` 函数中补充同一计算，确保 `TrendSnapshot` 构建一致。

### F2 — 新文件 `strategy/bcd_filter.py`

```python
"""BCD comfortable-top entry filter (SPEC-079)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
from pathlib import Path

# Risk-score thresholds (来自 Q038 walk-forward, 不允许修改)
_VIX_HIGH   = 15.0    # VIX ≤ this = complacent (condition 1)
_DIST_HIGH  = -0.01   # dist_30d_high_pct ≤ this = pulled back ≥1% from 30d high (condition 2)
_MA50_GAP   = 0.015   # ma_gap_pct > this = >1.5pp above MA50 (condition 3)

_SHADOW_LOG = Path("data/bcd_filter_shadow.jsonl")


def bcd_risk_score(vix: float, dist_30d_high_pct: Optional[float], ma_gap_pct: float) -> int:
    """Return risk score 0-3; score == 3 triggers filter."""
    score = 0
    if vix <= _VIX_HIGH:
        score += 1
    if dist_30d_high_pct is not None and dist_30d_high_pct <= _DIST_HIGH:
        score += 1
    if ma_gap_pct > _MA50_GAP:
        score += 1
    return score


def should_block_bcd(
    mode: str,          # "disabled" | "shadow" | "active"
    vix: float,
    dist_30d_high_pct: Optional[float],
    ma_gap_pct: float,
    date: str = "",
) -> bool:
    """
    Returns True if BCD entry should be blocked.
    Shadow mode: logs but returns False (does not actually block).
    Active mode: logs and returns True when risk_score == 3.
    """
    if mode == "disabled":
        return False
    score = bcd_risk_score(vix, dist_30d_high_pct, ma_gap_pct)
    would_block = (score == 3)
    if mode in ("shadow", "active"):
        _log_shadow(date, vix, dist_30d_high_pct, ma_gap_pct, score, would_block, mode)
    return would_block and (mode == "active")


def _log_shadow(date, vix, dist, gap, score, would_block, mode):
    try:
        _SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "date": date, "mode": mode, "vix": vix,
            "dist_30d_high_pct": dist, "ma_gap_pct": gap,
            "risk_score": score, "would_block": bool(would_block),
        }
        with _SHADOW_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass
```

### F3 — `StrategyParams` 增加 `bcd_comfort_filter_mode`

**[strategy/selector.py](strategy/selector.py)** StrategyParams dataclass：

```python
# BCD comfortable-top filter (SPEC-079)
bcd_comfort_filter_mode: str = "disabled"   # "disabled" | "shadow" | "active"
```

### F4 — `select_strategy` BCD 入场 wiring

**[strategy/selector.py](strategy/selector.py)** LOW_VOL + BULLISH BCD 分支（现有 Gate 2 SPEC-051 之后）：

```python
from strategy.bcd_filter import should_block_bcd

# 在 Gate 2 block 之后、_build_recommendation(BCD) 之前插入：
if should_block_bcd(
    params.bcd_comfort_filter_mode,
    vix=vix.vix,
    dist_30d_high_pct=trend.dist_30d_high_pct,
    ma_gap_pct=trend.ma_gap_pct,
    date=vix.date,
):
    return _reduce_wait(
        f"BCD comfortable-top filter (SPEC-079): risk_score=3 "
        f"(vix={vix.vix:.1f}, dist_30d={trend.dist_30d_high_pct:.3f}, "
        f"ma_gap={trend.ma_gap_pct:.3f})",
        vix, iv, trend, macro_warn,
        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
        params=params,
    )
```

### F5 — 生产 config 确认默认 `disabled`

**[web/server.py](web/server.py)** — 确认任何 production_config 里没有显式 override `bcd_comfort_filter_mode` 为其他值；如有，确保是 `"disabled"`。

### F6 — Unit test `tests/test_bcd_filter.py`

至少包含：
1. `test_risk_score_all_three()` — 三条件全满 → score=3
2. `test_risk_score_two_of_three()` — 任意两条满 → score=2，不阻断
3. `test_disabled_mode_never_blocks()` — mode="disabled" 无论 score → False
4. `test_shadow_mode_logs_but_not_blocks()` — mode="shadow"，score=3 → False（但写了 log）
5. `test_active_mode_blocks_on_score3()` — mode="active"，score=3 → True
6. `test_selector_returns_reduce_wait_when_active()` — 构造 vix/iv/trend snap 满足 score=3，params.bcd_comfort_filter_mode="active" → select_strategy 返回 REDUCE_WAIT

---

## In Scope

| 项目 | 说明 |
|---|---|
| F1 TrendSnapshot 字段 | 加 spx_30d_high + dist_30d_high_pct |
| F2 bcd_filter.py | should_block_bcd + shadow log |
| F3 StrategyParams | bcd_comfort_filter_mode 字段 |
| F4 selector wiring | BCD block logic |
| F5 生产 config 确认 | 确保 disabled |
| F6 unit test | 6 cases |

## Out of Scope

| 项目 | 理由 |
|---|---|
| risk_score 阈值调整 | Q038 locked，不允许 post-hoc 修改 |
| active/shadow toggle flip | PM 单独决定；Developer 不动 |
| BCD stop tightening | SPEC-080 范围 |
| Overlay-F / SPEC-075/076 | 独立 spec，Q036 canonical 分歧未解决 |

---

## 边界条件

- `dist_30d_high_pct = None`（数据不足，< 30 日历史）时 condition 2 视为不满足（不触发 filter）
- Shadow log 写入失败（权限/磁盘）应静默忽略，不影响主路径
- 测试时可用 `mock` 替换 `_log_shadow` 避免写磁盘

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `StrategyParams.bcd_comfort_filter_mode` 默认 `"disabled"` | grep |
| AC2 | `strategy/bcd_filter.py` 存在，`should_block_bcd` 可导入 | import |
| AC3 | mode="active" + score=3 → `select_strategy` 返回 `REDUCE_WAIT` | test case 6 |
| AC4 | mode="shadow" + score=3 → 不阻断入场 + 写 shadow log | test case 4 |
| AC5 | mode="disabled" → 永不阻断 | test case 3 |
| AC6 | `TrendSnapshot` 含 `dist_30d_high_pct` 字段 | grep |
| AC7 | `tests/test_bcd_filter.py` 所有 case PASS | pytest |
| AC8 | 现有 test suite 无回归 | pytest tests/ |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-02 | HC Quant 起草；基于 MC_Handoff_2026-05-01_v5.md + Q038 walk-forward 研究 F-26-04-29-1 | DRAFT |
| 2026-05-02 | PM 审批 → APPROVED；进入实施 | APPROVED |
| 2026-05-02 | F1-F6 全部落地（Codex 实施）：`TrendSnapshot` 加 `spx_30d_high` / `dist_30d_high_pct`；`strategy/bcd_filter.py` 新建；`StrategyParams.bcd_comfort_filter_mode="disabled"` 加入 `selector.py:127`；selector wiring at `selector.py:933`（Gate 2 后、`_build_recommendation` 前）；`scripts/export_backtest_trade_detail.py` 同步；`tests/test_bcd_filter.py` 6/6 PASS。3 条 pre-existing 失败（Gate 1 遗留，非本 spec 引入）已确认，全量 188 PASS / 3 pre-existing FAIL 无新增。AC3 live 验证：mode=active + score=3 → REDUCE_WAIT ✓；AC5 live 验证：mode=disabled → BCD ✓ | DONE |
