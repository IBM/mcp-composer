"""Typer parse-time validation for ``--auth-type`` style options."""

import typer

from mcp_composer.core.utils.stdio_allowlist import (
    AUTH_TYPE_NONE,
    normalize_auth_type,
)


def auth_type_callback(value: str | None) -> str | None:
    """Normalize ``--auth-type`` (case/whitespace) and reject unknown values."""
    try:
        return normalize_auth_type(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def peer_auth_type_callback(value: str | None) -> str:
    """
    Normalize ``--remote-auth-type`` / ``--client-auth-type``.

    Same validation as ``--auth-type``, but these options default to ``"none"``
    rather than ``None``, so an unset or blank value maps to ``"none"``.
    """
    return auth_type_callback(value) or AUTH_TYPE_NONE
