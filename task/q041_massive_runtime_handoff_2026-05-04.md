# Q041 Massive / Forward Runtime Handoff

**日期：** 2026-05-04  
**角色：** Developer → Quant Researcher  
**范围：** Q041 当日数据补跑、Massive snapshot collector 落地、old Air 定时任务状态

---

## 1. 结论

Q041 当前有两条可用的当日数据流，均已验证：

- **Schwab forward chain collector（old Air）**：已补跑完成，`17/17` 成功
- **Massive option snapshot collector（old Air）**：已落地并完成全量 run，`17/17` 成功

历史 Massive S3 flatfile 路径仍是 **T+1 语义**，**2026-05-04 当天的 day_aggs 文件在晚间仍未发布**，因此不能把 same-day historical 视为 close 后即可用。

---

## 2. 当日数据状态

### A. Schwab forward chains（old Air canonical）

路径：

```text
/Users/macbook/SPX_strat/data/q041_chains/2026-05-04/
```

结果：

- 产物：
  - `17` 个 symbol parquet
  - `_underlying.parquet`
  - `_summary.json`
- `_summary.json` 关键值：
  - `rows_calls = 30525`
  - `rows_puts  = 30525`
- 总计：`61050` chain rows

白名单（当前 17）：

- `AAPL`
- `MSFT`
- `AMZN`
- `GOOGL`
- `META`
- `NVDA`
- `BRK/B`
- `WMT`
- `COST`
- `JPM`
- `SPX`
- `QQQ`
- `TSLA`
- `AMD`
- `ASML`
- `TSM`
- `PANW`

备注：

- old Air 已同步到当前 Q041 whitelist 与 `collect_chains.py` 版本
- `collect_chains.py` 现已包含 `iv / gamma / theta / vega / rho / expiry_type / OHLC / last` 等列

### B. Massive snapshot（old Air canonical for delayed snapshot collection）

脚本：

```text
research/q041/collect_massive_snapshot.py
```

路径：

```text
/Users/macbook/SPX_strat/data/q041_massive_snapshot/2026-05-04/
```

结果：

- `ok = 17`
- `errors = 0`
- `total_rows = 95756`

关键样本：

- `SPX`: `29948 rows / 120 pages`
- `QQQ`: `10838 rows / 44 pages`
- `META`: `7882 rows / 32 pages`
- `TSLA`: `5726 rows / 23 pages`

summary 文件：

```text
/Users/macbook/SPX_strat/data/q041_massive_snapshot/2026-05-04/_summary.json
```

采集字段（每行一条 contract snapshot）重点包括：

- `delta / gamma / theta / vega / rho`
- `implied_volatility`
- `open_interest`
- `day_*`
- `last_trade_*`
- `last_quote_*`
- `underlying_price`

特别说明：

- `BRK/B` API path 已映射为 `BRK.B`
- 文件名仍保持 `BRK_B.parquet`
- `SPX` Massive 返回的 underlying ticker 是 `I:SPX`

### C. Massive historical flatfiles（主力机）

脚本：

```text
research/q041/download_massive.py
```

本次执行：

```bash
arch -arm64 venv/bin/python -m research.q041.download_massive --end 2026-05-04
```

结果：

- `kept = 80551`
- `skipped = 998`
- `holidays = 39`
- `errors = 0`

关键事实：

- `2026-05-04` 的 flatfile：

```text
us_options_opra/day_aggs_v1/2026/05/2026-05-04.csv.gz
```

在本次执行时仍不存在（`NoSuchKey` / `holiday_skip` 语义）

结论：

- Massive historical `day_aggs_v1` **不能当作 16:30–16:45 close 后立即可用**
- 这条线应按 **T+1** 使用

---

## 3. old Air 调度状态

### 已加载

#### `com.spxstrat.q041_collect`

- command:

```text
/Users/macbook/SPX_strat/venv/bin/python -m research.q041.collect_chains
```

- schedule: `16:30 ET`
- 状态：已 loaded

#### `com.spxstrat.q041_massive_snapshot`

- command:

```text
/Users/macbook/SPX_strat/venv/bin/python -m research.q041.collect_massive_snapshot
```

- schedule: `16:35 ET`
- 状态：已 loaded
- 已手动 kickstart 验证通过

### 已创建但未加载

#### `com.spxstrat.q041_massive_historical`

- command:

```text
/Users/macbook/SPX_strat/venv/bin/python -m research.q041.download_massive
```

- schedule: **`08:15 ET`**
- 状态：**未 loaded**

原因：

- same-day flatfile 不可依赖
- 已将原先 close 后窗口改为 `T+1 08:15`
- 保留给后续是否需要 old Air 自动补齐 historical 由 PM/Quant 再决定

---

## 4. 新增 collector 行为说明

### `collect_massive_snapshot.py` summary 语义更新

如果某 symbol 在该日 parquet 已存在，且本次运行未加 `--force`：

- `pages = null`
- `reused = true`

不再使用误导性的：

- `pages = 0`

示例（old Air 已验证）：

```json
{
  "symbol": "AAPL",
  "rows": 3184,
  "pages": null,
  "reused": true,
  "error": null
}
```

这点对 Quant 的意义：

- `pages = null + reused=true` 表示“本次未重新抓取，复用了已有当日 parquet”
- 不应把它解读为接口只返回了 0 页

---

## 5. Quant 可直接使用的 canonical 路径

### 当日 Schwab chains（canonical）

```text
/Users/macbook/SPX_strat/data/q041_chains/2026-05-04/
```

### 当日 Massive snapshots（canonical）

```text
/Users/macbook/SPX_strat/data/q041_massive_snapshot/2026-05-04/
```

### 历史 Massive day aggs（主力机）

```text
/Users/lienchen/Documents/workspace/SPX_strat/data/q041_historical/
```

---

## 6. 对 Quant 的实际含义

当前 Q041 数据面已经形成三层：

1. **历史段（Massive day_aggs）**
   - 2022-05-06 → 2026-05-01 当前确定可用
   - `2026-05-04` same-day historical 仍不可用

2. **当日 delayed chain snapshot（Massive snapshot）**
   - Greeks / IV / OI 可用
   - old Air 已能每日 `16:35 ET` 自动采

3. **当日 Schwab full chain**
   - 更接近 live forward accumulation
   - old Air 已能每日 `16:30 ET` 自动采

因此 Quant 现在可以做的事是：

- 直接把 `2026-05-04` 的 Massive snapshot 与 Schwab forward chain 做当日横向比对
- 不要把 same-day Massive historical 缺失误解为 collector 故障
- 若需要 close 后近期 Greeks / IV / OI，优先使用：
  - `data/q041_massive_snapshot/2026-05-04/`
  - `data/q041_chains/2026-05-04/`

---

## 7. 未完成 / 后续决策点

1. `com.spxstrat.q041_massive_historical` 是否需要在 old Air 上正式加载
   - 目前未加载
   - 时间已调到 `08:15 ET`

2. 是否需要把 `Massive snapshot` 的当天产物也定期复制回主力机，作为 Quant 的默认消费路径
   - 当前两边可分别访问，但未做自动同步

3. 若 Quant 后续需要 stitched dataset：
   - 现在应把 Massive snapshot 明确看作 **当日 delayed greeks/IV/OI source**
   - 把 Massive historical 明确看作 **T+1 historical OHLCV source**

---

**handoff 完成。**
