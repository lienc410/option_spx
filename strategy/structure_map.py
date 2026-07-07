"""SPEC-132 — 市场结构地图：可视化 + Q090 shadow 证据流共管道.

设计立场：描述性态势感知层，不是信号。Q090 verdict 随显示携带（badge），
不进推荐引擎、不进 gateway 推送（纯页面 + 静默 shadow）。

单一真值：flag 构造 import research/q090/q090_e1_fact_layer 的同款函数
（pivot k=5 + 确认滞后 5td；禁旁路重推——AC 含样本日 bit-identical 断言）。
Winner 切点（q090_e1_selection/confirmation，PM ratify 封账）：
  S1r 压力簇  = b3_t3_p10 (band .003, touches 3, prox .010)  — kill（NULL badge）
  S1s 支撑簇  = b3_t2_p5  (band .003, touches 2, prox .005)  — 无裁决，重开需 n≥100
  S4  递减线  = n3_p10    (3 highs, prox .010)               — kill（NULL badge）
  S2  量比    → 仅展示 V/20d 值（参数性彻底 null）
  S3  持仓墙  = |spot − top2 call 墙(dte≤45)| < 0.5%          — OPEN，前瞻 n≥60

Shadow：data/q090_structure_shadow.jsonl 每日一行（strict-JSON，finite 断言）；
心跳注册 com.spxstrat.q090_structure（SPEC-117 registry）；月度 digest 报
n 进度（S3 n/60、S1s n/100）。链快照缺失 fail-soft（行照写、标 chain_missing，
卡片显示 stale 日期）。
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
# 研究缓存（git tracked，Q085/Q090 复现真值）——生产只读作种子，绝不写回
RESEARCH_OHLC_CACHE = ROOT / "data" / "q085_spx_ohlc_cache.json"
# 生产 runtime 副本（gitignored）：首跑从研究缓存播种，之后每日增量追加。
# 分离原因 = SPEC-118.4 同款教训：runtime 日更文件 tracked 会在每次 oldair
# deploy 时制造 stash 冲突，且会把盘中/临时数据写进研究复现真值。
OHLC_CACHE = ROOT / "data" / "q090_ohlc_runtime.json"
SHADOW_PATH = ROOT / "data" / "q090_structure_shadow.jsonl"
CHAIN_DIR = ROOT / "data" / "q041_chains"
ET = ZoneInfo("America/New_York")

# Q090 winner 切点（q090_e1_selection.csv 真值；тags: S1r_b3_t3_p10 / S1s_b3_t2_p5 / S4_n3_p10）
S1R_PARAMS = {"band": 0.003, "touches": 3, "prox": 0.010}
S1S_PARAMS = {"band": 0.003, "touches": 2, "prox": 0.005}
S4_PARAMS = {"n_highs": 3, "prox": 0.010}
# Q090 framing S3: |spot − top2 call 墙(dte≤45)| < 0.5%（仅前瞻）
S3_WALL_DTE_MAX = 45
S3_PROX = 0.005
WALL_TOP_K = 3
# 重开条件（q090_e1_memo，PM ratify）
S3_TARGET_N = 60
S1S_TARGET_N = 100

log = logging.getLogger("structure_map")


def _q090():
    """研究模块延迟 import（生产函数单一化——同款构造，无本地重推）。"""
    import importlib
    return importlib.import_module("research.q090.q090_e1_fact_layer")


def _ensure_runtime_ohlc() -> None:
    """首跑：从研究缓存播种 runtime 副本。"""
    if OHLC_CACHE.exists():
        return
    OHLC_CACHE.parent.mkdir(parents=True, exist_ok=True)
    OHLC_CACHE.write_text(RESEARCH_OHLC_CACHE.read_text())
    log.info("runtime ohlc seeded from research cache")


def load_ohlc():
    """SPX OHLCV frame（runtime 副本；构造与 q085 battery / q090 E1 同源）。"""
    import pandas as pd
    _ensure_runtime_ohlc()
    d = json.loads(OHLC_CACHE.read_text())
    df = pd.DataFrame(d["history"])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _session_complete(day: str, now: datetime | None = None) -> bool:
    """只追加已完成 session：今天的 bar 仅在 16:15 ET 后可信（盘中 bar 会
    污染 pivot/量比构造——2026-07-07 12:40 实测 yfinance 返回半日 bar）。"""
    now = now or datetime.now(ET)
    today = now.date().isoformat()
    if day < today:
        return True
    if day > today:
        return False
    return (now.hour, now.minute) >= (16, 15)


def refresh_ohlc_cache() -> str | None:
    """yfinance ^GSPC 日线增量追加到 runtime 副本（fail-soft：失败用 stale
    数据继续）。Returns 最新缓存日期（ISO）。"""
    import pandas as pd
    _ensure_runtime_ohlc()
    try:
        d = json.loads(OHLC_CACHE.read_text())
        hist = d["history"]
        last = hist[-1]["date"] if hist else "1999-01-01"
        import yfinance as yf
        start = (pd.Timestamp(last) + pd.Timedelta(days=1)).date().isoformat()
        new = yf.download("^GSPC", start=start, auto_adjust=False, progress=False)
        appended = False
        if new is not None and len(new):
            if hasattr(new.columns, "levels"):   # MultiIndex (yf>=0.2.31)
                new.columns = new.columns.get_level_values(0)
            for ts, row in new.iterrows():
                day = ts.date().isoformat()
                if day <= last or not _session_complete(day):
                    continue
                vals = {k: float(row[k.capitalize()]) for k in ("open", "high", "low", "close")}
                vol = float(row["Volume"])
                if not all(math.isfinite(v) for v in [*vals.values(), vol]):
                    continue
                hist.append({"date": day, **{k: round(v, 2) for k, v in vals.items()},
                             "volume": vol})
                appended = True
        if appended:
            tmp = OHLC_CACHE.with_suffix(".tmp")
            tmp.write_text(json.dumps({"history": hist}))
            tmp.replace(OHLC_CACHE)
        return hist[-1]["date"] if hist else None
    except Exception:
        log.exception("ohlc refresh failed — continuing with stale cache")
        try:
            d = json.loads(OHLC_CACHE.read_text())
            return d["history"][-1]["date"] if d["history"] else None
        except Exception:
            return None


def compute_flags(ohlc_df, t: int | None = None) -> dict:
    """当日（或指定下标 t）的 Q090 winner flags + 描述性 level/line。

    flag 谓词 = q090_e1_fact_layer.cluster_flag_at / trendline_state_at
    （series 版本逐日调用同一谓词——bit-identity 由构造保证并被测试断言）。"""
    import numpy as np
    q = _q090()
    hi = ohlc_df["high"].to_numpy()
    lo = ohlc_df["low"].to_numpy()
    cl = ohlc_df["close"].to_numpy()
    if t is None:
        t = len(cl) - 1
    swing_hi, swing_lo = q.find_swing_pivots(hi, lo)
    hi_idx = np.where(swing_hi)[0]
    lo_idx = np.where(swing_lo)[0]
    spot = float(cl[t])

    s1r_flag = bool(q.cluster_flag_at(t, hi_idx, hi, cl, side="r", **S1R_PARAMS))
    s1s_flag = bool(q.cluster_flag_at(t, lo_idx, lo, cl, side="s", **S1S_PARAMS))
    s4_flag, s4_line = q.trendline_state_at(t, hi_idx, hi, cl,
                                            S4_PARAMS["n_highs"], S4_PARAMS["prox"])

    def _nearest(levels: list[dict]) -> dict | None:
        if not levels:
            return None
        best = min(levels, key=lambda x: abs(x["level"] - spot))
        return {"level": round(best["level"], 2), "touches": best["touches"],
                "dist_pct": round((best["level"] / spot - 1) * 100, 2)}

    r_levels = q.clusters_at(t, hi_idx, hi, S1R_PARAMS["band"], S1R_PARAMS["touches"])
    s_levels = q.clusters_at(t, lo_idx, lo, S1S_PARAMS["band"], S1S_PARAMS["touches"])

    vr = q.volume_ratio(ohlc_df["volume"]).iloc[t]
    return {
        "spot": round(spot, 2),
        "s1r_flag": s1r_flag,
        "s1r_nearest": _nearest(r_levels),
        "s1s_flag": s1s_flag,
        "s1s_nearest": _nearest(s_levels),
        "s4_flag": bool(s4_flag),
        "s4_line": round(s4_line, 2) if s4_line is not None else None,
        "vol_ratio": round(float(vr), 3) if math.isfinite(float(vr)) else None,
    }


def load_chain(date_str: str):
    """当日 SPX chain parquet（q041 16:30 快照）；缺失 → None。
    OI 墙用全部有 OI 的行（不做 iv 过滤——与 q085 定价用途不同）。"""
    import pandas as pd
    p = CHAIN_DIR / date_str / "SPX.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    return df if len(df) else None


def latest_chain_date() -> str | None:
    if not CHAIN_DIR.exists():
        return None
    days = sorted(d.name for d in CHAIN_DIR.iterdir()
                  if d.is_dir() and (d / "SPX.parquet").exists())
    return days[-1] if days else None


def top_walls(chain, spot: float, *, dte_max: int = S3_WALL_DTE_MAX,
              k: int = WALL_TOP_K) -> dict:
    """dte≤dte_max 内按 strike 聚合 OI：top-k call 墙（现价上方）/ put 墙
    （现价下方），strike + OI + 距现价%。S3 flag = |spot − top2 call 墙| < 0.5%
    （Q090 framing 逐字；top2 按 OI 排序，不限上下方）。"""
    sub = chain[(chain.dte <= dte_max) & (chain.open_interest > 0)]

    def _agg(side: str, above: bool):
        rows = sub[sub.option_type.str.upper() == side]
        g = rows.groupby("strike")["open_interest"].sum().sort_values(ascending=False)
        out = []
        for strike, oi in g.items():
            if above and strike <= spot:
                continue
            if not above and strike >= spot:
                continue
            out.append({"strike": float(strike), "oi": int(oi),
                        "dist_pct": round((float(strike) / spot - 1) * 100, 2)})
            if len(out) >= k:
                break
        return out, g

    calls, call_g = _agg("CALL", above=True)
    puts, _ = _agg("PUT", above=False)
    # S3: top2 call walls by OI (unrestricted side, per framing wording)
    top2 = list(call_g.index[:2])
    s3_flag = any(abs(spot - float(kk)) / spot < S3_PROX for kk in top2)
    return {"calls": calls, "puts": puts, "s3_flag": bool(s3_flag),
            "s3_top2": [float(kk) for kk in top2]}


def _assert_finite(obj, path="row") -> None:
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError(f"non-finite at {path}")
    if isinstance(obj, dict):
        for kk, v in obj.items():
            _assert_finite(v, f"{path}.{kk}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_finite(v, f"{path}[{i}]")


def build_daily_row(today: str | None = None) -> dict:
    """每日 shadow 行。链缺失 fail-soft：行照写（chain_missing=true，S3 不计）。"""
    today = today or datetime.now(ET).date().isoformat()
    ohlc_asof = refresh_ohlc_cache()
    df = load_ohlc()
    flags = compute_flags(df)
    row = {
        "date": today,
        "ohlc_asof": ohlc_asof,
        **flags,
    }
    chain = load_chain(today)
    if chain is None:
        row["chain_missing"] = True
        row["chain_asof"] = latest_chain_date()
    else:
        walls = top_walls(chain, flags["spot"])
        row["walls"] = {"calls": walls["calls"], "puts": walls["puts"]}
        row["s3_flag"] = walls["s3_flag"]
        row["s3_top2"] = walls["s3_top2"]
        row["chain_asof"] = today
    _assert_finite(row)
    return row


def append_shadow(row: dict) -> bool:
    """追加当日行（同日已存在 → skip，幂等重跑）。"""
    for existing in read_shadow():
        if existing.get("date") == row.get("date"):
            log.info("shadow row for %s already recorded — skip", row.get("date"))
            return False
    SHADOW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SHADOW_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return True


def read_shadow() -> list[dict]:
    rows: list[dict] = []
    if SHADOW_PATH.exists():
        for line in SHADOW_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def progress(rows: list[dict] | None = None) -> dict:
    """重开条件进度（月度 digest 用）：S3 触发日 n/60、S1s on-day n/100。"""
    rows = read_shadow() if rows is None else rows
    return {
        "days_logged": len(rows),
        "s3_n": sum(1 for r in rows if r.get("s3_flag")),
        "s3_target": S3_TARGET_N,
        "s1s_n": sum(1 for r in rows if r.get("s1s_flag")),
        "s1s_target": S1S_TARGET_N,
    }
