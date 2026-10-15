"""Security utilities for MCP Composer.

This module provides security-related utilities including:
- Configuration sanitization for safe logging
- Sensitive data masking
"""

from typing import Any
import copy

# Define sensitive field patterns (case-insensitive matching)
SENSITIVE_FIELDS: set[str] = {
    "password",
    "token",
    "api_key",
    "apikey",
    "secret",
    "credential",
    "auth",
    "authorization",
    "bearer",
    "private_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "api_secret",
    "session_id",
    "cookie",
}


def sanitize_config(config: dict[str, Any], mask: str = "***REDACTED***") -> dict[str, Any]:
    """
    Remove or mask sensitive fields from config for safe logging.

    This function recursively traverses dictionaries and lists, replacing
    values of fields that match sensitive patterns with a mask string.

    Args:
        config: Configuration dictionary to sanitize
        mask: String to replace sensitive values with (default: "***REDACTED***")

    Returns:
        Sanitized copy of config with sensitive fields masked

    Example:
        >>> config = {"api_key": "secret123", "endpoint": "https://api.example.com"}
        >>> sanitize_config(config)
        {"api_key": "***REDACTED***", "endpoint": "https://api.example.com"}
    """
    if not isinstance(config, dict):
        return config

    sanitized = copy.deepcopy(config)

    def _sanitize_recursive(obj: Any) -> Any:
        """Recursively sanitize nested structures."""
        if isinstance(obj, dict):
            return {k: mask if _is_sensitive_field(k) else _sanitize_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize_recursive(item) for item in obj]
        return obj

    return _sanitize_recursive(sanitized)


def _is_sensitive_field(field_name: str) -> bool:
    """
    Check if a field name matches sensitive patterns.

    Args:
        field_name: Field name to check

    Returns:
        True if field is sensitive, False otherwise
    """
    field_lower = field_name.lower()
    return any(sensitive in field_lower for sensitive in SENSITIVE_FIELDS)


def mask_value(value: str, show_chars: int = 4) -> str:
    """
    Mask a sensitive value, showing only first/last characters.

    Args:
        value: Value to mask
        show_chars: Number of characters to show at start/end

    Returns:
        Masked value string

    Example:
        >>> mask_value("secret_api_key_12345", show_chars=4)
        "secr...2345"
    """
    if not value or len(value) <= show_chars * 2:
        return "***REDACTED***"

    return f"{value[:show_chars]}...{value[-show_chars:]}"


# Made with Bob
