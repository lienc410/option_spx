# SPEC-089 Handoff

Status: IMPLEMENTED

Scope delivered:
- `etrade/auth.py`
  - OAuth 1.0a request/access/renew flow
  - persisted token file
  - persisted token-alert state for cross-process dedupe
- `etrade/client.py`
  - read-only balances + positions wrapper
  - normalized fail-soft payloads
- `web/server.py`
  - `GET /api/etrade/balances`
  - `GET /api/etrade/positions`
  - `GET /etrade/auth`
- `notify/telegram_bot.py`
  - 23:00 ET renewal job
  - token-expiry Telegram alert, once per invalid period
- `web/portfolio_surface.py`
  - combined Schwab + E-Trade maintenance summary support
- `web/templates/portfolio_home.html`
  - E-Trade PM read-only panel
  - combined BP breakdown display
- `pyproject.toml`
  - `pyetrade` dependency declaration
- `tests/test_spec_089.py`
  - AC-focused coverage

Notes:
- `pyetrade` is lazy-loaded so local/unit tests do not require the library at import time.
- Alert dedupe is persisted in `ETRADE_ALERT_STATE_FILE` so web and bot can coordinate across separate processes.
- E-Trade panel is intentionally read-only and does not alter existing `/api/recommendation` or SPX live write paths.
- Combined PM display uses account-level maintenance only; no per-position PM attribution is attempted.

Validation:
- `arch -arm64 venv/bin/python -m py_compile etrade/auth.py etrade/client.py web/server.py web/portfolio_surface.py notify/telegram_bot.py tests/test_spec_089.py`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_089 -v`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_085 tests.test_telegram_bot -v`
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_089 tests.test_spec_085 tests.test_telegram_bot tests.test_state_and_api -v`

Follow-up risks / deployment notes:
- First live `/etrade/auth` flow still depends on valid `ETRADE_CONSUMER_KEY`, `ETRADE_CONSUMER_SECRET`, `ETRADE_REDIRECT_URI`, and reachable public callback URL.
- `ETRADE_ACCOUNT_ID` is optional; if omitted the client attempts `list_accounts()` and uses the first returned account key.
- If old Air does not yet have `pyetrade` installed, deployment must include dependency sync before web/bot restart.
