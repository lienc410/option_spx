# FE Handoff — 基金清仓信号 前端 Tab

**日期**：2026-05-31
**提出**：Quant Researcher
**执行**：FE 工程师 / Developer
**目标**：在现有 Portfolio Command Center 加一个 tab，让 PM 追踪基金清仓信号 + 持仓。
**关联**：策略 `task/fund_exit_strategy_spec.md`；数据源脚本 `fund_exit/fund_exit_signals.py`。

> ⚠️ 临时性：这是逐步清仓期的过渡工具。**全仓清空后整个 `fund_exit/` folder + 本 tab 会被移除**，请保持低耦合（独立 route/template/api，勿侵入核心 portfolio 逻辑），方便一刀切删除。

---

## 0. 架构（关键：不要在页面加载时跑 akshare）

```
fund_exit/fund_exit_signals.py   (Quant 维护, akshare 拉数 ~30-60s, 限频)
        │  手动/cron 运行
        ▼
fund_exit/fund_signals.json  +  fund_exit/charts/*.png   (生成物, 已 gitignore)
        │  后端读取静态文件 (不触发计算)
        ▼
Flask  /api/fund-exit/signals   →  jsonify(JSON 内容)
Flask  /funds                   →  render_template("funds.html")
        ▼
前端 tab 渲染（纯展示, 无计算）
```

**铁律**：后端 endpoint **只读 JSON 文件**，绝不在请求里调用 akshare / 跑脚本（慢 + 限频 + 会 block worker）。数据刷新靠脚本 **日度(交易日)定时重跑**（launchd/cron，NAV T+1 每交易日变），与 web 解耦。月度的是"卖出动作节奏(保底时钟)"，不是数据刷新——两者不同 cadence。

---

## 1. 后端任务（Developer）

### 1.1 路由
```python
import json
from pathlib import Path
from flask import jsonify, render_template, send_from_directory, abort

_FUND_DIR = Path(__file__).resolve().parent.parent / "fund_exit"   # 按实际 repo 结构调整

@app.route("/funds")
def funds_page():
    return render_template("funds.html")

@app.route("/api/fund-exit/signals")
def fund_exit_signals():
    f = _FUND_DIR / "fund_signals.json"
    if not f.exists():
        # 空状态：脚本还没跑过
        return jsonify({"available": False,
                        "message": "信号未生成，请先运行 fund_exit/fund_exit_signals.py"}), 200
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    data["available"] = True
    return jsonify(data)

@app.route("/api/fund-exit/chart/<code>")
def fund_exit_chart(code):
    # charts/<code>_<name>.png —— 按 code 前缀匹配，避免中文文件名 URL 编码问题
    charts = _FUND_DIR / "charts"
    if not charts.exists():
        abort(404)
    match = next((p for p in charts.glob(f"{code}_*.png")), None)
    if not match:
        abort(404)
    return send_from_directory(charts, match.name)
```

### 1.2 导航 link
在 `web/templates/portfolio_home.html` 第 ~1088 行 `.nav-links` 块 + 其余页面同款 nav 内加：
```html
<a href="/funds" class="nav-link">Funds</a>
```
（清仓结束删除时，一并移除这一行。）

---

## 2. JSON 数据契约（schema）

`GET /api/fund-exit/signals` 返回：

```jsonc
{
  "available": true,
  "generated_at": "2026-05-31T14:05:12",   // 脚本运行时间 → 前端显示"数据新鲜度"
  "data_date": "2026-05-31",
  "market_regime": "沪深300 强(>MA60) 距MA60 +3.8%",  // 仅上下文提示, 不是决策
  "disclaimer": "纪律工具，非投资建议；阈值先验非优化；费率/锁定/赎回以中信App为准。",
  "params": { "DEEP": 0.15, "TRAIL_high": 0.10, "TRAIL_low": 0.06,
              "monthly_floor": 0.10, "deep_limit": "6-8周",
              "strong_rule": "全部上升趋势(最新>MA20>MA60)纯持有" },
  "account": {
    "total_mv": 908291.28,
    "held_strong_mv": 543687.78, "held_strong_pct": 0.5986,  // 上升趋势纯持有占比
    "non_strong_mv": 364603.5,
    "floor_target": 36460.35,      // 保底月清仓目标(仅非强势仓 ×10%)
    "suggested_total": 107243.99,  // 本期所有建议卖出额合计
    "floor_met": true
  },
  "funds": [
    {
      "name": "华夏卓越成长混合", "code": "024930",
      "mv": 152086.1, "pnl_pct": 0.52, "bucket": "high",   // bucket: high/low 波动档
      "ok": true, "err": "",
      "latest": 1.7234, "latest_date": "2026-05-29", "n": 191, "short_hist": false,
      "ma20": 1.71, "ma60": 1.65, "high60": 1.788, "roll_high": 1.788,
      "trail_trigger": 1.6092,    // 滚动高×(1-TRAIL_档) 追踪止盈触发位
      "rsi": 56.0, "ann_vol": 0.28,
      "dist_ma20": 0.007, "dist_ma60": 0.044, "dist_high60": -0.036,
      "trend": "上升",            // 上升/下降/震荡/数据不足
      "rule": 1,                  // 1..6 (见下表)
      "action": "①上升趋势：让利润奔跑，纯持有",
      "clip": 0.0,                // 建议卖出比例(占该仓)
      "clip_amt": 0.0,            // = mv*clip ¥
      "vs_twap": -0.10,           // clip - 10%; 负=比均匀清仓少卖(让赢家跑)
      "veto": false,             // 超卖否决是否触发
      "locked": "",              // 非空=锁定提示(目前仅 009010)
      "chart": "charts/024930_华夏卓越成长混合.png"
    }
    // ... 共 10 只；ok=false 时除 name/code/mv/err 外其余为 null
  ]
}
```

### rule → 语义 / 颜色映射（前端用）

| rule | 含义 | 建议色(theme token) |
|---|---|---|
| 1 | 上升趋势·纯持有(让利润奔跑) | `--green` |
| 2 | 深套防砍底·等待(硬时限6-8周) | `--red` |
| 3 | 趋势转弱·主动减仓 | `--gold` |
| 4 | 追踪止盈/止损·减仓(重仓出) | `--gold` |
| 5 | 跌破MA20·止盈减仓 | `--gold` |
| 6 | 持有观察(保底量) | `--text-2` |
| 0 | 数据不足 | `--text-2` |

`veto:true` → 在动作旁加灰标"超卖否决·暂不执行"。`locked` 非空 → 加 ⚠️ 锁定 badge。

---

## 3. UI 规格

### 3.1 顶部账户条（account header）
一行展示：
- 总市值 `total_mv`
- **上升持有** `held_strong_mv`（`held_strong_pct` 60%）—— 标注"让赢家跑·豁免保底"
- **保底进度**：`suggested_total` / `floor_target` + `floor_met` ✓/⚠️
- 市场 regime（小字, `--text-2`, 标"仅提示"）
- 数据新鲜度：`generated_at` + `data_date`（日度刷新；若 `generated_at` 距今 >2 交易日 → 黄色"数据偏旧, 定时任务可能挂了"）

### 3.2 主体：三个分组（按 rule）
PM 的心智是"今天做什么"，按动作分组优于按市值：

1. **🟡 可减仓队列**（rule 3/4/5）—— 按 `clip` 降序（=卖出优先级队列）。每行：基金名/代码、动作、`clip` %、`clip_amt` ¥、`dist_high60`、RSI、`vs_twap`、锁定 badge。
2. **🟢 上升趋势·持有**（rule 1）—— 纯持有，标"vs 均匀清仓少卖 10%"。
3. **🔴 深套/等待/其他**（rule 2/6/0）—— 深套两只(003095/009010)单独高亮，显示反弹锚(MA20)与硬时限提示。

### 3.3 每只展开 → 净值图
点击行展开/弹窗，`<img src="/api/fund-exit/chart/{code}">`（累计净值+MA20/60+近60高+追踪止盈位）。

### 3.4 底部 disclaimer
`disclaimer` 字段常驻页脚，`--text-2`。

---

## 4. 设计合规（必读 · 见 `DESIGN.md`，违反过 4+ 次的雷区）

- **必须** `<link rel="stylesheet" href="{{ url_for('static', filename='theme.css') }}?v=...">`；**禁止**在本模板重新内联 `:root` token，颜色一律用 shared CSS vars（`--green`/`--red`/`--gold`/`--text`/`--text-2`…）。
- **`--text-muted` 仅限占位符**。任何 PM 要读的 label/数字/动作/来源 一律 `--text-2`（或更亮的 `--text`），**不要**用 `--text-muted`。
- 字体沿用页面既有 `--f-display`(Newsreader) / `--f-mono`(JetBrains Mono) / `--f-ui`(DM Sans)；数字用 mono。
- 复用 portfolio_home 既有 `.nav` / `.container`(max 880px) / `.page-hero` 等 class，视觉与其余 tab 一致。
- 盈亏/涨跌色：盈/上升 `--green`，亏/下降 `--red`（与全站一致，勿自创色）。
- 深浅色主题都要过（theme.css 有 light 变体；只用 token 就自动适配）。

---

## 5. 空 / 异常状态
- `available:false` → 居中提示"信号未生成，运行 fund_exit/fund_exit_signals.py 后刷新"。
- 单只 `ok:false` → 该行显示"❌ 取数失败：{err}"，不影响其余（脚本已做隔离）。
- `generated_at` 过旧 → 顶部黄条提醒重跑。

---

## 6. Out of Scope（FE 不碰）
- `fund_exit_signals.py` 脚本本体 / akshare / 指标 / 规则逻辑（Quant 维护）。
- 信号阈值、clip 比例、规则语义（改动走 spec）。
- 脚本调度（cron）——可后续单独配；本 handoff 只要页面读现成 JSON。
- 赎回下单 / 交易执行（纯展示，不接券商）。

---

## 7. 验收
1. `/funds` tab 出现在 nav，风格与其余 tab 一致，深浅主题都正常。
2. 账户条正确显示 持有60% / 保底进度 / regime / 数据新鲜度。
3. 三分组按 rule 正确归类、可减仓队列按 clip 降序。
4. 点击展开能看到该基金净值图。
5. 009010 有锁定 ⚠️ badge；取数失败的基金优雅降级。
6. 无内联 `:root`、无 `--text-muted` 用于正文、颜色全走 token（过 DESIGN.md review）。
7. 清仓结束时，删除 `/funds` route + `funds.html` + nav link + `fund_exit/` 即可干净移除。
