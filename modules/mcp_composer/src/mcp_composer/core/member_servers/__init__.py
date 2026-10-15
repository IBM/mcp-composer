# src/member_servers/__init__.py
"""Member server package.

Heavy symbols are lazy so importing a leaf module does not pull builder and
auth into every import of this package.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "MCPServerBuilder",
    "ServerManager",
    "MemberMCPServer",
    "LayeredOpenAPIFactory",
]

_LAZY = {
    "MCPServerBuilder": (".builder", "MCPServerBuilder"),
    "ServerManager": (".server_manager", "ServerManager"),
    "MemberMCPServer": (".member_server", "MemberMCPServer"),
    "LayeredOpenAPIFactory": (".layered_factory_oa", "LayeredOpenAPIFactory"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name, __name__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
