"""
Utility module for managing optional dependencies in MCP Composer.

This module provides functions to detect which optional dependency groups
are needed based on environment variables, check if optional dependencies
are available, and generate helpful installation messages.
"""

import os
from typing import Set


def detect_required_extras() -> set[str]:
    """
    Detect which optional dependency groups are needed based on environment.

    Returns:
        Set of extra names that should be installed
    """
    extras = set()

    # Check for IBM Secrets Manager (optional)
    if os.getenv("IBM_SECRETS_MANAGER_URL") or os.getenv("IBM_CLOUD_API_KEY"):
        extras.add("ibm-cloud")

    # Check for PostgreSQL
    if os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL", "").startswith(
        "postgres"
    ):
        extras.add("databases")

    # Check for Vault
    if os.getenv("VAULT_ADDR") or os.getenv("VAULT_TOKEN"):
        extras.add("secrets")

    # Check for AI features
    if any(
        os.getenv(var)
        for var in [
            "GOOGLE_API_KEY",
            "LITELLM_API_KEY",
            "OLLAMA_HOST",
        ]
    ):
        extras.add("ai")

    # Check for A2A
    if os.getenv("A2A_ENABLED") == "true":
        extras.add("a2a")

    # Check for search
    if os.getenv("ENABLE_SEARCH") == "true":
        extras.add("search")

    return extras


def check_optional_dependency(feature: str, package: str) -> bool:
    """
    Check if an optional dependency is available.

    Args:
        feature: Feature name (e.g., "IBM Cloud", "PostgreSQL")
        package: Package name to check

    Returns:
        True if available, False otherwise
    """
    try:
        __import__(package)
        return True
    except ImportError:
        return False


def get_missing_extras_message(extras: set[str]) -> str:
    """
    Generate installation message for missing extras.

    Args:
        extras: Set of extra names

    Returns:
        Installation command message
    """
    if not extras:
        return ""

    extras_str = ",".join(sorted(extras))
    return (
        f"Missing optional dependencies detected. Install with:\n"
        f"  pip install mcp-composer[{extras_str}]\n"
        f"Or install all optional features:\n"
        f"  pip install mcp-composer[all]"
    )


def get_install_message(extra: str) -> str:
    """
    Generate installation message for a specific extra.

    Args:
        extra: Extra name (e.g., "ibm-cloud", "databases")

    Returns:
        Installation command message
    """
    return f"Install with: pip install mcp-composer[{extra}]"


# Made with Bob
