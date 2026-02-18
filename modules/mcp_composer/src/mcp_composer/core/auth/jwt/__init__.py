"""
JWT Authentication module for MCP Composer.

This module provides JWT authentication support using FastMCP's built-in JWTVerifier,
as well as ISV token validation for IBM Solis platform authentication.

Example (JWT):
    >>> from mcp_composer.core.auth.jwt import JWTAuthProvider, JWTConfig
    >>>
    >>> # Load from environment
    >>> jwt_config = JWTConfig.from_env(prefix="SOLIS_JWT_")
    >>> jwt_provider = JWTAuthProvider(config=jwt_config)
    >>>
    >>> # Use with MCPComposer
    >>> from mcp_composer import MCPComposer
    >>> composer = MCPComposer("my-composer", auth=jwt_provider.get_verifier())

Example (ISV Token):
    >>> from mcp_composer.core.auth.jwt import ISVTokenVerifier
    >>>
    >>> # Create ISV verifier
    >>> isv_verifier = ISVTokenVerifier(environment='test')
    >>>
    >>> # Use with MCPComposer
    >>> composer = MCPComposer("my-composer", auth=isv_verifier)
"""

from .jwt_config import JWTConfig
from .jwt_provider import JWTAuthProvider
from .jwt_utils import (
    extract_jwt_from_header,
    decode_jwt_token,
    generate_jwt_token,
    validate_jwt_claims,
)
from .isv_token_validator import (
    ISVTokenVerifier,
    ISVTokenValidator,
    ISVEnvironmentConfig,
    ISVTokenCache,
)

__all__ = [
    # JWT Authentication
    "JWTConfig",
    "JWTAuthProvider",
    "extract_jwt_from_header",
    "decode_jwt_token",
    "generate_jwt_token",
    "validate_jwt_claims",
    # ISV Token Authentication
    "ISVTokenVerifier",
    "ISVTokenValidator",
    "ISVEnvironmentConfig",
    "ISVTokenCache",
]

__version__ = "1.1.0"
