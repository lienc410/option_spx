"""SPEC-130 — pytest 全局密闭层（INCIDENT 2026-07-07）.

事故：dev 机 pytest 全量跑把 ~187（7/7）+68（7/6）条测试夹具推送真发给了 PM
（.env 真 token + event_push 运行时 env 读取 + 测试未全局 mock 传输层）。
"测试触碰生产资源"第二实例——按二次浮面规则，密闭性升级为强制房规。

════════════════════════════════════════════════════════════════════════════
外部副作用通道隔离清单（房规落点——新增通道必须同步登记到这里，不开镜像文档）
════════════════════════════════════════════════════════════════════════════
1. Telegram 推送（本 conftest，SPEC-130）
   - 出口：notify/event_push._send、notify/telegram_bot._safe_send、遗留直连
     sender（scripts/etrade_status_notify、research/q041/collect_chains、
     research/q041/daily_chain_sanity）——全部先过 event_push.push_enabled()
     主机 guard（SPX_PUSH_ENABLE=1 仅 oldair 生产 plists 设置）。
   - 测试态：autouse fixture 强制 delenv SPX_PUSH_ENABLE（guard 兜底）+
     api.telegram.org HTTP 绊线（触真网络即 pytest.fail）+ push_stats /
     push_ledger（SPEC-139 #22 send-ledger）/ gateway dedupe 重定向 tmp。真活体
     发送 = @pytest.mark.live_push + SPX_TEST_LIVE_PUSH=1 双重 opt-in，默认 skip。
2. Ledger 文件（#1 实例 ghost ledger rows，47648fa）
   - logs/trade_log.jsonl（logs.trade_log_io.TRADE_LOG_FILE）、
     data/closed_trades.jsonl（strategy.state.CLOSED_TRADES_FILE）、
     logs/current_position.json（strategy.state.STATE_FILE）——任何触发
     open/close/roll 路径的测试必须在 setUp monkeypatch 三者到 tmp
     （范例：tests/test_state_and_api.py）。ledger 是 append-only 生产真值，
     测试写入即污染（2026-06-07 与 07-06 各发生一次）。
3. Broker 写操作（Schwab/E-Trade token 刷新、订单接口）
   - 测试不得运行 scripts/*_token_*.py / etrade_reauth 流程主体；auth 层
     token 文件路径如被测试触及必须 monkeypatch（当前无测试直达真 broker
     写路径——新增时先登记）。
4. 磁盘缓存 / 运行时状态文件
   - data/backtest_*_cache.json（测试内用 server 模块的 _RESULTS_DISK_CACHE
     等 monkeypatch）、logs/push_stats.json 与 data/.push_dedupe.json（本
     conftest 自动重定向）、data/q087_bcd_governance_state.json 等治理状态
     （范例：tests/test_spec_123.py 的 gov.*_PATH monkeypatch）。
5. Overlay F shadow log（2026-07-13 顺序 flake 绊线第 2 触发时发现的漏项）
   - strategy/overlay._SHADOW_LOG / _ALERT_LATEST 是相对路径，任何走
     get_recommendation 全链的测试都在向真实 data/overlay_f_shadow.jsonl
     追加（dev 机已积到 26MB）——本 conftest 自动重定向 tmp。需要断言
     写路径行为的测试自行 patch 专用 tmp（范例：test_overlay_f_monitoring）。
════════════════════════════════════════════════════════════════════════════

层 3 元断言：session 结束时断言真实 logs/push_stats.json 在会话期间零增量
（stats 写入位于主机 guard 之后，任何增量都意味着密闭被穿透）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import requests

import notify.event_push as _ep
import notify.gateway as _gw

_REPO = Path(__file__).resolve().parents[1]
_REAL_PUSH_STATS = _REPO / "logs" / "push_stats.json"
_REAL_PUSH_LEDGER = _REPO / "logs" / "push_ledger.jsonl"   # SPEC-139 #22
_REAL_REQUESTS_POST = requests.post

# 会话期间被密闭层拦下/记录的推送尝试（调试用，可在测试里 import 检查）
PUSH_ATTEMPTS: list[str] = []

_REAL_SEND = _ep._send  # 原始传输函数引用（AC-1 类测试直接测它）


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_push: 真活体 Telegram 发送的集成冒烟（默认 skip；需要 "
        "SPX_TEST_LIVE_PUSH=1 且宿主 guard 允许才运行）",
    )


def _stats_totals() -> dict:
    if not _REAL_PUSH_STATS.exists():
        return {}
    try:
        return json.loads(_REAL_PUSH_STATS.read_text())
    except json.JSONDecodeError:
        return {}


def _ledger_snapshot() -> str:
    """SPEC-139 #22 — raw bytes of the real send-ledger for the零增量 meta-assert."""
    if not _REAL_PUSH_LEDGER.exists():
        return ""
    return _REAL_PUSH_LEDGER.read_text()


@pytest.fixture(scope="session", autouse=True)
def _push_stats_meta_assert():
    """SPEC-130 层 3 — 元断言：真实 push_stats.json 与 push_ledger.jsonl 会话
    期间零增量（两者写入均位于主机 guard 之后，任何增量即密闭被穿透）。"""
    baseline = _stats_totals()
    ledger_baseline = _ledger_snapshot()
    yield
    if os.environ.get("SPX_TEST_LIVE_PUSH") == "1":
        return  # live_push opt-in 会话允许真实计数增长
    after = _stats_totals()
    assert after == baseline, (
        "SPEC-130 元断言失败：logs/push_stats.json 在测试会话期间发生增量 "
        f"{baseline} -> {after} — 有测试穿透了推送密闭层（真发送已发生）！"
    )
    assert _ledger_snapshot() == ledger_baseline, (
        "SPEC-139 元断言失败：logs/push_ledger.jsonl 在测试会话期间发生增量 "
        "— 有测试穿透了 send-ledger 密闭层（真发送已发生）！"
    )


@pytest.fixture(autouse=True)
def _hermetic_push(request, monkeypatch, tmp_path):
    """SPEC-130 层 2 — 每个测试的推送密闭：

    1. 强制 delenv SPX_PUSH_ENABLE → 生产主机 guard 处于 deny 态（防线一）；
       需要测试 guard=1 分支的测试自行 setenv（配合 mock 的 HTTP 层）。
    2. api.telegram.org HTTP 绊线：任何测试尝试真 Telegram 调用立即 fail
       （防线二——即使 guard 被回归破坏也拦得住）。
    3. event_push._send 包装为 recorder（记录尝试 + 透传给真函数；真函数被
       guard 拦下，零 HTTP）——既保留对真实传输代码路径的持续检验，又不破坏
       在 requests 层 mock 的存量传输测试。
    4. push_stats / gateway dedupe 重定向 tmp（隔离清单 §4）。

    @pytest.mark.live_push 的测试跳过密闭（且默认整体 skip，须
    SPX_TEST_LIVE_PUSH=1 opt-in）。
    """
    if request.node.get_closest_marker("live_push"):
        if os.environ.get("SPX_TEST_LIVE_PUSH") != "1":
            pytest.skip("live_push 集成冒烟需要 SPX_TEST_LIVE_PUSH=1 显式 opt-in")
        yield
        return

    monkeypatch.delenv(_ep.PUSH_ENABLE_ENV, raising=False)
    monkeypatch.setattr(_ep, "PUSH_STATS", tmp_path / "push_stats.json")
    monkeypatch.setattr(_ep, "PUSH_LEDGER", tmp_path / "push_ledger.jsonl")  # SPEC-139 #22
    monkeypatch.setattr(_gw, "DEDUPE_PATH", tmp_path / "push_dedupe.json")

    # 隔离清单 §5 — overlay F shadow 通道（相对路径，get_recommendation 全链
    # 测试曾向真实 data/ 追加）；测试内自行 patch 者以其 patch 为准。
    import strategy.overlay as _ov
    monkeypatch.setattr(_ov, "_SHADOW_LOG", tmp_path / "overlay_f_shadow.jsonl")
    monkeypatch.setattr(_ov, "_ALERT_LATEST", tmp_path / "overlay_f_alert_latest.txt")

    def _guarded_post(url, *args, **kwargs):
        if "api.telegram.org" in str(url):
            pytest.fail(
                "SPEC-130 密闭性违规：测试尝试对 api.telegram.org 发起真实 "
                "HTTP 调用。活体发送必须用 @pytest.mark.live_push + "
                "SPX_TEST_LIVE_PUSH=1 opt-in。"
            )
        return _REAL_REQUESTS_POST(url, *args, **kwargs)

    monkeypatch.setattr(requests, "post", _guarded_post)

    def _recording_send(text, *, disable_notification=False, meta=None):
        PUSH_ATTEMPTS.append(str(text))
        return _REAL_SEND(text, disable_notification=disable_notification, meta=meta)

    monkeypatch.setattr(_ep, "_send", _recording_send)
    yield
