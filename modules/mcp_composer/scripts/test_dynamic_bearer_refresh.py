#!/usr/bin/env python3
"""
Test script for dynamic_bearer auth with OAuth refresh_token.

Runs a mock OAuth token server, then exercises DynamicTokenClient
with client_id/client_secret/refresh_token. Use this to verify the
refresh flow without a real IdP.

Run from repo root:
  cd modules/mcp_composer && uv run python scripts/test_dynamic_bearer_refresh.py

Or with uv from repo root:
  uv run --project modules/mcp_composer python modules/mcp_composer/scripts/test_dynamic_bearer_refresh.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure mcp_composer is importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp import web

from mcp_composer.core.auth_handler.dynamic_token_client import DynamicTokenClient
from mcp_composer.core.utils import ConfigKey

# Mock token server state
MOCK_ACCESS_TOKEN = "mock-access-token-12345"
MOCK_TOKEN_URL = "http://127.0.0.1:8765/oauth/token"


async def handle_token(request: web.Request) -> web.Response:
    """Fake OAuth token endpoint: accepts refresh_token grant, returns access_token."""
    if request.method != "POST":
        return web.json_response({"error": "method_not_allowed"}, status=405)
    try:
        body = await request.post()
    except Exception:
        return web.json_response({"error": "invalid_request"}, status=400)
    if body.get("grant_type") != "refresh_token":
        return web.json_response({"error": "unsupported_grant_type"}, status=400)
    if not body.get("refresh_token") or not body.get("client_id") or not body.get("client_secret"):
        return web.json_response({"error": "invalid_request"}, status=400)
    return web.json_response({
        "access_token": MOCK_ACCESS_TOKEN,
        "token_type": "Bearer",
        "expires_in": 3600,
    })


async def run_test() -> None:
    app = web.Application()
    app.router.add_post("/oauth/token", handle_token)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8765)
    await site.start()
    print("Mock token server listening on http://127.0.0.1:8765/oauth/token")

    try:
        auth_data = {
            ConfigKey.Token_URL: MOCK_TOKEN_URL,
            ConfigKey.CLIENT_ID: "test-client",
            ConfigKey.CLIENT_SECRET: "test-secret",
            ConfigKey.REFRESH_TOKEN: "test-refresh-token",
        }
        client = DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )
        await client._refresh_token()
        if client._access_token != MOCK_ACCESS_TOKEN:
            print("FAIL: expected access_token", MOCK_ACCESS_TOKEN, "got", client._access_token)
            sys.exit(1)
        print("OK: _refresh_token() set access_token:", client._access_token[:20] + "...")
        print("All checks passed. dynamic_bearer refresh_token flow works.")
    finally:
        await runner.cleanup()


def main() -> None:
    asyncio.run(run_test())


if __name__ == "__main__":
    main()
