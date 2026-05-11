# SPEC-094.1 Handoff

## 修改文件

- `strategy/q042_sizing.py` — `_OTM_PCT` 拆为 `_OTM_PCT_A=0.025` / `_OTM_PCT_B=0.05`；`_DTE_A=30` / `_DTE_B=90`；`compute_sizing()` 内 `oTM` / `dte` 按 sleeve 分支
- `signals/q042_trigger.py` — `get_q042_history()` Sleeve A expiry `days=90` → `days=30`；Sleeve B 保持 `days=90`
- `production/q042_executor.py` — `expiry` 拆为 `expiry_a`（30d）/ `expiry_b`（90d）；`_format_alert` DTE 字段 per-sleeve；`_write_pending_record` `dte` 字段 per-sleeve
- `backtest/q042_engine.py` — `_DTE/_OTM` 拆为 A/B；`_apply_no_overlap` 分别传 `_DTE_A`/`_DTE_B`；`_exp_date(sig, dte)` 加参数；`_enter()` 内 dte/otm per-sleeve
- `web/templates/index.html` — Sleeve A 标题 1.3/yr→1.81/yr，结构说明更新；grandfather 说明注脚
- `task/q042_manual_sop.md` — Sleeve A 结构改为 ATM/+2.5%、DTE 30；effective date 和 grandfather 注释

## 收尾

- 缓存清除：否（不涉及主策略 selector / engine / signals）
- Web 重启：否（template 改动需 push+deploy 生效；old Air 上 web 已在运行，前端改动下次 kickstart 时生效）
- Old Air 部署：`git pull` 已完成（commit `39092d1`）

## 验收结果

| AC | 项 | 结果 |
|---|---|---|
| AC-1.1 | no-overlap 30d → n≈35 | ✅ n=35（精确） |
| AC-1.2 | Sleeve A WR=74%±5pp, AnnROE=9.94%±0.5pp | ✅ WR=71.4%（±5pp内）/ ⚠️ AnnROE=9.03%（目标9.94%，-0.91pp，超±0.5pp容差） |
| AC-1.3 | Telegram DTE=30, short=ATM+2.5% for Sleeve A | ✅ 实测 DTE=30, K_short=7585（ATM 7400×1.025）|
| AC-1.4 | n=35 WR=74%±5pp ann=+9.94%±0.5pp MaxDD=-19.0%±2pp | ✅ n=35 / WR=71.4% / MaxDD=-19.0% / ⚠️ AnnROE=9.03% |
| AC-1.5 | 2026-03-12 OPEN expiry=2026-06-10 (old Air) | 跳过（dev 环境该仓位 DTE 30 → 已 CLOSED in backtest）|
| AC-1.6 | old Air state.json sleeve_a expiry=2026-06-10 | 未触碰 old Air state.json（grandfather 自动保护）|
| AC-1.7 | /api/q042/state 显示当前 in-flight dte=90 | 需 old Air 上 web 重启后验证 |
| AC-1.8 | index.html Sleeve A spec card 文案更新 | ✅ 1.81/yr, DTE 30, +2.5%, grandfather 注脚 |
| AC-1.9 | q042_manual_sop.md Sleeve A 1.81/yr + 结构更新 | ✅ |
| AC-1.10 | RESEARCH_LOG R-20260510-15 entry | ⚠️ **未找到**（Quant 尚未写入）|

## 阻塞/备注

- **AC-1.2/1.4 AnnROE 偏差 -0.91pp**：dev 层 AnnROE=9.03% vs 研究目标 9.94%。n=35/WR/MaxDD 全达标。偏差来源：Q062 研究脚本与 q042_engine.py 使用不同定价参数/数据截止点。Quant review 时确认是否在可接受范围内。
- **AC-1.10 RESEARCH_LOG 缺失**：DEVELOPER.md 规定 Developer 不修改 RESEARCH_LOG。需 Quant 补写 R-20260510-15 entry。
- **AC-1.7 验证**：old Air 上的 in-flight 2026-03-12 仓位通过 state machine 自动 grandfather（`active_position_id != null` 时 Sleeve A 不接受新 trigger）。验证命令：`curl http://localhost:5050/api/q042/state` 确认 `sleeve_a.active_position_expiry = "2026-06-10"`。
- **不在范围内**：Sleeve B 参数、old Air state.json、strategy/q042_gate.py、SPEC-098 前端。
