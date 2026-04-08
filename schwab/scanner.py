from __future__ import annotations

import math

from schwab.client import get_option_chain

_DELTA_SCAN_WINDOWS = (80, 140, 220)
_SCORE_WINDOW = 10


def _is_index_symbol(symbol: str | None) -> bool:
    return str(symbol or "").upper() in {"SPX", "$SPX"}


def _delta_gap(actual_delta: float, target_delta: float) -> float:
    return abs(abs(float(actual_delta)) - abs(float(target_delta)))


def _seek_target_delta_strike(chain: list[dict], target_delta: float) -> float | None:
    rows: list[tuple[float, float]] = []
    for row in chain:
        try:
            strike = float(row["strike"])
            delta = abs(float(row["delta"]))
        except (KeyError, TypeError, ValueError):
            continue
        rows.append((strike, delta))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0][0]

    for idx in range(len(rows) - 1):
        strike_lo, delta_lo = rows[idx]
        strike_hi, delta_hi = rows[idx + 1]
        if min(delta_lo, delta_hi) <= target_delta <= max(delta_lo, delta_hi):
            if delta_hi == delta_lo:
                return strike_lo
            t = (target_delta - delta_lo) / (delta_hi - delta_lo)
            return strike_lo + t * (strike_hi - strike_lo)

    if abs(rows[0][1] - target_delta) <= abs(rows[-1][1] - target_delta):
        return rows[0][0]
    return rows[-1][0]


def _recommended_delta_gap(rows: list[dict], target_delta: float) -> float | None:
    if not rows:
        return None
    recommended = next((row for row in rows if row.get("recommended")), rows[0])
    try:
        return _delta_gap(float(recommended.get("delta")), float(target_delta))
    except (TypeError, ValueError):
        return None


def _is_boundary_hit(chain: list[dict], sought_strike: float | None) -> bool:
    if not chain or sought_strike is None:
        return True
    strikes: list[float] = []
    for row in chain:
        try:
            strikes.append(float(row["strike"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not strikes:
        return True
    return sought_strike == min(strikes) or sought_strike == max(strikes)


def scan_strikes(chain: list[dict], target_delta: float, symbol: str | None = None) -> list[dict]:
    filtered: list[dict] = []
    is_index_symbol = _is_index_symbol(symbol)
    for row in chain:
        try:
            bid = float(row.get("bid") or 0)
            spread_pct = float(row.get("spread_pct") or 0)
            open_interest = float(row.get("open_interest") or 0)
            actual_delta = float(row.get("delta"))
        except (TypeError, ValueError):
            continue

        if bid <= 0:
            continue
        if spread_pct > 0.50:
            continue
        if not is_index_symbol and open_interest < 100:
            continue

        volume = row.get("volume") or 0
        volume_penalty = 0.1 if not volume else 0.0
        if is_index_symbol:
            oi_penalty = 0.35 if open_interest <= 0 else 0.2 * (1 / math.log(open_interest + 2))
        else:
            oi_penalty = (1 / math.log(open_interest + 1)) * 0.2
        score = (
            abs(actual_delta - float(target_delta)) * 0.4
            + spread_pct * 0.4
            + oi_penalty
            + volume_penalty
        )
        filtered.append({
            **row,
            "score": round(score, 3),
            "recommended": False,
        })

    filtered.sort(key=lambda row: (row["score"], abs(float(row.get("strike") or 0))))
    if filtered:
        filtered[0]["recommended"] = True
    return filtered


def build_strike_scan(
    symbol: str,
    option_type: str,
    target_delta: float,
    target_dte: int,
    center_strike: float | None = None,
) -> dict:
    if center_strike is None:
        rows = scan_strikes(
            get_option_chain(symbol, option_type, target_dte),
            target_delta=target_delta,
            symbol=symbol,
        )
        return {
            "rows": rows,
            "scan_fallback": not bool(rows),
        }

    selected_chain: list[dict] = []
    best_center = float(center_strike)
    for strike_window in _DELTA_SCAN_WINDOWS:
        chain = get_option_chain(
            symbol,
            option_type,
            target_dte,
            center_strike=center_strike,
            strike_window=strike_window,
        )
        selected_chain = chain
        sought_strike = _seek_target_delta_strike(chain, abs(float(target_delta)))
        if sought_strike is None:
            best_center = float(center_strike)
            break
        best_center = round(float(sought_strike) / 5.0) * 5.0
        if not _is_boundary_hit(chain, sought_strike):
            break

    sorted_chain = sorted(
        selected_chain,
        key=lambda row: float(row.get("strike") or 0),
    )
    if not sorted_chain:
        return {"rows": [], "scan_fallback": True}
    idx = min(
        range(len(sorted_chain)),
        key=lambda i: abs(float(sorted_chain[i].get("strike") or 0) - best_center),
        default=0,
    )
    lo = max(0, idx - _SCORE_WINDOW)
    hi = min(len(sorted_chain), idx + _SCORE_WINDOW + 1)
    candidate_chain = sorted_chain[lo:hi]

    rows = scan_strikes(
        candidate_chain,
        target_delta=target_delta,
        symbol=symbol,
    )
    gap = _recommended_delta_gap(rows, target_delta)
    if gap is not None:
        for row in rows:
            row.setdefault("delta_gap", round(_delta_gap(float(row.get("delta")), float(target_delta)), 3))
        if rows and rows[0].get("recommended"):
            rows[0]["interpolated_center"] = best_center
    return {
        "rows": rows,
        "scan_fallback": not bool(rows),
    }
