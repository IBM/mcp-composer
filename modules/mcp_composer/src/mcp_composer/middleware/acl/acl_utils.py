"""
ACL utilities for policy enforcement and role resolution.
"""

import os
from typing import Any
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def resolve_role_from_context(context: dict[str, Any]) -> str:
    """
    Resolve the current role from the context.

    Args:
        context: Dictionary containing request context including user info

    Returns:
        str: The resolved role for the current user/request
    """
    # Try to extract role from various possible locations in context
    if isinstance(context, dict):
        # Check for explicit role in context
        if "role" in context:
            return context["role"]

        # Check for user info that might contain role
        if "user" in context and isinstance(context["user"], dict):
            user = context["user"]
            if "role" in user:
                return user["role"]
            if (
                "roles" in user
                and isinstance(user["roles"], list)
                and len(user["roles"]) > 0
            ):
                return user["roles"][0]  # Use first role if multiple

        # Check for JWT claims
        if "claims" in context and isinstance(context["claims"], dict):
            claims = context["claims"]
            if "role" in claims:
                return claims["role"]
            if (
                "roles" in claims
                and isinstance(claims["roles"], list)
                and len(claims["roles"]) > 0
            ):
                return claims["roles"][0]

        # Check for headers that might contain role info
        if "headers" in context and isinstance(context["headers"], dict):
            headers = context["headers"]
            if "x-user-role" in headers:
                return headers["x-user-role"]
            if "x-role" in headers:
                return headers["x-role"]

    # Default to environment variable or fallback
    default_role = os.getenv("DEFAULT_USER_ROLE", "user")
    logger.debug("No role found in context, using default: %s", default_role)
    return default_role


def extract_context_info(context: dict[str, Any]) -> dict[str, Any]:
    """
    Extract relevant information from context for policy evaluation.

    Args:
        context: The request context

    Returns:
        Dict containing extracted context information
    """
    extracted = {
        "role": resolve_role_from_context(context),
        "timestamp": context.get("timestamp"),
        "user_id": None,
        "project": None,
        "agent_type": None,
        "resource_type": None,
    }

    # Extract user ID
    if "user" in context and isinstance(context["user"], dict):
        extracted["user_id"] = context["user"].get("id") or context["user"].get(
            "user_id"
        )

    # Extract project info
    if "project" in context:
        extracted["project"] = context["project"]
    elif "headers" in context and isinstance(context["headers"], dict):
        extracted["project"] = context["headers"].get("x-project")

    # Extract agent type
    if "agent_type" in context:
        extracted["agent_type"] = context["agent_type"]
    elif "headers" in context and isinstance(context["headers"], dict):
        extracted["agent_type"] = context["headers"].get("x-agent-type")

    # Extract resource type
    if "resource_type" in context:
        extracted["resource_type"] = context["resource_type"]

    return extracted


def validate_policy_config(config: dict[str, Any]) -> bool:
    """
    Validate policy configuration.

    Args:
        config: Policy configuration dictionary

    Returns:
        bool: True if valid, False otherwise
    """
    # Handle None config
    if config is None:
        logger.error("Policy config is None")
        return False

    required_fields = ["mode"]
    if not all(field in config for field in required_fields):
        logger.error("Missing required fields in policy config: %s", required_fields)
        return False

    valid_modes = ["file", "vault", "opa", "jwt", "permit"]
    if config["mode"] not in valid_modes:
        logger.error(
            "Invalid policy mode: %s. Valid modes: %s", config["mode"], valid_modes
        )
        return False

    return True
