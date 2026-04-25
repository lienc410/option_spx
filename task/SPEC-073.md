# SPEC-073: BEAR_CALL_DIAGONAL Dead-Code Cleanup

Status: DONE

## 目标

**What**：从 HC 主线代码中移除 `BEAR_CALL_DIAGONAL` 策略的 dead code，使代码库与 selector 当前真实行为对齐。

**Why**：
- 当前 selector 决策路径无任何分支返回 `StrategyName.BEAR_CALL_DIAGONAL`（grep 结果仅 `engine._build_legs` / `engine._compute_bp` / `margin.html` UI 残留）
- 历史 SPEC-004（diagonal 系列扩展）阶段引入；后续 SPEC 已转向 BPS_HV / IC_HV 路径，BCD 从未真正进入 production
- 残留代码与 UI 误导：margin 页仍显示 BCD 卡片，给 PM / 维护者 "策略可被推荐" 的错觉
- MC 已在 v3 handoff 中列入清理项；HC 同步此清理避免长期分叉

---

## 核心原则

- **只删 dead code，不改 behavior**：selector 当前不会返回 BCD，因此移除 `_build_legs` / `_compute_bp` 分支不影响任何已有交易决策
- **保留 `StrategyName.BEAR_CALL_DIAGONAL` 枚举值**：研究 prototype 脚本（SPEC-016/017/021）仍以字符串 `"Bear Call Diagonal"` 作为 baseline 对照参考；删除枚举值会破坏 import-time 兼容性，且代价远大于收益。仅注释枚举值为 deprecated
- **不动历史 SPEC 文档与 RESEARCH_LOG**：task/SPEC-004.md / SPEC-011.md / 历史 strategy_status / claude_quant_notes 皆为 frozen 历史记录，不在本 SPEC 范围
- **不修改 backtest/prototype/SPEC-016/017/021_*.py**：研究脚本属历史快照，非 production 路径

---

## 功能定义

### F1 — 移除 engine `_build_legs` 中 BEAR_CALL_DIAGONAL 分支

**[backtest/engine.py:363-373](backtest/engine.py#L363-L373)**：

当前：
```python
if strategy == StrategyName.BEAR_CALL_DIAGONAL:
    # Bearish put diagonal: long deep-ITM put (90 DTE) + short OTM put (45 DTE)
    # Mirrors BULL_CALL_DIAGONAL but with puts for a bearish directional bias.
    short_dte = 45
    long_dte  = 90
    short_k   = find_strike_for_delta(spx, short_dte, sigma, 0.30, is_call=False)
    long_k    = find_strike_for_delta(spx, long_dte,  sigma, 0.70, is_call=False)
    return [
        (+1, False, long_k,  long_dte,  1),
        (-1, False, short_k, short_dte, 1),
    ], short_dte
```

修改后：删除整个分支。

### F2 — 移除 engine `_compute_bp` 中 BEAR_CALL_DIAGONAL 分支

**[backtest/engine.py:445-448](backtest/engine.py#L445-L448)**：

当前：
```python
if strategy == StrategyName.BEAR_CALL_DIAGONAL:
    # Debit trade (mirror of Bull Call Diagonal with puts).
    bp = entry_value * 100
    return 0.0, max(bp, 0.0)
```

修改后：删除整个分支。

### F3 — 移除 margin.html UI 残留

**[web/templates/margin.html](web/templates/margin.html)**：

- 删除 line 382-403 区间的 `<!-- Bear Call Diagonal -->` strategy card 块
- 删除 line 446 处 BP 表格中 `Bear Call Diagonal` 行
- 修改 line 480 标签 `Bull Call Diagonal & Bear Call Diagonal` → `Bull Call Diagonal`（或合并到 diagonal 通用条目，由 frontend 实施时定）

具体行号需 Developer 在实施时再次 grep 确认（HTML 行号易漂移）。

### F4 — 标记枚举值为 deprecated

**[strategy/selector.py:184](strategy/selector.py#L184)**：

当前：
```python
BEAR_CALL_DIAGONAL  = "Bear Call Diagonal"
```

修改后：
```python
BEAR_CALL_DIAGONAL  = "Bear Call Diagonal"   # DEPRECATED — selector never returns this; retained for prototype script string-compat
```

---

## In Scope

| 项目 | 说明 |
|---|---|
| `_build_legs` BCD 分支删除 | engine.py:363-373 |
| `_compute_bp` BCD 分支删除 | engine.py:445-448 |
| `margin.html` BCD UI 元素删除 | strategy card + BP 表格行 + 文案标签 |
| 枚举值 deprecated 注释 | selector.py:184 |
| 完整回归对照 | 用 baseline_2026-04-24 比对：trades / metrics 必须 byte-identical（dead code 删除不应改变任何 trade） |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 删除 `StrategyName.BEAR_CALL_DIAGONAL` 枚举值本身 | prototype 脚本字符串依赖；移除收益 < 破坏成本 |
| 修改 backtest/prototype/SPEC-016/017/021_*.py | 历史研究快照，非 production |
| 修改 task/SPEC-004.md / SPEC-011.md / 历史 strategy_status_*.md | frozen 历史文档 |
| BULL_CALL_DIAGONAL 同类清理 | BCD-only 删除；BCDiag 仍是当前活跃策略 |
| 重新设计 diagonal 类策略入场条件 | 与本清理无关 |
| 删除 Trade record 中残留的 BCD 历史交易（若有）| baseline 显示 0 笔 BCD trade，无需处理 |

---

## 边界条件与约束

- **回归口径**：删除前后，`run_baseline.py` 输出 `trade_log.csv` / `metrics.json` / `2026-03-strikes.json` 必须完全一致（允许 timestamp / 浮点末尾位差异）。任何数值差异都意味着 BCD 实际并非 dead code，需要回滚 SPEC 重做分析
- **import 兼容性**：保留枚举值，所有 `from strategy.selector import StrategyName` 用例继续可用
- **frontend regression**：margin 页面在删除 BCD 卡片后排版应正常，不留空白槽位

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| `doc/baseline_2026-04-24/trade_log.csv` | 已生成 | 对照基线 |
| `doc/baseline_2026-04-24/metrics.json` | 已生成 | 对照基线 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `backtest/engine.py` 中无任何 `BEAR_CALL_DIAGONAL` 引用 | `grep -n BEAR_CALL_DIAGONAL backtest/engine.py` 返回 0 行 |
| AC2 | `web/templates/margin.html` 中无 `Bear Call Diagonal` 字样 | `grep -n "Bear Call Diagonal" web/templates/margin.html` 返回 0 行 |
| AC3 | `strategy/selector.py` `BEAR_CALL_DIAGONAL` 枚举值仍存在且带 `DEPRECATED` 注释 | 代码审查 |
| AC4 | 重新运行 `doc/baseline_2026-04-24/run_baseline.py`，与基线 `trade_log.csv` / `metrics.json` 完全一致 | diff 对比，预期无差异 |
| AC5 | margin 页面在浏览器中渲染无空白卡片或断行 | 人工 visual check |
| AC6 | `arch -arm64 venv/bin/python -c "from strategy.selector import StrategyName; print(StrategyName.BEAR_CALL_DIAGONAL.value)"` 仍输出 `"Bear Call Diagonal"` | 一行命令验证 |
| AC7 | 无新增 lint / type-check warning | `python -m py_compile backtest/engine.py strategy/selector.py` 成功 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-24 | 初始草稿 — MC v3 handoff 同步项；HC 验证 BCD 在 selector 决策路径中已无 reach；起草 PM 审批 | DRAFT |
| 2026-04-24 | PM 批准，进入实施 | APPROVED |
| 2026-04-24 | F1/F2/F3/F4 实施完成；AC1/2/3/4/6/7 全部 PASS（trade_log/metrics/strikes 与 baseline byte-identical）；AC5 留待 frontend smoke 时人工 visual check | DONE |
