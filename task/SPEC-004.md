# SPEC-004: 禁用 Bear Call Diagonal（LOW_VOL + BEARISH → REDUCE_WAIT）

## 目标

将 `LOW_VOL + BEARISH` 路径的策略由 Bear Call Diagonal 改为 REDUCE_WAIT，彻底移除该策略。

**Why：**
- ALL 数据（2000–2026，11 笔）：36% 胜率，总 PnL -$4,475，平均 -$407/笔
- 三重结构性缺陷：
  1. 入场环境矛盾：LOW_VOL (VIX<15) 意味着市场平静，BEARISH 仅是短期回调，V 型反转概率高
  2. 低 IV 环境损益不对称：VIX<15 时短腿保费极少，抵不过 SPX 小幅反弹的 delta 损失
  3. 无有效退出机制：SPEC-2 已验证 BULLISH trend_flip 无法区分胜负，亏损持仓被动拖至 72 天
- LOW_VOL 体制下市场结构性偏多，做空方向性期权无统计边际
- 真正的趋势性熊市（2022 年等）通常伴随 VIX > 20，不会触发 LOW_VOL 入场条件

## 策略/信号逻辑

**变更前：**
```
LOW_VOL + any_IV + BEARISH  →  Bear Call Diagonal (SPX, long PUT δ0.70 90DTE / short PUT δ0.30 45DTE)
```

**变更后：**
```
LOW_VOL + any_IV + BEARISH  →  REDUCE_WAIT
  理由文本："LOW_VOL + BEARISH — 低波动环境中的方向性看跌无统计边际；V型反转概率高，等待趋势确认"
```

## 接口定义

### `strategy/selector.py`

`select_strategy()` 函数中，LOW_VOL 分支的 BEARISH 路径：

**变更前：**
```python
# BEARISH in LOW_VOL
action = get_position_action(StrategyName.BEAR_CALL_DIAGONAL.value, is_wait=False)
return Recommendation(
    strategy        = StrategyName.BEAR_CALL_DIAGONAL,
    ...
)
```

**变更后：**
```python
# BEARISH in LOW_VOL → no edge; low-vol pullbacks are V-shaped, not trend-following
return _reduce_wait(
    "LOW_VOL + BEARISH — 低波动环境中的方向性看跌无统计边际；V型反转概率高，等待趋势确认",
    vix, iv, trend, macro_warn,
)
```

### `strategy/selector.py` 文件头注释

决策矩阵注释第 3 行：

**变更前：**
```
LOW_VOL       any         BEARISH    → Bear Call Diagonal     SPX 45/90
```

**变更后：**
```
LOW_VOL       any         BEARISH    → Reduce / Wait          —
```

### 不需要修改

- `backtest/engine.py`：`_build_legs()` 中 BEAR_CALL_DIAGONAL 分支保留（代码不删，仅不触发）
- `StrategyName` 枚举：保留 `BEAR_CALL_DIAGONAL`（不破坏枚举兼容性）
- 回测入参：无变化

## 边界条件与约束

- LOW_VOL + NEUTRAL 路径（→ Iron Condor）不受影响
- LOW_VOL + BULLISH 路径（→ Bull Call Diagonal）不受影响
- NORMAL / HIGH_VOL 中无 Bear Call Diagonal，无需处理
- 修改后需清除 `data/backtest_stats_cache.json` 并重启 web 服务（per CLAUDE.md）

## 不在范围内

- 不替换为 Bear Put Spread 或其他策略（方案 C）
- 不添加 `above_200=False` 过滤后保留策略（方案 B）
- 不修改 `StrategyName.BEAR_CALL_DIAGONAL` 枚举定义
- 不修改回测引擎中 BEAR_CALL_DIAGONAL 的腿构建逻辑

## Prototype

无需 prototype。变更为纯入场过滤（REDUCE_WAIT 替换），无新数学逻辑。
回测验证将由 Codex 实施后通过 `python main.py --backtest` 直接确认。

## Review

- 结论：PASS
- 问题：无

核查要点：
1. `selector.py:14` — 矩阵注释已改为 `Reduce / Wait` ✅
2. `selector.py:341` — BEARISH 分支已改为 `_reduce_wait(...)` 含正确理由文本 ✅
3. `engine.py` / `StrategyName` 枚举未修改（Spec 要求保留）✅
4. 回测验证：PnL $70,017 > $58,423，Sharpe 1.16 > 1.02 ✅
5. 缓存清除 + Web 重启已确认 ✅

## 验收标准

1. `python main.py --backtest --start 2000-01-01` 输出中 `Bear Call Diagonal` 行消失（或 n=0）
2. 全局回测 total PnL ≥ $58,423（移除亏损策略后应提升，不应下降）
3. 全局 Sharpe ≥ 1.02（同上）
4. `LOW_VOL + BEARISH` 信号日期在 signal_history 中显示 strategy = "Reduce / Wait"
5. Web Dashboard 矩阵页 LOW_VOL × BEARISH 格显示 "Reduce / Wait"

---
Status: DONE
