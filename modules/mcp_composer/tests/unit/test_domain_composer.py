"""Domain composer bind rules and the think-composer tool surface."""

from __future__ import annotations

from typing import Any

import pytest

from mcp_composer.core.domain_composer import (
    SEQUENTIAL_THINKING_TOOL,
    THINK_COMPOSER_NAME,
    configure_think_composer,
    resolve_listen,
    resolve_mode,
    serve_domain_composer,
)


def test_resolve_mode_defaults_to_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_MODE", raising=False)
    assert resolve_mode() == "http"
    assert resolve_mode("SSE") == "sse"


def test_resolve_mode_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported MCP_MODE"):
        resolve_mode("websocket")


def test_resolve_listen_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.delenv("MCP_PORT", raising=False)
    assert resolve_listen("http") == ("127.0.0.1", 9000)


def test_resolve_listen_refuses_public_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TYPE", "oauth")
    with pytest.raises(ValueError, match="without authentication"):
        resolve_listen("http", host="0.0.0.0", port=9000)


class _FakeComposer:
    def __init__(self) -> None:
        self.disabled = False
        self.tools: list[Any] = []
        self.members_loaded = False
        self.http: tuple[str, int] | None = None

    async def disable_composer_tool(self) -> str:
        self.disabled = True
        return "ok"

    def add_tool(self, tool: Any) -> None:
        self.tools.append(tool)

    async def setup_member_servers(self) -> None:
        self.members_loaded = True

    async def run_http_async(self, **kwargs: Any) -> None:
        self.http = (kwargs["host"], kwargs["port"])


@pytest.mark.asyncio
async def test_configure_think_composer_registers_sequential_thinking() -> None:
    composer = _FakeComposer()
    await configure_think_composer(composer)
    assert composer.disabled is True
    assert [tool.name for tool in composer.tools] == [SEQUENTIAL_THINKING_TOOL]
    assert THINK_COMPOSER_NAME == "think-composer"


@pytest.mark.asyncio
async def test_serve_loads_members_then_binds_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.delenv("MCP_PORT", raising=False)
    composer = _FakeComposer()
    await serve_domain_composer(composer, mode="http")
    assert composer.members_loaded is True
    assert composer.http == ("127.0.0.1", 9000)
