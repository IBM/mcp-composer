"""
Policy-based Access Control package for MCP Composer.

This package provides a single PolicyMiddleware that follows the adapter pattern
to support multiple policy providers (File, JWT, Vault, OPA, Permit).
"""

from .policy_middleware import PolicyMiddleware
from .config import PolicyMode, IdentityMode, Settings, SETTINGS
from .identity_manager import IdentityManager
from .schemas import AuthContext

__all__ = [
    "PolicyMiddleware",
    "PolicyMode",
    "IdentityMode",
    "Settings",
    "SETTINGS",
    "IdentityManager",
    "AuthContext",
]
