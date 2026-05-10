# Q054 Pilot — UW Web Export 操作指引

**目标**：在 Retail Basic 订阅下，手动 export 90 天 unusual options flow 数据，供 hit-rate 研究使用。
**预计时间**：60-90 分钟（你 PM 端）
**输出落点**：`data/q054_flow_pilot/<segment>.csv`（每段一个文件，命名见下）

---

## Step 1 — 打开 UW Flow Alerts 页面

URL: `https://unusualwhales.com/option-flow-alerts`（或左侧菜单 "Flow Alerts"）

确认 Retail Basic 能访问该页（如果跳转到付费墙，请告知，我们改路径）。

## Step 2 — 设置过滤条件（**所有 segment 用同一组 filter**）

| Filter | 值 | 说明 |
|---|---|---|
| Min Premium | **$200,000** | 过滤小单 |
| Min Volume / OI Ratio | **1.0** | 偏向 opening trades（不是平仓） |
| Min DTE | **7** | 跳过 0DTE / 1DTE 噪声 |
| Max DTE | **45** | 不要 LEAP（信号噪声） |
| OTM Range | **2% – 15%** | OTM 太近 = ATM hedge；太远 = 彩票 |
| Issue Type | **Common Stock + ADR** | 暂不含 ETF / Index（先建立 single-name 基线） |
| Rule Name | **RepeatedHits, RepeatedHitsAscendingFill, RepeatedHitsDescendingFill** | 多次重复触及（最常见 unusual 形态） |
| Type | **All** (call + put 都要) | 后面按 ask/bid 分 bullish/bearish |

> 如果 UI 上某项 filter 不存在或命名不同，按最接近的语义选；保持其余一致即可。

## Step 3 — 分段 export（90 天分 9 段，每段 10 个交易日）

UW 的 list view 通常只能一次显示数百-数千行，**所以必须分段拉**。日期窗口分割：

| Segment | Start | End | 文件名 |
|---|---|---|---|
| 1 | 2026-05-01 | 2026-05-09 | `seg_01_20260501_20260509.csv` |
| 2 | 2026-04-21 | 2026-04-30 | `seg_02_20260421_20260430.csv` |
| 3 | 2026-04-09 | 2026-04-20 | `seg_03_20260409_20260420.csv` |
| 4 | 2026-03-30 | 2026-04-08 | `seg_04_20260330_20260408.csv` |
| 5 | 2026-03-20 | 2026-03-29 | `seg_05_20260320_20260329.csv` |
| 6 | 2026-03-10 | 2026-03-19 | `seg_06_20260310_20260319.csv` |
| 7 | 2026-02-26 | 2026-03-09 | `seg_07_20260226_20260309.csv` |
| 8 | 2026-02-15 | 2026-02-25 | `seg_08_20260215_20260225.csv` |
| 9 | 2026-02-05 | 2026-02-14 | `seg_09_20260205_20260214.csv` |

> 若 UI 最大回溯 < 90 天（比如只到 30 天），就拉到上限即可，segment 数对应减少。文件命名仍按上表保留次序。

## Step 4 — Export 每段为 CSV

每段操作：
1. 设定日期 from/to（按上表）
2. 点击 "Export CSV"（或导出按钮）
3. 文件落到 `/Users/lienchen/Documents/workspace/SPX_strat/data/q054_flow_pilot/seg_NN_YYYYMMDD_YYYYMMDD.csv`
4. 命名严格按上表，否则脚本不会自动 pick up

## Step 5 — 必须包含的列（最低要求）

如果 UW export 列可选，**请勾选以下列**（如果默认全包含就跳过此步）：

```
ticker, created_at (or tape_time), rule_name, option_chain, type (call/put),
strike, expiry, dte, price, underlying_price,
volume, open_interest, volume_oi_ratio,
total_premium, total_ask_side_prem, total_bid_side_prem,
trade_count, has_sweep, has_floor, has_multileg, has_singleleg,
sector, issue_type
```

最关键的 5 列：`ticker`、`created_at`、`total_ask_side_prem`、`total_bid_side_prem`、`underlying_price`。其他列若 UI 不给可缺，但前 5 列缺任何一个，研究无法做。

## Step 6 — 完成后通知

把文件落到上面目录后，发我一句"export 完成"或者贴 `ls data/q054_flow_pilot/` 输出。我会跑 `research/q054/q054_pilot_hit_rate.py`，30 分钟内出结果备忘 `task/q054_pilot_results_2026-05-10.md`。

---

## 备注 / 故障排查

- **如果 UW export 是 zip 而非 CSV**：解压后保留 csv 文件即可。
- **如果某段无数据返回**（filter 太严）：略过该段即可，最终样本量会少但不影响方法。
- **如果 `total_ask_side_prem` / `total_bid_side_prem` 列名不同**：UW UI 上常见别名 `ask_side_premium` / `bid_side_premium`，保留即可，脚本会做名称匹配。
- **如果 `issue_type` 列缺失或筛不掉 ETF**：脚本会用 ticker 黑名单（SPY/QQQ/IWM/...）二次过滤。
- **本研究不用 `dark pool` 数据**——仅 options flow alerts。下一阶段（如果 pilot pass）才考虑 dark pool 增量。

预祝顺利。需要任何 UI 上的术语翻译或 filter 名称澄清随时问。
