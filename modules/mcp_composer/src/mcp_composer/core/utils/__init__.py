# src/utils/__init__.py
"""Core utilities package.

Import leaf modules (for example ``mcp_composer.core.utils.logger``) from code
on the auth import cycle. ``get_client`` is lazy so this package does not
eagerly import auth adapters.
"""

from __future__ import annotations

from typing import Any

from .exceptions import ToolGenerateError
from .health import HealthMonitor
from .logger import LoggerFactory
from .validator import (
    AllServersValidator,
    AuthStrategy,
    ConfigKey,
    MemberServerType,
    ServerConfigValidator,
    ValidationError,
)

__all__ = [
    "HealthMonitor",
    "LoggerFactory",
    "ValidationError",
    "ServerConfigValidator",
    "AllServersValidator",
    "ConfigKey",
    "MemberServerType",
    "AuthStrategy",
    "ToolGenerateError",
    "build_prompt_from_dict",
    "get_version_adapter",
    "get_member_health",
    "get_client",
    "load_custom_mappings_from_json",
    "load_json",
    "load_json_sync",
    "load_spec_from_url",
    "ensure_dependencies_installed",
    "extract_imported_modules",
    "get_server_doc_info",
]

_LAZY_AUTH = {"get_client"}
_LAZY_UTILS = {
    "build_prompt_from_dict",
    "ensure_dependencies_installed",
    "extract_imported_modules",
    "get_member_health",
    "get_server_doc_info",
    "get_version_adapter",
    "load_custom_mappings_from_json",
    "load_json",
    "load_json_sync",
    "load_spec_from_url",
}


def __getattr__(name: str) -> Any:
    """Load adapters that would otherwise cycle through member servers."""
    if name in _LAZY_AUTH:
        from .auth_strategy import get_client

        return get_client
    if name in _LAZY_UTILS:
        from . import utils as utils_module

        return getattr(utils_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
