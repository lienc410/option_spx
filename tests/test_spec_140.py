"""SPEC-140 — 推送-泳道对齐：真值源合并 acceptance tests.

AC map:
  §1 逐字相等断言 ×4（同一触发器：推送人话主文 == Decision Trace 节点
     label_human）：
       Lane B 21-DTE / Lane B collapse       → VerbatimLaneBTests
       Lane D halt（容量归零 veto）/ 联动线   → VerbatimLaneDTests
  §2 digest 四泳道镜像（A/B/D 结构 + C 缺席 + 无仓行）
     + 收件预算不变断言（分类与 dedupe 行为零变化）  → DigestFourLaneTests
  §3 DESIGN.md about↔lane 映射表 + gateway docstring 同步 + 晨报/digest
     尾部深链                                        → ContractAndDeeplinkTests
  §4 outcome↔category 映射常量 + 断言函数 + 全 gateway 调用点分类合规扫描
                                                     → OutcomeCategoryTests
  §5 推送哲学 doctrine 逐字入 DESIGN.md（与 task/SPEC-140.md §5 blockquote
     byte-identical）+ Decisions Log + Lane C 零推送钩子  → DoctrineTests
  单源静态断言（自写行文清除 + 消费方 import 同源函数）  → SingleSourceStaticTests

密闭：Lane B 触发器引擎跑真代码但仓位/链数据全为测试内 fixture
（open_bcd_positions patched——零 ledger 读写）；Lane D 装配复用
tests/test_spec_135_5 的 patch 面与脚本生成向量。
"""
from __future__ import annotations

import asyncio
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import notify.gateway as gw
import strategy.bcd_governance as gov
import strategy.decision_trace as dt
from tests.test_spec_135_5 import VECTORS, _lane_d_with

TODAY = "2026-07-13"


def _bcd_pos(*, expiry: str, short_strike: float = 6100.0,
             entry_price: float = 2.0) -> dict:
    """最小 open BCD 仓位（无 roll），current_short_leg 直接可解析。"""
    return {"id": "2026-06-03_bcd_001", "voided": False, "close": None,
            "rolls": [],
            "open": {"strategy_key": "bull_call_diagonal",
                     "short_strike": short_strike, "expiry": expiry,
                     "short_entry_price": entry_price,
                     "long_strike": 6000.0, "long_expiry": "2026-12-18"}}


def _chain(expiry: str, strike: float, mid: float) -> pd.DataFrame:
    return pd.DataFrame([{"expiry": expiry, "strike": strike, "mid": mid,
                          "bid": mid - 0.05, "ask": mid + 0.05}])


class VerbatimLaneBTests(unittest.TestCase):
    """§1 AC：H-5 推送正文首行 == Lane B 节点 label_human（逐字，×2）。
    两侧共享同一触发器引擎输出（evaluate_short_leg_actions 真代码），
    行文只在 decision_trace.lane_b_action_label 存在一份。"""

    def _both_sides(self, pos: dict, calls) -> tuple[str, dict]:
        with patch.object(gov, "open_bcd_positions", return_value=[pos]), \
             patch.object(gov, "_suggest_new_short", return_value=None):
            actions = gov.evaluate_short_leg_actions(TODAY, calls)
            self.assertEqual(len(actions), 1)
            push_body = gov._action_message(actions[0])
            lane_b = dt.lane_b_positions(TODAY, calls)
        node = next(n for n in lane_b if n["trade_id"] == pos["id"])
        return push_body, node

    def test_verbatim_1_lane_b_21dte(self) -> None:
        # 短腿 9 天到期（2026-07-22 vs today 07-13）→ 21-DTE 触发
        push_body, node = self._both_sides(_bcd_pos(expiry="2026-07-22"), None)
        self.assertEqual(node["state"], "action")
        self.assertEqual(push_body.splitlines()[0], node["label_human"])
        self.assertIn("只剩 9 天到期", node["label_human"])
        self.assertIn("平掉或滚动（roll）", node["label_human"])
        # 自写第二套（"机械规则动作: CLOSE 或 ROLL"版）已被单源取代
        self.assertNotIn("机械规则动作", push_body)

    def test_verbatim_2_lane_b_collapse(self) -> None:
        # 短腿 46 天到期（>21）但残值 0.25 ≤ 15% × 入场 2.00 → collapse 触发
        pos = _bcd_pos(expiry="2026-08-28")
        calls = _chain("2026-08-28", 6100.0, 0.25)
        push_body, node = self._both_sides(pos, calls)
        self.assertEqual(node["state"], "action")
        self.assertEqual(push_body.splitlines()[0], node["label_human"])
        self.assertIn("collapse buyback", node["label_human"])
        self.assertIn("12%", node["label_human"])       # 0.25/2.00 → 残值占比
        self.assertNotIn("天到期", node["label_human"].split("→")[0].split("残值")[0])

    def test_hold_label_same_source(self) -> None:
        """未触发行：digest/网页共用 lane_b_hold_label（阈值参数传入）。"""
        pos = _bcd_pos(expiry="2026-12-18")
        with patch.object(gov, "open_bcd_positions", return_value=[pos]):
            lane_b = dt.lane_b_positions(TODAY)
        node = lane_b[0]
        self.assertEqual(node["state"], "hold")
        self.assertEqual(node["label_human"],
                         dt.lane_b_hold_label(158, gov.SHORT_ACTION_DTE))
        self.assertIn("（>21 天）", node["label_human"])


class VerbatimLaneDTests(unittest.TestCase):
    """§1 AC：q042 executor alert 状态行 / digest 联动线 == Lane D 联动线
    节点 label_human（逐字，×2）。gate 行 = 135.5 脚本生成向量
    （compute_gate 唯一公式源）。"""

    def _linkage_node(self, gate_row: dict) -> dict:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            lane_d = _lane_d_with(VECTORS["inputs"], Path(tmp),
                                  gate_rows=[gate_row])
        return next(n for n in lane_d["engines"]
                    if n["check"] == "dd_overlay_main_linkage")

    def test_verbatim_3_lane_d_halt_blocked_alert(self) -> None:
        """容量归零（veto，真拦截）：executor 拦截 alert 状态行 == trace。"""
        from production.q042_executor import _format_blocked_alert
        from strategy.q042_gate import compute_gate
        row = VECTORS["inputs"]["gate_row_zero"]           # main_bp 65 → cap 0
        node = self._linkage_node(row)
        self.assertEqual(node["outcome"], "veto")
        gate = compute_gate(row["main_bp_pct"], date=row["date"])
        body = _format_blocked_alert(
            sleeve_id="A", blocked_reason="gate_binding_allowance_0",
            contracts=2, est=5000.0, ddath=-0.05,
            gate=gate, gate_available=True)
        self.assertEqual(body.splitlines()[2], node["label_human"])
        self.assertIn("容量归零（双 sleeve 禁开）", body)
        # fail-closed 档（gate 数据不可用推送的状态行）同源同函数
        from production.q042_executor import _linkage_status_line
        failclosed_node = self._linkage_node(
            VECTORS["inputs"]["gate_row_failclosed"])
        self.assertEqual(_linkage_status_line(None, False),
                         failclosed_node["label_human"])

    def test_verbatim_4_lane_d_linkage_digest_line(self) -> None:
        """联动线（压缩档 advisory）：digest 附行 == trace 节点（逐字）。"""
        import notify.telegram_bot as bot
        row = VECTORS["inputs"]["gate_row_squeezed"]       # main_bp 55 → cap 5
        node = self._linkage_node(row)
        self.assertEqual(node["outcome"], "advisory")
        lane_d = {"semantics": "…", "summary_line": "DD Overlay ARMED×2",
                  "engines": [node]}
        rec = MagicMock()
        rec.strategy_key = "reduce_wait"
        rec.canonical_strategy = "Bull Put Spread"
        with patch.object(bot, "get_recommendation", return_value=rec), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": []}), \
             patch("strategy.decision_trace.lane_b_positions",
                   return_value=[]), \
             patch("strategy.decision_trace.lane_d_sleeves",
                   return_value=lane_d), \
             patch("strategy.bcd_governance.is_halted", return_value=None), \
             patch("strategy.bcd_governance.quote_gate_status",
                   return_value={"unlocked": True, "days": 10, "needed": 10}), \
             patch.object(bot, "read_state", return_value={}):
            _, _, body = bot.build_preclose_digest()
        digest_line = next(l for l in body.splitlines()
                           if "与主策略的联动" in l)
        self.assertEqual(digest_line.strip(), node["label_human"])
        self.assertIn("被压缩到", digest_line)

    def test_linkage_pass_not_in_digest(self) -> None:
        """联动线"未压缩"档（pass）不附行（SPEC-140 §2）。"""
        import notify.telegram_bot as bot
        node = self._linkage_node(VECTORS["inputs"]["gate_log_rows"][1])
        self.assertEqual(node["outcome"], "pass")
        lane_d = {"semantics": "…", "summary_line": "DD Overlay ARMED×2",
                  "engines": [node]}
        rec = MagicMock()
        rec.strategy_key = "reduce_wait"
        rec.canonical_strategy = "Bull Put Spread"
        with patch.object(bot, "get_recommendation", return_value=rec), \
             patch("strategy.state.read_all_positions",
                   return_value={"positions": []}), \
             patch("strategy.decision_trace.lane_b_positions",
                   return_value=[]), \
             patch("strategy.decision_trace.lane_d_sleeves",
                   return_value=lane_d), \
             patch("strategy.bcd_governance.is_halted", return_value=None), \
             patch("strategy.bcd_governance.quote_gate_status",
                   return_value={"unlocked": True, "days": 10, "needed": 10}), \
             patch.object(bot, "read_state", return_value={}):
            _, _, body = bot.build_preclose_digest()
        self.assertNotIn("与主策略的联动", body)


def _digest_env(*, rec_key="reduce_wait", positions=None, lane_b=None,
                lane_d=None, halted=None, reauth=False):
    """build_preclose_digest 的统一 patch 面（密闭固定向量）。"""
    import notify.telegram_bot as bot
    rec = MagicMock()
    rec.strategy_key = rec_key
    rec.canonical_strategy = "Bull Put Spread"
    rec.strategy = "Bull Put Spread"
    lane_d = lane_d or {"semantics": "…", "engines": [],
                        "summary_line": "DD Overlay ARMED×2 · Aftermath 未激活 · "
                                        "压力机 CALM · ES Ladder HOLD 1/5"}
    return (
        patch.object(bot, "get_recommendation", return_value=rec),
        patch("strategy.state.read_all_positions",
              return_value={"positions": positions or []}),
        patch("strategy.decision_trace.lane_b_positions",
              return_value=lane_b or []),
        patch("strategy.decision_trace.lane_d_sleeves", return_value=lane_d),
        patch("strategy.bcd_governance.is_halted", return_value=halted),
        patch("strategy.bcd_governance.quote_gate_status",
              return_value={"unlocked": True, "days": 10, "needed": 10}),
        patch.object(bot, "read_state",
                     return_value={"requires_reauth": True} if reauth else {}),
    )


def _build_digest(**kw):
    import contextlib
    import notify.telegram_bot as bot
    with contextlib.ExitStack() as stack:
        for p in _digest_env(**kw):
            stack.enter_context(p)
        return bot.build_preclose_digest()


class DigestFourLaneTests(unittest.TestCase):
    """§2 AC：digest 快照结构（A/B/D + C 缺席）+ 收件预算不变断言。"""

    _LANE_B_ACTION = [{"trade_id": "2026-06-03_bcd_001", "state": "action",
                       "label_human": "卖出的近月 call 腿只剩 9 天到期 → 规则"
                                      "要求今天平掉或滚动（roll），已推送提醒",
                       "code_ref": "SPEC-127 §4 (21-DTE/collapse)"}]

    def test_structure_a_b_d_order_and_c_absent(self) -> None:
        _, _, body = _build_digest(
            positions=[{"trade_id": "2026-06-03_bcd_001",
                        "strategy_key": "bull_call_diagonal",
                        "expiry": "2099-12-17"}],
            lane_b=list(self._LANE_B_ACTION))
        i_a = body.index("今日新仓裁决")
        i_b = body.index("持仓 2026-06-03_bcd_001")
        i_d = body.index("<b>引擎</b>")
        i_gov = body.index("<b>治理</b>")
        i_link = body.index("完整决策链")
        self.assertTrue(i_a < i_b < i_d < i_gov < i_link, body)
        # B 行 = Lane B label 同源（触发器语义入 digest）
        self.assertIn("平掉或滚动（roll）", body)
        # D 行 = Lane D 摘要条同源
        self.assertIn("DD Overlay ARMED×2 · Aftermath 未激活 · 压力机 CALM · "
                      "ES Ladder HOLD 1/5", body)
        # Lane C（地形）缺席：描述层永不进 digest（Q090 封账口径）
        for token in ("地形", "call 墙", "量比", "趋势线"):
            self.assertNotIn(token, body)

    def test_no_open_positions_line(self) -> None:
        _, _, body = _build_digest(positions=[], lane_b=[])
        self.assertIn("今天没有 open 仓位", body)

    def test_lane_c_never_pushed_docstrings(self) -> None:
        """C 明确不推写死进 gateway/digest docstring（SPEC-140 §2）。"""
        import notify.telegram_bot as bot
        self.assertIn("Lane C", bot.build_preclose_digest.__doc__)
        self.assertIn("明确不推", bot.build_preclose_digest.__doc__)
        self.assertIn("Lane C", gw.__doc__)
        self.assertIn("永不推送", gw.__doc__)

    # ── 收件预算不变断言：分类与 dedupe 行为零变化 ────────────────────────────
    def test_budget_category_matrix_unchanged(self) -> None:
        # SPEC-126 分类规则逐字节等价：OPEN / dte≤7 / halt / 异常 → ACTION
        cat, _, _ = _build_digest()
        self.assertEqual(cat, "FYI")                        # 干净日
        cat, _, _ = _build_digest(rec_key="bull_put_spread")
        self.assertEqual(cat, "ACTION")                     # OPEN 候选
        cat, _, _ = _build_digest(positions=[
            {"trade_id": "T", "strategy_key": "bull_put_spread",
             "expiry": "2026-07-15"}])
        self.assertEqual(cat, "ACTION")                     # dte ≤ 7
        cat, _, _ = _build_digest(halted={"at": "2026-07-06"})
        self.assertEqual(cat, "ACTION")                     # halt
        cat, _, _ = _build_digest(reauth=True)
        self.assertEqual(cat, "ACTION")                     # 异常区

    def test_budget_mirror_rows_never_flip_category(self) -> None:
        """B/D 泳道镜像行与深链是纯渲染：Lane B action 行、联动线 advisory
        行都不得把干净日 FYI 抬成 ACTION（预算不变的核心断言）。"""
        lane_d = {"semantics": "…", "summary_line": "DD Overlay ARMED×2",
                  "engines": [{"check": "dd_overlay_main_linkage",
                               "outcome": "advisory",
                               "label_human": "与主策略的联动：主策略 BP 占用 "
                                              "55.0% 挤占 60% 预算线 → DD "
                                              "Overlay 容量档位被压缩到 5.0%"}]}
        cat, _, body = _build_digest(
            positions=[{"trade_id": "2026-06-03_bcd_001",
                        "strategy_key": "bull_call_diagonal",
                        "expiry": "2099-12-17"}],
            lane_b=list(self._LANE_B_ACTION), lane_d=lane_d)
        self.assertIn("平掉或滚动", body)                    # 镜像行在
        self.assertIn("与主策略的联动", body)                # 联动线在
        self.assertEqual(cat, "FYI")                        # 分类零变化

    def test_budget_single_send_same_dedupe_key(self) -> None:
        """仍是单条 digest，dedupe_key=preclose_digest 零变化。"""
        import notify.telegram_bot as bot
        apush = AsyncMock()
        with patch.object(bot, "is_trading_day", return_value=True), \
             patch.object(bot, "build_preclose_digest",
                          return_value=("FYI", "t", "b")), \
             patch("notify.gateway.apush", apush):
            asyncio.run(bot.scheduled_preclose_digest(MagicMock(), "c"))
        self.assertEqual(apush.await_count, 1)
        self.assertEqual(apush.await_args.kwargs.get("dedupe_key"),
                         "preclose_digest")
        self.assertEqual(apush.await_args.args[2:4], ("FYI", "系统状态"))


class ContractAndDeeplinkTests(unittest.TestCase):
    """§3 AC：DESIGN.md 映射表 + gateway docstring 同步 + 深链渲染。"""

    def test_design_md_about_lane_mapping_table(self) -> None:
        d = (REPO / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("about ↔ 泳道映射 (SPEC-140 §3)", d)
        for row in ("| 关于新开仓 | Lane A（今天开不开新仓） |",
                    "| 关于持仓 X | Lane B（手上的仓位要动吗） |",
                    "| 系统状态 | Lane D（决策引擎状态）及治理/运维事件 |"):
            self.assertIn(row, d)
        self.assertIn("Lane C（地形，只描述不决策）**永不推送**", d)

    def test_gateway_docstring_mapping_synced(self) -> None:
        for token in ("关于新开仓 = Lane A", "关于持仓 X = Lane B",
                      "系统状态   = Lane D", "Lane C", "永不推送"):
            self.assertIn(token, gw.__doc__)

    def test_digest_tail_deeplink(self) -> None:
        _, _, body = _build_digest()
        self.assertEqual(body.splitlines()[-1], gw.TRACE_DEEPLINK)
        self.assertIn("https://spx.portimperialventures.com/spx",
                      gw.TRACE_DEEPLINK)

    def test_morning_push_tail_deeplink(self) -> None:
        import notify.telegram_bot as bot
        rec = MagicMock()
        rec.strategy_key = "reduce_wait"
        apush = AsyncMock()
        with patch.object(bot, "is_trading_day", return_value=True), \
             patch.object(bot, "get_recommendation", return_value=rec), \
             patch.object(bot, "_safe_append_recommendation_event"), \
             patch.object(bot, "_format_recommendation",
                          return_value="BODY"), \
             patch("notify.gateway.apush", apush):
            asyncio.run(bot.scheduled_push(MagicMock(), "c"))
        self.assertEqual(apush.await_count, 1)
        body = apush.await_args.args[5]
        self.assertTrue(body.endswith(gw.TRACE_DEEPLINK), body)
        # 晨报 dedupe 零变化（预算不变）
        self.assertEqual(apush.await_args.kwargs.get("dedupe_key"),
                         "morning_push")


class OutcomeCategoryTests(unittest.TestCase):
    """§4 AC：映射常量 + 断言函数 + 全 gateway 调用点分类合规扫描。"""

    def test_mapping_constant_exact(self) -> None:
        self.assertEqual(gw.OUTCOME_CATEGORIES, {
            "halt": ("ALERT", "ACTION"),
            "veto": ("ALERT", "ACTION"),
            "advisory": ("STATE", "FYI"),
            "pass": (),
            "info": (),
        })

    def test_assert_outcome_category(self) -> None:
        self.assertEqual(gw.assert_outcome_category("halt", "ACTION"), "ACTION")
        self.assertEqual(gw.assert_outcome_category("veto", "ALERT"), "ALERT")
        self.assertEqual(gw.assert_outcome_category("advisory", "STATE"), "STATE")
        self.assertEqual(gw.assert_outcome_category("advisory", "FYI"), "FYI")
        with self.assertRaises(ValueError):
            gw.assert_outcome_category("advisory", "ALERT")   # 提示档不得响铃
        with self.assertRaises(ValueError):
            gw.assert_outcome_category("veto", "FYI")         # 真拦截不得静默
        with self.assertRaises(ValueError):
            gw.assert_outcome_category("pass", "FYI")         # pass/info 不推
        with self.assertRaises(ValueError):
            gw.assert_outcome_category("info", "STATE")
        with self.assertRaises(ValueError):
            gw.assert_outcome_category("route", "FYI")        # 未知 outcome

    # 与 test_spec_126 TestMigrationCompleteness 同款全仓扫描器
    _SKIP_DIRS = {"node_modules", "tests", ".git", ".claude"}

    @staticmethod
    def _is_skippable(part: str) -> bool:
        return (part.startswith("venv") or part.startswith(".venv")
                or part == "site-packages")

    def _repo_py_files(self):
        for p in REPO.rglob("*.py"):
            parts = p.relative_to(REPO).parts
            if any(part in self._SKIP_DIRS or self._is_skippable(part)
                   for part in parts):
                continue
            yield p

    def test_all_gateway_callsites_use_legal_categories(self) -> None:
        """全仓扫描：gateway push/apush 调用点的字面 category 只允许四类
        （pass/info 没有对应 category——正确做法是不调用 push）。"""
        pat = re.compile(
            r"\b(?:gw_push|apush|push)\(\s*(?:bot\s*,\s*chat_id\s*,\s*)?"
            r"[\"']([A-Z]+)[\"']")
        legal = set(gw.CATEGORY_EMOJI)
        offenders = []
        for p in self._repo_py_files():
            src = p.read_text(encoding="utf-8")
            if "notify.gateway" not in src and "notify import gateway" not in src:
                continue
            for m in pat.finditer(src):
                if m.group(1) not in legal:
                    offenders.append(f"{p.relative_to(REPO)}: {m.group(1)}")
        self.assertEqual(offenders, [],
                         f"gateway 调用点使用非法 category：{offenders}")

    def test_outcome_carrying_callsites_wired_to_assertion(self) -> None:
        """已知 outcome-携带调用点必须走 assert_outcome_category（防漂移）：
        BCD halt（halt→ACTION）、q042 拦截（veto→ACTION / advisory→FYI）、
        晨报敞口降级（advisory→STATE，SPEC-131 先例）。"""
        cases = {
            "strategy/bcd_governance.py": 'assert_outcome_category("halt", "ACTION")',
            "production/q042_executor.py": "assert_outcome_category(",
            "notify/telegram_bot.py": 'assert_outcome_category("advisory", "STATE")',
        }
        for rel, token in cases.items():
            src = (REPO / rel).read_text(encoding="utf-8")
            self.assertIn(token, src, rel)


class DoctrineTests(unittest.TestCase):
    """§5 AC：doctrine 段逐字落 DESIGN.md（与 SPEC-140 §5 blockquote
    byte-identical）+ Decisions Log 一行 + Lane C 层零推送钩子。"""

    def test_doctrine_verbatim_from_spec(self) -> None:
        spec = (REPO / "task" / "SPEC-140.md").read_text(encoding="utf-8")
        block = next(l for l in spec.splitlines()
                     if l.startswith("> **Telegram = 打断权"))
        design = (REPO / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn(block, design)       # 逐字（含 blockquote 前缀）

    def test_decisions_log_row(self) -> None:
        d = (REPO / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("推送哲学入宪（SPEC-140 §5）", d)
        self.assertIn("State Map（SPEC-141）=首个判例", d)

    def test_lane_c_layer_zero_gateway_import(self) -> None:
        """AC-5 本仓可执行部分：Lane C 真值层（structure_map）零 gateway
        import（SPEC-141 State Map 模块的同款断言由 141 lane 落地）。"""
        src = (REPO / "strategy" / "structure_map.py").read_text(encoding="utf-8")
        self.assertNotIn("notify.gateway", src)
        self.assertNotIn("from notify import gateway", src)


class SingleSourceStaticTests(unittest.TestCase):
    """§1 静态：唯一 copy 源存在、消费方 import、同一行文不得第二处出现。"""

    def test_copy_source_functions_exist(self) -> None:
        src = (REPO / "strategy" / "decision_trace.py").read_text(encoding="utf-8")
        for fn in ("def lane_b_action_label", "def lane_b_hold_label",
                   "def lane_d_linkage_label"):
            self.assertIn(fn, src)

    def test_consumers_import_shared_functions(self) -> None:
        gov_src = (REPO / "strategy" / "bcd_governance.py").read_text(encoding="utf-8")
        self.assertIn("from strategy.decision_trace import lane_b_action_label",
                      gov_src)
        ex_src = (REPO / "production" / "q042_executor.py").read_text(encoding="utf-8")
        self.assertIn("lane_d_linkage_label", ex_src)
        bot_src = (REPO / "notify" / "telegram_bot.py").read_text(encoding="utf-8")
        self.assertIn("lane_b_positions", bot_src)
        self.assertIn("lane_d_sleeves", bot_src)

    def test_no_second_copy_of_lane_b_wording(self) -> None:
        """"平掉或滚动"主文只活在 decision_trace（其余处只能经 import 渲染）。"""
        offenders = []
        for rel in ("strategy/bcd_governance.py", "notify/telegram_bot.py",
                    "production/q042_executor.py"):
            src = (REPO / rel).read_text(encoding="utf-8")
            if "平掉或滚动" in src:
                offenders.append(rel)
        self.assertEqual(offenders, [], f"Lane B 行文出现第二 copy 源：{offenders}")

    def test_no_second_copy_of_linkage_wording(self) -> None:
        offenders = []
        for rel in ("production/q042_executor.py", "notify/telegram_bot.py"):
            src = (REPO / rel).read_text(encoding="utf-8")
            if "与主策略的联动" in src:
                offenders.append(rel)
        self.assertEqual(offenders, [],
                         f"Lane D 联动线行文出现第二 copy 源：{offenders}")

    def test_old_self_written_copy_removed(self) -> None:
        gov_src = (REPO / "strategy" / "bcd_governance.py").read_text(encoding="utf-8")
        self.assertNotIn("机械规则动作", gov_src)   # 自写"CLOSE 或 ROLL"版已清除


if __name__ == "__main__":
    unittest.main()
