"""Shared startup for domain-specific composer processes.

A domain composer is a process with one job: thinking, catalog, or another
fixed tool surface. It can still mount member servers. HTTP and SSE stay on
the loopback address. A public bind belongs on the CLI, which attaches
authentication before it listens.
"""

from __future__ import annotations

import os
from typing import Any

from mcp_composer.core.tools.sequential_thinking_tool import SequentialThinkingTool
from mcp_composer.core.utils.stdio_allowlist import assert_network_bind_allowed

THINK_COMPOSER_NAME = "think-composer"
SEQUENTIAL_THINKING_TOOL = "sequential_thinking"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
SUPPORTED_MODES = frozenset({"http", "sse", "stdio"})


def resolve_mode(mode: str | None = None) -> str:
    """Return a supported transport, defaulting to HTTP."""
    selected = (
        (mode if mode is not None else os.getenv("MCP_MODE", "http")).strip().lower()
    )
    if selected not in SUPPORTED_MODES:
        raise ValueError(
            f"Unsupported MCP_MODE: {selected}. Use 'http', 'sse', or 'stdio'"
        )
    return selected


def resolve_listen(
    mode: str,
    host: str | None = None,
    port: int | None = None,
) -> tuple[str, int]:
    """Return the loopback bind for HTTP or SSE.

    ``MCP_HOST`` may select another loopback name. Any other address is refused
    here, even if an auth environment variable is set, because this process
    does not install an authenticator.
    """
    if host is None:
        selected_host = os.getenv("MCP_HOST", DEFAULT_HOST)
    else:
        selected_host = host
    if port is None:
        selected_port = int(os.getenv("MCP_PORT", str(DEFAULT_PORT)))
    else:
        selected_port = port
    assert_network_bind_allowed(mode, selected_host, None)
    return selected_host, selected_port


def thinking_tools() -> list[SequentialThinkingTool]:
    """Tools that define the think-composer surface."""
    return [SequentialThinkingTool({"name": SEQUENTIAL_THINKING_TOOL})]


async def configure_think_composer(composer: Any) -> None:
    """Hide generic management tools and register the thinking surface."""
    await composer.disable_composer_tool()
    for tool in thinking_tools():
        composer.add_tool(tool)


async def serve_domain_composer(
    composer: Any,
    *,
    mode: str | None = None,
    host: str | None = None,
    port: int | None = None,
    log_level: str = "info",
) -> None:
    """Load members, then serve the composer on the selected transport."""
    selected = resolve_mode(mode)
    await composer.setup_member_servers()
    if selected == "stdio":
        await composer.run_stdio_async()
        return
    listen_host, listen_port = resolve_listen(selected, host, port)
    if selected == "http":
        await composer.run_http_async(
            host=listen_host,
            port=listen_port,
            log_level=log_level,
            path="/mcp",
        )
        return
    await composer.run_async(
        transport="sse",
        host=listen_host,
        port=listen_port,
        log_level=log_level,
    )
