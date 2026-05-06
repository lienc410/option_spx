# Q041 Data Alignment Note — Massive ↔ Schwab Stitching Design

**日期：** 2026-05-03  
**状态：** DRAFT — Quant Researcher  
**前提：** Gate 0 = PASS WITH CONSTRAINTS。Massive 历史段 + Schwab forward 段共同构成 Phase 1 建模数据。本文不涉及策略 alpha，只解决数据口径与拼接规则。

---

**一句话总判断：**  
两边数据结构可对齐，拼接规则明确；但 **Massive day_aggs 无 Greeks / IV / OI**，历史段这三类字段不可用，Phase 1 建模必须以此为约束前提入场。

---

## 1. Contract Identity / Symbol Normalization

### 1.1 Massive OCC ticker 格式

```
O:{underlying}{yymmdd}{C/P}{strike×1000 padded 8-digit}
示例：O:AAPL220520C00120000  → AAPL, 2022-05-20, Call, $120.000
     O:SPXW220506C03400000  → SPXW (SPX 周度), 2022-05-06, Call, $3400
     O:BRKB220506C00300000  → BRK/B, 2022-05-06, Call, $300
```

解析规则（固定后缀）：
- 从末尾取 9 位：最后 8 位 = strike×1000，第 9 位 = C/P
- 从第 9 位前倒数 6 位 = yymmdd
- 剩余前缀 = underlying symbol

### 1.2 两边 symbol 统一表

| Massive OCC 前缀 | Schwab `symbol` | 文件名 | 备注 |
|---|---|---|---|
| `AAPL` | `AAPL` | `AAPL.parquet` | — |
| `SPX` | `SPX` | `SPX.parquet` | **月度到期**（第三个周五） |
| `SPXW` | `SPX` | `SPX.parquet` | **周度到期**，Massive 区分 / Schwab 不区分 |
| `BRKB` | `BRK/B` | `BRK_B.parquet` | Massive 无斜杠 |
| `FB` | — | → `META` | 2022-05-06 ~ 2022-06-08，改名为 META |
| `META` | `META` | `META.parquet` | 2022-06-09 起正常 |
| 其余（MSFT AMZN GOOGL NVDA QQQ TSLA AMD ASML TSM PANW WMT COST JPM） | 同名 | 同名 | 无特殊 |

### 1.3 合并键（canonical join key）

对齐时使用 4 元组：

```
(underlying_norm, expiry_date, option_type, strike)
```

- `underlying_norm`：统一后的大写 underlying，BRK/B → `BRKB`，FB → `META`，SPXW → `SPX`（附加 `is_weekly=True`）
- `expiry_date`：`YYYY-MM-DD` 字符串（Massive 从 yymmdd 转换，Schwab 原生）
- `option_type`：`C` / `P`（Massive OCC 单字母，Schwab `CALL/PUT` 统一为单字母）
- `strike`：float，Massive = OCC 8 位整数 ÷ 1000，Schwab 原生 float

### 1.4 SPXW 处理规则

Massive 对 SPX 区分 `O:SPX...`（月度）和 `O:SPXW...`（周度），但两者在 Schwab 都归属 `symbol=SPX`，靠 `expiry_date` 自然区分（不同日期不会重复）。  
**规则：** 解析 Massive ticker 时，`SPXW` 前缀 → `underlying_norm=SPX, is_weekly=True`；`SPX` 前缀 → `underlying_norm=SPX, is_weekly=False`。拼接时不用 `is_weekly` 做 join key，只做标注。

---

## 2. Field Mapping

### 2.1 最小 Canonical Schema（Phase 1 输入层）

| 字段 | 类型 | Massive | Schwab | 来源规则 |
|---|---|---|---|---|
| `date` | date | `window_start` ns→ET日期 | `snapshot_date` | 两边各用各的 |
| `underlying` | str | OCC前缀（标准化后） | `symbol` | 均可 |
| `option_type` | str C/P | OCC第9位 | `CALL/PUT`→C/P | 均可 |
| `expiry` | date | OCC yymmdd→日期 | `expiry` | 均可 |
| `strike` | float | OCC 8位÷1000 | `strike` | 均可 |
| `close` | float | `close` ✅ | ❌ 无（仅 bid/ask/mid/last 快照） | **Massive 为主（历史）** |
| `open` | float | `open` ✅ | ❌ | **Massive 独有** |
| `high` | float | `high` ✅ | ❌ | **Massive 独有** |
| `low` | float | `low` ✅ | ❌ | **Massive 独有** |
| `volume` | int | `volume` ✅ | `volume` ✅ | **Massive 历史 / Schwab 近期**（不混） |
| `transactions` | int | `transactions` ✅ | ❌ | Massive 独有，Phase 1 可选 |
| `open_interest` | int | ❌ **无** | `open_interest` ✅ | **Schwab 独有**，历史段不可用 |
| `bid` | float | ❌ | `bid` ✅ | **Schwab 独有** |
| `ask` | float | ❌ | `ask` ✅ | **Schwab 独有** |
| `mid` | float | ❌ | `mid` ✅ | **Schwab 独有** |
| `spread_pct` | float | ❌ | `spread_pct` ✅ | **Schwab 独有** |
| `delta` | float | ❌ **无** | `delta` ✅ | **Schwab 独有**，历史段不可用 |
| `iv` | float | ❌ **无** | ❌ **无** | 两边均无（day_aggs 不含 IV；Schwab chain 未采集 IV） |
| `dte` | int | 计算得出（expiry−date） | `dte` ✅ | 均可计算 |
| `is_weekly` | bool | 从 SPXW 前缀推断 | ❌（expiry 可推断） | 标注用 |

### 2.2 关键字段缺口总结

| 缺口 | 影响 |
|---|---|
| **历史 Greeks（delta/gamma/theta/vega）** | 历史段 (~4年) 无法回测 delta-targeting 策略 |
| **历史 IV / IV Rank** | 历史段无 IV Rank/Percentile；需靠 VIX 代理或另购数据 |
| **历史 OI** | 历史段无法做 OI-weighted 分析 |
| **历史 bid/ask** | 历史段无法计算实际成本 spread；只能用 close 近似 |
| **Schwab 无 OHLC** | 近期段（Schwab only）无每日 open/high/low |

> **Phase 1 入场约束（必须接受）：**  
> 历史段建模只能用 close / volume / OHLC（价格类）；Greeks 和 IV 仅在 Schwab 采集起始日（2026-05-03）之后可用。Phase 1 模型如需历史 Greeks，需另行评估数据源。

---

## 3. Overlap Window Design

### 3.1 两段边界定义

| 段 | 数据来源 | 时间范围 |
|---|---|---|
| 历史段 | Massive day_aggs | 2022-05-06 → overlap end |
| 近期段 | Schwab forward collector | 2026-05-03 → 持续更新 |
| Overlap 窗口 | 两边同时有数据 | 2026-05-03 起，Massive 延迟 ~1-2 天 |

### 3.2 Overlap 长度建议

**目标：15 个交易日（约 3 周）**。  
理由：足够发现系统性偏差（价格异常、symbol 缺失、字段格式差异），但不浪费大量对比时间。

实际执行：
- Schwab 已从 2026-05-03 起每日采集
- Massive 新文件一般 T+1 可用
- 到 2026-05-23 左右可积累满 15 个交易日 overlap

### 3.3 Overlap 期间比对字段

优先级从高到低：

1. **合并键命中率**：同一 (underlying, expiry, option_type, strike) 在两边都能找到 ≥90% 的合约
2. **close vs mid/last**：Schwab mid 对比 Massive close，偏差控制
3. **volume**：方向一致性（Massive 全日 vs Schwab 16:30 快照，数量接近但非等值）
4. **open_interest**：仅 Schwab 有，作为基线建立，确认采集稳定

---

## 4. Acceptable Tolerance / Reconciliation Rules

| 指标 | 可接受阈值 | 若超出则 |
|---|---|---|
| Underlying symbol match rate | 100%（映射后） | 检查 FB/BRKB 映射逻辑 |
| OCC join key 命中率（expiry / strike / type 三合一） | ≥ 90% | 检查 strike rounding 和 OCC 解析 |
| Expiry match rate | ≥ 95% | 检查日历转换（yymmdd 解析 bug） |
| Strike match rate | ≥ 98%（±$0.001 容差） | 检查除以 1000 精度 |
| Price 偏差（Massive close vs Schwab mid） | ≤ 2% on median ATM contracts | 若 > 5% 则暂停 |
| Volume 偏差 | 不做硬性要求（两边采集口径不同） | 用 Spearman rank-correlation ≥ 0.8 作软性检查 |
| IV 偏差 | 不适用（Massive 无 IV） | — |
| Delta 偏差 | 不适用（Massive 无 delta） | — |
| OI 缺失率（Massive 历史段） | 100% 缺失，预期中 | Phase 1 必须接受 |
| SPXW 命中率（Massive vs Schwab expiry） | ≥ 90% | 检查周度 expiry 转换 |

**volume 对比说明：**  
Massive = 全日成交量，Schwab = 16:30 快照时的 cumulative volume。在收盘后采集时，两者理论上接近但非等值。不做点对点校验，用 rank-correlation 检验方向一致性即可。

---

## 5. Stitching Rule

### 5.1 主权规则

| 时间段 | Canonical 来源 | 备注 |
|---|---|---|
| 历史段（< 2026-05-03） | **Massive** | OHLCV；Greeks/OI/bid-ask 不可用，置 null |
| 近期段（≥ Schwab start） | **Schwab** | bid/ask/delta/OI 全有；open/high/low 置 null |
| Overlap 同一日期 | **Schwab 优先**（字段更丰富） | Massive open/high/low 可作补充合并 |

### 5.2 字段级决策树（overlap 期间同字段两边都有）

```
if field in (close, volume):
    if abs(massive_val - schwab_val) / schwab_val < 0.02:
        use schwab_val   # Schwab 为近期 canonical
    else:
        flag as reconciliation_issue; use schwab_val; log warning
else if field in (bid, ask, mid, delta, open_interest):
    always use schwab_val   # Massive 无此字段
else if field in (open, high, low):
    use massive_val if schwab_val is null   # Schwab 无 OHLC
```

### 5.3 Phase 1 降级处理（字段长期缺失）

| 缺失字段 | 降级方案 |
|---|---|
| 历史 delta | 用 strike / S / expiry 计算理论 BS delta（需 underlying price + IV） |
| 历史 IV | 用 VIX / VIX3M 作为 proxy；或只在 Schwab 段做 IV-sensitive 建模 |
| 历史 OI | 跳过 OI filter；或只用近期 OI 建立基线 |
| 历史 bid/ask | 用 close×liquidity_proxy（volume）近似 spread；需标注误差 |
| 近期 open/high/low | 跳过日内区间分析；仅用 snapshot 价格 |

---

## 6. Final Verdict

**`ready to collect and align`**

理由：
- 两边 symbol 映射规则完整明确（SPXW / BRKB / FB→META）
- OCC ticker 解析规则确定，可实现 100% 机械解析
- 字段缺口（Greeks / IV / OI）已知且有降级方案
- 对齐验证逻辑可执行（5个命中率指标 + price rank-corr）

**条件：**
- Phase 1 建模设计必须以"历史段无 Greeks/IV/OI"为硬约束输入
- Overlap 验证需在 2026-05-23 前完成（积累 15 个交易日），Phase 1 建模不早于此开始

---

## 附：立即执行项

1. **SPEC → Developer**：`download_massive.py` 批量下载 2022-05-06 至今，按标的 parquet，含 FB→META 映射  
2. **Overlap 验证脚本**（Quant 或 Developer）：每周运行一次，输出上述 6 项命中率指标  
3. **Schwab IV 字段确认**（Quant）：确认 `_parse_chain_response` 是否丢弃了 IV 字段；若有则补采集  

---
*本文档是 Q041 Phase 1 建模的数据前提文件，应在 Phase 1 Spec 起草前由 PM 确认。*
