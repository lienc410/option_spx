# Q041 Overlap Validation / Reconciliation Protocol

**日期：** 2026-05-03  
**状态：** Quant Researcher — 研究结论  
**前提：** Massive 订阅可保留约 30 天；SPEC-081（历史下载）和 SPEC-082（Schwab IV/Greeks 补采集）正在执行中；Q041 仍处于 Gate 0 pass with constraints / alignment phase，本轮不进入 Phase 1 建模。

---

**一句话总判断：**  
以 **20 个交易日**作为正式校验窗口，剩余 10 天作为修正缓冲；比对的核心是 symbol 命中率 + Schwab `last` vs Massive `close` 价格一致性 + volume rank 相关性；IV 在两边都有后优先验证单位口径；30 天结束时交付一份逐标的的 Reconciliation Table，作为 PM 判断 Phase 1 入场条件的唯一依据。

---

## 1. 建议 Overlap 校验窗口长度

**建议：20 个交易日（约 4 周），剩余 10 天为修正 + 复验缓冲。**

### 为什么不是 10–15 天

10–15 天可以完成 schema 格式验证和一次性 symbol mapping 检查，但对以下场景覆盖不足：

- **低频标的**（ASML / TSM / PANW）：合约稀疏，单日行可能为零。需要足够的交易日才能积累统计意义的样本。
- **月度到期日边界**：5 月第三个周五前后，expiry rollover 会改变合约集合。需要至少跨越一次月度到期才能确认 expiry mapping 在 rollover 时不破。
- **间歇性偏差**：部分数据源问题（如 Massive 延迟、Schwab 盘后修订）不是每天出现，需要更长窗口才能识别 pattern vs 噪声。

### 为什么不用满 30 天

- 30 天窗口的前 5–7 天，SPEC-081 可能还在运行历史批量下载；鲜活的每日并行数据实际上从第 5–7 天才开始可靠积累。
- 剩余 10 天（第 21–30 天）应保留作为：发现问题后的修正时间 + 修正后的复验窗口。如果 20 天的校验干净，10 天缓冲也是整个历史下载的收尾保障。
- 让 Massive 过期前保留修正余地，比把全部时间压在"验证窗口"上更稳健。

### 时间线

| 阶段 | 日期（大约） | 内容 |
|---|---|---|
| Day 1–5 | 2026-05-03 ~ 2026-05-09 | SPEC-081/082 执行；历史批量下载运行中 |
| Day 6–25 | 2026-05-12 ~ 2026-05-30 | **正式 20 交易日并行校验窗口** |
| Day 26–30 | 2026-06-02 ~ 2026-06-06 | 修正 / 口径调整 / 复验；Massive 订阅到期前收尾 |
| Day 30+ | 2026-06-06 以后 | Massive 可取消；Phase 1 入场判断 |

---

## 2. 持续跟踪指标

以下指标分两类：**每日自动跑**（脚本输出 jsonl / csv）和**周度人工 review**。

### 2A. 每日自动指标

| # | 指标 | 计算方式 | 目标阈值 |
|---|---|---|---|
| M1 | **Symbol match rate** | 4元组 (underlying, expiry, C/P, strike) 在 Massive 和 Schwab 当日均有记录的比例 / Schwab 总合约数 | ≥ 90% |
| M2 | **Expiry match rate** | (underlying, expiry) 二元组在两边均有记录的比例 | ≥ 95% |
| M3 | **Strike match rate** | 已对齐 expiry 内，strike 精确匹配（±$0.001 容差）的比例 | ≥ 98% |
| M4 | **Price deviation** | 仅对 `delta 0.10–0.50` 且 `close > $1.00` 的液态段合约，计算 ATM±2 strike 内 `Schwab last` vs `Massive close` 的中位绝对偏差（%） | ≤ 2% |
| M5 | **Volume rank-correlation** | 每个 underlying 内，两边 volume 的 Spearman 秩相关系数 | ≥ 0.75 |
| M6 | **IV completeness rate** | ATM±5 strike 合约中，两边 IV 均存在的比例；比较时 Massive `implied_volatility` 先 `×100` 后再与 Schwab `iv` 对齐（SPEC-082 完成后） | ≥ 90% |
| M7 | **Greeks completeness rate** | Schwab `delta` / `gamma` / `theta` / `vega` 四列均非 null 的比例 | ≥ 85% |
| M8 | **OI completeness rate** | Schwab `open_interest` 非 null 的比例 | ≥ 80% |
| M9 | **SPX/SPXW split stability** | Massive `O:SPX` vs `O:SPXW` 的合约行数比；Schwab `expiry_type=W` vs `M` 的合约行数比；两边比值偏差 | ≤ 10% 偏差 |
| M10 | **BRK/B naming stability** | `BRKB`（Massive）→ `BRK/B`（canonical）映射每日命中率 | 100% |

### 2B. 周度人工 Review

| 指标 | 内容 |
|---|---|
| **IV 单位一致性** | Schwab `iv` 字段（20.027）是否与预期百分比口径一致；若出现值 < 1.0，则已变为小数口径，需修正 |
| **Rollover 边界** | 月度到期日前后，symbol 集合是否平滑过渡（旧合约 volume 归零 → 新合约出现），两边同步 |
| **稀疏标的完整性** | ASML / TSM / PANW 的每周 symbol match rate 单独统计，防被大标的平均掩盖 |
| **Timestamp 日历** | Massive `window_start` 解析出的 ET 日期 与 Schwab `snapshot_date` 是否对齐（需防 DST 切换导致 ±1 小时偏移）|

---

## 3. 两类差异：可吸收 vs 阻止 Stitching

### 3A. 可接受 / 可通过规则吸收的差异

| 差异类型 | 预期原因 | 吸收规则 |
|---|---|---|
| Volume 数量偏差（非秩序） | Massive = 全日成交；Schwab = 16:30 快照累计，盘后成交不含。部分标的盘后成交可达 5–15% | 不做点对点校验，只用 rank-correlation（M5 ≥ 0.75）|
| Schwab `last` vs Massive `close` ≤ 2% | 16:30 快照 vs 真正 EOD 收盘价（4:00 PM ET）之间的盘后波动 | 接受；Phase 1 用 Massive `close` 为价格 canonical |
| OI 历史段全 null | Massive day_aggs 不含 OI | 预期中；Phase 1 OI 分析仅限 Schwab 起始日之后 |
| Greeks 历史段全 null | Massive day_aggs 不含 Greeks | 预期中；同上 |
| IV 历史段全 null | Massive day_aggs 不含 IV | 预期中；同上 |
| 稀疏标的（ASML / TSM 等）单日 0 行 | 低流动性；部分到期日可能全日无成交 | 接受，记录 `sparse_day` 标记；不当作 pipeline 错误 |
| Massive T+1 延迟 | 部分日期 Massive 新文件有 ~1 天延迟 | 接受；以 Schwab 为"今日 canonical"，Massive 落盘后补入 |
| `FB` 行出现在 Massive 历史 | ≤ 2022-06-08 的合约为 `O:FB...` | 已在 SPEC-081 中规定 rename → META；无需后处理 |

### 3B. 会阻止 Stitching 的差异

| 差异类型 | 判断标准 | 处置 |
|---|---|---|
| Symbol match rate < 85%（M1） | OCC 解析逻辑错误，或 underlying 映射缺漏 | 暂停 stitching；定位解析 bug，修正 SPEC-081 |
| Price deviation > 5%（M4，液态段） | 可能数据源污染、复权 / 分拆处理异常、错误日期 join，或未先过滤到 `delta 0.10–0.50 / close > $1.00` 的可交易区间 | 暂停；手动抽查 3–5 合约对照 Schwab 原始 API 响应 |
| Expiry date mismatch（同合约两边 expiry 不同，M2 < 90%） | OCC yymmdd 解析 bug，或 Schwab expiry 格式异常 | 修正解析逻辑；这是基础 key，不修就无法 join |
| Strike 精度错误（M3 < 95%，且非浮点噪声） | OCC 末 8 位 ÷ 1000 实现错误（如整除而非浮点） | 修正 SPEC-081 parse_occ_ticker；可能影响数万条记录 |
| IV 单位混淆且未修正 | Schwab 返回小数（0.20）而非百分比（20.0），或反之，且未在 pipeline 中统一 | 所有 IV 相关分析都错；必须修正后才能进 Phase 1 IV 建模 |
| SPX/SPXW 行数比偏差 > 20%（M9） | SPXW 合约被错误归类、漏掉或重复计 | 排查 `expiry_type` 映射；影响 SPX 链覆盖完整性 |
| Greeks 全 null（SPEC-082 完成后，M7 < 50%） | SPEC-082 实施错误（字段名写错、`rows.append` 漏加） | Review SPEC-082；重新跑 `--force` |

---

## 4. 若发现系统性偏差，修正优先级

**固定顺序，不跳级。**

```
1. Symbol normalization（最高优先）
   → OCC 解析 / BRKB / FB→META / SPXW 映射
   → 理由：所有 join 的基础。symbol 错则一切 downstream 全错。

2. Date / timestamp convention
   → Massive window_start ns UTC → ET 日期；Schwab snapshot_date ET
   → 特别注意 DST 切换（UTC 偏移 -5 → -4 或反向）
   → 理由：日期对不齐则行级 join 全部错位，污染所有数值比较。

3. Price / field mapping
   → 确认 Schwab `last` = 最新成交（同日 canonical），
     Schwab `close` = 前日收盘（≠ 同日 Massive close，不可直接比）
   → 理由：这个混淆是最高频的"看起来偏差很大但其实 key 用错了"情形。

4. IV 单位 / 口径
   → 验证 Schwab `volatility` 字段确实是百分比（20.027 = 20.027%）
   → Massive `implied_volatility` 在 overlap 比较时统一先 `×100`，再与 Schwab `iv` 做同口径比较
   → Pipeline 内统一记录口径；Phase 1 建模层负责换算
   → 理由：单次确认，一次性解决；乘错 100 会让 IV rank 完全失真。

5. Missingness handling
   → 针对每个字段和时间段，写下明确的 null 策略
     （历史段 Greeks = null = 预期；Schwab 段 IV null = 异常）
   → 理由：null 策略不写清楚，Phase 1 建模遇到 NaN 会被迫做临时决定。

6. Canonical source priority
   → 已在 alignment note 中定义；只在出现真实 overlap 冲突时才需调整
   → 理由：这是最后一层决策，优先级低于上面所有步骤。
```

---

## 5. 30 天 Overlap 结束后的最小 Deliverable

**文档名：** `doc/q041_reconciliation_report_YYYY-MM-DD.md`  
**触发条件：** 20 个交易日校验期结束（约 2026-05-30），或 Massive 订阅到期前 7 天（以先到者为准）

**必须包含以下内容，PM 据此做 Phase 1 入场判断：**

---

### Section 1：Symbol Coverage Table（逐标的）

| Underlying | Massive 合约数/日均 | Schwab 合约数/日均 | Symbol Match Rate (M1) | 未命中原因 |
|---|---|---|---|---|
| AAPL | ... | ... | ...% | — |
| SPX | ... | ... | ...% | — |
| BRK/B | ... | ... | ...% | BRKB→BRK/B mapping |
| ... | | | | |
| **全体均值** | | | **目标 ≥ 90%** | |

### Section 2：Price Alignment Table（ATM ± 2 strikes，逐标的）

| Underlying | 样本合约数（仅 `delta 0.10–0.50` 且 `close > $1.00`） | Schwab last vs Massive close 中位偏差% | 最大单日偏差% | 判断 |
|---|---|---|---|---|
| AAPL | ... | ...% | ...% | ✅ / ⚠️ / ❌ |
| ... | | | | |

### Section 3：Volume Consistency Table

| Underlying | Spearman rank-corr (均值，20天) | 最低单日值 | 判断 |
|---|---|---|---|
| AAPL | ... | ... | ✅ / ⚠️ / ❌ |
| ... | | | |

### Section 4：IV Completeness Table（Schwab SPEC-082 之后）

| Underlying | ATM±5 合约数 | IV 非 null 率 | IV 均值（ATM，Massive 先 `×100`） | 单位确认 | 判断 |
|---|---|---|---|---|---|
| AAPL | ... | ...% | ~20% | pct ✅ | ✅ |
| SPX | ... | ...% | ... | | |
| ... | | | | | |

### Section 5：Known Deviations / Corrections Log

每条格式：
```
[编号] 类型 | 发现日期 | 描述 | 分类（可吸收/已修正/阻塞）| 修正方式
```

示例：
```
[D1] IV unit | 2026-05-12 | Schwab iv=20.0 confirmed pct, not decimal | 可吸收 | 文档化，建模层 ÷100
[D2] Volume rank | 2026-05-15 | PANW rank-corr=0.62 on 3 sparse days | 可吸收 | sparse_day 标记，不入 Phase 1 OI filter
```

### Section 6：Stitching Readiness Verdict（每字段 × 每时间段）

| 字段 | 历史段（Massive） | 近期段（Schwab） | Overlap 一致性 | Phase 1 可用 |
|---|---|---|---|---|
| close / last | ✅ Massive canonical | ✅ Schwab last | ✅ ≤2% 偏差 | ✅ |
| volume | ✅ | ✅ | ⚠️ rank-corr only | ✅（不点对点） |
| iv | ❌ 历史无 | ✅ SPEC-082 后 | N/A（无历史对比） | ⚠️（仅近期） |
| delta | ❌ | ✅ | N/A | ⚠️（仅近期） |
| open_interest | ❌ | ✅ | N/A | ⚠️（仅近期） |
| open/high/low | ✅（Massive） | ✅（SPEC-082 后） | 待验证 | ✅（两段均有） |

### Section 7：PM 入场判断门

**所有以下条件满足 → Phase 1 可入场：**

| 条件 | 状态 |
|---|---|
| M1 Symbol match rate ≥ 90%（全体均值） | ☐ |
| M4 Price deviation ≤ 2%（ATM 中位，全体均值） | ☐ |
| M5 Volume rank-corr ≥ 0.75（大标的，AAPL/SPX/QQQ/TSLA）| ☐ |
| M6 IV completeness ≥ 90%（SPEC-082 完成后，ATM±5）| ☐ |
| IV 单位口径已明确（pct 或 decimal，已入文档）| ☐ |
| Section 5 中无 "阻塞" 类偏差 | ☐ |
| Massive 历史批量下载已完成（2022-05-06 至今，17 symbol）| ☐ |

**任一未满足 → 仍处于 alignment phase，不进入 Phase 1 建模。**

---

## 附：Quant 对 30 天并行期的额外价值判断

并行 30 天比原来设想的"短 overlap 抽样"多出一个意外好处：SPEC-082 会让 Schwab 从现在起采集完整 IV / Greeks，这意味着我们将积累 ~20–25 个交易日的完整 Schwab IV 数据。这批数据可以直接用于：

1. **验证 IV 单位**（百分比 vs 小数）——用 ATM 合约的 BS 隐含波动反算，20.027 对应的 BS 价格应与 bid/ask 中间价一致
2. **建立 IV Rank / IV Percentile 的近期基线**——虽然 ~25 天太短做 IV Rank，但至少能确认 IV 的数值范围和分布合理性
3. **为 Phase 1 提前积累 Schwab-first 的 Greeks 序列**

这是并行期的"副产品"，不影响 alignment 结论，但对 Phase 1 有价值。

---
*本文档与 `doc/q041_data_alignment_note_2026-05-03.md` 构成 Q041 alignment phase 的完整工作文件。Phase 1 建模不得早于 Reconciliation Report 完成且 PM 确认入场条件满足。*
