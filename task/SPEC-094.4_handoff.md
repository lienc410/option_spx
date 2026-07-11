# SPEC-094.4 Handoff — 实施停止（AC-3 rollback 条款触发）

**Date**: 2026-07-11（Developer）
**Verdict**: **BLOCKED — 未实施**。spec 给定的 live 分类器定义在 35 个历史触发上的重放对齐 = **30/35 < 33/35**，触发 Handoff Contract 第 5 条："若 AC-3 对齐 < 33/35 → 停止实施回 Quant 复核分类定义"。且 5 笔差异中 4 笔恰好是全部 4 个突发型（安全关键分层），错向危险侧。生产代码零改动。

---

## 一、文件对照

| 文件 | 动作 |
|---|---|
| `production/q042_executor.py` | **未改动**（F1/F2 建议块与分类逻辑未接线） |
| `strategy/q042_gate.py` / `data/q042_gate_log.jsonl` schema | **未改动**（`ammo_advisory` 字段未引入） |
| `tests/test_spec_094_4.py` | **未创建**（AC-3 重放断言 ≥33/35 必红；在 Quant 裁决分类定义前造测试无意义） |
| `task/SPEC-094.4_handoff.md` | 本文件（唯一新增） |

分析所用（只读）：`task/SPEC-094.4.md`、`research/q095/q095_p6_findings_2026-07-12.md`、`research/q095/q095_p6_bps_sub.csv`（pricing=FLAT 的 35 行 stratum 为对齐目标）、`research/q095/q095_p6_bps_substitution.py`（研究分层真值代码）、`research/q095/q095_p2b_episode_race.py`（C5 定义与 `find_episodes` 参照）、`research/q095/q095_p2b_episodes.csv`、`data/q042_backtest_trades.csv`（sleeve A 35 个 signal_date）、`data/market_cache/yahoo__GSPC__max__1d.pkl`（本地日线缓存，2026-07-11 17:12 刷新，与 episodes.csv 同源同期——我的 `find_episodes` 复算与已发布 185 段**逐段完全一致**，排除数据漂移解释）。

工作区原有 dirty 文件（RESEARCH_LOG.md、selector.py 等）均非本任务改动。

## 二、AC 逐条 + 证据

| AC | 结论 | 证据 |
|---|---|---|
| AC-94.4-3（关键） | **FAIL — 30/35** | spec 定义句逐字实现（episode ⟺ 信号日前 7 日历日内含当日，存在 trailing 15TD Close 极差比 ≤5% 的交易日；比值 = rolling(15) 的 (max−min)/mean，与 P2b `C5_TrailBand` 位同）重放 35 个 sleeve A signal_date：**30/35**。差异逐笔见第四节。稳健性：lookback 6d/7d 同为 30/35；分母改 (max+min)/2 或 min、窗口 shift(1) 均不翻转任何一笔（差异笔的比值离 5% 阈值 0.3-2.5pp）。 |
| AC-94.4-1 | 未实施 | 三分支文案（含分支 2 收益差距提醒句）依赖分类器输出；rollback 条款生效后停止。 |
| AC-94.4-2 | 未实施 | `ammo_advisory` gate log 字段同上。 |
| AC-94.4-4 | 未实施 | fail-soft `弹药路由 n/a` 路径同上。 |
| AC-94.4-5 | 未实施 | dry-run 零落盘断言同上。 |
| AC-94.4-6 | **PASS（基线）** | 094.2 + 094.3 全绿（见第三节）；本任务零生产改动，不可能破坏。 |

## 三、回归数字

```
venv/bin/python -m pytest tests/test_spec_094_2.py tests/test_spec_094_3.py -q
→ 35 passed in 2.61s   （22 + 13，全绿）
```

## 四、取舍歧义（核心：spec 定义句 vs AC-3 门槛互斥）

### 4.1 spec 逐字定义（变体 A，"C5 trailing 直译"）— 30/35，5 笔差异

| signal | P6 stratum | live(A) | 机制 |
|---|---|---|---|
| 2018-02-05 | sudden | episode | 02-01 trailing 比值 3.74% ≤5%：窗口**跨骑**已完结 episode（2017-12-15..2018-01-19，距信号 17 日历日 >7）尾部 + 1 月末顶部 |
| 2020-02-24 | sudden | episode | 02-18 比值 4.66%：跨骑 2019-12-19..2020-02-11 episode 尾 + ATH 顶部 |
| 2020-09-04 | sudden | episode | 09-01 比值 4.49%：跨骑 2020-08-05..08-27 episode |
| 2025-02-27 | sudden | episode | 02-20/21 比值 2.46%：跨骑 2024-11-08..2025-02-14 episode 尾 |
| 2020-10-19 | episode | sudden | 研究真值是 inside（episode 2020-10-07..10-27 的第 ~9TD），trailing 15TD 窗口 7 日内最小 5.79% >5% |

**方向致命**：前 4 笔正是 P6 突发型全部 4 例（BPS −$101k vs call spread capped −$25k 的那 4 笔）。逐字定义会在现金不足时把 4/4 的崩盘延续型触发路由到"BPS fallback"分支——恰是本规则要防的失败模式。根因：纯 trailing 窗口会跨骑"已完结超 7 天的旧 episode"，研究分层的贪婪不重叠分段已把那些天消费掉，故不算。

### 4.2 诊断变体 B（因果贪婪分段直译，非 spec 文本）— 31/35；补尾窗修正后 32/35

对截断至信号日的 Close 序列跑与研究**同一段** `find_episodes`（贪婪左起、不重叠、纯 trailing 可算），episode ⟺ 存在段尾距信号 ≤7 日历日。4 个突发型全对；差异 3 笔全为"inside-early"（信号落在 episode 形成的第 9-13 TD，段满 15TD 是**后视信息**，任何 trailing-only 分类器在锁死参数下原理上不可判）：

| signal | P6 stratum | live(B) | 信号在段内位置 |
|---|---|---|---|
| 2015-11-13 | episode | sudden | 2015-10-28 起第 ~13TD |
| 2019-05-13 | episode | sudden | 2019-04-29 起第 ~11TD |
| 2020-10-19 | episode | sudden | 2020-10-07 起第 ~9TD |

（第 4 笔 2013-10-08 属研究代码 `while s < n - MIN_LEN` 的尾窗边界：截断数据上恰好 15TD 收尾于信号日的段不被扫描；live 版放宽为 `s <= n - MIN_LEN` 即对齐，全量数据上两者等价——185 段复算逐段一致。）

**方向保守**：B 的 3 笔错全部把 episode 误判为 sudden → 建议空仓，少赚不多亏（该 3 笔 episode 型 BPS 历史为正收益，错失而非亏损）。

### 4.3 结论

在 5%/15TD/7d 锁死参数下，**任何 trailing-only 分类器均无法达到 33/35**：抓 inside-early 需要跨骑窗口（把 4 个 sudden 拉错到危险侧），不跨骑则 inside-early 3 笔结构性漏判。定义句与 AC-3 门槛在数据上互斥——这不是实现自由度能解决的，是分类定义问题，按 rollback 条款回 Quant。

## 五、复核提示（供 Quant 裁决，非 Developer 决定）

1. **若"突发型 4/4 对齐"是硬要求**（机制上 BPS 亏 4× 就集中在这 4 笔），变体 B（因果贪婪分段直译 + 尾窗修正，32/35）是唯一满足者；需修订 spec 分类定义句，并把 AC-3 门槛改为方向敏感形态（例如 "sudden 4/4 + episode ≥28/31"）或降为 ≥32/35。
2. **若坚持 ≥33/35 平铺门槛**：锁死参数下无解；抓 inside-early 需更短 trailing 窗口 = 参数改动 = 按 spec"改动须新研究"条款走新研究。
3. 变体 B 完全复用研究已验证代码路径（`find_episodes` 原样 + 截断），符合 spec "Prototype: 分类逻辑复用 research/q095 已验证代码路径" 的初衷；其 3 笔误差方向与"宁可空仓"的规则精神同向。
4. 复现命令（数据 = `data/market_cache/yahoo__GSPC__max__1d.pkl` + `q095_p6_bps_sub.csv` FLAT 35 行）：

```python
# venv/bin/python 下逐字重放（变体 A = spec 定义句）
import pandas as pd
df = pd.read_pickle("data/market_cache/yahoo__GSPC__max__1d.pkl")
idx = pd.to_datetime(df.index); idx = idx.tz_localize(None) if idx.tz is not None else idx
c = pd.Series(df["Close"].values, index=idx.normalize()).dropna()
ratio = (c.rolling(15).max() - c.rolling(15).min()) / c.rolling(15).mean()
sub = pd.read_csv("research/q095/q095_p6_bps_sub.csv"); sub = sub[sub.pricing == "FLAT"]
live = sub.signal.map(lambda s: "episode" if (ratio.loc[pd.Timestamp(s)-pd.Timedelta(days=7):pd.Timestamp(s)].dropna() <= 0.05).any() else "sudden")
print((live.values == sub.stratum.values).sum(), "/ 35")   # → 30 / 35
```

裁决后重新下发 spec（或修订 AC-3），F1/F2/gate log/dry-run/测试骨架当天可完成——机制层无任何未知数，唯一未决点就是分类定义。

---

## 六、完稿注记（Quant 2026-07-12）

Developer 于裁决后完成实施（executor +159 行 / gate +24 行 / tests 13 个），但在更新本 handoff 与发送最终汇报前会话中断。以下最终数字由 Quant 亲自执行取得，权威性等同：

- **AC-3（修订门槛）**：实施版 `_classify_trigger_type` 重放 35 笔 → **总对齐 32/35 ✓（≥31）；突发型 4/4 ✓（硬）；3 笔差异（2015-11-13/2019-05-13/2020-10-19）全部错向 sudden/空仓（保守侧）✓**——恰为预测的 inside-early 不可判例。
- **全套测试**：094.4 × 13 + 094.2 × 22 + 094.3 × 13 = **48 passed**（Quant 亲跑）。
- AC-1 分支 2 收益差距提醒句逐字断言在测（test 行 219）；AC-2 gate log `ammo_advisory` 字段（branch/episode_type/liquid/need）；AC-4 分类/报价双失败降级 n/a；AC-5 dry-run 零落盘零推送。
