# SPEC-082: Schwab Chain 补采集 IV + Full Greeks + expiry_type + OHLC + last

Status: DONE

## 目标

`_parse_chain_response` 当前丢弃了 Schwab 每个合约返回的大量字段。本 Spec 将以下 10 个字段补入采集流水线，使 Q041 forward-collection parquet 从 2026-05-03 起包含完整 Greeks、IV、OHLC 及 last，为后续项目做准备：`volatility`（IV）、`gamma`、`theta`、`vega`、`rho`、`expirationType`、`highPrice`、`lowPrice`、`openPrice`、`closePrice`、`last`。

## 背景

- 确认方式：2026-05-03 实测 Schwab `/marketdata/v1/chains` 响应，`volatility: 20.027`（ATM 1-DTE AAPL call），单位为百分比（20.027 = 20.027%）
- `expirationType` 返回 `'W'`（weekly）/ `'M'`（monthly）/ `'S'`（standard），可直接区分 SPX 与 SPXW，替代 alignment note 中靠 OCC 前缀推断的方案

## 修改范围

**仅两处文件，不涉及 engine / signals / web / notify：**

1. `schwab/client.py` — `_parse_chain_response`
2. `research/q041/collect_chains.py` — `_build_chain_frame`

## 接口定义

### 1. `schwab/client.py` — `_parse_chain_response`（line 251–262）

在 `rows.append({...})` 中新增 11 个字段：

```python
rows.append({
    # ... 现有字段不变 ...
    "iv":          contract.get("volatility"),       # 百分比，e.g. 20.027
    "gamma":       contract.get("gamma"),
    "theta":       contract.get("theta"),
    "vega":        contract.get("vega"),
    "rho":         contract.get("rho"),
    "expiry_type": contract.get("expirationType"),   # 'W' / 'M' / 'S'
    "open":        contract.get("openPrice"),
    "high":        contract.get("highPrice"),
    "low":         contract.get("lowPrice"),
    "close":       contract.get("closePrice"),       # 前日收盘价
    "last":        contract.get("last"),             # 最新成交价
})
```

**字段命名说明：**
- `volatility` → 存为 `iv`，避免与 underlying volatility 混淆
- `expirationType` → 存为 `expiry_type`，snake_case 与其他字段一致
- `openPrice` / `highPrice` / `lowPrice` / `closePrice` → 去掉 `Price` 后缀，统一为 `open` / `high` / `low` / `close`

### 2. `research/q041/collect_chains.py` — `_build_chain_frame`

**`cols_order` 列表末尾追加：**

```python
cols_order = [
    # ... 现有 14 列不变 ...
    "iv",
    "gamma",
    "theta",
    "vega",
    "rho",
    "expiry_type",
    "open",
    "high",
    "low",
    "close",
    "last",
]
```

**类型转换（在现有 `pd.to_numeric` 块之后追加）：**

```python
for col in ("iv", "gamma", "theta", "vega", "rho", "open", "high", "low", "close", "last"):
    df[col] = pd.to_numeric(df[col], errors="coerce")
# expiry_type 保持 str，不转换
```

## 边界条件与约束

- 已有 parquet（2026-05-03 首日采集）的新字段列值为 `NaN`（历史行无此数据）— 可接受，Phase 1 只用 Schwab 起始日之后的数据
- `iv` 单位：百分比原值（不除以 100），与 Schwab 原始值保持一致；Phase 1 建模层自行换算
- `expirationType` 在非期权合约响应中可能为 `None` → `errors="coerce"` 或 str 保留 `None`，均可
- 不修改 `get_option_chain`（主策略调用路径），其调用方只用 `delta`，新增字段不影响
- 不修改已有列顺序，新字段只追加在末尾

## 不在范围内

- 历史段（Massive）IV 回填 — 另行评估
- 已有 parquet 的 schema migration — 追加列后 pandas 读旧文件会自动填 NaN，无需迁移

## Prototype

无（字段已实测存在，直接补采集）

## 验收标准

- AC1：`python -m research.q041.collect_chains --force --verbose` 运行成功（当日覆盖写入）
- AC2：`data/q041_chains/YYYY-MM-DD/AAPL.parquet` 包含全部新增列（`iv`、`gamma`、`theta`、`vega`、`rho`、`expiry_type`、`open`、`high`、`low`、`close`、`last`），且 `iv` 列无全 NaN
- AC3：`iv` 列值范围合理：10 ≤ iv ≤ 200（百分比，极端行情外）
- AC4：`expiry_type` 列出现 `'W'` 和 `'M'` 两种值（AAPL 同时有周度和月度到期）
- AC5：SPX parquet 的 `expiry_type` 出现 `'W'`（SPXW）和 `'M'`（月度），不再需要从文件名推断
- AC6：`close` 列（前日收盘）与 `last` 列（最新成交）均有值，且 `close` ≠ `last`（非同一字段）
- AC7：现有主策略调用 `get_option_chain` 行为不变（新字段不影响调用方）

## Review

- 结论：PASS
- AC3 说明：`iv_min=-999.0` 是 Schwab API 哨兵值（"IV 无法计算"），非实现 bug。Spec AC3 阈值规格错误。Quant Fast Path 修正已在 `collect_chains.py:195` 追加 `df["iv"] = df["iv"].where(df["iv"] > 0, other=pd.NA)`，清洗哨兵后 AC3 不再适用（实际 IV 值范围可超过 200 for deep-OTM）。
- AC4 说明：Schwab `expirationType='S'` = Standard（第三周五月度到期），`'M'` = End-of-month（极少见）。实测 `['S','W']` 完全正确，Spec AC4 对枚举值的假设有误。代码无需修改，口径已更新。
- 附注：`expiry_type` 枚举完整映射：`W`=Weekly / `S`=Standard月度 / `Q`=Quarterly / `M`=End-of-month
