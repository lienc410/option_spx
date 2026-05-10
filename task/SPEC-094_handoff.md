# SPEC-094 Handoff

## 修改文件

**新規ファイル（8）**：
- `strategy/q042_pricing.py` (new) — BS + skew haircut + term-multiplier 定价函数（F2/F8 共用）
- `signals/q042_trigger.py` (new) — 双 sleeve 状态机（F1）；re-arm is position-agnostic (matches research methodology); state persisted to `data/q042_state.json`
- `strategy/q042_sizing.py` (new) — SPX-only position sizing（F2）；`compute_sizing(nlv, spx_close, vix, sleeve_id)`
- `strategy/q042_gate.py` (new) — joint BP gate（F3）；`compute_gate`, `log_gate`；daily log → `data/q042_gate_log.jsonl`
- `production/q042_executor.py` (new) — EOD evaluation + Telegram alert（F5 revised）；Telegram-only, no Schwab API; `run_eod_evaluation`
- `production/q042_positions.py` (new) — position tracking & European cash settlement（F6）；expiry = signal + 90 calendar days
- `backtest/q042_engine.py` (new) — walk-forward 2007-2026 backtest（F8）；trigger detection uses research methodology (find_triggers_ddath + apply_no_overlap); outputs `data/q042_backtest_trades.csv` (AC22) + daily BP series (AC23)
- `data/q042_state.json` (new) — initial sleeve state（both armed=true, no positions）

**修正ファイル（5）**：
- `research/q041/collect_chains.py:63` — `_STRIKE_COUNT["$SPX"]` 100 → 160（+3.4% → ±5.4% OTM coverage; Quant 指定 to-do）
- `web/server.py:460` — `/api/q042/state` endpoint added（F7）
- `web/templates/index.html:864` — Q042 dual-sleeve card HTML + `renderQ042()` + `loadQ042()` JS + auto-refresh 5分おき（F7）
- `sync/open_questions.md:6,1445` — Q042 status updated to IMPLEMENTED
- `QUANT_RESEARCHER.md:500` — Q042 Active Strategy section added（F9）

## 修訂ノート（F5 修訂 + AC21 debug）

### F5 修訂（Telegram-only アーキテクチャ）
- `q042_executor.py` を全面書き直し：Schwab API 呼び出し削除、`run_t1_placement` 削除
- Telegram alert format は AC14 準拠（"→ Place SPX call spread at T+1 open" 追記済み）
- `_write_pending_record` で `fill_debit=null, entry_time=null` の pending record を書き込み（AC17）
- AC15（60s window）は SPEC で削除済み

### AC21 debug（2026-05-10 実施）

**根因 A（主因）**: `backtest/q042_engine.py` の `_enter()` で `contracts = int(budget / debit) = 0` になる trade が skip されていた。現在の SPX 水準（7400）では spread debit ~$12k > 10% × $100k seed = $10k → contracts=0 → skip。

**根因 B（metrics 定義不一致）**: `account_pct = pnl / account_at_entry` は research 定義 `account_pct = (pnl_pct_debit/100) × sizing_pct` と異なる。

**根因 C（state machine divergence）**: `signals/q042_trigger.py` の `update_sleeve_a/b` が re-arm に `not has_pos` チェックを含んでおり、position open 中に ddATH が -2% 回復しても re-arm されなかった。研究スクリプト（find_triggers_ddath）は position-agnostic で re-arm → no-overlap フィルタで重複除去する設計。

**修正**:
1. `signals/q042_trigger.py`: re-arm 条件から `not has_pos` を削除（position-agnostic re-arm）
2. `backtest/q042_engine.py`: trigger 検出を research 方式（`_find_triggers_ddath + _apply_no_overlap`）に切り替え；`_enter()` で `contracts=1.0`（固定）；`account_pct = (pnl_ps / debit_ps) × sizing_pct`（research 定義）
3. 全ファイル: expiry 91 → 90 calendar days（research の no-overlap 定義に合わせる）

## 収尾

- 缓存清除：否（不涉及 `strategy/selector.py` / `backtest/engine.py` / `signals/`）
- Web 重启：否（前端変更を反映するには git push + deploy to old Air が必要）

## 验收结果

### AC21 実測値（2026-05-10）

```
Sleeve A: n=25 ✓, win=64% ✓, total=97.3% (target 99%, diff=-1.7pp ✓), max_dd=-15.9% (target -16.3%, diff=+0.4pp ✓)
Sleeve B: n=5 ✓, win=100% ✓, total=42.5% (target 41%, diff=+1.5pp ✓), max_dd=0% ✓
AC22: data/q042_backtest_trades.csv 書き込み済み ✓
AC23: daily_rows=4868 ✓
```

### 冒烟检查コマンド（AC6/7/9/10/11）

```bash
# AC6: sizing $500k
python3 -c "from strategy.q042_sizing import compute_sizing; print(compute_sizing(500000, 7400, 25, 'A'))"
# Expected: (7400, 7770, 4, ~11000)

# AC7: sizing $150k
python3 -c "from strategy.q042_sizing import compute_sizing; print(compute_sizing(150000, 7400, 25, 'A'))"
# Expected: (None, None, 0, None)

# AC9: gate main_bp=30%
python3 -c "from strategy.q042_gate import compute_gate; g=compute_gate(30); print(g.sleeve_a_allowance, g.sleeve_b_allowance)"
# Expected: 10.0 10.0

# AC10: gate main_bp=55%
python3 -c "from strategy.q042_gate import compute_gate; g=compute_gate(55); print(g.sleeve_a_allowance, g.sleeve_b_allowance)"
# Expected: 2.5 2.5

# AC11: gate main_bp=65%
python3 -c "from strategy.q042_gate import compute_gate; g=compute_gate(65); print(g.sleeve_a_allowance, g.sleeve_b_allowance)"
# Expected: 0.0 0.0

# AC21: backtest
python3 -m backtest.q042_engine
# Sleeve A: n=25, win=64%, total~99%, max_dd~-16%
# Sleeve B: n=5, win=100%, total~41%, max_dd=0%
```

### 未检查项

- AC14（Telegram format）: requires live TELEGRAM_BOT_TOKEN；format code reviewed only
- AC5（state persistence）: code reviewed; data/q042_state.json 初期值 written

## 阻塞/备注

- **RESEARCH_LOG.md 未更新**：DEVELOPER.md 規則「Developer 默认不修改 RESEARCH_LOG.md」；F9 の RESEARCH_LOG 更新は Quant Researcher が補充
- **F4 standing obligation**：首次 live HIGH_VOL trigger（VIX ≥ 22）当天，Quant 必须 re-run `research/q042/q042_f4_oldair_backfill.py` 对当天 chain 重新验证 delta
- **collect_chains +5% coverage**：改动仅影响未来 archive 收集；历史 archive（2026-05-04~05-08）strike 范围不变（仍到 +3.4% OTM）
- **生産 trigger 判定と backtest の微妙な差異**：`signals/q042_trigger.py` の state machine（daily EOD 用）と `backtest/q042_engine.py` の `_find_triggers_ddath + apply_no_overlap`（バックテスト用）は理論的に同値だが、実際のシグナル日程は edge case で数日ずれる可能性あり。Quant review 時に確認推奨
