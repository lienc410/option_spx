# Strategy Spec — 已同意但未实现的改动

记录已通过分析/讨论达成共识、但尚未在代码中落地的规则变更。
每项包含：**Inputs / Rules / Edge Cases**。

---

## SPEC-1：7日快速退出 vs min_hold_days 矛盾

**状态：✅ 完全解决（2026-03-29）**
- SPEC-1A（文本修复）：✅ 已实施，selector.py 文本已更新
- SPEC-1B（7日快速退出）：❌ 否决 — 修复 `_entry_value` Bug 后，7天内 0/14 笔触发；规则永不生效，维持 `min_hold_days=10`

**现状：代码不一致**

`strategy/selector.py` 的所有策略 `roll_rule` 字段描述：
> "Close at 21 DTE; take early profit at 50% **if within first 7 trading days**"

但 `backtest/engine.py` 实际逻辑（line 508）：
```python
if pnl_ratio >= params.profit_target and position.days_held >= params.min_hold_days:
    exit_reason = "50pct_profit"
```
`min_hold_days = 10`——profit target 在第 10 天前**不能触发**，与"7天内快速退出"矛盾。

**需决策并实施其中一个方向：**

---

### 方案 A：保留 min_hold=10，更新文本（推荐）

研究结论（research_notes §11）已明确：min_hold=10 是有意设计，防止运气性超短期套利。"7天"描述已过时。

#### Inputs
- 无新 input，只修改 selector 文本

#### Rules
- 将所有 `roll_rule` / `target_return` 中的 "within 7 trading days" 替换为 "after 10+ days held"
- `min_hold_days = 10` 保持不变

#### Edge Cases
- 无逻辑变更，仅文档一致性修复

---

### 方案 B：实现真正的 7 日快速退出（绕过 min_hold）

若认为快速达到 50% 的交易不应被强制持有到 10 天，则需在 engine 中添加快速路径。

#### Inputs
- `position.days_held`：当前持仓天数
- `pnl_ratio`：当前收益 / 初始权利金
- `params.profit_target`：50%
- `FAST_EXIT_DAYS = 7`（新常量）

#### Rules
```
IF pnl_ratio >= profit_target:
    IF days_held <= FAST_EXIT_DAYS:
        exit_reason = "50pct_fast"      # 7天内快速达到目标，立即退出
    ELIF days_held >= min_hold_days:
        exit_reason = "50pct_profit"    # 正常路径
```

#### Edge Cases
| 场景 | 期望行为 |
|------|---------|
| Day 3 达到 50%，继续上涨到 80% | Day 3 即退出（快速退出不等更多利润）|
| Day 8 达到 50%（7 < 8 < 10） | 不退出，等待 Day 10 |
| Day 1 就达到 50% | 退出（无下限保护噪声风险） |
| Diagonal entry，short call 次日大跌 50% | Day 1 触发，是否合理？需压测 |

**注意：** 方案 B 引入了新的短期退出路径，需全局回测验证净 PnL 影响再实施。

---

## SPEC-2：Bear Call Diagonal — BULLISH 趋势翻转退出

**状态：❌ 已验证，否决（2026-03-29）**

### 验证结论

对全部 11 笔历史 Bear Call Diagonal 进行 BULLISH 信号逐日分析（days_held ≥ 3）：

| 交易 | 结果 | BULLISH 首现天数 | 入场后 SPX 涨幅 |
|------|------|----------------|----------------|
| 2004-07-16 | WIN +960 | Day 34 | +1.54% |
| 2005-01-20 | WIN +1782 | Day 11 | +2.35% |
| 2005-08-26 | WIN +1551 | Day 7 | +2.59% |
| 2014-08-12 | WIN +1534 | Day 5 | +2.47% |
| 2015-06-09 | WIN +1706 | Day 26 | +2.12% |
| 2005-04-19 | **LOSS -1579** | Day 21 | +2.84% |
| 2006-02-07 | **LOSS -1544** | Day 7 | +2.76% |
| 2006-05-26 | **LOSS -685** | Day 43 | -0.13% |
| 2007-03-08 | **LOSS -1670** | Day 20 | +2.99% |
| 2016-09-26 | **LOSS -1692** | Day 33 | +1.00% |
| 2024-05-02 | **LOSS -1520** | Day 3 | +2.44% |

**BULLISH 信号出现在全部 5 笔赢利 + 全部 6 笔亏损中，完全无法区分。**

### 否决原因

Bull Call Diagonal BEARISH exit 有效是因为：
- 赢利交易中 BEARISH 出现极晚或极短暂
- 亏损交易中 BEARISH 早期且持续

Bear Call Diagonal 的结构不同（long deep-ITM put + short OTM put）：
- SPX 上涨时，short OTM put 加速 theta decay → 盈利仍可能
- BULLISH 信号出现时，持仓可能仍处于盈利区间
- 规则会误退 5/5 赢利交易，不具备区分能力

### 结论

Bear Call Diagonal 无可行的 trend_flip 提前止损规则。与 BPS/IC 类似，风险管理应前置到**入场过滤**（选择信号足够 BEARISH 的环境），而非持仓期干预。记录到 `doc/research_notes.md`。

---

## SPEC-3：文档一致性修复（附属）

**状态：✅ 已实施（2026-03-29，随 SPEC-1A 同步完成）**

selector.py 中全部 "7 trading days" 文本已替换为 "min 10 days held"，无逻辑变更。

---

## 实施优先级

| SPEC | 类型 | 优先级 | 前提条件 |
|------|------|--------|---------|
| SPEC-1A（文本修复） | 文档 | 高 — 简单，消除混乱 | 无 |
| SPEC-2（Bear Call Diagonal） | 研究 + 实施 | 中 — 样本只有 6 笔 | 先验证历史数据 |
| SPEC-1B（7日快速退出） | 逻辑 | 低 — 与 min_hold 设计理念冲突 | 需全局回测验证 |
| SPEC-3（文档） | 文档 | 高（同 SPEC-1A） | 无 |
