# SPEC-122 仲裁——存量链回填版（2026-07-05，预注册标准提前触发）

**PM 洞察**: 完整链+希腊值已在每日记录 → 价格记录仪已存在，SPEC-122 归约为"信号日抽取+对比"。存量窗口内重建信号：**12 个 carve 信号日**（2026-06-01~07-02），超过预注册 ≥8 门槛——仲裁当日执行。

## 结果（q087_spec122_backfill_arbitration.csv）

12/12 天真实 debit 均高于两个模型；中位误差（vs mid）：**FLAT −10.0%，CALIB −3.3%**——每一天 CALIB 都更接近真实。

**按预注册标准：PASS-CALIB**（real 更接近 CALIB_tconv 一致口径）→ 触发预注册后果：**BCD 家族复审 packet（carve 处置 + 主格 Q088 提前）→ 外审 → PM**。

## 判定的准确含义（防过度解读）

- 证实的是：FLAT 惯例把 BCD 入场 debit 低估 ~10%，校准定价是可信口径 → SPEC-120 的 CALIB(tconv) P&L 数字（主格 $26.8k/26y、carve $9.4k/26y——**皆为正，但薄**）是当前最可信的模型估计
- 未证实的是：主格（LOW_VOL，VIX<15）的报价几何——窗口内无 LOW_VOL 日，12 天全部为 carve 型 regime（VIX 15-18）；主格外推是推断非测量
- 复审 packet 的实际问题是"薄边际是否值得占用"而非"是否亏损"；2024+ 时代 CALIB 下仍为正、真实 ledger 为正、carve 至今零实盘流水（现金 7/3 才解锁）

## 信号重建 caveat

12 天由 VIX/OHLC 重建（IVR=VIX 252d rank、trend=MA50 gap），非生产 selector 逐日输出（cache 止于 05-27）；SPEC-122 前向实现仍应部署（含生产 selector 判定 + LOW_VOL regime 覆盖 + 长期证据流）。
