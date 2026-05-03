"""Q041 covered-call / cash-secured-put forward-collection whitelist.

Approved by PM 2026-05-03 (Gate 0 → forward-collection start).
10 large-cap names with deep option liquidity.

SPX/QQQ/ES added 2026-05-03 to accumulate main-strategy real chain data.
Symbol conventions:
  - "SPX"  → schwab.client._marketdata_symbol converts to "$SPX"
  - "BRK/B"→ mid-slash; parquet filename stored as "BRK_B.parquet"

Note on /ES (E-mini futures options):
  Schwab /marketdata/v1/chains returns 400 for futures symbols (/ES encodes
  to %2FES and is rejected). ES futures option chains require a separate
  endpoint not in the Schwab Developer API v1 public spec. Removed 2026-05-03.
"""

WHITELIST: tuple[str, ...] = (
    # Q041 large-cap CC/CSP candidates
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOGL",
    "META",
    "NVDA",
    "BRK/B",
    "WMT",
    "COST",
    "JPM",
    # Main-strategy chain accumulation
    "SPX",
    "QQQ",
)
