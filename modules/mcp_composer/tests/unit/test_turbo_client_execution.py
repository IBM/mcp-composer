"""Tests for TurboJWTClient auth flow and integration."""

import time
from unittest.mock import AsyncMock

import httpx
import pytest


class TestTurboJWTClientAuthFlow:
    """Ensure the auth handler injects and refreshes bearer tokens."""

    @pytest.mark.asyncio
    async def test_auth_flow_injects_authorization_header(self):
        from mcp_composer.core.auth_handler.turbo_auth_handler import TurboJWTClient

        auth_data = {
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "test_scope",
        }

        client = TurboJWTClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
            headers={"X-Test": "1"},
        )

        client._access_token = "test_token"
        client._expires_at = time.time() + 60

        request = httpx.Request("GET", "https://api.example.com/resource")
        async for prepared in client.async_auth_flow(request):
            assert prepared.headers["Authorization"] == "Bearer test_token"
            assert prepared.headers["X-Test"] == "1"
            assert prepared.headers["Accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_token_refresh_runs_when_expired(self):
        from mcp_composer.core.auth_handler.turbo_auth_handler import TurboJWTClient

        auth_data = {
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "test_scope",
        }

        client = TurboJWTClient(base_url="https://api.example.com", auth_data=auth_data)

        async def set_new_token():
            client._access_token = "new_token"
            client._expires_at = time.time() + 60

        client._refresh_token = AsyncMock(side_effect=set_new_token)
        client._access_token = None
        client._expires_at = 0

        request = httpx.Request("GET", "https://api.example.com/resource")
        async for prepared in client.async_auth_flow(request):
            assert prepared.headers["Authorization"] == "Bearer new_token"

        client._refresh_token.assert_awaited()

    @pytest.mark.asyncio
    async def test_httpx_client_uses_auth_handler(self):
        from mcp_composer.core.auth_handler.turbo_auth_handler import TurboJWTClient

        auth_data = {
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "test_scope",
        }

        captured = {}

        async def handler(request: httpx.Request) -> httpx.Response:  # type: ignore[override]
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)

        client = TurboJWTClient(base_url="https://api.example.com", auth_data=auth_data)

        async def set_new_token():
            client._access_token = "live_token"
            client._expires_at = time.time() + 60

        client._refresh_token = AsyncMock(side_effect=set_new_token)

        async with httpx.AsyncClient(
            base_url="https://api.example.com",
            auth=client,
            transport=transport,
        ) as http_client:
            response = await http_client.get("/ping")

        assert response.status_code == 200
        assert captured["auth"] == "Bearer live_token"

    def test_turbo_client_initial_state(self):
        from mcp_composer.core.auth_handler.turbo_auth_handler import TurboJWTClient

        auth_data = {
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "test_scope",
        }

        client = TurboJWTClient(base_url="https://api.example.com", auth_data=auth_data)

        assert client._access_token is None
        assert client._expires_at == 0.0
