#!/usr/bin/env python3
"""LinkedIn OAuth — exchanges an auth code for tokens and stores them in Orcheo vault.

Tokens are written directly to the vault via `orcheo credential create`; they are
never printed to stdout so the calling agent never sees them.

Required env vars:
  LINKEDIN_CLIENT_ID      LinkedIn app client id
  LINKEDIN_CLIENT_SECRET  LinkedIn app client secret

Optional env vars:
  LINKEDIN_REDIRECT_URI   Callback URL (default: http://127.0.0.1:8765/callback)
  LINKEDIN_SCOPES         Space or comma-separated scope override

CLI args:
  --profile NAME  Orcheo profile to use when creating credentials (optional)
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import requests


CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get(
    "LINKEDIN_REDIRECT_URI",
    "http://127.0.0.1:8765/callback",
).strip()
SCOPES_OVERRIDE = os.environ.get("LINKEDIN_SCOPES", "").strip()

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
DEFAULT_SCOPES = ["openid", "profile", "w_member_social", "w_organization_social"]


@dataclass
class OAuthCallbackResult:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


class _CallbackState:
    def __init__(self) -> None:
        self.result = OAuthCallbackResult()
        self.event = threading.Event()


_CALLBACK = _CallbackState()


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        _CALLBACK.result = OAuthCallbackResult(
            code=(query.get("code") or [None])[0],
            state=(query.get("state") or [None])[0],
            error=(query.get("error") or [None])[0],
            error_description=(query.get("error_description") or [None])[0],
        )
        _CALLBACK.event.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if _CALLBACK.result.code:
            html = "<html><body><h2>Authorization received. You can return to the terminal.</h2></body></html>"
        else:
            html = (
                f"<html><body><h2>Authorization failed.</h2>"
                f"<p>{_CALLBACK.result.error or 'unknown_error'}</p></body></html>"
            )
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def _start_local_server() -> HTTPServer:
    parsed = urllib.parse.urlparse(REDIRECT_URI)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    server = HTTPServer((host, port), _OAuthCallbackHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _resolve_scopes() -> list[str]:
    if SCOPES_OVERRIDE:
        normalized = SCOPES_OVERRIDE.replace(",", " ").split()
        seen: set[str] = set()
        unique: list[str] = []
        for s in normalized:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique
    return list(DEFAULT_SCOPES)


def _build_auth_url(state: str, scopes: list[str]) -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": " ".join(scopes),
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Token exchange failed ({response.status_code}): {response.text}"
        )
    return response.json()


def _store_credential(name: str, value: str, profile: str | None) -> None:
    """Store a single token in Orcheo vault. The secret value is passed as a
    CLI argument directly to the subprocess; it is never written to stdout."""
    cmd = ["orcheo"]
    if profile:
        cmd += ["--profile", profile]
    cmd += [
        "credential", "create", name,
        "--provider", "LinkedIn",
        "--secret", value,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to store credential '{name}': {result.stderr.strip() or result.stdout.strip()}"
        )
    print(f"  Stored: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn OAuth → Orcheo vault")
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help="Orcheo profile to use when creating credentials",
    )
    args = parser.parse_args()

    if not CLIENT_ID:
        print("ERROR: Missing required env var: LINKEDIN_CLIENT_ID", file=sys.stderr)
        sys.exit(1)
    if not CLIENT_SECRET:
        print("ERROR: Missing required env var: LINKEDIN_CLIENT_SECRET", file=sys.stderr)
        sys.exit(1)

    state = secrets.token_urlsafe(24)
    scopes = _resolve_scopes()

    print("Starting local callback server...")
    server = _start_local_server()

    try:
        auth_url = _build_auth_url(state, scopes)
        print(f"Requesting LinkedIn scopes: {' '.join(scopes)}")
        print("\nOpen this URL if your browser does not launch:\n")
        print(auth_url)
        print("\nWaiting for LinkedIn authorization callback...")
        webbrowser.open(auth_url, new=1, autoraise=True)

        if not _CALLBACK.event.wait(timeout=300):
            raise RuntimeError("Timed out waiting for OAuth callback (5 min)")

        result = _CALLBACK.result
        if result.error:
            raise RuntimeError(
                f"OAuth authorization failed: {result.error} "
                f"{result.error_description or ''}".strip()
            )
        if result.state != state:
            raise RuntimeError("State mismatch; possible CSRF or stale callback")
        if not result.code:
            raise RuntimeError("No authorization code received")

        print("\nExchanging authorization code for tokens...")
        token = _exchange_code(result.code)

        access_token = str(token.get("access_token") or "").strip()
        refresh_token = str(token.get("refresh_token") or "").strip()
        id_token = str(token.get("id_token") or "").strip()

        print("\nStoring credentials in Orcheo vault...")
        stored = 0
        if access_token:
            _store_credential("linkedin_access_token", access_token, args.profile)
            stored += 1
        if refresh_token:
            _store_credential("linkedin_refresh_token", refresh_token, args.profile)
            stored += 1
        if id_token:
            _store_credential("linkedin_id_token", id_token, args.profile)
            stored += 1
        else:
            print(
                "\nNote: no id_token returned. Add 'openid profile' scopes or enable "
                "'Sign in with LinkedIn using OpenID Connect' on your LinkedIn app "
                "to avoid the userinfo API call on each post."
            )

        print(f"\nDone. {stored} credential(s) stored successfully.")
        if args.profile:
            print(f"Profile: {args.profile}")

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
