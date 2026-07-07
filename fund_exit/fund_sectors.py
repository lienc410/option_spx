# -*- coding: utf-8 -*-
"""基金重仓行业透视 (display-only, 不进卖出规则)

数据链:
  ak.fund_portfolio_hold_em    → 每只基金最新季度前十大重仓 (滞后~1季度, 覆盖 ~40-60% NAV)
  ak.stock_profile_cninfo      → 单股所属行业(证监会分类); 按需取、永久缓存
  (备注: EM 个股/板块端点 2026-07 起被反爬; sina 行业成分 49×2.5min 太慢, 均弃用)

输出 fund_sectors.json:
  {generated_at, quarter, funds: {code: {name, coverage, sectors:[[行业,占NAV%],..]}},
   account: {sectors:[[行业, 占已披露部分%],..], top_sector, top_share, disclosed_mv}}

定位: 透明层。行业数据滞后一季度且只覆盖前十大 → 不足以驱动自动卖出闸门
(同 5.5 市场 regime 降级先例), 但足以回答"剩下这几只是不是同一笔行业赌注"——
供 PM 每周决定 hold/加速 时参考。

刷新策略: 主扫描内嵌 refresh_if_stale() —— fund_sectors.json < 7 天跳过;
股票→行业缓存 sector_map_cache.json 按需增量(行业极少变, 永久复用)。
全程异常隔离, 失败不影响主扫描。
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

OUTDIR = Path(__file__).resolve().parent
SECTORS_JSON = OUTDIR / "fund_sectors.json"
MAP_CACHE = OUTDIR / "sector_map_cache.json"
SECTORS_MAX_AGE_D = 7      # fund_sectors.json 刷新周期


def _age_days(path: Path) -> float:
    if not path.exists():
        return 1e9
    try:
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        ts = datetime.fromisoformat(meta.get("generated_at", "1970-01-01T00:00:00"))
        return (datetime.now() - ts).total_seconds() / 86400
    except Exception:  # noqa: BLE001
        return 1e9


def _load_map_cache() -> dict:
    if MAP_CACHE.exists():
        try:
            with open(MAP_CACHE, encoding="utf-8") as f:
                return json.load(f).get("map", {})
        except (ValueError, OSError):
            pass
    return {}


def _save_map_cache(mapping: dict):
    import os
    tmp = str(MAP_CACHE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(timespec="seconds"),
                   "map": mapping}, f, ensure_ascii=False)
    os.replace(tmp, MAP_CACHE)


def resolve_sectors(codes: list, mapping: dict) -> dict:
    """按需补齐 股票→行业(证监会分类, cninfo 单股查询, 永久缓存)。"""
    import akshare as ak
    missing = [c for c in codes if c not in mapping]
    for c in missing:
        try:
            p = ak.stock_profile_cninfo(symbol=c)
            ind = str(p["所属行业"].iloc[0]) if "所属行业" in p.columns and len(p) else ""
            mapping[c] = ind or "未映射"
        except Exception as e:  # noqa: BLE001
            print(f"  {c} 行业查询失败(不缓存, 下次重试): {type(e).__name__}")
        time.sleep(0.5)
    if missing:
        _save_map_cache(mapping)
    return mapping


def fund_top10(code: str):
    """最新季度前十大重仓 [(股票代码, 股票名称, 占净值%), ...]"""
    import akshare as ak
    df = ak.fund_portfolio_hold_em(symbol=code, date=str(datetime.now().year))
    if df is None or len(df) == 0:   # 年初可能还没当年披露 → 退回上一年
        df = ak.fund_portfolio_hold_em(symbol=code, date=str(datetime.now().year - 1))
    if df is None or len(df) == 0:
        return None, []
    latest_q = sorted(df["季度"].unique())[-1]
    sub = df[df["季度"] == latest_q]
    rows = [(str(r["股票代码"]).zfill(6), str(r["股票名称"]), float(r["占净值比例"]))
            for _, r in sub.iterrows()]
    return latest_q, rows


def refresh(holdings) -> dict:
    """holdings: [(name, code, mv, pnl)] 活跃基金。生成 fund_sectors.json。"""
    smap = _load_map_cache()
    funds_out, quarter = {}, ""
    all_tops = {}
    for name, code, mv, _pnl in holdings:
        try:
            q, top = fund_top10(code)
        except Exception as e:  # noqa: BLE001
            print(f"  {code} 重仓获取失败: {type(e).__name__}")
            continue
        if top:
            all_tops[code] = (name, mv, q, top)
            quarter = q or quarter
        time.sleep(0.4)
    # 汇总所有需要的股票, 一次性补齐行业映射
    need = sorted({sc for _, _, _, top in all_tops.values() for sc, _, _ in top})
    smap = resolve_sectors(need, smap)

    acct_sector_val = {}      # 行业 → ¥(按基金 mv × 占NAV%)
    disclosed_mv = 0.0
    for code, (name, mv, q, top) in all_tops.items():
        sec_pct = {}
        for scode, sname, pct in top:
            sector = smap.get(scode, "未映射")
            sec_pct[sector] = sec_pct.get(sector, 0.0) + pct
        coverage = sum(p for _, _, p in top) / 100.0
        funds_out[code] = {
            "name": name,
            "coverage": round(coverage, 4),          # 前十大占 NAV 比例
            "sectors": sorted(((k, round(v, 2)) for k, v in sec_pct.items()),
                              key=lambda x: -x[1]),
            "top_holdings": [[c, n, p] for c, n, p in top[:10]],
        }
        for k, v in sec_pct.items():
            acct_sector_val[k] = acct_sector_val.get(k, 0.0) + mv * v / 100.0
        disclosed_mv += mv * coverage

    acct_sorted = sorted(acct_sector_val.items(), key=lambda x: -x[1])
    acct_sectors = [[k, round(v / disclosed_mv, 4)] for k, v in acct_sorted] if disclosed_mv else []
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "quarter": quarter,
        "note": "季报前十大重仓(滞后~1季度, 覆盖40-60% NAV); 仅透明层, 不进卖出规则",
        "funds": funds_out,
        "account": {
            "disclosed_mv": round(disclosed_mv, 2),
            "sectors": acct_sectors,                       # 占已披露部分的比例
            "top_sector": acct_sectors[0][0] if acct_sectors else None,
            "top_share": acct_sectors[0][1] if acct_sectors else None,
        },
    }
    import os
    tmp = str(SECTORS_JSON) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SECTORS_JSON)
    print(f"写出 {SECTORS_JSON} ({len(funds_out)} 只, 季度 {quarter})")
    return payload


def refresh_if_stale(holdings):
    """主扫描内嵌入口: fund_sectors.json 新鲜则跳过; 全程隔离不影响主扫描。"""
    try:
        if _age_days(SECTORS_JSON) < SECTORS_MAX_AGE_D:
            return
        refresh(holdings)
    except Exception as e:  # noqa: BLE001
        print(f"  行业透视刷新失败(跳过): {type(e).__name__}: {e}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(OUTDIR.parent))
    from fund_exit.fund_exit_signals import load_holdings
    refresh(load_holdings())
