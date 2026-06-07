# SPEC-114 — Q041 Chain Sanity (replace alignment) + SPX/QQQ Retry Guard

**Type**: data infrastructure / monitoring
**Date**: 2026-06-06
**Status**: **RATIFIED** by PM 2026-06-06 (§8 Q2 "可以开始" + Q4 "自动检查") per `research/q041/q041_alignment_conclusion_2026-06-06.md`.
**Cross-reference**: [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md) §7 Guardrail-1/-2.
**Parent**: `research/q041/daily_alignment_check.py` (replace) + `research/q041/collect_chains.py` (extend).
**Owner**: Quant Researcher (draft) → Developer (impl).

---

## 0. TL;DR

Massive 订阅 6/3 last run; dual-source alignment 不再有效。把 daily alignment job 改造成 **Schwab-only chain sanity** monitor，再给 `collect_chains.py` 加 **SPX/QQQ retry guard + Telegram alert**。

两件一起做，因为它们共享同一个 Telegram 告警通道、共享同一份 17-symbol whitelist，分两个 SPEC 是过度切片。

---

## 1. Background

Q041 alignment 18 日验证（5/4–6/3）verdict: Schwab single-source production-ready。两个非 verdict 但 must-have 的发现：

1. **Schwab 偶发缺 SPX/QQQ chain** — 18 日中 2 次（5/12, 5/15），rate = 11.1%。Q041 SPX CSP Δ0.20 DTE30 是 formal candidate，SPX chain missing 当天无法生成信号。
2. **Massive 已停** → daily_alignment_check.py 6/4 起每天写 `missing_data:massive` 一条 noise，且 dual-source 的 M1/M4/M6 三指标失去 cross-source 意义。alignment job 已临时 unload（2026-06-06 ops），等 SPEC-114 deploy 后由 chain_sanity job 替代。

---

## 2. Specification

### 2.1 Part A — `daily_chain_sanity.py`（替换 `daily_alignment_check.py`）

**新文件**: `research/q041/daily_chain_sanity.py`
**旧文件归档**: `daily_alignment_check.py` → `research/q041/_archived/daily_alignment_check.py.2026-06-06` (保留 read-only reference)
**输出文件**: `data/q041_chain_sanity_daily.jsonl` （旧 `q041_overlap_daily.jsonl` 停写）

**检查项**:

| 指标 | 定义 | Alert 阈值 |
|---|---|---|
| **S1 symbol completeness** | Schwab 当日成功收集的 whitelist symbol 数 / 17 | < 17 (any missing) |
| **S2 chain row count anomaly** | per-symbol row count vs **7-day rolling median** | row_n < 0.50 × median OR > 2.0 × median |
| **S3 IV completeness** | 0.25-0.75 \|Δ\| 区间合约 IV 字段非空率（继承自 alignment M6） | < 95% |
| **S4 underlying EOD presence** | `_underlying.parquet` 存在且 17 个 symbol 都有 EOD bar | < 17 underlying rows |

**Telegram 报告**（每日 daily report，同原 alignment 格式）:

```
📋 Q041 Chain Sanity {date}
S1 symbol cov:    17/17 ✅
S2 row anomaly:   0 sym out of band ✅   (per-sym median±50%)
S3 IV complete:  100.0% ✅
S4 EOD presence:  17/17 ✅
```

Alert（仅在有 fail 时单独 push）:
```
⚠ Q041 Chain Sanity Alert {date}
S1: missing symbols: [SPX, QQQ]
S2: row anomaly: AAPL n=1800 vs median 2870 (63% of median)
```

**Schedule**: 16:45 ET daily (与原 alignment 同时段, after `q041_collect` 16:30 ET 完成)

### 2.2 Part B — `collect_chains.py` SPX/QQQ retry guard

**现状** (`research/q041/collect_chains.py`): 每个 whitelist symbol 调一次 Schwab `get_option_chain`, 失败就跳过，写 zero-row file or 不写。SPX/QQQ 偶发失败时 silently skip → next-day Q041 SPX CSP 无信号。

**改动**: 对 `{SPX, QQQ}` 这两个 index symbol 增加 retry 包装:

```python
INDEX_SYMBOLS = {"SPX", "QQQ"}
INDEX_RETRY_MAX = 3
INDEX_RETRY_BACKOFF_SEC = 30

def _fetch_with_retry(sym: str) -> pd.DataFrame | None:
    """For INDEX_SYMBOLS: retry up to 3x with 30s backoff on empty/failed fetch.
    For non-index whitelist symbols: single attempt (existing behavior).
    """
    attempts = INDEX_RETRY_MAX if sym in INDEX_SYMBOLS else 1
    for i in range(attempts):
        try:
            df = _fetch_chain(sym)  # existing logic
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            log.warning(f"{sym} fetch attempt {i+1}/{attempts}: {e}")
        if i < attempts - 1:
            time.sleep(INDEX_RETRY_BACKOFF_SEC)
    return None  # final fail
```

**Alert on final fail**: 如果 SPX 或 QQQ 在 3 次 retry 后仍失败, 写一条 `data/q041_collector_alert.jsonl`:
```json
{"date": "2026-06-06", "symbol": "SPX", "reason": "empty_chain_after_3_retries", "ts": "16:31:42-04:00"}
```
**并** push Telegram:
```
🚨 Q041 Collector Failure
SPX chain fetch failed 3x at 16:30 ET.
Q041 SPX CSP DTE30 signal will be UNAVAILABLE today.
```

Telegram 与 Part A 共用 `notify/telegram_bot.py` 现有 push helper。

### 2.3 launchd plist

Replace archived `com.spxstrat.q041align.plist` with new `com.spxstrat.q041_chain_sanity.plist`:

```xml
<key>Label</key>
<string>com.spxstrat.q041_chain_sanity</string>
<key>ProgramArguments</key>
<array>
  <string>/Users/macbook/SPX_strat/venv/bin/python</string>
  <string>-m</string>
  <string>research.q041.daily_chain_sanity</string>
</array>
<key>WorkingDirectory</key>
<string>/Users/macbook/SPX_strat</string>
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>16</integer>
  <key>Minute</key><integer>45</integer>
  <key>Weekday</key><integer>1</integer>  <!-- weekday only, NYSE 日历 5 entries -->
</dict>
<key>StandardOutPath</key>
<string>/Users/macbook/SPX_strat/logs/q041_chain_sanity.out.log</string>
<key>StandardErrorPath</key>
<string>/Users/macbook/SPX_strat/logs/q041_chain_sanity.err.log</string>
```

（实际需要 5 个 `StartCalendarInterval` dict for Weekday 1-5；plist 不支持 single dict with multiple weekdays — 用 array of dicts。）

---

## 3. Acceptance Criteria

### AC-1 — chain_sanity smoke test
Run `python -m research.q041.daily_chain_sanity --date 2026-06-03` on existing parquet. Output:
- jsonl record appended to `data/q041_chain_sanity_daily.jsonl`
- S1=17/17, S2=0 anomaly, S3=100%, S4=17/17
- no Telegram alert push（all OK）

### AC-2 — chain_sanity on a known-bad day
Run `python -m research.q041.daily_chain_sanity --date 2026-05-12`. Output:
- S1=15/17 (SPX + QQQ missing per `q041_overlap_daily.jsonl` history)
- Telegram alert fired with `S1: missing symbols: [QQQ, SPX]`

### AC-3 — chain_sanity skips non-trading days
`--date 2026-05-25` (Memorial Day): writes one record `{"date": "...", "notes": "skipped:non_trading_day", "alert_fired": false}`, no Telegram.

### AC-4 — collect_chains.py SPX retry triggered
Mock Schwab `get_option_chain("SPX")` to return empty 3 times. `collect_chains.py` should:
- log 3 retry attempts with 30s backoff
- final fail → write `data/q041_collector_alert.jsonl` record
- Telegram alert pushed

### AC-5 — collect_chains.py SPX retry succeeds on 2nd attempt
Mock Schwab `get_option_chain("SPX")` to fail once then succeed. `collect_chains.py` should:
- write SPX parquet normally
- no alert
- log notes single retry success

### AC-6 — Non-index symbols unchanged
Mock `get_option_chain("AAPL")` to fail. `collect_chains.py` should:
- single attempt (no retry) — existing behavior preserved
- skip silently (no alert) — existing behavior preserved

### AC-7 — launchd job activates
`launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_chain_sanity.plist` and verify next 16:45 ET run writes a sanity record to `data/q041_chain_sanity_daily.jsonl`.

---

## 4. Files to change

| File | Action |
|---|---|
| `research/q041/daily_chain_sanity.py` | **NEW** (~250 lines, partial copy from `daily_alignment_check.py` keeping Telegram helpers / non-trading-day logic) |
| `research/q041/daily_alignment_check.py` | **MOVE** to `research/q041/_archived/daily_alignment_check.py.2026-06-06` (read-only ref) |
| `research/q041/collect_chains.py` | **EDIT** — add `INDEX_SYMBOLS` set + `_fetch_with_retry` helper + alert-write |
| `~/Library/LaunchAgents/com.spxstrat.q041_chain_sanity.plist` | **NEW** (on oldair, post-impl deploy) |
| `tests/test_chain_sanity.py` | **NEW** — AC-1/2/3 unit tests |
| `tests/test_collect_chains_retry.py` | **NEW** — AC-4/5/6 unit tests |

`data/q041_overlap_daily.jsonl` / `data/q041_overlap_alert_state.jsonl` **不删**（历史归档），新文件 `data/q041_chain_sanity_daily.jsonl` 平行开始写。

---

## 5. Test plan

```bash
# Unit tests
arch -arm64 venv/bin/python -m pytest tests/test_chain_sanity.py tests/test_collect_chains_retry.py -v

# AC-1/2/3 (replay historical parquet)
arch -arm64 venv/bin/python -m research.q041.daily_chain_sanity --date 2026-06-03  # AC-1
arch -arm64 venv/bin/python -m research.q041.daily_chain_sanity --date 2026-05-12  # AC-2
arch -arm64 venv/bin/python -m research.q041.daily_chain_sanity --date 2026-05-25  # AC-3

# Deploy chain_sanity plist
scp com.spxstrat.q041_chain_sanity.plist oldair:~/Library/LaunchAgents/
ssh oldair launchctl load ~/Library/LaunchAgents/com.spxstrat.q041_chain_sanity.plist

# AC-7 wait for next 16:45 ET trigger, then verify
ssh oldair "tail -1 /Users/macbook/SPX_strat/data/q041_chain_sanity_daily.jsonl"
```

---

## 6. Rollout

1. Dev impl + 测试 → push
2. Deploy oldair: `git pull` + scp plist + `launchctl load`
3. 第一天 daily Telegram report 看格式是否 OK
4. 一周后 PM 复盘 — 是否有任何 false alert / missed alert / 报告 noise

无需 backtest cache refresh（这是 monitoring layer，不参与 backtest）。

无需 production code 改动以外的 SPEC 联动。

---

## 7. Forward dependency

SPEC-114 deploy 完之后，**Q041 paper trade promote 是下一个工作流（SPEC-115，单独 draft）**。SPEC-114 是 SPEC-115 的前置（必须先有可信的单源 chain 数据 + 监控）。

---

## 8. Related

- [research/q041/q041_alignment_conclusion_2026-06-06.md](../research/q041/q041_alignment_conclusion_2026-06-06.md) — conclusion + PM ratify
- `feedback_kill_gate_external_read` — 单源后 false negative 不可观测，依赖 sanity 自查
- `feedback_verify_before_conclude` — daily 报告与 PM 沟通时优先放 raw 数字
