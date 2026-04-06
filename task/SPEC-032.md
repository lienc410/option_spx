# SPEC-032: Frontend — Decision Strip & Risk Flag Bar

## 目标

**What**：在 Dashboard 顶部新增两个组件：
1. **Decision Strip**：一行摘要，直接回答"现在该做什么、为什么不能做、解锁条件是什么"
2. **Risk Flag Bar**：紧凑的风险状态行，显示所有当前激活的 guardrail / 风险标志

**Why**（来自 OAI 2nd quant review）：
当前 Dashboard 是 research-forward（先看信号再推断行动），
但交易员开盘时需要的是 action-forward（先看行动再看原因）。
信息都在，但层级不对。这两个组件重新排列优先级，不改变底层数据。

---

## 数据可用性分析

### 已在 `/api/recommendation` 中的字段

| 字段 | 用途 |
|------|------|
| `position_action` | OPEN / HOLD / WAIT / CLOSE_AND_OPEN / CLOSE_AND_WAIT |
| `strategy` | 当前推荐策略名称 |
| `guardrail_label` | 触发 guardrail 的原因（EXTREME VOL / BACKWARDATION 等） |
| `macro_warning` | bool，SPX below 200MA |
| `backwardation` | bool，VIX spot > VIX3M |
| `vix_snapshot.regime` | LOW / NORMAL / HIGH / EXTREME_VOL |
| `vix_snapshot.transition_warning` | bool，VIX 接近 regime 边界 |

### 需要后端新增的字段

| 字段 | 位置 | 说明 |
|------|------|------|
| `canonical_strategy` | Recommendation dataclass | 不考虑 guardrail 时 matrix 的原始推荐策略名 |
| `re_enable_hint` | Recommendation dataclass | guardrail 的解锁提示文字（selector.py 静态生成） |
| `overlay_mode` | Recommendation dataclass | 当前 overlay 模式（"disabled"/"shadow"/"active"） |
| `shock_mode` | Recommendation dataclass | 当前 shock 模式（"disabled"/"shadow"） |

---

## 功能定义

### F1 — Decision Strip

**位置**：Dashboard，Signal Strip 上方，Intraday Bar 下方（若 Intraday Bar 隐藏则紧贴 nav）

**形态**：单行横向 strip，背景 `var(--surface)`，高度约 42px

**显示逻辑：**

```
场景 A：无 guardrail，正常推荐
  ● OPEN  ·  Bull Put Spread  ·  [no blockers]

场景 B：有 guardrail（WAIT）
  ● WAIT  ·  Reduce / Wait
    Blocked by: EXTREME VOL
    Canonical: Bull Put Spread (High Vol)
    Re-enable: VIX below 35

场景 C：HOLD
  ● HOLD  ·  Bull Put Spread  ·  position open since 2026-03-15
```

**字段映射：**

| 显示项 | 数据来源 |
|--------|---------|
| Action pill（OPEN/HOLD/WAIT 等） | `position_action` |
| 策略名 | `strategy` |
| Blocked by | `guardrail_label`（非空时显示） |
| Canonical | `canonical_strategy`（与 strategy 不同时显示） |
| Re-enable | `re_enable_hint` |

**颜色规则：**
- OPEN → green pill
- HOLD → blue pill
- WAIT / CLOSE_AND_WAIT → orange pill
- CLOSE_AND_OPEN → gold pill

**边界：**
- guardrail_label 为空时，Blocked by / Canonical / Re-enable 行不显示
- canonical_strategy == strategy 时（无 override），Canonical 行不显示
- 推荐 API 加载中时，Strip 显示 skeleton placeholder

---

### F2 — Risk Flag Bar

**位置**：Decision Strip 下方，Signal Strip 上方（始终可见）

**形态**：横向 flag 列表，仅显示当前激活（True）的 flag，
全部为 False 时显示 `✓ No active risk flags`（绿色）

**Flag 定义：**

| Flag 名称 | 触发条件 | 颜色 |
|----------|---------|------|
| EXTREME VOL | `vix_snapshot.regime == "EXTREME_VOL"` | red |
| BACKWARDATION | `backwardation == true` | orange |
| MACRO DOWNTREND | `macro_warning == true` | orange |
| VIX RISING | `vix_snapshot.transition_warning == true` | gold |
| OVERLAY ACTIVE | `overlay_mode == "active"` | blue |
| SHOCK SHADOW | `shock_mode == "shadow"` | gray（informational） |

**视觉格式：**
```
[EXTREME VOL]  [BACKWARDATION]  [MACRO DOWNTREND]
```
每个 flag 是一个小 badge，样式复用现有 `.badge` CSS。

**边界：**
- SHOCK SHADOW 仅在 shock_mode != "disabled" 时显示，作为 info 标志（不是警告）
- OVERLAY ACTIVE 仅在 overlay_mode == "active" 时显示（当前为 "disabled"，不会触发）
- flag 数量可能为 0 个（显示绿色 "No active risk flags"）

---

## 后端改动（selector.py + server.py）

### selector.py

**Recommendation dataclass 新增 4 个字段：**

```python
canonical_strategy: str = ""   # matrix 原始推荐（guardrail 介入前）
re_enable_hint:     str = ""   # guardrail 解锁条件提示
overlay_mode:       str = "disabled"
shock_mode:         str = "disabled"
```

**`_guardrail_rec()` 函数改动：**
传入 `canonical_strategy` 和对应的 `re_enable_hint`：

```python
# re_enable_hint 静态映射（selector.py 内部）
_RE_ENABLE = {
    "EXTREME VOL":     "VIX below {extreme_vix:.0f}",
    "BACKWARDATION":   "VIX spot falls below VIX3M (contango restored)",
    "VIX RISING":      "VIX trend turns FLAT or FALLING",
    "MACRO DOWNTREND": "SPX recovers above 200MA",
}
```

**`get_recommendation()` 在构建各路径时：**
- 正常推荐路径：`canonical_strategy = strategy.value`（与 strategy 相同）
- guardrail 触发路径（REDUCE_WAIT）：
  `canonical_strategy = <被 guardrail 拦截的原始策略名>`

**`overlay_mode` / `shock_mode`**：
从 `params.overlay_mode` / `params.shock_mode` 直接透传到 Recommendation。

### server.py

`/api/recommendation` 的序列化（`_json_dc`）已自动处理新字段，无需改动。

---

## 接口定义

### `/api/recommendation` 响应新增字段

```json
{
  "canonical_strategy": "Bull Put Spread (High Vol)",
  "re_enable_hint": "VIX below 35",
  "overlay_mode": "disabled",
  "shock_mode": "shadow",
  ...existing fields...
}
```

### 前端改动

| 文件 | 改动 |
|------|------|
| `web/templates/index.html` | F1：Decision Strip HTML + CSS + JS；F2：Risk Flag Bar HTML + CSS + JS |
| `web/server.py` | 无改动（序列化自动处理） |
| `strategy/selector.py` | Recommendation 新增 4 字段；`_guardrail_rec()` 填充 canonical + hint；`get_recommendation()` 各路径填充 canonical_strategy |

---

## 边界条件与约束

- 不改动 `engine.py`、`signals/`、backtest 逻辑
- `canonical_strategy` 为空字符串时，前端不显示 "Canonical" 行
- `re_enable_hint` 仅为提示性文字，不是系统承诺
- Risk Flag Bar 中 OVERLAY / SHOCK 的 flag 触发条件完全由 params 决定，不依赖运行时计算
- BP utilization 不在本 SPEC 范围（需要实时持仓估值，留到后续）

---

## 不在范围内

- BP utilization / headroom（需实时持仓估值 API）
- short_gamma concurrent count（state.py 目前只记录 1 个持仓）
- "Next eligible state" 的动态判断逻辑（静态 hint 已足够）
- Matrix 页的 counterfactual 深度改造（单独 SPEC）

---

## Review

- 结论：PASS
- AC1–AC7 全部通过代码核查
- AC6 扩展验证：VIX RISING 路径（HIGH_VOL + BEARISH）canonical="Bear Call Spread (High Vol)"，hint="VIX trend turns FLAT or FALLING"，overlay_mode/shock_mode 透传正确
- `_re_enable_hint()` 额外覆盖了 IVP FILTER / PREMIUM FILTER 两个路径，超出 SPEC 范围但无害

---

## 验收标准

1. **AC1**：Dashboard Signal Strip 上方有 Decision Strip，显示 action pill + 策略名
2. **AC2**：guardrail 激活时，Decision Strip 显示 Blocked by / Canonical / Re-enable 三行
3. **AC3**：Risk Flag Bar 显示所有当前激活的 flag badge
4. **AC4**：无任何 flag 激活时，Risk Flag Bar 显示 `✓ No active risk flags`（绿色）
5. **AC5**：`/api/recommendation` 响应包含 `canonical_strategy`、`re_enable_hint`、`overlay_mode`、`shock_mode` 四个新字段
6. **AC6**：selector.py 的 guardrail 路径正确填充 `canonical_strategy`（EXTREME_VOL / BACKWARDATION 两个主路径验证）
7. **AC7**：API 失败时两个组件静默降级（不产生 JS 错误）

---

Status: DONE
