#!/usr/bin/env python3
"""
E-Trade headless re-authentication via Playwright.

Runs on oldair via launchd at 05:30 ET daily (before market open).
Requires ETRADE_USERNAME and ETRADE_PASSWORD in .env.

⚠  If your E-Trade account has MFA / Symantec VIP enabled, this script
   will not work — the MFA prompt cannot be automated. In that case you
   must use the web-based flow: open https://www.portimperialventures.com/etrade/auth

Usage (manual test):
    python3 scripts/etrade_reauth_headless.py [--visible]   # --visible shows browser window

How it works:
  1. Calls request_token() to get the E-Trade authorization URL (via pyetrade)
  2. Playwright navigates to the URL, fills in credentials, clicks Authorize
  3. E-Trade redirects to portimperialventures.com/etrade/auth?oauth_verifier=...
  4. Web server saves the token automatically (same route as the manual web flow)
  5. Script polls until the token on disk is valid
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etrade_headless")

WEB_SERVER = "https://www.portimperialventures.com"
POLL_INTERVAL = 3
POLL_TIMEOUT = 120


def _etrade_credentials() -> tuple[str, str]:
    username = os.getenv("ETRADE_USERNAME", "")
    password = os.getenv("ETRADE_PASSWORD", "")
    if not username or not password:
        log.error(
            "ETRADE_USERNAME / ETRADE_PASSWORD not set in .env — "
            "headless auth cannot proceed"
        )
        sys.exit(1)
    return username, password


def _get_etrade_auth_url() -> str:
    """Trigger request_token on the web server and return E-Trade's authorize URL."""
    import requests as _req
    try:
        resp = _req.get(
            f"{WEB_SERVER}/etrade/auth",
            allow_redirects=False,
            timeout=20,
        )
        location = resp.headers.get("Location", "")
        if "etrade.com" in location or "us.etrade.com" in location:
            return location
        log.warning("Unexpected redirect location from web server: %s", location)
    except Exception as e:
        log.warning("Could not reach web server: %s — falling back to direct request_token", e)

    # Fallback: call request_token() directly (saves request token locally)
    from etrade.auth import request_token
    payload = request_token()
    url = payload.get("authorize_url", "")
    if not url:
        log.error("request_token() returned no authorize_url")
        sys.exit(1)
    return str(url)


def _poll_token_valid(timeout: int = POLL_TIMEOUT) -> bool:
    """Poll until the E-Trade token on disk is valid or timeout."""
    from etrade.auth import token_status
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if token_status().get("authenticated"):
            return True
        time.sleep(POLL_INTERVAL)
    return False


def _run_playwright(auth_url: str, username: str, password: str, visible: bool) -> bool:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not visible)
        ctx = browser.new_context(
            # Pretend to be a real browser to avoid simple bot-detection
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        try:
            log.info("Navigating to E-Trade authorization URL...")
            page.goto(auth_url, timeout=30_000)

            # ── Login form ────────────────────────────────────────────────────
            # E-Trade login page selectors (may change; add fallbacks)
            log.info("Filling login credentials...")
            page.wait_for_selector("input#USER, input[name='USER'], input[name='username']", timeout=20_000)

            for sel in ("input#USER", "input[name='USER']", "input[name='username']"):
                if page.locator(sel).count() > 0:
                    page.fill(sel, username)
                    break

            for sel in ("input#PASSWORD", "input[name='PASSWORD']", "input[name='password']"):
                if page.locator(sel).count() > 0:
                    page.fill(sel, password)
                    break

            for sel in ("input#logon_button", "input[type='submit']", "button[type='submit']"):
                if page.locator(sel).count() > 0:
                    page.click(sel)
                    break

            # ── Wait for possible MFA / security question ─────────────────────
            # If MFA appears, we can't handle it — log and exit
            try:
                page.wait_for_url("**/etrade.com**", timeout=10_000)
            except PwTimeout:
                pass

            current = page.url
            if "challenge" in current or "verify" in current or "mfa" in current.lower():
                log.error(
                    "MFA / security challenge detected at %s. "
                    "Headless auth cannot proceed — "
                    "disable MFA or use manual web flow.",
                    current,
                )
                browser.close()
                return False

            # ── Authorization / Accept page ───────────────────────────────────
            log.info("Looking for authorization accept button...")
            try:
                # E-Trade shows "Accept and Continue" or "Authorize" button
                for sel in (
                    "input[value*='Accept']",
                    "input[value*='Accept and Continue']",
                    "button:has-text('Accept')",
                    "a:has-text('Accept')",
                ):
                    if page.locator(sel).count() > 0:
                        page.click(sel)
                        log.info("Clicked accept button")
                        break
            except PwTimeout:
                log.warning("Accept button not found — may have already authorized")

            # ── Wait for redirect back to our server ──────────────────────────
            log.info("Waiting for redirect to %s ...", WEB_SERVER)
            try:
                page.wait_for_url(f"{WEB_SERVER}/**", timeout=20_000)
                log.info("Redirect complete: %s", page.url)
            except PwTimeout:
                # Might have redirected to a different URL; check verifier in URL
                final = page.url
                log.info("Final URL: %s", final)
                parsed = urlparse(final)
                qs = parse_qs(parsed.query)
                verifier = (qs.get("oauth_verifier") or [""])[0]
                if verifier:
                    # Manually exchange if web server didn't handle it
                    log.info("Manually exchanging verifier...")
                    from etrade.auth import get_access_token
                    get_access_token(verifier)

            browser.close()
            return True

        except Exception as e:
            log.error("Playwright error: %s", e)
            try:
                browser.close()
            except Exception:
                pass
            return False


def main() -> None:
    visible = "--visible" in sys.argv

    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    from etrade.auth import is_configured, token_status

    if not is_configured():
        log.error("ETRADE_CONSUMER_KEY / ETRADE_CONSUMER_SECRET not set — skipping")
        sys.exit(0)

    if token_status().get("authenticated"):
        log.info("E-Trade token already valid — nothing to do")
        sys.exit(0)

    log.info("E-Trade token expired — starting headless re-auth...")

    username, password = _etrade_credentials()
    auth_url = _get_etrade_auth_url()
    log.info("Got E-Trade auth URL (length=%d)", len(auth_url))

    ok = _run_playwright(auth_url, username, password, visible=visible)
    if not ok:
        log.error("Playwright flow failed")
        sys.exit(1)

    log.info("Playwright done — polling for token validity...")
    if _poll_token_valid():
        log.info("E-Trade re-auth complete ✓")
    else:
        log.error(
            "Token still not valid after %ds — "
            "check logs or use manual web flow",
            POLL_TIMEOUT,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
