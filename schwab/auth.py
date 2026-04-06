from __future__ import annotations

import base64
import json
import os
import secrets
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests


_ET = ZoneInfo("America/New_York")
TOKEN_FILE = Path.home() / ".spxstrat" / "schwab_token.json"
AUTHORIZE_URL = os.getenv("SCHWAB_AUTHORIZE_URL", "https://api.schwabapi.com/v1/oauth/authorize")
TOKEN_URL = os.getenv("SCHWAB_TOKEN_URL", "https://api.schwabapi.com/v1/oauth/token")


def client_id() -> str | None:
    return os.getenv("SCHWAB_CLIENT_ID")


def client_secret() -> str | None:
    return os.getenv("SCHWAB_CLIENT_SECRET")


def redirect_uri() -> str:
    return os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8182/callback")


def is_configured() -> bool:
    return bool(client_id() and client_secret())


def load_token() -> dict | None:
    try:
        if TOKEN_FILE.exists():
            return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None
    return None


def save_token(payload: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(payload, indent=2))


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def token_status() -> dict:
    token = load_token()
    if not is_configured():
        return {
            "configured": False,
            "authenticated": False,
            "token_expires_in": None,
            "refresh_expires_in": None,
            "stale": False,
        }
    if not token:
        return {
            "configured": True,
            "authenticated": False,
            "token_expires_in": None,
            "refresh_expires_in": None,
            "stale": False,
        }
    now = datetime.now(_ET)
    expires_at = _parse_dt(token.get("expires_at"))
    refresh_expires_at = _parse_dt(token.get("refresh_expires_at"))
    token_in = int((expires_at - now).total_seconds()) if expires_at else None
    refresh_in = int((refresh_expires_at - now).total_seconds()) if refresh_expires_at else None
    return {
        "configured": True,
        "authenticated": bool(token_in and token_in > 0),
        "token_expires_in": token_in,
        "refresh_expires_in": refresh_in,
        "stale": False,
    }


def _basic_auth_header() -> dict[str, str]:
    raw = f"{client_id()}:{client_secret()}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def _token_request(data: dict) -> dict:
    res = requests.post(
        TOKEN_URL,
        headers={
            **_basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data,
        timeout=20,
    )
    res.raise_for_status()
    return res.json()


def refresh_access_token(token: dict | None = None) -> dict:
    token = token or load_token()
    if not token or not token.get("refresh_token"):
        raise RuntimeError("auth_required")
    now = datetime.now(_ET)
    data = _token_request({
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "redirect_uri": redirect_uri(),
    })
    merged = {
        **token,
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", token["refresh_token"]),
        "expires_at": (now + timedelta(seconds=int(data.get("expires_in", 1800)))).isoformat(),
        "refresh_expires_at": token.get("refresh_expires_at") or (now + timedelta(days=7)).isoformat(),
    }
    save_token(merged)
    return merged


def ensure_access_token() -> str:
    if not is_configured():
        raise RuntimeError("not_configured")
    token = load_token()
    if not token:
        raise RuntimeError("auth_required")
    now = datetime.now(_ET)
    expires_at = _parse_dt(token.get("expires_at"))
    if expires_at and expires_at - now > timedelta(minutes=5):
        return token["access_token"]
    refreshed = refresh_access_token(token)
    return refreshed["access_token"]


def build_authorize_url(state: str | None = None) -> tuple[str, str]:
    real_state = state or secrets.token_urlsafe(16)
    params = urlencode({
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "readonly",
        "state": real_state,
    })
    return f"{AUTHORIZE_URL}?{params}", real_state


def exchange_code_for_token(code: str) -> dict:
    now = datetime.now(_ET)
    data = _token_request({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
    })
    payload = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": (now + timedelta(seconds=int(data.get("expires_in", 1800)))).isoformat(),
        "refresh_expires_at": (now + timedelta(days=7)).isoformat(),
        "account_number": data.get("account_number"),
    }
    save_token(payload)
    return payload


def extract_code_from_redirect(redirect_url: str) -> str:
    parsed = urlparse(redirect_url)
    query = parse_qs(parsed.query)
    if "code" not in query:
        raise RuntimeError("No authorization code found in redirect URL")
    return query["code"][0]


def interactive_setup() -> None:
    if not is_configured():
        raise RuntimeError("Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET before setup")
    url, _state = build_authorize_url()
    print("Open this URL in your browser and authorize Schwab access:\n")
    print(url)
    print("\nA browser window will also open automatically.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    redirect = input("\nPaste the full redirect URL here: ").strip()
    payload = exchange_code_for_token(extract_code_from_redirect(redirect))
    print(f"Saved token to {TOKEN_FILE}")
    if payload.get("account_number"):
        print(f"Account: {payload['account_number']}")
