"""Member routes under multi-server HTTP routing must enforce the composer's auth."""

import pytest
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from starlette.testclient import TestClient

from mcp_composer.core.composer import MCPComposer

ISSUER = "https://issuer.test"
AUDIENCE = "composer"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _member() -> FastMCP:
    member = FastMCP("member")

    @member.tool
    def read_vault() -> str:
        return "SECRET"

    return member


def _routed_composer(monkeypatch, auth=None) -> MCPComposer:
    monkeypatch.setenv("ENABLE_MULTI_SERVER_HTTP_ROUTING", "true")
    composer = MCPComposer("composer", auth=auth)
    composer._http_mounted_servers["member"] = _member()
    return composer


@pytest.fixture
def key_pair() -> RSAKeyPair:
    return RSAKeyPair.generate()


@pytest.fixture
def verifier(key_pair: RSAKeyPair) -> JWTVerifier:
    return JWTVerifier(public_key=key_pair.public_key, issuer=ISSUER, audience=AUDIENCE)


@pytest.mark.parametrize("path", ["/mcp", "/member/mcp"])
def test_routes_reject_unauthenticated_requests(monkeypatch, verifier, path):
    app = _routed_composer(monkeypatch, auth=verifier).get_multi_server_http_app()

    with TestClient(app) as client:
        response = client.post(path, json=INITIALIZE, headers=MCP_HEADERS)

    assert response.status_code == 401


def test_member_route_accepts_composer_token(monkeypatch, verifier, key_pair):
    app = _routed_composer(monkeypatch, auth=verifier).get_multi_server_http_app()
    token = key_pair.create_token(issuer=ISSUER, audience=AUDIENCE)

    with TestClient(app) as client:
        response = client.post(
            "/member/mcp",
            json=INITIALIZE,
            headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("host", [None, "0.0.0.0", "10.0.0.5"])
async def test_routed_server_without_auth_refuses_non_loopback_bind(monkeypatch, host):
    composer = _routed_composer(monkeypatch)

    with pytest.raises(ValueError, match="Refusing to bind"):
        await composer.run_http_async(show_banner=False, host=host)
