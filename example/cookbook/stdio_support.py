"""Helpers for recipes that mount a local stdio member."""

import os
import sys
from pathlib import Path

from mcp_composer import MCPComposer


def python_bin() -> str:
    return str(Path(sys.executable).resolve())


def allow_stdio() -> None:
    os.environ["MCP_COMPOSER_STDIO_ALLOWLIST"] = python_bin()


def child_env() -> dict[str, str]:
    kept = {}
    for key in ("PATH", "HOME", "LANG", "VIRTUAL_ENV"):
        value = os.environ.get(key)
        if value:
            kept[key] = value
    for entry in sys.path:
        if entry.endswith("site-packages"):
            kept["PYTHONPATH"] = entry
            return kept
    raise RuntimeError("Could not find site-packages for the member server.")


def composer_in(tmp: str) -> MCPComposer:
    store = str(Path(tmp) / "servers.json")
    return MCPComposer(
        "composer",
        database_config={"type": "local_file", "file_path": store},
    )


def stdio_config(server_id: str, server: Path) -> dict:
    return {
        "id": server_id,
        "type": "stdio",
        "command": python_bin(),
        "args": [str(server)],
        "cwd": str(server.parent),
        "env": child_env(),
    }


def active_ids(composer: MCPComposer) -> str:
    rows = composer._server_manager.list_servers()
    names = [str(row["id"]) for row in rows]
    return ", ".join(names) if names else "none"
