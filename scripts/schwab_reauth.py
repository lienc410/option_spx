#!/usr/bin/env python3
"""
Schwab OAuth re-authentication.

Run on your LOCAL Mac (not oldair). Opens a browser for Schwab login,
captures the OAuth callback automatically, then syncs the token to oldair.

Usage:
    python3 scripts/schwab_reauth.py              # reauth + auto-sync to oldair
    python3 scripts/schwab_reauth.py --no-sync    # reauth only (keep token local)

Requirements:
  - openssl available in PATH (pre-installed on macOS)
  - SSH alias "oldair" configured in ~/.ssh/config
  - .env in repo root with SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET
"""

from __future__ import annotations

import os
import ssl
import sys
import subprocess
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── project root on PYTHONPATH ─────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

from schwab.auth import (
    TOKEN_FILE,
    build_authorize_url,
    exchange_code_for_token,
    is_configured,
    redirect_uri,
)

OLDAIR_HOST = "oldair"
OLDAIR_TOKEN_PATH = "~/.spxstrat/schwab_token.json"


# ── Self-signed TLS cert ───────────────────────────────────────────────────────

def _gen_self_signed_cert() -> tuple[str, str] | tuple[None, None]:
    """Generate a one-day self-signed cert for 127.0.0.1 via openssl."""
    cert = tempfile.mktemp(suffix=".pem")
    key = tempfile.mktemp(suffix=".key")
    try:
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", key, "-out", cert,
                "-days", "1", "-nodes",
                "-subj", "/CN=127.0.0.1",
            ],
            capture_output=True,
            check=True,
        )
        return cert, key
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None


# ── Callback HTTP handler ──────────────────────────────────────────────────────

class _CallbackHandler(BaseHTTPRequestHandler):
    captured_code: list[str] = []

    def do_GET(self) -> None:
        if self.path.startswith("/favicon"):
            self.send_response(204)
            self.end_headers()
            return
        params = parse_qs(urlparse(self.path).query)
        code = (params.get("code") or [""])[0]
        if code:
            self.__class__.captured_code.append(code)
            body = b"<h2 style='font-family:sans-serif'>Authorization successful. You may close this tab.</h2>"
        else:
            body = b"<h2 style='font-family:sans-serif'>No code found in callback.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # suppress request logs
        pass


# ── Callback server ────────────────────────────────────────────────────────────

def _start_server(port: int, use_https: bool, cert: str | None, key: str | None) -> HTTPServer:
    _CallbackHandler.captured_code = []
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    if use_https and cert and key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    return server


def _serve_until_code(server: HTTPServer, timeout: int = 180) -> str | None:
    """Block until a code is captured or timeout (seconds). Returns code or None."""
    deadline = time.monotonic() + timeout
    while not _CallbackHandler.captured_code:
        server.timeout = max(0.5, deadline - time.monotonic())
        server.handle_request()
        if time.monotonic() >= deadline:
            break
    return _CallbackHandler.captured_code[0] if _CallbackHandler.captured_code else None


# ── Token sync to oldair ───────────────────────────────────────────────────────

def _sync_to_oldair() -> bool:
    print(f"\nSyncing token to {OLDAIR_HOST}...")
    try:
        subprocess.run(
            ["ssh", OLDAIR_HOST, "mkdir -p ~/.spxstrat"],
            check=True, capture_output=True,
        )
        r = subprocess.run(
            ["scp", str(TOKEN_FILE), f"{OLDAIR_HOST}:{OLDAIR_TOKEN_PATH}"],
            capture_output=True,
        )
        if r.returncode == 0:
            print(f"  ✓ Token synced to {OLDAIR_HOST}:{OLDAIR_TOKEN_PATH}")
            return True
        print(f"  scp failed: {r.stderr.decode().strip()}")
    except Exception as e:
        print(f"  Sync error: {e}")
    print(f"\n  Manual fallback:")
    print(f"    scp {TOKEN_FILE} {OLDAIR_HOST}:{OLDAIR_TOKEN_PATH}")
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    no_sync = "--no-sync" in sys.argv

    # Load .env so SCHWAB_* vars are available
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    if not is_configured():
        print("ERROR: SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET not found in .env")
        sys.exit(1)

    redir = redirect_uri()
    parsed = urlparse(redir)
    use_https = parsed.scheme == "https"
    port = parsed.port or (443 if use_https else 80)

    cert_path = key_path = None
    if use_https:
        print("Generating temporary self-signed cert for HTTPS callback server...")
        cert_path, key_path = _gen_self_signed_cert()
        if not cert_path:
            print("ERROR: openssl not found. Cannot create self-signed cert.")
            print("       Falling back to manual mode.\n")
            from schwab.auth import interactive_setup
            interactive_setup()
            return
        print("  ✓ Cert generated (in-memory, deleted after auth)\n")

    print(f"Starting callback server on port {port} ({'HTTPS' if use_https else 'HTTP'})...")
    server = _start_server(port, use_https, cert_path, key_path)

    auth_url, _ = build_authorize_url()
    print("Opening Schwab authorization in your browser...\n")
    if use_https:
        print("  ⚠  Your browser will warn about an untrusted certificate.")
        print("     This is expected (self-signed, valid for this session only).")
        print("     Chrome: type 'thisisunsafe' on the warning page.")
        print("     Safari: Show Details → Visit This Website.")
        print("     Firefox: Advanced → Accept the Risk.\n")

    webbrowser.open(auth_url)
    print("Waiting for Schwab authorization (3-minute timeout)...")

    code = _serve_until_code(server, timeout=180)
    server.server_close()

    # Clean up temp cert files
    for f in (cert_path, key_path):
        if f:
            try:
                Path(f).unlink(missing_ok=True)
            except Exception:
                pass

    if not code:
        print("\nERROR: No authorization code received within 3 minutes.")
        print("       Try again, or run the manual flow: python3 schwab/setup.py")
        sys.exit(1)

    print("Exchanging authorization code for access token...")
    payload = exchange_code_for_token(code)
    print(f"  ✓ Token saved to {TOKEN_FILE}")
    if payload.get("account_number"):
        acct = payload["account_number"]
        print(f"  ✓ Account: ...{acct[-4:]}")

    if not no_sync:
        _sync_to_oldair()

    print("\nDone. Schwab authentication complete.")


if __name__ == "__main__":
    main()
