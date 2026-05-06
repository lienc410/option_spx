# SPEC-083: Q041 Paper Trade Ledger and Review Support

Status: DONE

## 目标

为 `Q041` 当前已确认的三层 paper-trading 路由提供一套**最小支持面**：

- 独立 paper-trade ledger
- 手动 entry / close / expiry / notes 记录路径
- Tier 预算检查
- 月度 / 事件级 review export
- 最小 dashboard / report 可见性

本 Spec 的定位是 **paper-trading support**，不是第二套策略产品系统。

---

## 背景

`Q041` 已完成 Phase 1 / Phase 2，且 `2nd Quant` 已给出 **PASS Routing B**。当前正式路由固定为：

- Tier 1: `SPX CSP Δ0.20 DTE30` → 正式 paper trading
- Tier 2: `GOOGL CSP Δ0.20 DTE21` + `AMZN CSP Δ0.25 DTE21` → tail-caveated paper trading
- Tier 3: `COST/JPM` earnings IC → observe-only，且 `VIX >= 15` 为硬前置

对应的执行规则、预算和必录字段已经收口在：

- `doc/q041_execution_prep_packet_2026-05-05.md`
- `doc/q041_2nd_quant_review_feedback.md`

当前系统缺口不是新的策略研究，而是工程支持面：

- 现有生产 SPX 主策略状态文件不适合承载 `Q041` 多标的、多 Tier、手工 paper-trade 记录
- 需要单独的 paper ledger，避免与 live SPX 主策略状态混淆
- 需要最小 review/export 支持，便于按月 / 按财报事件回看

---

## 核心原则

- **与现有生产 SPX 主策略状态隔离**：`Q041` paper trades 不写入当前 live 主状态语义
- **手动优先**：只支持 manual logging，不做自动交易
- **预算先于展示**：先保证 ledger 与 BP budget tracking 正确，再做最小可见性
- **执行支持，不做策略引擎**：不把 `Q041` 并入当前 SPX 主 recommendation engine
- **窄范围交付**：只交付 paper-trading 支持，不扩展为完整 portfolio / MTM / alert 平台

---

## In Scope

1. `Q041` 独立 paper-trade ledger / record schema
2. 手动 logging path（entry / close / expiry / notes / flags）
3. Tier 预算检查与汇总
4. 月度 CSP review export
5. earnings IC 事件级 review export
6. 最小 dashboard / report visibility

---

## Out of Scope

- 自动下单
- broker integration 扩展
- 自动择券 / 自动 strike helper
- 自动事件调度 / earnings calendar orchestrator
- full mark-to-market engine
- live Greeks / live PnL 面板
- 并入当前 SPX 主 recommendation engine
- 新策略研究 / 新候选扫描
- 复杂图表、scorecard、reminder / bot alert
- 账户 BP 的自动读取（`account_total_bp` 由 PM 手动配置，不从 broker 同步）

---

## 功能定义

### F1 — 独立 paper-trade ledger / record schema

新增一套独立于现有生产主策略状态的 `Q041` paper-trade ledger。

**存储：**

- `data/q041_paper_trades.jsonl`
- 每行一条完整 JSON record
- 写入必须原子（write-then-rename 或 line-append + flush），失败时 fail closed，不 silently drop

**`record_id` 生成规则：** `{entry_date_yyyymmdd}-{symbol}-{seq:02d}`，同日同标的从 01 顺序递增。

**公共字段（所有 strategy_type 必须包含）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `record_id` | str | 见上 |
| `status` | enum: `open` / `closed` / `expired` | 默认 `open` |
| `tier` | enum: `tier1` / `tier2` / `tier3` | 必填 |
| `strategy_type` | enum: `csp` / `earnings_ic` | 必填 |
| `symbol` | str | 必填 |
| `entry_date` | str YYYY-MM-DD | 必填 |
| `expiry` | str YYYY-MM-DD | 必填 |
| `act_dte` | int | 入场时实际 DTE |
| `S_entry` | float | 入场时标的价格 |
| `iv_entry` | float | 入场时 ATM IV（百分比格式，如 `14.5`） |
| `vix_entry` | float | 入场时 VIX |
| `net_prem` | float \| null | 收到净权利金（open 时填，closed/expired 时确认） |
| `bp_reserved` | float | 名义 BP 敞口（美元，见公式）；必须在 open 时显式填写 |
| `contracts` | int | 合约数，默认 1 |
| `S_exit` | float \| null | 到期/平仓时标的价格；open 时为 null |
| `settle_cost` | float \| null | 结算成本；open 时为 null |
| `pnl` | float \| null | 净 PnL；open 时为 null |
| `hit` | bool \| null | 是否被击穿；open 时为 null |
| `close_date` | str YYYY-MM-DD \| null | close/expiry 日期 |
| `flags` | list[str] | 见枚举表，可空列表 |
| `notes` | str | 自由文本备注 |

**`bp_reserved` 计算公式（写入前由 PM / Quant 计算，显式传入，不自动推导）：**

- CSP：`bp_reserved = strike × 100 × contracts`
- earnings IC：`bp_reserved = spread_width × 100 × contracts`
  （其中 `spread_width = implied_move × S_entry × width_multiplier`）

**`flags` 枚举（仅允许以下值，可组合）：**

| 值 | 含义 |
|---|---|
| `iv_compression_warning` | 持仓中 VIX < 18 且 S 较入场上涨 > 5% |
| `vix_spike_adverse` | 持仓中 VIX 单周上升 > 40% |
| `consecutive_loss` | 同策略连续第 2 次亏损触发记录 |
| `atypical_move` | realized_move 超过 implied_move 的 1.5 倍 |
| `vix_gate_fail` | earnings IC：入场时 VIX < 15，本次跳过（不应产生 open 记录，只供审计用） |
| `imr_below_33` | JPM IC：IMR < 33%，选择性跳过时记录 |

**strategy_type 补充字段：**

CSP 额外字段：
- `strike` (float)
- `pct_otm` (float，如 `4.2` 代表 4.2% OTM)
- `delta_actual` (float)

earnings IC 额外字段：
- `k_put_short` (float)
- `k_put_long` (float)
- `k_call_short` (float)
- `k_call_long` (float)
- `event_name` (str，如 `COST-2026Q2`)
- `earnings_date` (str YYYY-MM-DD)
- `implied_move_pct` (float，入场时 implied move %)
- `vix_gate_passed` (bool，入场时 VIX >= 15)

**约束：**

- `tier` / `strategy_type` / `bp_reserved` 任一缺失 → 拒绝写入
- `status=closed` 或 `expired` 时 `pnl` 不得为 null
- earnings IC 的 `vix_gate_passed=false` 时不应产生 `status=open` 记录

---

### F2 — Manual logging path

提供最小手动记录路径，支持：

- 新建 entry（写入 open record）
- 记录 close / expiry outcome（填写 S_exit / settle_cost / pnl / hit / close_date）
- 更新 notes / flags（可独立操作）

最小实现形式：

- `scripts/q041_paper_ledger.py`（CLI 脚本）

CLI 操作语义：

```
# 新建 CSP entry
python scripts/q041_paper_ledger.py add-csp --symbol SPX --tier tier1 ...

# 新建 earnings IC entry
python scripts/q041_paper_ledger.py add-ic --symbol COST --tier tier3 ...

# 记录 close/expiry
python scripts/q041_paper_ledger.py close --record-id 20260516-SPX-01 --s-exit 7250 --pnl 31.33 --hit false

# 更新 notes / flags
python scripts/q041_paper_ledger.py update --record-id 20260516-SPX-01 --notes "IV spike observed" --flags iv_compression_warning
```

必须满足：

- 可手动写入 open record
- 可手动补全 close / expiry 结果
- 可更新备注与风险标记
- 不自动生成交易建议
- 不自动向 broker 发单

---

### F3 — BP budget tracking

基于 open paper positions 计算当前 `Q041` BP 占用，并做 tier-level 检查。

**`account_total_bp` 来源：**

- 配置文件：`data/q041_paper_trade_config.json`
- 字段：`{ "account_total_bp": <float> }`
- 由 PM 手动维护；未配置时 budget tracking 拒绝运行（不使用默认值）

**BP% 计算：**

```
tier1_bp_pct = sum(bp_reserved for open records in tier1) / account_total_bp * 100
tier2_bp_pct = sum(bp_reserved for open records in tier2) / account_total_bp * 100
tier3_bp_pct = sum(bp_reserved for open records in tier3) / account_total_bp * 100
total_q041_bp_pct = tier1 + tier2 + tier3
```

**硬约束：**

- Tier 1 ≤ 20%
- Tier 2 combined ≤ 15%
- Tier 3 ≤ 5%
- total `Q041` ≤ 40%

**输出结构：**

```json
{
  "tier1_bp_pct": 18.2,
  "tier2_bp_pct": 12.1,
  "tier3_bp_pct": 2.3,
  "total_q041_bp_pct": 32.6,
  "within_limits": true,
  "violations": []
}
```

若 violations 非空，每条格式为 `"tier2 exceeds 15%: 16.3%"`。

说明：

- Tier 2 是 **combined** 预算（GOOGL + AMZN 合计），不是逐名单独检查
- Tier 3 当前是 observe-only，但仍纳入预算计算

---

### F4 — Review export

提供两类最小 review export，输出到 `data/q041_paper_trade_review/` 目录。

#### F4.1 月度 CSP review export

文件名：`csp_review_{YYYY-MM}.csv`

覆盖：Tier 1 + Tier 2 CSP，按 entry_date 在指定月份内的记录。

字段：`record_id`, `month`, `symbol`, `tier`, `entry_date`, `expiry`, `act_dte`, `delta_actual`, `pct_otm`, `vix_entry`, `bp_reserved`, `net_prem`, `pnl`, `hit`, `flags`, `notes`

#### F4.2 earnings IC 事件级 review export

文件名：`ic_review_{symbol}_{YYYY}.csv`

覆盖：Tier 3 earnings IC，逐标的导出。

字段：`record_id`, `event_name`, `symbol`, `entry_date`, `earnings_date`, `expiry`, `vix_entry`, `vix_gate_passed`, `k_put_short`, `k_put_long`, `k_call_short`, `k_call_long`, `implied_move_pct`, `bp_reserved`, `net_prem`, `pnl`, `hit`, `flags`, `notes`

两类 export 均输出 CSV，允许 PM / Quant 直接用 Excel / pandas 回看。

---

### F5 — Minimal visibility

提供最小 dashboard / report visibility。

实现选项（二选一，Developer 可选更简单的）：

- **选项 A：** 在现有 Flask dashboard 下新增一个只读的 `/q041` 页面（Jinja2 template）
- **选项 B：** `scripts/q041_paper_ledger.py status` 命令，输出 terminal-friendly 汇总表

不论选哪个，必须展示：

- **current paper positions**：所有 `status=open` 记录，字段：record_id / symbol / tier / strategy_type / entry_date / expiry / bp_reserved / net_prem / flags
- **recent entries**：最近 10 条 entry（包含已关闭的），按 entry_date 倒序
- **BP usage**：tier1 / tier2 / tier3 / total 占比（%），标注是否超限
- **next review item**：
  - CSP：最近一个 `expiry <= today + 7` 的 open CSP record（即将到期提示）
  - earnings IC：最近一个 `earnings_date <= today + 7` 的 open IC record

要求：

- 只做列表 / summary，不做复杂图表
- 不展示 live strategy state
- 不与当前 SPX 主持仓混合
- 不触发任何写操作（只读）

---

## 数据与接口建议

### 文件布局

```
data/
  q041_paper_trades.jsonl          # ledger（主数据）
  q041_paper_trade_config.json     # account_total_bp 等配置
  q041_paper_trade_review/
    csp_review_YYYY-MM.csv
    ic_review_SYMBOL_YYYY.csv

scripts/
  q041_paper_ledger.py             # F2 + F3 + F4 CLI
  （可选：F5 选项 B 的 status 命令集成于此）

web/templates/
  q041_paper.html                  # 仅 F5 选项 A 需要
```

---

## 边界条件与约束

- `bp_reserved` 必须为显式字段，不能靠事后推导替代
- 未提供 `bp_reserved` / `tier` / `strategy_type` 的 open record → 拒绝写入
- `vix_gate_passed=false` 的 earnings IC → 不创建 `status=open` 记录
- `status=closed` 或 `expired` 时 `pnl=null` → 拒绝 close 操作
- `account_total_bp` 未配置时 → F3 拒绝运行，打印 configuration error
- ledger 写入失败时 → fail closed，不 silently drop，调用方必须收到异常
- Tier 3 observe-only 特性体现在人工规程里（`vix_gate_passed` 字段）；ledger 本身不拦截 Tier 3 的写入

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | 存在独立 `data/q041_paper_trades.jsonl`，未读取 / 未写入任何现有生产 SPX 主策略状态文件 | 代码审查 + grep |
| AC2 | CLI 能写入一笔完整的 SPX CSP open record，包含 execution-prep packet 全部 15 个必录字段，写入后 JSONL 可 json.loads 解析 | 单测 |
| AC3 | CLI 能对一笔 open CSP record 执行 close，回填 S_exit / pnl / hit / close_date；close 后该 record 的 status=closed 且 pnl 非 null | 单测 |
| AC4 | CLI 能写入一笔 COST earnings IC open record，包含四腿 strike、vix_gate_passed=true；另测 vix_gate_passed=false 时拒绝创建 open record | 单测 |
| AC5 | 给定 account_total_bp=500000，2 个 open records（tier1 bp_reserved=95000，tier2 bp_reserved=70000），F3 正确输出 tier1=19.0%, tier2=14.0%，within_limits=true | 单测 |
| AC6 | 给定 tier1 bp_reserved=105000（超过 20% of 500000），F3 violations 包含 "tier1 exceeds 20%" 字样 | 单测 |
| AC7 | F4.1 月度 CSP export 生成 `csp_review_YYYY-MM.csv`，含该月所有 CSP 记录，字段完整 | 导出测试 |
| AC8 | F4.2 earnings IC export 生成 `ic_review_COST_YYYY.csv`，含该年全部 COST IC 记录，字段完整 | 导出测试 |
| AC9 | F5 展示内容包含：open positions 列表、recent 10 entries、BP tier 占比、next review item（到期 ≤ 7 天）| 页面 / CLI smoke |
| AC10 | 现有 backtest engine 回归测试通过，`Q041` ledger 与主推荐路径零交集 | 现有测试套件 |

---

## Implementation Units

建议按以下顺序实施（Unit 1 → 2 → 3 → 4）：

### Unit 1 — Ledger / schema（F1）

- 定义 `Q041PaperTrade` dataclass（或 TypedDict）
- 实现 JSONL append-write（原子写入）和 read-all / filter 函数
- 无 CLI，只有 library module

验收：AC1、AC2（前半段 schema 部分）

### Unit 2 — Manual logging path（F2）

- `scripts/q041_paper_ledger.py` 的 `add-csp` / `add-ic` / `close` / `update` 子命令
- `data/q041_paper_trade_config.json` 读取
- 参数验证（缺字段拒绝，枚举值校验）

验收：AC2、AC3、AC4

### Unit 3 — Budget tracking + review export（F3 + F4）

- F3：`budget_status()` 函数，读 config + ledger，输出 BP% 结构
- F4.1：`export_csp_review(month: str)` → CSV
- F4.2：`export_ic_review(symbol: str, year: int)` → CSV
- 集成到 CLI 的 `budget` / `export-csp` / `export-ic` 子命令

验收：AC5、AC6、AC7、AC8

### Unit 4 — Minimal visibility（F5）

- 实现 F5（选项 A 或选项 B）
- 只读，不写 ledger
- 若选 A：新增 `/q041` Flask route + `q041_paper.html` template

验收：AC9

---

## 不在本 Spec 内的后续候选

以下若未来需要，必须单独起 Spec：

- reminder / bot alert
- auto strike helper（自动选 K 建议）
- earnings date auto-scheduler
- mark-to-market / live risk 面板
- richer dashboard charts
- Q041 与主 recommendation engine 的耦合

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-05 | Quant 完成初稿，收口到 ledger / manual logging / budget / export / minimal visibility；修正三处技术缺口：account_total_bp 分母来源（F3 必须读 config 文件，未配置拒绝运行）、flags 枚举（6 个预定义值）、bp_reserved 公式显式化（CSP = strike×100×contracts，IC = spread_width×100×contracts）| DRAFT |
| 2026-05-05 | PM APPROVED | APPROVED |
| 2026-05-05 | Quant review PASS，AC1–AC10 全通过，状态更新为 DONE | DONE |

---

## Review

- 结论：**PASS**
- AC1–AC10 全部通过，逐项确认如下：
  - **AC1 PASS**：存在独立 `data/q041_paper_trades.jsonl` 语义；实现不读取、不写入任何现有生产 SPX 主策略状态文件
  - **AC2 PASS**：CLI 可写入完整 `SPX CSP` open record，JSONL 写回后可稳定解析
  - **AC3 PASS**：open `CSP` record 可正确 close，`status=closed` 且 `pnl` 非空
  - **AC4 PASS**：`COST` earnings IC open record 正常；`vix_gate_passed=false` 时拒绝创建 open record
  - **AC5 PASS**：budget 计算在给定样例下正确输出 `tier1=19.0%`、`tier2=14.0%`、`within_limits=true`
  - **AC6 PASS**：超限样例会显式返回 violation，包含 `"tier1 exceeds 20%"`
  - **AC7 PASS**：月度 `CSP` review export 成功生成并字段完整
  - **AC8 PASS**：事件级 `earnings IC` export 成功生成并字段完整
  - **AC9 PASS**：F5 采用 Option B，`scripts/q041_paper_ledger.py status` 已覆盖 open positions / recent entries / BP usage / next review item
  - **AC10 PASS**：现有 backtest / recommendation 主路径回归保持通过，`Q041` ledger 与主推荐路径零交集
- F5 选用 Option B（`scripts/q041_paper_ledger.py status`），符合 Spec 允许的最小实现路径
- 独立性已逐点确认：`logs/q041_paper_trade_io.py` 和 `scripts/q041_paper_ledger.py` 只处理 `Q041` paper-trade 语义，不读写生产 SPX 主状态，不并入主 recommendation engine
- 原子写入已逐点确认：`_atomic_write_jsonl` 使用 write-to-tmp + `os.replace()` + `fsync()`；append path 也执行 flush + fsync，满足 fail-closed / 不 silently drop 的要求
- gate 强制已逐点确认：`vix_gate_passed=false` 的拒绝逻辑位于 library 层（`_validate_strategy_specific`），不是只靠 CLI 入口做人为约束
- budget fail-closed 已确认：`account_total_bp` 未配置时，`budget_status()` / `status_snapshot()` 均拒绝运行，不使用默认值兜底
- test 隔离已确认：env-var 覆盖（`Q041_PAPER_LEDGER_FILE` / `Q041_PAPER_CONFIG_FILE` / `Q041_PAPER_REVIEW_DIR`）保证测试用 ledger / config / review 目录与真实运行面完全分离，无需 mock 主状态文件
- 回归测试结果：25/25 PASS，主推荐路径无影响
- 审查者：Quant Researcher，2026-05-05
