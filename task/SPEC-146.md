# SPEC-146 — 晨报盘中数据源：双源 + 显式披露（静默回退退役）

## 动因（生产实锤，2026-07-13 晨报）

09:35 晨报显示 "VIX 15.0 [NORMAL]" 并按 SPEC-113 carve 推荐 BCD。事实：当日
bot 日志 `ERROR yfinance: $^VIX: possibly delisted; no price data found`——盘中
5m 主源失败，`except: pass` **静默回退到上周五收盘 15.03**；真实早盘 VIX
16.0-16.5（开盘 16.32）。当日 IVR 恰好未跨 30 界（真值 ~20-24 仍 IV_LOW），
路由侥幸未翻；若边界在早盘另一侧，就是一条按过期数据发出的错误 ACTION。
B1 silent-fallback 家族第 5 例（SPEC-094.2 B1 / SPEC-141 F1 / SPEC-118.2 同谱系）。

## 改动

1. `strategy/selector.py get_recommendation(use_intraday=True)`：
   - VIX/SPX 盘中主源（yfinance 5m）失败 → **第二源 Schwab quote**；
   - 双源均失败 → 回退上一收盘**但必须披露**（`Recommendation.data_notes`
     新字段，注明回退值与日期 + 提示人工复核 regime/IV）。
2. `notify/telegram_bot._format_recommendation`：渲染 `data_notes`（每条
   独立成行，feedback_multiline_notes）。

## AC（tests/test_spec_146.py，3 tests + 相邻 78+19 绿）

| AC | 结果 |
|---|---|
| 主源失败 → Schwab 值生效 + "替代"注记 | ✅ |
| 双源失败 → 回退值=上一收盘 + "双源均失败"注记进推送正文 | ✅ |
| 主源健康 → 零注记 | ✅ |
| select_strategy/回测路径零触碰（bit-identity 19 tests） | ✅ |

Status: DEPLOYED 2026-07-14
