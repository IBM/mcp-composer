"""
JWT Authentication module for MCP Composer.

This module provides JWT authentication support using FastMCP's built-in JWTVerifier.
It offers a clean interface for configuring and using JWT authentication in MCP Composer applications.

Example:
    >>> from mcp_composer.core.auth.jwt import JWTAuthProvider, JWTConfig
    >>>
    >>> # Load from environment
    >>> jwt_config = JWTConfig.from_env(prefix="SOLIS_JWT_")
    >>> jwt_provider = JWTAuthProvider(config=jwt_config)
    >>>
    >>> # Use with MCPComposer
    >>> from mcp_composer import MCPComposer
    >>> composer = MCPComposer("my-composer", auth=jwt_provider.get_verifier())
"""

from .jwt_config import JWTConfig
from .jwt_provider import JWTAuthProvider
from .jwt_utils import (
    extract_jwt_from_header,
    decode_jwt_token,
    generate_jwt_token,
    validate_jwt_claims,
)

__all__ = [
    "JWTConfig",
    "JWTAuthProvider",
    "extract_jwt_from_header",
    "decode_jwt_token",
    "generate_jwt_token",
    "validate_jwt_claims",
]

__version__ = "1.0.0"
