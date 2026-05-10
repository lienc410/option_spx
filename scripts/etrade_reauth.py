#!/usr/bin/env python3
"""
E-Trade OAuth re-authentication.

Run on your LOCAL Mac (not oldair). Opens a browser for E-Trade login.
Your Cloudflare tunnel (portimperialventures.com → oldair:5050) handles
the verifier callback automatically via the web server's /etrade/auth route.
The script polls until auth succeeds.

Usage:
    python3 scripts/etrade_reauth.py

Requirements:
  - SSH alias "oldair" configured in ~/.ssh/config
  - .env with ETRADE_CONSUMER_KEY / ETRADE_CONSUMER_SECRET
  - pyetrade + requests_oauthlib installed in venv (already in repo deps)
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

# ── project root on PYTHONPATH ─────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

# Public URL of the web server (Cloudflare tunnel)
WEB_URL = "https://www.portimperialventures.com"
OLDAIR_HOST = "oldair"
OLDAIR_TOKEN_PATH = "~/.spxstrat/etrade_token.json"
LOCAL_TOKEN_DIR = Path.home() / ".spxstrat"

POLL_INTERVAL = 4   # seconds between status checks
POLL_TIMEOUT  = 300  # 5 min total


# ── Token status via SSH ───────────────────────────────────────────────────────

def _check_token_valid_on_oldair() -> bool:
    """SSH to oldair and check if E-Trade token is valid (authenticated=True)."""
    try:
        r = subprocess.run(
            [
                "ssh", OLDAIR_HOST,
                "cd ~/SPX_strat && "
                "venv/bin/python3 -c \""
                "from etrade.auth import token_status; "
                "s=token_status(); "
                "print('ok' if s.get('authenticated') else 'no')"
                "\"",
            ],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() == "ok"
    except Exception:
        return False


# ── Trigger request token via web server ─────────────────────────────────────

def _trigger_etrade_auth_via_web() -> str | None:
    """
    Calls the web server's /etrade/auth endpoint (no verifier) to get the
    E-Trade authorization URL. Returns the final E-Trade URL after redirect.
    """
    import urllib.request
    # We need requests so that redirects are followed but we stop at the
    # external E-Trade URL (not fetch it).
    try:
        import requests
        resp = requests.get(f"{WEB_URL}/etrade/auth", allow_redirects=False, timeout=15)
        # Expect a 302 to E-Trade's authorization URL
        location = resp.headers.get("Location", "")
        if "etrade.com" in location or "us.etrade.com" in location:
            return location
        # If it redirected to "/" it means auth was already valid or error
        if location.endswith("/"):
            return None
        return location or None
    except Exception as e:
        print(f"  Warning: could not reach {WEB_URL}: {e}")
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from etrade.auth import is_configured, token_status

    if not is_configured():
        print("ERROR: ETRADE_CONSUMER_KEY / ETRADE_CONSUMER_SECRET not found in .env")
        sys.exit(1)

    print("E-Trade re-authentication")
    print("=" * 40)

    # Step 1: Check if already valid on oldair
    print("Checking current token status on oldair...")
    if _check_token_valid_on_oldair():
        print("  ✓ E-Trade token is already valid on oldair. Nothing to do.")
        return

    print("  Token expired — starting re-auth flow.\n")

    # Step 2: Trigger /etrade/auth on web server to get the E-Trade authorize URL
    print(f"Requesting E-Trade authorization URL from {WEB_URL}...")
    etrade_url = _trigger_etrade_auth_via_web()

    if etrade_url:
        print(f"  ✓ Got E-Trade auth URL. Opening browser...\n")
        print("  Log in with your E-Trade credentials and click Authorize.")
        print("  After authorizing, the page will redirect automatically.")
        print("  You can close the browser tab once you see the portfolio homepage.\n")
        webbrowser.open(etrade_url)
    else:
        # Fallback: open the web server's auth route directly and let it redirect
        print(f"  Could not get redirect URL directly. Opening {WEB_URL}/etrade/auth...\n")
        print("  The page will redirect you to E-Trade login.")
        print("  After authorizing, it returns to the portfolio homepage automatically.\n")
        webbrowser.open(f"{WEB_URL}/etrade/auth")

    # Step 3: Poll until token is valid on oldair
    print(f"Polling oldair every {POLL_INTERVAL}s for up to {POLL_TIMEOUT // 60} minutes...")
    deadline = time.monotonic() + POLL_TIMEOUT
    dots = 0
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        dots += 1
        print(f"  {'.' * dots}", end="\r")
        if _check_token_valid_on_oldair():
            print(f"\n  ✓ E-Trade token is now valid on oldair.")
            break
    else:
        print(f"\n  Timed out after {POLL_TIMEOUT // 60} minutes.")
        print("  If you completed authorization, wait a moment and check the portfolio page.")
        print(f"  Or check token status: ssh {OLDAIR_HOST} \"cd ~/SPX_strat && venv/bin/python3 -c 'from etrade.auth import token_status; print(token_status())'\"")
        sys.exit(1)

    print("\nDone. E-Trade authentication complete.")


if __name__ == "__main__":
    main()
