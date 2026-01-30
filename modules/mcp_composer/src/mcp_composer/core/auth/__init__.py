"""
Authentication module for MCP Composer.

This module provides authentication support including OAuth and JWT.
"""

# JWT Authentication
from .jwt import (
    JWTConfig,
    JWTAuthProvider,
    extract_jwt_from_header,
    decode_jwt_token,
    generate_jwt_token,
    validate_jwt_claims,
)

__all__ = [
    # JWT
    "JWTConfig",
    "JWTAuthProvider",
    "extract_jwt_from_header",
    "decode_jwt_token",
    "generate_jwt_token",
    "validate_jwt_claims",
]
