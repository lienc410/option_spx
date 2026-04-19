# SPEC-060: Recommendation Event Log

## 目标

**What**：新增 live recommendation 的结构化事件日志，记录 Telegram bot 在关键触发点生成的 recommendation 快照，写入 append-only 文件：

```text
logs/recommendation_log.jsonl
```

**Why**：
- 当前系统已有 `trade_log.jsonl`、live performance、backtest cache，但缺少 live recommendation 历史日志
- Quant researcher 无法系统复盘 morning push / EOD push / `/today` 手动请求当时到底给了什么建议
- 无法稳定对照 recommendation、实际交易和 backtest 结果三者之间的关系
- 需要一个对 agent / pandas / jq 都友好的只追加日志源，供主力机只读分析

---

## 功能定义

### F1 — 新增 recommendation log I/O 模块（`logs/recommendation_log_io.py`）

新增模块，职责：

- 定义 recommendation log 文件路径
- 提供 append helper
- 创建 `logs/` 目录（若不存在）
- 以 JSONL 格式追加写入 recommendation event

**文件路径**：

```text
logs/recommendation_log.jsonl
```

**格式要求**：

- UTF-8
- append-only
- 每行一个完整 JSON object
- 不覆盖、不改写历史记录

---

### F2 — recommendation event schema

每条记录代表一次“有业务意义的 recommendation 事件”，而不是一次页面轮询。

每条记录至少包含以下字段：

```json
{
  "timestamp": "2026-04-18T09:35:02-04:00",
  "source": "scheduled_push",
  "mode": "intraday",
  "date": "2026-04-18",

  "underlying": "SPX",
  "position_action": "OPEN",
  "strategy": "Bull Put Spread",
  "strategy_key": "bull_put_spread",
  "rationale": "Low vol, bullish trend, no backwardation",

  "macro_warning": false,
  "backwardation": false,

  "vix": 17.4,
  "regime": "LOW_VOL",
  "vix3m": 19.1,

  "iv_rank": 31.0,
  "iv_percentile": 42.0,
  "iv_signal": "NORMAL",

  "spx": 5234.1,
  "trend_signal": "BULLISH",

  "legs": [
    {
      "action": "SELL",
      "option": "PUT",
      "dte": 30,
      "delta": -0.30,
      "note": "short put"
    }
  ],

  "params_hash": "479998b833"
}
```

**字段规则**：

- `timestamp`：ET ISO 时间字符串
- `source`：事件来源
- `mode`：`intraday` / `eod`
- `date`：recommendation 对应交易日
- `strategy_key`：使用 canonical key
- `legs`：永远存在；`Reduce / Wait` 时为 `[]`
- `vix3m`：允许为 `null`
- `params_hash`：`hashlib.sha256(json.dumps(StrategyParams().__dict__, sort_keys=True)).hexdigest()[:10]`；反映当前 live/default 参数版本，用于后续复盘

---

### F3 — 写入触发点（`notify/telegram_bot.py`）

只在真正有业务意义的 live recommendation 触发点写日志：

1. `scheduled_push()`
2. `scheduled_eod_push()`
3. Telegram `/today`

**source 映射**：

- `scheduled_push` → `source="scheduled_push"`，`mode="intraday"`
- `scheduled_eod_push` → `source="scheduled_eod_push"`，`mode="eod"`
- `/today` → `source="telegram_today"`，`mode="intraday"`（固定值）

---

### F4 — 不记录普通 dashboard recommendation 轮询

`/api/recommendation` 当前会被 dashboard 周期性调用；该 endpoint 不应默认写 recommendation log。

理由：

- recommendation log 应是“业务事件日志”，不是“页面访问日志”
- 若在 `/api/recommendation` 写日志，会造成重复和噪音
- 该文件应保持小而高信噪比，便于 quant researcher 直接读取

---

### F5 — logging failure 不影响 bot 主流程

recommendation log 属于 observability / research trace，不应影响 live delivery。

要求：

- append 失败时，Telegram 推送仍然照常发送
- 失败仅写 warning / error log，不 crash bot
- 每个触发点都采用 best-effort append

---

## 接口定义

### `logs/recommendation_log_io.py`

```python
RECOMMENDATION_LOG_FILE: Path

def append_recommendation_event(
    *,
    rec: Recommendation,
    source: str,
    mode: str,
    timestamp: str,
    params_hash: str,
) -> None:
    """Append one recommendation event to logs/recommendation_log.jsonl."""
```

### `notify/telegram_bot.py`

在以下路径调用 append helper：

- `scheduled_push()`
- `scheduled_eod_push()`
- `/today` handler

---

## 边界条件与约束

- 不改动策略选择逻辑
- 不改动 backtest engine
- 不新增前端页面或 API endpoint
- 不对 `/api/recommendation` 做日志写入
- recommendation log 为 append-only，不做 update / dedupe / compaction
- 若 recommendation 为 `Reduce / Wait`，仍必须落一条完整记录
- 缺失的可选值写 `null`，不要省略字段
- helper 实现应显式序列化稳定 schema，不直接盲目 dump 整个 dataclass

---

## 不在范围内

- recommendation 历史查询 UI
- recommendation log 的 HTTP 读取接口
- 与 backtest 页面联动展示 recommendation history
- 对旧 recommendation 事件做回填
- 对 dashboard 自动刷新去重
- 将 recommendation log 自动同步到主力机
- `/ES` recommendation 记录（待 `/ES` 研究达到里程碑后再扩展）

---

## 修改文件

| 文件 | 改动 |
|------|------|
| `logs/recommendation_log_io.py` | 新建：append-only JSONL helper |
| `notify/telegram_bot.py` | 在 `scheduled_push()`、`scheduled_eod_push()`、`/today` handler 写 recommendation event |

---

## 验收标准

1. **AC1**：运行 `scheduled_push()` 时，`logs/recommendation_log.jsonl` 追加一条新记录
2. **AC2**：运行 `scheduled_eod_push()` 时，追加一条 `source="scheduled_eod_push"` 且 `mode="eod"` 的记录
3. **AC3**：触发 Telegram `/today` 时，追加一条 `source="telegram_today"` 的记录
4. **AC4**：`Reduce / Wait` recommendation 仍生成合法记录，且 `legs=[]`
5. **AC5**：append helper 异常不会阻断 Telegram 推送流程
6. **AC6**：每行均为合法 JSON，能被逐行解析
7. **AC7**：Section F2 中定义的字段在每条记录上都存在
8. **AC8**：普通 `/api/recommendation` dashboard 轮询不会写入 recommendation log

---

## 测试建议

- append helper 生成合法 JSONL
- `Reduce / Wait` 序列化测试
- `scheduled_push()` 调用 append helper
- `scheduled_eod_push()` 调用 append helper
- `/today` 调用 append helper
- append helper 抛异常时，bot 主流程仍继续
- `/api/recommendation` 不触发写日志

---

## 依赖

- 依赖现有 `Recommendation` 对象字段
- `params_hash` 可复用现有 hashing 逻辑；若无合适 helper，可在实现时以最小方式新增

---

## Review

### Spec 审阅（Quant Researcher，2026-04-17）
- 结论：PASS
  1. `params_hash` 明确为 `StrategyParams.__dict__` 的 SHA-256 前 10 位 — 已写入 F2 字段规则
  2. `/ES` recommendation 不在范围内 — 已加入"不在范围内"
  3. `/today` 的 `mode` 固定为 `"intraday"` — 已修改 F3

### 实现 Review（Quant Researcher，2026-04-17）
- 结论：PASS
- 测试：6/6 通过
- AC 覆盖：AC1–AC8 全部验证通过
- 核查要点：
  1. `recommendation_log_io.py` — schema 显式列举 21 个字段，`default=str` 兜底序列化，符合 F2
  2. `_params_hash()` — 使用 `asdict(StrategyParams())` + `json.dumps(sort_keys=True)` + SHA-256[:10]，与 Spec 修订一致
  3. `_safe_append_recommendation_event()` — try/except 包裹，失败仅 `log.exception`，不阻断推送，符合 F5
  4. 三个触发点（`scheduled_push`、`scheduled_eod_push`、`cmd_today`）均在 `get_recommendation()` 之后、Telegram send 之前调用，source/mode 正确
  5. `/api/recommendation` 无写入调用，符合 F4
  6. `cmd_today` 中 `_safe_append_recommendation_event` 在外层 try 内部——若 append 内部异常已被 `_safe_` 吞掉不影响后续 `reply_text`；若 `get_recommendation()` 本身失败则整体走 except 分支，也不会写日志，行为正确

Status: DONE
