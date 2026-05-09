from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


log = logging.getLogger(__name__)
load_dotenv()

_ET = ZoneInfo("America/New_York")
TOKEN_FILE = Path(os.getenv("ETRADE_TOKEN_FILE", str(Path.home() / ".spxstrat" / "etrade_token.json")))
ALERT_STATE_FILE = Path(
    os.getenv("ETRADE_ALERT_STATE_FILE", str(Path.home() / ".spxstrat" / "etrade_token_alert_state.json"))
)
_PUBLIC_AUTH_URL = os.getenv("ETRADE_AUTH_PUBLIC_URL", "https://www.portimperialventures.com/etrade/auth")


def consumer_key() -> str | None:
    return os.getenv("ETRADE_CONSUMER_KEY")


def consumer_secret() -> str | None:
    return os.getenv("ETRADE_CONSUMER_SECRET")


def redirect_uri() -> str:
    return os.getenv("ETRADE_REDIRECT_URI", _PUBLIC_AUTH_URL)


def account_id() -> str | None:
    value = os.getenv("ETRADE_ACCOUNT_ID")
    return str(value).strip() if value else None


def is_configured() -> bool:
    return bool(consumer_key() and consumer_secret())


def public_auth_url() -> str:
    return os.getenv("ETRADE_AUTH_PUBLIC_URL", _PUBLIC_AUTH_URL)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict | None:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.warning("etrade.auth: failed to load %s", path, exc_info=True)
    return None


def _save_json(path: Path, payload: dict) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def load_token() -> dict | None:
    return _load_json(TOKEN_FILE)


def save_token(payload: dict) -> None:
    _save_json(TOKEN_FILE, payload)


def load_alert_state() -> dict:
    return _load_json(ALERT_STATE_FILE) or {
        "invalid": False,
        "reason": None,
        "alert_sent": False,
        "updated_at": None,
    }


def save_alert_state(payload: dict) -> None:
    _save_json(ALERT_STATE_FILE, payload)


def record_token_issue(reason: str) -> None:
    state = load_alert_state()
    now = datetime.now(_ET).isoformat(timespec="seconds")
    payload = {
        **state,
        "invalid": True,
        "reason": reason,
        "updated_at": now,
    }
    if not state.get("invalid"):
        payload["alert_sent"] = False
    save_alert_state(payload)


def mark_token_alert_sent() -> None:
    state = load_alert_state()
    save_alert_state({
        **state,
        "invalid": True,
        "alert_sent": True,
        "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
    })


def clear_token_issue() -> None:
    if ALERT_STATE_FILE.exists():
        try:
            ALERT_STATE_FILE.unlink()
        except Exception:
            log.warning("etrade.auth: failed to clear %s", ALERT_STATE_FILE, exc_info=True)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _next_midnight_et(now: datetime | None = None) -> datetime:
    current = now or datetime.now(_ET)
    next_day = (current + timedelta(days=1)).date().isoformat()
    return datetime.fromisoformat(f"{next_day}T00:00:00").replace(tzinfo=_ET)


def token_status() -> dict:
    token = load_token()
    state = load_alert_state()
    if not is_configured():
        return {
            "configured": False,
            "authenticated": False,
            "token_expires_in": None,
            "stale": False,
            "alert_state": state,
        }
    if not token:
        return {
            "configured": True,
            "authenticated": False,
            "token_expires_in": None,
            "stale": False,
            "alert_state": state,
        }
    now = datetime.now(_ET)
    expires_at = _parse_dt(token.get("expires_at"))
    token_in = int((expires_at - now).total_seconds()) if expires_at else None
    return {
        "configured": True,
        "authenticated": bool(token_in and token_in > 0),
        "token_expires_in": token_in,
        "stale": False,
        "alert_state": state,
    }


def is_token_valid() -> bool:
    status = token_status()
    return bool(status.get("configured") and status.get("authenticated"))


def _load_pyetrade():
    try:
        import pyetrade  # type: ignore

        return pyetrade
    except Exception as exc:  # pragma: no cover - exercised via fail-soft tests
        raise RuntimeError("pyetrade_missing") from exc


def _build_oauth():
    pyetrade = _load_pyetrade()
    return pyetrade.ETradeOAuth(consumer_key(), consumer_secret())


def _extract_saved_request_parts(oauth: Any, request_url: str) -> dict:
    parsed = urlparse(str(request_url))
    query = parse_qs(parsed.query)
    token = None
    secret = None
    for attr in ("oauth_token", "request_token", "token", "_oauth_token"):
        token = token or getattr(oauth, attr, None)
    for attr in ("oauth_token_secret", "request_token_secret", "token_secret", "_oauth_token_secret"):
        secret = secret or getattr(oauth, attr, None)
    return {
        "request_oauth_token": token or query.get("key", [None])[0] or query.get("oauth_token", [None])[0],
        "request_oauth_token_secret": secret,
        "authorize_url": str(request_url),
    }


def _prime_request_token(oauth: Any, token: dict) -> None:
    token_value = token.get("request_oauth_token")
    secret_value = token.get("request_oauth_token_secret")
    for attr in ("oauth_token", "request_token", "token", "_oauth_token"):
        try:
            setattr(oauth, attr, token_value)
        except Exception:
            pass
    for attr in ("oauth_token_secret", "request_token_secret", "token_secret", "_oauth_token_secret"):
        try:
            setattr(oauth, attr, secret_value)
        except Exception:
            pass


def request_token() -> dict:
    if not is_configured():
        raise RuntimeError("not_configured")
    oauth = _build_oauth()
    request_url = oauth.get_request_token()
    request_parts = _extract_saved_request_parts(oauth, request_url)
    payload = {
        **(load_token() or {}),
        **request_parts,
        "redirect_uri": redirect_uri(),
        "updated_at": datetime.now(_ET).isoformat(timespec="seconds"),
    }
    save_token(payload)
    return payload


def get_access_token(verifier: str) -> dict:
    if not is_configured():
        raise RuntimeError("not_configured")
    token = load_token() or {}
    oauth = _build_oauth()
    _prime_request_token(oauth, token)
    tokens = oauth.get_access_token(verifier)
    now = datetime.now(_ET)
    payload = {
        **token,
        **(tokens or {}),
        "expires_at": _next_midnight_et(now).isoformat(),
        "updated_at": now.isoformat(timespec="seconds"),
    }
    save_token(payload)
    clear_token_issue()
    return payload


def renew_access_token() -> dict:
    if not is_configured():
        return {"ok": False, "reason": "not_configured"}
    token = load_token() or {}
    if not token.get("oauth_token") or not token.get("oauth_token_secret"):
        record_token_issue("auth_required")
        return {"ok": False, "reason": "auth_required"}
    try:
        oauth = _build_oauth()
        for attr in ("oauth_token", "access_token", "token", "_oauth_token"):
            try:
                setattr(oauth, attr, token.get("oauth_token"))
            except Exception:
                pass
        for attr in ("oauth_token_secret", "access_token_secret", "token_secret", "_oauth_token_secret"):
            try:
                setattr(oauth, attr, token.get("oauth_token_secret"))
            except Exception:
                pass
        renewed = oauth.renew_access_token()
        now = datetime.now(_ET)
        payload = {
            **token,
            **(renewed or {}),
            "expires_at": _next_midnight_et(now).isoformat(),
            "updated_at": now.isoformat(timespec="seconds"),
        }
        save_token(payload)
        clear_token_issue()
        return {"ok": True, "token": payload}
    except Exception as exc:
        log.warning("etrade.auth: renew_access_token failed", exc_info=True)
        record_token_issue("renew_failed")
        return {"ok": False, "reason": str(exc)}

