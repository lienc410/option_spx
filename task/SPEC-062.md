# SPEC-062: Backtest Research View (Minimal)

Status: APPROVED

## 目标

**What**：在现有 backtest web page 中加入轻量 Research View，固定展示少数经过验证的研究交易集，使 PM 可以在同一界面反复对比 baseline 和已完成研究的边际交易。

**Why**：
- 研究成果（Q015 IVP<55 边际交易、Q016 Dead Zone A recovery BPS）目前只存在于 prototype 脚本的 stdout 输出中，跑完即丢
- PM 需要在同一张 PnL / 日期轴上反复对比 baseline vs 研究交易，但目前只能手动重跑 prototype 脚本
- 不需要通用 research tag 平台——只要把已验证研究的固定交易集可视化

---

## 核心原则

- **不做通用研究标签平台**——视图数量和字段由 SPEC 固定，不支持用户自建
- **数据来自预生成 JSON**——不在 web request 中重跑 backtest / prototype
- **UI 最小侵入**——在现有 backtest page 增加切换，不新建页面，不重做布局

---

## 功能定义

### F1 — 预生成研究 artifact

新增 CLI 命令，将研究交易集导出为静态 JSON：

```
arch -arm64 venv/bin/python -m backtest.research_views generate
```

输出文件：`data/research_views.json`

schema：
```json
{
  "generated_at": "2026-04-19T15:00:00",
  "params_hash": "a1b2c3d4e5",
  "views": {
    "baseline": {
      "label": "Baseline (Production)",
      "description": "当前生产参数的完整回测",
      "trades": [ <trade_obj>, ... ]
    },
    "q015_ivp55_marginal": {
      "label": "Q015: IVP [50,55) Marginal BPS",
      "description": "BPS gate 从 IVP<50 放宽到 IVP<55 的边际交易",
      "trades": [ <trade_obj>, ... ]
    },
    "q016_dza_recovery_bps": {
      "label": "Q016: Dead Zone A Recovery BPS",
      "description": "NORMAL+HIGH+BULLISH 恢复窗口 BPS（已否决，仅留存参考）",
      "trades": [ <trade_obj>, ... ]
    }
  }
}
```

`<trade_obj>` 复用现有 `/api/backtest` 的交易字段：

```json
{
  "strategy": "Bull Put Spread",
  "strategy_key": "bps",
  "entry_date": "2019-01-31",
  "exit_date": "2019-02-13",
  "entry_spx": 2704.10,
  "exit_spx": 2745.73,
  "entry_vix": 17.94,
  "entry_credit": 3.20,
  "exit_pnl": 2641.00,
  "exit_reason": "roll_21dte",
  "dte_at_entry": 45,
  "dte_at_exit": 21,
  "spread_width": 50,
  "contracts": 1.0,
  "source_view": "q015_ivp55_marginal"
}
```

### F2 — API 端点

```
GET /api/research/views
```

直接读取 `data/research_views.json` 并返回。无运算、无缓存逻辑。
若文件不存在，返回 `{"empty": true, "message": "Run: python -m backtest.research_views generate"}`。

### F3 — 前端 UI

在现有 backtest page 的 trade log 上方增加一行 **view 切换 pill bar**：

```
[Production]  [Q015 IVP 50-55]  [Q016 DZ-A]
```

行为：
- **Production**（默认激活）：显示正常 `/api/backtest` 的交易表，行为与当前完全相同
- **Q015 IVP 50-55**：trade log 替换为 `q015_ivp55_marginal` 的交易列表；metric cards 显示该子集的汇总（n / total PnL / avg PnL / win rate）
- **Q016 DZ-A**：同上，使用 `q016_dza_recovery_bps`

切换 pill 时：
- 只替换 trade log 表格和 metric cards
- equity curve chart 不变（始终显示 production baseline）
- 切换不触发新的 API 请求（research views 在页面 load 时一次性获取）

### F4 — 视觉区分

Research view 激活时：
- Pill 使用 `--blue` 色系（区别于 production 的 `--gold`）
- Trade log 上方显示一行蓝色 banner：`Research View · {label} · {description}`
- Metric cards 标题追加 `(Research)` 后缀

---

## In Scope

| 项目 | 说明 |
|---|---|
| CLI 导出命令 | `backtest.research_views generate` |
| 静态 JSON artifact | `data/research_views.json` |
| API 端点 | `GET /api/research/views` |
| 前端 pill 切换 | 3 个固定 pill |
| Research metric cards | n / total PnL / avg PnL / win rate |
| 蓝色视觉区分 | pill + banner |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 用户自建 research view | 不做通用平台 |
| 运行时重跑 backtest | 数据来自预生成 JSON |
| Research equity curve | 第一版只做 trade log + metric cards |
| 跨 view 对比叠加 | 一次只显示一个 view |
| 自动触发 generate | 手动 CLI 命令，不在 server 启动时自动跑 |
| Research view 的参数编辑 | 视图内容固定，不支持调参 |
| 新页面或新路由 | 在现有 `/backtest` 页内完成 |

---

## Data Contract

### 输入

- `backtest.research_views generate` 内部调用：
  - `run_backtest(start_date="2000-01-01")` — baseline
  - monkey-patch `sel.BPS_NNB_IVP_UPPER` 跑 IVP<55 变体，diff 得到边际交易
  - monkey-patch `select_strategy` 跑 Dead Zone A 变体，diff 得到 recovery BPS
- 输出写入 `data/research_views.json`

### 输出

- `/api/research/views` 返回完整 JSON，前端一次性加载
- 预期大小：baseline ~300 trades × ~200B = ~60KB，research views ~30 trades = ~6KB，合计 <100KB

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `python -m backtest.research_views generate` 成功生成 `data/research_views.json` | CLI 运行 + 文件存在 |
| AC2 | JSON 包含 3 个 view key：`baseline`, `q015_ivp55_marginal`, `q016_dza_recovery_bps` | jq 检查 |
| AC3 | `GET /api/research/views` 返回 JSON；文件不存在时返回 `{"empty": true}` | curl 测试 |
| AC4 | Backtest 页面默认显示 Production pill（行为与当前相同） | 页面加载验证 |
| AC5 | 点击 Q015 pill 后 trade log 切换为 IVP [50,55) 边际交易 | 手动点击 |
| AC6 | Research view 激活时 pill 为蓝色，顶部显示蓝色 banner | 视觉检查 |
| AC7 | Research view 的 metric cards 显示该子集的 n / total PnL / avg PnL / win rate | 数值核对 |
| AC8 | 切换回 Production pill 恢复原始 trade log 和 metric cards | 来回切换验证 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-19 | 初始草稿 | DRAFT |
