# middleware_manager.py
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp_composer.core.middleware.middleware_config import (
    MiddlewareConfig,
    load_and_validate_config,
)
from mcp_composer.core.middleware.hook_filter import HookFilter

# FastMCP interfaces
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.exceptions import ToolError


# =========================
# Utility helpers
# =========================


def _match_glob(pat: str, s: str) -> bool:
    """Simple '*' glob matcher (full-string)."""
    rx = "^" + re.escape(pat).replace("\\*", ".*") + "$"
    return re.match(rx, s or "") is not None


def _import_kind(kind: str):
    """
    Import 'module.Class' and return the class object.
    Raises ImportError / AttributeError if unresolved.
    """
    module_path, cls_name = kind.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)


def _hook_name(h: Any) -> str:
    """
    Normalize hook identifier to string.
    Supports Enum-like objects with `.value`, else returns as-is.
    """
    return getattr(h, "value", h)


class MiddlewareManager:
    """
    Builds, orders, and attaches middleware instances from declarative config.
    """

    def __init__(
        self, config_path: Optional[str] = None, *, ensure_imports: bool = False
    ):
        self._config_path = config_path
        self._config: Optional[MiddlewareConfig] = None
        self._middlewares: List[Middleware] = []
        if config_path:
            self.load(config_path, ensure_imports=ensure_imports)

    # ----- Public API -----

    def load(self, path: str, *, ensure_imports: bool = False) -> MiddlewareConfig:
        """
        Load & validate config (JSON). Use ensure_imports=True to also verify that
        each 'kind' module.Class resolves at import time.
        """
        self._config = load_and_validate_config(path, ensure_imports=ensure_imports)
        # Build instances immediately
        self._middlewares = self._build_from_config(self._config)
        return self._config

    def attach_to_server(self, mcp_server: Any) -> None:
        """
        Add built middlewares to a FastMCP server (in execution order).
        """
        for mw in self._middlewares:
            mcp_server.add_middleware(mw)

    def get_enabled_middlewares(self) -> List[Middleware]:
        """
        Return the list of enabled middlewares (already ordered).
        """
        return list(self._middlewares)

    def describe(self) -> List[Dict[str, Any]]:
        """
        Introspection helper for UIs/CLIs: returns name, priority, hooks for enabled items.
        """
        out: List[Dict[str, Any]] = []
        if not self._config:
            return out
        enabled_by_name = {
            m.entry.name: m for m in self._middlewares if isinstance(m, HookFilter)
        }
        for entry in sorted(
            (e for e in self._config.middleware if e.mode == "enabled"),
            key=lambda x: x.priority,
        ):
            hooks = [_hook_name(h) for h in entry.applied_hooks]
            out.append(
                {
                    "name": entry.name,
                    "priority": entry.priority,
                    "applied_hooks": hooks,
                    "attached": entry.name in enabled_by_name,
                }
            )
        return out

    # ----- Internals -----

    def _build_from_config(self, cfg: MiddlewareConfig) -> List[Middleware]:
        """
        Build middleware instances from the validated config and sort by priority.
        Respects settings.fail_on_middleware_error; otherwise logs to stderr and skips.
        """
        items: List[tuple[int, Middleware]] = []
        fail_hard = bool(cfg.middleware_settings.fail_on_middleware_error)

        for entry in cfg.middleware:
            if getattr(entry, "mode", "enabled") != "enabled":
                continue

            try:
                Kind = _import_kind(entry.kind)
            except Exception as e:
                msg = f"[middleware_manager] Failed to import kind '{entry.kind}' for '{entry.name}': {e}"
                if fail_hard:
                    raise
                print(msg, file=sys.stderr)
                continue

            try:
                # Instantiate with **config dict
                inner = Kind(**(entry.config or {}))
                wrapped = HookFilter(inner, entry)
                items.append((entry.priority, wrapped))
            except Exception as e:
                msg = f"[middleware_manager] Failed to instantiate '{entry.name}' ({entry.kind}): {e}"
                if fail_hard:
                    raise
                print(msg, file=sys.stderr)
                continue

        # Order: lower priority number runs earlier
        items.sort(key=lambda x: x[0])
        return [mw for _, mw in items]


# =========================
# Convenience function
# =========================


def load_and_build(
    config_path: str, *, ensure_imports: bool = False
) -> List[Middleware]:
    """
    One-shot helper: returns built/ordered middlewares from a config path.
    """
    cfg = load_and_validate_config(config_path, ensure_imports=ensure_imports)
    mgr = MiddlewareManager()
    return mgr._build_from_config(cfg)
