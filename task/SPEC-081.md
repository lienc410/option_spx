# SPEC-081: Q041 Massive Historical Bulk Download (`download_massive.py`)

Status: DONE

## 目标

实现 `research/q041/download_massive.py`，从 Massive.com Flat Files S3 批量下载 Q041 whitelist 标的的历史期权日度 OHLCV 数据（2022-05-06 至今），输出为按标的分区的 parquet 文件，供 Q041 Phase 1 数据对齐与建模使用。

## 背景

- Massive Flat Files 路径：`s3://flatfiles/us_options_opra/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz`
- 每日一个全市场文件，约 250K 行、2.8 MB，包含所有期权合约的 OHLCV
- 凭证存于 `.env`：`MASSIVE_S3_ACCESS_KEY_ID`, `MASSIVE_S3_SECRET_ACCESS_KEY`, `MASSIVE_S3_BUCKET=flatfiles`, `MASSIVE_S3_ENDPOINT=https://files.massive.com`
- 使用 `boto3` + `Config(signature_version='s3v4')`，经测试 GetObject 可成功下载（无需额外 auth）

## 接口定义

### 输入

- `.env` 中的 S3 凭证（已测试可用）
- `research/q041/whitelist.py` 中的 `WHITELIST`（17 个标的）
- 命令行参数：
  - `--start YYYY-MM-DD`（默认 `2022-05-06`，Massive 最早可用日期）
  - `--end YYYY-MM-DD`（默认今天）
  - `--symbols`（可选，覆盖 whitelist，空格分隔）
  - `--force`（重新下载已存在的日期，默认跳过）
  - `--verbose`

### 输出

```
data/q041_historical/{SYMBOL}.parquet
```

- 每个标的一个 parquet 文件，行为该标的所有历史日期的期权合约记录
- 追加写入（append）：运行多次不重复，已有日期默认跳过（通过 `date` 列去重）
- 示例：`data/q041_historical/AAPL.parquet`，`data/q041_historical/SPX.parquet`

### Canonical Schema（每行一条期权合约快照）

| 列名 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `date` | str `YYYY-MM-DD` | `window_start` ns→ET日期 | 交易日期 |
| `underlying` | str | 从 OCC ticker 解析 + 标准化 | 见 symbol mapping |
| `option_type` | str `C`/`P` | OCC ticker 第 9 位从末 | — |
| `expiry` | str `YYYY-MM-DD` | OCC ticker yymmdd→日期 | — |
| `strike` | float | OCC ticker 末 8 位 ÷ 1000 | — |
| `open` | float | Massive `open` | — |
| `high` | float | Massive `high` | — |
| `low` | float | Massive `low` | — |
| `close` | float | Massive `close` | — |
| `volume` | int | Massive `volume` | — |
| `transactions` | int | Massive `transactions` | — |
| `occ_ticker` | str | Massive `ticker` 原值 | 保留原始 OCC ticker 供 join |

## Symbol Mapping（OCC前缀 → underlying）

| OCC 前缀 | `underlying` 输出 | 条件 |
|---|---|---|
| `SPXW` | `SPX` | 无条件；附加 `is_weekly=True`（不是 join key，仅标注） |
| `SPX` | `SPX` | — |
| `BRKB` | `BRK/B` | — |
| `FB` | `META` | 仅 date ≤ 2022-06-08；date ≥ 2022-06-09 正常为 `META` |
| 其余 | 同 OCC 前缀 | AAPL/MSFT/AMZN/GOOGL/NVDA/META/QQQ/TSLA/AMD/ASML/TSM/PANW/WMT/COST/JPM |

**不在 whitelist 的标的全部过滤掉，不写入 parquet。**  
过滤在读取每个 CSV.gz 后立即执行，避免内存膨胀。

## 核心逻辑

### OCC Ticker 解析函数

```python
def parse_occ_ticker(ticker: str) -> dict | None:
    """
    Input:  "O:AAPL220520C00120000"
    Output: {underlying_raw, expiry, option_type, strike}
    Returns None if parse fails.
    """
    # 去掉 "O:" 前缀
    # 末尾 8 位 = strike 整数部分
    # 第 9 位从末 = C/P
    # 前 9 位之前的末 6 位 = yymmdd
    # 剩余前缀 = underlying_raw
```

### 主流程

```
for date in trading_days(start, end):
    if all symbols already exist for this date → skip (unless --force)
    download s3://flatfiles/us_options_opra/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz
    parse OCC tickers → filter to whitelist
    apply symbol mapping (BRKB→BRK/B, FB→META, SPXW→SPX)
    for each underlying in whitelist:
        append rows to data/q041_historical/{SYMBOL}.parquet
    log: date | rows_total | rows_kept | symbols_found | errors
```

### 断点续传（skip 逻辑）

- 启动时读取每个已有 parquet 的 `date` 列，建立 `{symbol: set(dates)}` 字典
- 找出已有数据中的 **最后一个日期**（`max_existing_date`）
- 若某日期 < `max_existing_date` 且在所有 whitelist symbol 中均已有记录 → 跳过下载
- 若某日期 == `max_existing_date` → **强制覆盖**（防止上次运行中断导致数据不全）
- 若部分 symbol 缺失该日期（且 < max_existing_date）→ 仍下载，补写缺失 symbol
- `--force` 时：全部日期覆盖（忽略上述规则）

### Parquet 写入策略

每次处理完一个日期，将该日期的新行追加写入各 symbol parquet。  
使用 `pyarrow` 写入，保证 schema 一致性。

## 边界条件与约束

- 仅下载交易日（周一至周五）。跳过规则：若 CSV.gz 不存在（假期）→ 静默跳过，记录 `holiday_skip`
- 文件不存在（404 / NoSuchKey）→ 静默跳过（假期 or Massive 延迟），不报错
- 网络超时（30s per file）→ 重试 3 次，仍失败则记录 error，继续下一日期
- S3 Rate limit：无需 pause（Flat Files 不受 API rate limit 限制）
- `data/q041_historical/` 目录已在 `.gitignore` 中（与 `data/q041_chains/` 同级规则，若不在则需添加）
- 不修改 `whitelist.py`、`collect_chains.py`、engine、signals 任何生产代码

## 不在范围内

- 数据质量验证（overlap 与 Schwab 的对齐校验）→ 由单独脚本完成
- Greeks / IV 计算 → Phase 1 另行评估
- 增量调度（launchd cron）→ 手动运行即可，不需要 plist

## Prototype

无（下载脚本逻辑直接明确，不需要先验证方向）

## 验收标准

- AC1：`python -m research.q041.download_massive --start 2022-05-06 --end 2022-05-10 --verbose` 运行成功，产出 17 个 symbol parquet 文件（`data/q041_historical/`）
- AC2：AAPL.parquet 含 2022-05-06 ~ 2022-05-10 的行，schema 与上表一致
- AC3：FB 行被重命名为 META，underlying 列值为 `META`，occ_ticker 保留原始 `O:FB...`
- AC4：SPXW 合约 underlying 列为 `SPX`，occ_ticker 保留 `O:SPXW...`
- AC5：BRK/B 的 parquet 文件为 `BRK_B.parquet`（safe filename），underlying 列为 `BRK/B`
- AC6：重复运行相同日期范围 → 不新增重复行（skip 逻辑生效）
- AC7：`--force` 重跑相同日期范围 → 行数与首次运行相同（覆盖而非追加两份）
- AC8：不在 whitelist 的标的（如 `O:TSLA` 不在旧白名单... 实际均在）→ 过滤后不出现在 parquet 中
- AC9：`_summary.json`（或 `_download_log.json`，可选）记录每次运行的日期范围、总行数、per-symbol 行数、跳过的日期

## Review

- 结论：PASS
- AC1–AC9 全通过（含小窗验收 2022-05-06~2022-05-10 + 全量下载）
- 代码核心逻辑正确：OCC 解析、symbol mapping（FB→META/SPXW→SPX/BRKB→BRK/B）、断点续传（max_existing_date 强制覆盖）、parquet 去重 merge 均无问题
- 非阻塞观察：`_normalize_day_frame` 中 `occ` 变量在第 243/254 行重复赋值但语义不同（一次是去前缀版本，一次是原始版本），不影响正确性，可在后续重构时清理
