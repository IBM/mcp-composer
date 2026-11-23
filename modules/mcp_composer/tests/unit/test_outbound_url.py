"""Caller-supplied URLs must not reach loopback, metadata, or private networks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_composer.a2a_service import a2a_mcp
from mcp_composer.core.utils.outbound_url import (
    OUTBOUND_ALLOWLIST_ENV,
    assert_outbound_url_allowed,
)

BLOCKED_URLS = [
    "http://127.0.0.1:8080/internal-only/secret",
    "http://localhost/admin",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/",
    "http://192.168.1.10/",
    "http://172.16.0.1/",
    "http://0.0.0.0/",
]


@pytest.fixture(autouse=True)
def _empty_allowlist(monkeypatch):
    monkeypatch.delenv(OUTBOUND_ALLOWLIST_ENV, raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_refuses_non_public_destinations(url):
    with pytest.raises(ValueError, match="non-public address"):
        await assert_outbound_url_allowed(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://127.0.0.1/",
        "ftp://example.com/",
        "http:///nohost",
    ],
)
async def test_refuses_non_http_schemes_and_missing_host(url):
    with pytest.raises(ValueError):
        await assert_outbound_url_allowed(url)


@pytest.mark.asyncio
async def test_refuses_unresolvable_host():
    with pytest.raises(ValueError, match="could not be resolved"):
        await assert_outbound_url_allowed("http://does-not-exist.invalid/")


@pytest.mark.asyncio
async def test_allows_public_address():
    assert (
        await assert_outbound_url_allowed("https://8.8.8.8/agent")
        == "https://8.8.8.8/agent"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "allowlist,url",
    [
        ("localhost", "http://localhost:10000/"),
        ("127.0.0.0/8", "http://127.0.0.1:10000/"),
        ("10.0.0.5", "http://10.0.0.5/"),
    ],
)
async def test_operator_allowlist_permits_internal_hosts(monkeypatch, allowlist, url):
    monkeypatch.setenv(OUTBOUND_ALLOWLIST_ENV, allowlist)
    assert await assert_outbound_url_allowed(url) == url


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_register_agent_does_not_fetch_non_public_url(monkeypatch, url):
    monkeypatch.setattr(a2a_mcp, "registered_agents", {})
    monkeypatch.setattr(a2a_mcp, "save_to_json", MagicMock())
    ctx = MagicMock(info=AsyncMock())
    with patch.object(a2a_mcp.httpx, "AsyncClient") as client_cls:
        result = await a2a_mcp.register_agent(url, ctx)

    client_cls.assert_not_called()
    assert result["status"] == "error"
    assert a2a_mcp.registered_agents == {}


@pytest.mark.asyncio
async def test_fetch_agent_card_refuses_card_pointing_at_internal_url():
    card = MagicMock(url="http://169.254.169.254/")
    with patch.object(
        a2a_mcp, "_fetch_agent_card_unchecked", AsyncMock(return_value=card)
    ):
        with pytest.raises(ValueError, match="non-public address"):
            await a2a_mcp.fetch_agent_card("https://8.8.8.8/agent")


@pytest.mark.parametrize(
    "config",
    [
        {"id": "a", "type": "http", "endpoint": "http://169.254.169.254/"},
        {"id": "a", "type": "sse", "endpoint": "http://127.0.0.1:8080/sse"},
        {
            "id": "a",
            "type": "openapi",
            "open_api": {
                "endpoint": "http://10.0.0.5/",
                "spec_url": "https://example.com/s.json",
            },
        },
        {
            "id": "a",
            "type": "openapi",
            "open_api": {
                "endpoint": "https://example.com",
                "spec_url": "http://192.168.1.10/s.json",
            },
        },
        {
            "id": "a",
            "type": "http",
            "endpoint": "https://example.com",
            "auth": {"token_url": "http://169.254.169.254/token"},
        },
        {
            "id": "a",
            "type": "graphql",
            "graphql": {"endpoint": "http://localhost/graphql"},
        },
    ],
)
@pytest.mark.asyncio
async def test_member_config_refuses_non_public_destinations(config):
    from mcp_composer.core.utils.outbound_url import (
        assert_member_config_destinations_allowed,
    )

    with pytest.raises(ValueError, match="non-public|http or https"):
        await assert_member_config_destinations_allowed(config)


@pytest.mark.asyncio
async def test_member_config_skips_stdio_without_urls():
    from mcp_composer.core.utils.outbound_url import (
        assert_member_config_destinations_allowed,
    )

    await assert_member_config_destinations_allowed(
        {"id": "a", "type": "stdio", "command": "/bin/x", "args": ["1"]}
    )


@pytest.mark.asyncio
async def test_member_config_honours_allowlist(monkeypatch):
    from mcp_composer.core.utils.outbound_url import (
        assert_member_config_destinations_allowed,
    )

    monkeypatch.setenv(OUTBOUND_ALLOWLIST_ENV, "10.0.0.0/8")
    await assert_member_config_destinations_allowed(
        {"id": "a", "type": "http", "endpoint": "http://10.0.0.5/mcp"}
    )


@pytest.mark.asyncio
async def test_register_server_rejects_metadata_endpoint():
    from mcp_composer.core.member_servers.server_manager import ServerManager
    from mcp_composer.core.utils.exceptions import ServerConfigurationError

    manager = ServerManager.__new__(ServerManager)
    composer = MagicMock()
    with pytest.raises(ServerConfigurationError):
        await manager.register_server(
            {"id": "evil", "type": "http", "endpoint": "http://169.254.169.254/"},
            composer,
        )
