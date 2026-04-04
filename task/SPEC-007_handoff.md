# SPEC-007 Handoff

## 实施摘要
已在 `NORMAL` 制度下，将 `IV HIGH + BEARISH` 和 `IV NEUTRAL + BEARISH` 两条原本 `Reduce / Wait` 的子路径替换为条件化的 `Iron Condor` 入场。实现保留了 Spec 要求的风控边界：`VIX RISING` 时不入场，`IV HIGH` 下 `IVP ≥ 50` 不入场，`IV NEUTRAL` 下 `IVP` 需处于 `20–50`。

## 修改文件
- `strategy/selector.py:420` — 将 `NORMAL + IV HIGH + BEARISH` 从 `Reduce / Wait` 改为条件化 `Iron Condor`
- `strategy/selector.py:421` — 新增 `VIX RISING` 过滤：`NORMAL + IV HIGH + BEARISH + VIX RISING → Reduce / Wait`
- `strategy/selector.py:426` — 新增 `IVP ≥ 50` 过滤：stressed vol 时仍 `Reduce / Wait`
- `strategy/selector.py:431` — 新增 `NORMAL + IV HIGH + BEARISH` 的 `Iron Condor` 推荐结构与理由文案
- `strategy/selector.py:568` — 将 `NORMAL + IV NEUTRAL + BEARISH` 从 `Reduce / Wait` 改为条件化 `Iron Condor`
- `strategy/selector.py:569` — 新增 `VIX RISING` 过滤：`NORMAL + IV NEUTRAL + BEARISH + VIX RISING → Reduce / Wait`
- `strategy/selector.py:574` — 新增 `IVP outside 20–50` 过滤
- `strategy/selector.py:579` — 新增 `NORMAL + IV NEUTRAL + BEARISH` 的 `Iron Condor` 推荐结构与理由文案

## 收尾步骤
- 缓存清除：是
- Web 重启：是

## 验收结果（自测）
1. `python main.py --backtest --start=2000-01-01` 输出中 `Iron Condor` 总笔数增加 ≥ 20 笔（相对 SPEC-006 后基准） → SPEC-006 基准 `n=21`，本次实测 `n=24`，仅增加 `+3`，未通过
2. Iron Condor（全部）WR ≥ 75% → 实测 `88%`，通过
3. 全局 Total PnL ≥ $100,000（SPEC-006 实际 $78,738，预期新增 ≥ $21,000） → 实测 `$86,393`，未通过
4. 全局 Sharpe ≥ 1.00（SPEC-006 实际 0.95，新增稳定 IC 交易应改善） → 实测 `1.12`，通过
5. `python main.py --dry-run` 在 NORMAL + BEARISH 环境下，当 VIX 非 RISING 且 IVP 在有效区间时，输出 `Iron Condor` 推荐 → 当日真实行情不是 `NORMAL + BEARISH`；使用合成快照验证后，`select_strategy()` 返回 `Iron Condor`，通过

## 备注
- `backtest/engine.py` 按 Spec 保持不变；本次仅修改 `strategy/selector.py`
- 当前真实 dry-run 环境仍是 `HIGH_VOL + BEARISH + VIX RISING`，因此不会命中本 Spec 的新分支
- 全局 Sharpe 已从 SPEC-006 的 `0.95` 改善到 `1.12`，但新增 IC 笔数和总收益未达到 Spec 阈值，建议由 PM / Claude 决定是否接受该 tradeoff

---

## v2 实施摘要
按修订后的 SPEC-007 v2，补充实现了 `NORMAL + IV LOW + BEARISH` 路径：当 `VIX` 非 `RISING` 且 `IVP ≥ 15` 时，原 `Reduce / Wait` 改为 `Iron Condor`；当 `VIX RISING` 或 `IVP < 15` 时继续等待。v1 已完成的 `IV HIGH` / `IV NEUTRAL` 两条 BEARISH 路径未重复修改。

## v2 修改文件
- `strategy/selector.py:487` — 将 `iv_s == IVSignal.LOW` 块内 `BEARISH` 分支从 `_reduce_wait(...)` 改为条件化 `Iron Condor`
- `strategy/selector.py:492` — 新增 `VIX RISING` guard：`NORMAL + IV LOW + BEARISH + VIX RISING → Reduce / Wait`
- `strategy/selector.py:497` — 新增 `IVP < 15` guard：保费过低时继续 `Reduce / Wait`
- `strategy/selector.py:502` — 新增 `NORMAL + IV LOW + BEARISH` 的 `Iron Condor` 推荐结构与理由文案

## v2 收尾步骤
- 缓存清除：是
- Web 重启：是

## v2 验收结果（自测）
1. `python main.py --backtest --start=2000-01-01` 输出中 `Iron Condor` 总笔数增加 ≥ 30 笔（相对 SPEC-006 后基准 n=21） → 实测 `n=39`，较基准 `+18`，未通过
2. Iron Condor（全部）WR ≥ 75% → 实测 `77%`，通过
3. 全局 Total PnL ≥ $100,000（SPEC-006 实际 $78,738，预期新增 ≥ $21,000） → 实测 `$78,101`，未通过
4. 全局 Sharpe ≥ 1.00 → 实测 `0.90`，未通过
5. `python main.py --dry-run` 在 NORMAL + BEARISH 环境下，当 VIX 非 RISING 且 IVP ≥ 15 时，输出 `Iron Condor` 推荐 → 当日真实行情仍非 `NORMAL + BEARISH`；使用合成快照验证后，`select_strategy()` 返回 `Iron Condor`，通过

## v2 备注
- v2 明显扩大了 `Iron Condor` 覆盖面：`n=24 → 39`
- 但全局结果从 v1 的 `Total PnL=$86,393 / Sharpe=1.12` 回落到 `Total PnL=$78,101 / Sharpe=0.90`
- 修订后的覆盖主要改善了路径覆盖率，但没有转化为更好的组合层面表现

---

## v2 回滚确认
按 PM 指令，已回滚 `SPEC-007 v2` 中唯一新增的 `iv_s == IVSignal.LOW` / `BEARISH` Iron Condor 路径，恢复为单行 `Reduce / Wait`：

```python
if t == TrendSignal.BEARISH:
    return _reduce_wait(
        "NORMAL + IV LOW + BEARISH — low premium insufficient for IC; skip",
        vix, iv, trend, macro_warn,
    )
```

## v2 回滚范围
- `strategy/selector.py:509` — 移除 v2 新增的 `VIX RISING` guard
- `strategy/selector.py:509` — 移除 v2 新增的 `IVP < 15` guard
- `strategy/selector.py:509` — 移除 v2 新增的 `Iron Condor` recommendation，恢复为单行 `_reduce_wait(...)`

## v2 回滚收尾
- 缓存清除：是
- Web 重启：是

## v2 回滚备注
- v1 已完成的 `IV HIGH + BEARISH → IC` 与 `IV NEUTRAL + BEARISH → IC` 路径保持不变，未触碰
- 本次按要求未额外运行回测；已通过代码检查确认 `NORMAL + IV LOW + BEARISH` 文案恢复为 `low premium insufficient for IC; skip`
