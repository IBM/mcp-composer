"""
Utility helpers for rendering the MCP Composer startup banner.
"""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

TransportLiteral = Literal["stdio", "http", "sse", "streamable-http"]

# Simple ASCII block for MCP Composer branding (kept ASCII-only for portability)
BANNER_ASCII = """ \x1b[38;2;0;180;255m
┏┳┓┏━╸┏━┓   ┏━╸┏━┓┏┳┓┏━┓┏━┓┏━┓┏━╸┏━┓
┃┃┃┃  ┣━┛   ┃  ┃ ┃┃┃┃┣━┛┃ ┃┗━┓┣╸ ┣┳┛
╹ ╹┗━╸╹     ┗━╸┗━┛╹ ╹╹  ┗━┛┗━┛┗━╸╹┗╸
\x1b[0m""".strip()

_DOCS_ENV = "https://ibm.github.io/mcp-composer/"
_HOST_ENV = "MCP_COMPOSER_HOSTING_URL"
_VERSION_ENV = "0.0.0.0"


def _resolve_version() -> str:
    try:
        return version("mcp_composer")
    except PackageNotFoundError:
        return os.getenv(_VERSION_ENV, "0.0.0-dev")


def _resolve_value(value: str | None, env_key: str, placeholder: str) -> str:
    return value or os.getenv(env_key) or placeholder


def print_mcp_composer_banner(
    *,
    server_name: str,
    transport: TransportLiteral,
    host: str | None = None,
    port: int | None = None,
    path: str | None = None,
    docs_label: str = "Docs",
    docs_value: str | None = None,
    hosting_label: str = "PyPI",
    hosting_value: str | None = None,
) -> None:
    """Render a Rich panel that mirrors the FastMCP banner with MCP branding."""

    docs_display = _resolve_value(docs_value, _DOCS_ENV, "https://ibm.github.io/mcp-composer/")
    hosting_display = _resolve_value(
        hosting_value, _HOST_ENV, "https://pypi.org/project/mcp-composer/"
    )

    transport_display = {
        "stdio": "STDIO",
        "http": "HTTP",
        "sse": "SSE",
        "streamable-http": "Streamable HTTP",
    }[transport]

    logo_text = Text.from_ansi(BANNER_ASCII, no_wrap=True, style="bold cyan")
    title_text = Text(f"MCP Composer {_resolve_version()}", style="bold white on blue")

    info_table = Table.grid(padding=(0, 1))
    info_table.add_column(style="bold", justify="center")
    info_table.add_column(style="cyan", justify="left")
    info_table.add_column(style="dim", justify="left")

    info_table.add_row("🖥", "Server name:", Text(server_name or "mcp-composer", style="bold cyan"))
    info_table.add_row("📦", "Transport:", transport_display)

    if transport in ("http", "streamable-http", "sse") and host and port:
        server_url = f"http://{host}:{port}"
        # Add transport-specific path if not already provided
        if path:
            server_url += f"/{path.lstrip('/')}"
        else:
            # Default paths based on transport type
            if transport == "sse":
                server_url += "/sse"
            elif transport in ("http", "streamable-http"):
                server_url += "/mcp"
        info_table.add_row("🔗", "Server URL:", server_url)

    info_table.add_row("", "", "")
    info_table.add_row("📚", docs_label + ":", docs_display)
    info_table.add_row("🚀", hosting_label + ":", hosting_display)

    panel_content = Group(
        Align.center(logo_text),
        "",
        Align.center(title_text),
        "",
        Align.center(info_table),
    )

    panel = Panel(
        panel_content,
        border_style="cyan",
        padding=(1, 4),
        width=86,
    )

    Console(stderr=True).print(Group("\n", Align.center(panel), "\n"))

