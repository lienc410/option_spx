# Q021 — 2nd Quant Review Packet

- **日期**: 2026-04-25
- **被 review 者**: Quant Researcher (1st pass)
- **请审者**: 2nd Quant Reviewer
- **决定 deadline**: PM 等本 review 收口后才决定 SPEC-066 是否调整
- **预期审阅时长**: 30–45 分钟

---

## 0. 一句话上下文

`SPEC-066`（IC_HV `cap=2 + B filter` 同时实施）已在生产中运行 2 周。PM 在 2026-04-25
观察到 2026-03 实战双峰案例下，SPEC-066 的两笔入场（03-09, 03-10）都集中在第一峰
aftermath，**没有抓到第二峰**，怀疑当前实现是 *"同峰 back-to-back exposure 增加"*
而不是 *"多峰捕捉"*，因此设错。

1st Quant 跑了两阶段研究：
- **Phase 1** — 信号层归因（doc/q021_phase1_attribution_2026-04-25.md）：确认 PM 直觉
- **Phase 2** — 全引擎 prototype（doc/q021_phase2_full_engine_2026-04-25.md）：跑了 4 个变体

**1st Quant 的最终结论**：保留 SPEC-066，记录语义偏差，不开 DRAFT spec。

**请 2nd Reviewer 判定**：
1. Phase 1 / Phase 2 的方法学是否成立？
2. 数据归因是否有偏？
3. "保留 SPEC-066" 的 recommendation 是否被全引擎数据真正支撑，还是反过来？
4. 有没有 1st Quant 漏掉的关键变体？

---

## 1. 必读文件清单（按优先级）

### 1.1 Tier 1 — 直接相关

| 文件 | 用途 |
|---|---|
| `task/SPEC-066.md` | 当前 IC_HV 多 slot + B filter 规范 |
| `doc/q021_phase1_attribution_2026-04-25.md` | Phase 1 信号层归因 |
| `doc/q021_phase2_full_engine_2026-04-25.md` | Phase 2 全引擎结果（最终结论文） |
| `backtest/prototype/q021_phase2_distinct_peak.py` | Phase 2 prototype 代码 |

### 1.2 Tier 2 — 背景

| 文件 | 用途 |
|---|---|
| `task/SPEC-064.md` | aftermath HIGH_VOL IC_HV bypass（Q021 前置） |
| `sync/open_questions.md` Q021 entry | 原始 PM 提问 |
| `RESEARCH_LOG.md` R-20260420-03 | Q021 question framing |
| `backtest/engine.py:976-980` | `_already_open` 实现行（被 Phase 2 patch） |
| `strategy/selector.py:170-175` | `IC_HV_MAX_CONCURRENT = 2`、`AFTERMATH_OFF_PEAK_PCT = 0.10` 常量 |

### 1.3 Tier 3 — 可选

| 文件 | 用途 |
|---|---|
| `backtest/prototype/q018_phase2a_full_engine.py` | Phase 2 prototype 借用的 inspect-source patch 模式来源 |
| `backtest/prototype/q018_phase2d_cap_sweep.py` | 之前的 cap 扫描（cap=1..7） |
| `data/market_cache/yahoo__VIX__max__1d.pkl` | Phase 2 cluster map 输入（VIX close） |

---

## 2. 1st Quant 的核心声明（请逐条挑战）

### Claim A：Phase 1 信号层归因

> SPEC-066 vs cap=1 baseline 的 +18 trades / +$9,593 增量中：
>   - **Same-peak back-to-back: 14 trades / $+8,458（88% 美元、78% 笔数）**
>   - Distinct-second-peak captures: 4 trades / $+1,135（12% 美元）

**计算方法**（Phase 1 doc §3）：
- 用 VIX close 重建每日 aftermath 状态（peak_10d ≥ 28 ∧ off_peak ≥ 10%）
- 把连续 aftermath 日合成 cluster
- 对 50 笔 IC_HV trade 按 entry_date 落 cluster id
- "back-to-back" 定义：同一 cluster 内出现多笔 IC_HV 时，第 2 笔起算 back-to-back

**可挑战点**：
1. cluster 阈值（28 / 10%）任意选定，与 SPEC-064 selector 实现一致但未做敏感性
2. "back-to-back" 没考虑入场是否有真实独立信号 — 同 cluster 第 2 笔可能也来自重新触发的 selector
3. 第 1 笔 vs 第 2 笔的 PnL 归因是按笔而非按"边际 PnL"分摊
4. 仅用信号层重放，不模拟全引擎 BP/shock/overlay 否决路径

### Claim B：2026-03 真实案例

> Peak 1 = 2026-03-06 (VIX 29.49), aftermath cluster = 2026-03-09..03-11
> Peak 2 = 2026-03-27 (VIX 31.05), aftermath cluster = 2026-03-31..04-13
> SPEC-066 入场 2026-03-09 + 03-10，**两笔都在 peak 1 cluster**
> Peak 2 cluster 9 个 aftermath 日，**0 笔 IC_HV**

**核对方法**：
- VIX 数据来自 `data/market_cache/yahoo__VIX__max__1d.pkl`
- Trade 列表来自 `data/research_views.json` `spec064_aftermath_ic_hv` view
- 03-09 持仓 21d 后退出 04-01；03-10 持仓 21d 后退出 04-02 — 退出日恰好是 peak 2 cluster 起始

**可挑战点**：
1. peak 2 cluster 期间 IC_HV 0 笔可能不是 cap=2 限制造成 — 可能是 selector 那时给出 `REDUCE_WAIT`，需读 `data/signals.json` 确认
2. 即使 selector 推荐了，可能 BP / shock 否决，与 cap 无关

### Claim C：Phase 2 全引擎结果

| Variant | n | Total PnL | Sharpe | MaxDD | MaxConc IC_HV |
|---|---:|---:|---:|---:|---:|
| V0 baseline (cap=1, 0.05) | 404 | +400,734 | 0.41 | -13,213 | 2 |
| **V1 spec066 (cap=2, 0.10)** | 400 | **+403,850** | **0.42** | **-10,323** | **2** |
| V2 pm_intent (cluster, no cap) | 405 | +404,793 | 0.41 | -12,617 | **6** |
| V3 pm_intent + cap=2 | 389 | +395,643 | 0.41 | -10,323 | 2 |

> V3（PM Q4 "minimum rule"）系统层 -$9,200 vs V1，IC_HV 子集 -$8,207

**实施方法**（`q021_phase2_distinct_peak.py`）：
- `inspect.getsource(engine.run_backtest)` 取源码，replace `_already_open = (...)` 整块
- 替换为对 `_q021_block_cluster(positions, rec, date_str, cluster_map, cap)` helper 的调用
- helper 在 engine 模块 namespace 内通过 `exec` 注入 — 全引擎 BP/shock/overlay 链路不变
- cluster_map 由 `build_cluster_map()` 从 VIX 历史构建

**可挑战点**：
1. **Cluster 定义在 patched function 与 selector 实际使用是否一致**：selector 用的是 `peak_10d` rolling 窗口；prototype 用纯 backward 10 天窗口。两者是否完全等价？
2. **`_q021_block_cluster` 在 cur_cluster=None 分支的 fallback 逻辑**（line 134-137）：
   ```python
   if cur_cluster is None:
       return False  # 不阻挡
   ```
   这意味着 V2 (cap=None) 在非 aftermath 日**不限制 IC_HV 数量**，导致 max concurrent = 6。这是否真的代表 "PM intent 纯净版"，还是工程实现取巧？
3. **V1 spec066 baseline 的 selector_state 一致性**：跑 V1 时把 `sel.AFTERMATH_OFF_PEAK_PCT` 设为 0.10，与生产一致；但 `IC_HV_MAX_CONCURRENT` 通过源码 patch 改为 2，没有走 import 路径 — 是否有未捕获的副作用？
4. **样本切片缺失**：未做 2018-2026 vs 全样本对比；Q021 Phase 1 doc §3 提到的 35 cluster 中分布是否极不均匀？
5. **V3 vs V2 的差异 -$9,150**：V3 比 V2 严格仅多了非 aftermath 日的 cap=2 限制；这意味着 V2 多出来的 +$1K 几乎全靠 max concurrent=6 时多开的非 aftermath HV 第二腿 — 是不是 V2 跑赢只是把 HC live BP 风险换 PnL 的伪命题？

### Claim D：Disaster window

| Variant | n | W/L | Net |
|---|---:|---|---:|
| V0 baseline | 7 | 3W/4L | -$2,588 |
| **V1 spec066** | 5 | 3W/2L | **+$302** |
| V2/V3 pm_intent | 4 | 2W/2L | -$374 |

> V1 spec066 disaster 表现最优；V2/V3 在 Tariff 窗口少抓 1 笔（同 cluster 屏蔽）

**可挑战点**：
1. 总 disaster trade 数太少（4–7 笔），统计显著性弱
2. GFC 窗口 V0 抓 2 笔（-$2,890），V1/V2/V3 都 0 笔 — 这是 cap 还是 OFF_PEAK 0.05→0.10 造成？V1 与 V2/V3 都把 OFF_PEAK 从 0.05 改到 0.10，所以 V0 vs V1 的 GFC 差异不能归给 cap。

---

## 3. 关键 trade-set diff (V1 → V3)

V3 vs V1：`Dropped 23 trades / $+17,166` and `Gained 28 trades / $+18,109`，看似 +$943，
但**实际 V3 系统 -$9,200 vs V1**。差异来源：

- `Gained` 列表含 5 笔较大亏损（roll_21dte 退出）：
  - 2007-12-12 → 2008-01-17: -$3,026
  - 2022-08-22 → 2022-09-26: -$3,320
  - 2002-08-27 → 2002-10-01（V1 中存在的 -$852 在 V3 也在）
  - 几笔 +$1K～$1.5K 抵消
- `Dropped` 列表多为 +$500~+$1.5K 的 50pct_profit 退出，结构稳定
- 跨 trade 总账：BP/shock/overlay 还有非 IC_HV 影响（V0 vs V1 系统层差异 +$3,116 但 IC_HV 子集差 +$3,116 几乎全部 — V2/V3 的非 IC_HV 损失从哪来？需要 reviewer 确认）

**请 reviewer 帮判**：
- "Gained 28 trades net +$18,109" 但系统总 PnL 反而减少 $9,200 — 这 $27K 的差从哪来？是不是非 IC_HV 策略被这些新 IC_HV 占 BP 挤掉？
- 如果是，那 V3 的真实代价其实不是 IC_HV 子集而是**整套组合的 BP 拥挤**，1st Quant 的归因不完整

---

## 4. 1st Quant 的最终建议（请挑战）

> **(a) 保留 SPEC-066，将语义偏差记录入 sync/open_questions.md Q021 close-out，不开 DRAFT spec。**

### 支持理由
1. V3（PM 最小规则）系统 -$9,200 vs V1
2. V2 表面 +$943 但 max concurrent 6，HC live BP 不可接受
3. 2026-03 case 增量仅 +$111
4. V1 disaster 表现最佳

### 反方可能反驳
1. **统计显著性**：V1 vs V3 -$9,200 / 26 年，年化仅 -$354，远小于一个 IC_HV trade 的 σ（~$2K）。这个差是噪声还是信号？
2. **PM 语义优先于 PnL**：如果 PM 把 "exposure-only" 当 *设计错误*，即使 PnL 略低也应该改 — 因为 *risk-adjusted* 不只看 backtest，还要看可解释性 / 操作复杂度
3. **样本期偏差**：V1 是 2026-04 才上线的；2026-03 之前数据全是事后检验。是否 V3 在 *未来* 更适合？
4. **cluster 阈值任意**：peak ≥ 28、off ≥ 10%，是 SPEC-064 的选择，不是 SPEC-066 的；如果调阈值，V3 可能反超
5. **未测 size scaling**：1st Quant 在 Phase 1 deliverable 提过 "back_to_back_half_size" 但 Phase 2 没实施。如果 PM intent 配半 size，是否更优？

---

## 5. 请 2nd Reviewer 输出格式

```markdown
# Q021 2nd Quant Review

## 总体结论
[CONFIRM / CHALLENGE / NEED_MORE_DATA] 关于 1st Quant 的 (a) recommendation

## 方法学审查
- Phase 1 cluster 定义: ...
- Phase 2 patch 正确性: ...
- 全引擎一致性: ...

## 数据归因审查
- Claim A (78% 同峰): ...
- Claim B (2026-03 case): ...
- Claim C (V3 -$9,200): ...
- Claim D (Disaster): ...

## 漏掉的变体 / 需要补做
- ...

## 最终建议
- 保留 SPEC-066 / 改为 V3 / 改为其他 / 暂缓决定
- 理由: ...
```

---

## 6. 时间盒

- **30 分钟版**：只读 §0、§2、§4，并跑一次 prototype 看输出是否 reproducible
- **45 分钟版**：上面 + §3 的 trade-set diff 自己复算 1-2 笔
- **完整版（90 分钟+）**：上面 + 跑 size scaling 变体或 cluster 阈值敏感性

如果 30 分钟版你已能 CHALLENGE 1st Quant 的结论，请直接出 review；不需要走完整版。

---

## 7. Quick reproduce 命令

```bash
arch -arm64 venv/bin/python -m backtest.prototype.q021_phase2_distinct_peak
```

预期输出包含：
- "990 aftermath days across 172 clusters"
- V0/V1/V2/V3 系统层 + IC_HV 子集表
- V1 vs V2 trade-set diff
- 2026-03 double-peak case
- Cluster coverage table
- Disaster window 表

---

## 8. 联系

- 如对 1st Quant 的归因有疑问，请把疑点列入 review，**不要试图替 1st Quant 修复证据**
- 如发现关键 bug（例：Phase 2 patch 没真正生效），请 STOP_REVIEW 并 ping PM
