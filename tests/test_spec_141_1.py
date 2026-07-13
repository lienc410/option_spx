"""SPEC-141.1 — 三图接缝三项 AC（纯展示层，零逻辑变更）.

覆盖：
  §1 State Map ↔ Decision Trace 互链
     AC-1a trace_render.js 四个整卡渲染点（node / ev-inline / anchor / laneD）
           均经 _idOf 生成稳定 id="trace-<check>"；Lane D 区块锚 trace-lane-d；
           首页锚点摘要（trace-anchor-compact）不挂 id（同页整卡并存防重复 id）
     AC-1b state_map 深链 href 的 check 集合与后端 trace check 名同源生成断言
           （check 名 regex 直接提取自 strategy/selector.py 与
           strategy/decision_trace.py 源码——不建镜像清单，防漂移）
     AC-1c 每灯/卡可点（4 灯 + 3 引擎卡 = 7 链）+ hover title
           「查看决策链对应节点」
     AC-1d :target 高亮为纯 CSS（theme.css trace 共享段，双主题 vars 零裸 hex）；
           theme.css / trace_render.js 版本键随内容全站同步（Decisions Log
           2026-07-11 房规）
  §2 badge 双轴词汇映射（DESIGN.md）
     AC-2a 映射小表 + 「并存不互替」规则 + Decisions Log 行落地
     AC-2b 静态扫描无跨轴借词：state_map 徽章轴无词表词（ARMED/HOLD/…），
           trace 渲染器徽章轴无路由态词（ON/STANDBY）
  §3 nav 日期 ET 单源
     AC-3a _nav.html 唯一写点 + timeZone America/New_York（ET 交易日语义）
     AC-3b 全站模板零残留 nav-date 写点；state_map 根因写法（toISOString=UTC）
           不得回潮
     AC-3c 周日晚 ET 断言：UTC 已翻次日时 ET 日期仍是周日（根因回归钉）
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
TPL = REPO / "web" / "templates"
JS = (REPO / "web" / "static" / "trace_render.js").read_text(encoding="utf-8")
CSS = (REPO / "web" / "static" / "theme.css").read_text(encoding="utf-8")
STATE_MAP = (TPL / "state_map.html").read_text(encoding="utf-8")
NAV = (TPL / "_nav.html").read_text(encoding="utf-8")

ALL_TEMPLATES = sorted(TPL.glob("*.html"))


# ── 同源 check 名提取（与后端自吐同一源码，零镜像清单） ────────────────────────

def _trace_check_vocabulary() -> set[str]:
    """后端 trace 节点 check 名全集：selector 的 T.gate/T.add 第二参 +
    decision_trace 的 _sleeve_node 首参与 dict 字面量 "check" 键。"""
    checks: set[str] = set()
    selector_src = (REPO / "strategy" / "selector.py").read_text(encoding="utf-8")
    checks |= set(re.findall(r'T\.gate\([^,\n]*,\s*"([a-z0-9_]+)"', selector_src))
    checks |= set(re.findall(r'T\.add\("[a-z]+",\s*"([a-z0-9_]+)"', selector_src))
    dt_src = (REPO / "strategy" / "decision_trace.py").read_text(encoding="utf-8")
    checks |= set(re.findall(r'_sleeve_node\(\s*"([a-z0-9_]+)"', dt_src))
    checks |= set(re.findall(r'"check":\s*"([a-z0-9_]+)"', dt_src))
    return checks


def _state_map_linked_checks() -> list[str]:
    return re.findall(r'href="/spx#trace-([A-Za-z0-9_-]+)"', STATE_MAP)


# ── AC-1a — 渲染器稳定 id ────────────────────────────────────────────────────

def test_ac1a_trace_render_generates_stable_ids():
    assert 'id="trace-${' in JS.replace("String(n.check)", "")  # _idOf 模板
    # _idOf 定义 + 4 个渲染点消费（node / ev-inline / anchor / laneD）
    assert "function _idOf(n)" in JS
    assert JS.count("${_idOf(n)}") == 4
    # Lane D 区块锚（Premium/Trend 卡 fallback 目标）
    assert 'id="trace-lane-d"' in JS


def test_ac1a_compact_summary_carries_no_ids():
    """首页 SPX 卡锚点摘要与整卡同页并存——摘要不挂 id，防重复 id。"""
    i = JS.index("trace-anchor-compact")
    block = JS[max(0, i - 400):i + 400]
    assert "_idOf" not in block


# ── AC-1b — 深链目标与 check 名同源断言 ──────────────────────────────────────

def test_ac1b_state_map_links_resolve_to_backend_checks():
    vocab = _trace_check_vocabulary()
    # 断言提取器本身活着（防 regex 静默失配 → 空集恒真）
    for must in ("extreme_vol", "cash_floor", "dd_overlay",
                 "sleeve_stress_machine", "aftermath_window", "es_ladder"):
        assert must in vocab, f"check 提取器丢失 {must}——同源断言失效"
    linked = _state_map_linked_checks()
    assert linked, "state_map 无深链"
    for check in linked:
        if check == "lane-d":       # Lane D 区块锚（trace_render 卡内静态 id）
            continue
        assert check in vocab, f"state_map 深链 #trace-{check} 无后端 check 对应"


def test_ac1b_expected_light_and_card_targets():
    """四灯 + 三卡的具体指向（与 spec §1 括号内映射一致；second_leg 与 caps
    的真值同住 sleeve_stress_machine 节点——trace 无各自独立门行，见 spec
    冲突记录；Premium/Trend 无单一 lane_d 行 → 区块锚）。"""
    linked = _state_map_linked_checks()
    assert len(linked) == 7                       # 4 灯 + 3 引擎卡
    assert linked.count("extreme_vol") == 1
    assert linked.count("sleeve_stress_machine") == 2   # second_leg + caps
    assert linked.count("cash_floor") == 1
    assert linked.count("dd_overlay") == 1              # Convexity
    assert linked.count("lane-d") == 2                  # Premium + Trend


# ── AC-1c — 可点 + hover title ───────────────────────────────────────────────

def test_ac1c_links_are_anchors_with_hover_title():
    assert STATE_MAP.count('title="查看决策链对应节点"') == 7
    # 四灯是 <a class="veto-light">（整灯可点）
    assert STATE_MAP.count('<a class="veto-light" href="/spx#trace-') == 4
    # 三卡标题内 <a>（标题可点）
    assert len(re.findall(
        r'class="engine-name"><a href="/spx#trace-', STATE_MAP)) == 3


# ── AC-1d — :target 纯 CSS 高亮 + 版本键全站同步 ──────────────────────────────

def test_ac1d_target_highlight_is_pure_css():
    i = CSS.index("trace-target-flash")
    block = CSS[max(0, i - 700):i + 700]
    assert ":target" in block
    assert "scroll-margin-top" in block
    assert "var(--gold-bg)" in block              # 双主题 vars
    rules = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    assert "#" not in rules.replace("#trace", "")  # 零裸 hex
    # 深链 reveal 只做最小定位（开卡/解折叠/重放 fragment），高亮零 JS
    assert "traceRevealHash" in JS
    assert "location.replace(h)" in JS


def test_ac1d_asset_versions_bumped_sitewide():
    """theme.css 内容变更 → 版本键全站同步（DESIGN.md Decisions Log 2026-07-11）。"""
    refs = 0
    for p in ALL_TEMPLATES:
        src = p.read_text(encoding="utf-8")
        for m in re.finditer(r"theme\.css'\) \}\}\?v=([a-z0-9_]+)", src):
            assert m.group(1) == "spec141_1", f"{p.name} 钉旧版本 {m.group(1)}"
            refs += 1
    assert refs >= 20
    for page in ("spx.html", "portfolio_home.html"):
        src = (TPL / page).read_text(encoding="utf-8")
        assert "trace_render.js') }}?v=spec141_1" in src, page


# ── AC-2 — badge 双轴词汇映射 ────────────────────────────────────────────────

def test_ac2a_design_md_mapping_table_and_decisions_log():
    design = (REPO / "DESIGN.md").read_text(encoding="utf-8")
    assert "Routing-state axis vs word-vocabulary axis (SPEC-141.1)" in design
    # 小表两行
    assert re.search(r"\|\s*ON\s*\|\s*（无对应——当日被路由）\s*\|", design)
    assert re.search(r"\|\s*STANDBY\s*\|\s*ARMED / CALM / NO ENTRY\s*\|", design)
    # 并存不互替 + 页面内禁混轴
    assert "并存不互替" in design
    assert "不得混轴借词" in design
    # Decisions Log 行
    assert re.search(r"\| 2026-07-12 \| ON/STANDBY（State Map 路由态轴）", design)


def test_ac2b_state_map_has_no_vocabulary_axis_words_as_badges():
    """State Map 徽章轴只有 ON/STANDBY（SPEC-141 AC-5 已钉）；词表轴词不得
    以元素文本形式借入（Trigger armed: 行内字段除外，非徽章）。"""
    for banned in (">ARMED<", ">HOLD<", ">WATCHING<", ">CALM<",
                   ">NO ENTRY<", ">SIGNAL<", ">BLOCKED<", ">OPEN<", ">CLOSE<"):
        assert banned not in STATE_MAP, banned


def test_ac2b_trace_renderer_has_no_routing_axis_words():
    """trace 渲染器徽章轴 = DESIGN.md 词表词；路由态轴词 ON/STANDBY 不得借入。"""
    assert "'ON'" not in JS
    assert "STANDBY" not in JS
    assert "tb-on" not in JS and "tb-standby" not in JS
    # 词表轴映射表仍完整（防误删）
    for word in ("'SIGNAL'", "'ARMED'", "'WATCHING'", "'WARNING'",
                 "'HOLD'", "'NO ENTRY'", "'CALM'", "'BLOCKED'"):
        assert word in JS, word


# ── AC-3 — nav 日期 ET 单源 ──────────────────────────────────────────────────

def test_ac3a_nav_single_source_with_et_timezone():
    assert "getElementById('nav-date')" in NAV
    assert "timeZone: 'America/New_York'" in NAV
    assert NAV.count("toLocaleDateString") == 1


def test_ac3b_no_page_level_nav_date_writers_remain():
    for p in ALL_TEMPLATES:
        if p.name == "_nav.html":
            continue
        src = p.read_text(encoding="utf-8")
        assert "getElementById('nav-date')" not in src, p.name
        assert 'getElementById("nav-date")' not in src, p.name
    # 根因写法不得回潮：state_map nav 日期曾用 toISOString()（UTC 语义）
    assert "toISOString" not in STATE_MAP


def test_ac3c_sunday_evening_et_semantics():
    """根因回归钉：周日 2026-07-12 21:00 ET 时 UTC 已是 07-13——
    toISOString()（UTC 日期）显 07-13，ET 语义必须仍显 07-12（周日）。"""
    et = ZoneInfo("America/New_York")
    sunday_evening = datetime(2026, 7, 12, 21, 0, tzinfo=et)
    assert sunday_evening.astimezone(timezone.utc).date().isoformat() \
        == "2026-07-13"                       # 旧写法（UTC）的错误输出
    assert sunday_evening.date().isoformat() == "2026-07-12"   # ET 交易日语义
    assert sunday_evening.strftime("%a") == "Sun"
