"""Stdio member-server command allowlist.

Unauthenticated (or even authenticated) callers must not be able to spawn
arbitrary binaries via ``register_mcp_server`` with ``type: stdio``. Operators
opt in by listing absolute paths in ``MCP_COMPOSER_STDIO_ALLOWLIST``.
"""

from __future__ import annotations

import os
from pathlib import Path

STDIO_ALLOWLIST_ENV = "MCP_COMPOSER_STDIO_ALLOWLIST"


def parse_stdio_allowlist(raw: str | None = None) -> set[str]:
    """Return absolute realpaths from a comma-separated allowlist string."""
    value = raw if raw is not None else os.getenv(STDIO_ALLOWLIST_ENV, "")
    entries: set[str] = set()
    for part in (value or "").split(","):
        item = part.strip()
        if not item:
            continue
        path = Path(item).expanduser()
        if not path.is_absolute():
            continue
        try:
            entries.add(str(path.resolve()))
        except OSError:
            entries.add(str(path))
    return entries


def assert_stdio_command_allowed(command: str | None) -> str:
    """
    Validate ``command`` against ``MCP_COMPOSER_STDIO_ALLOWLIST``.

    Returns the resolved absolute path on success.
    Raises ``ValueError`` when the allowlist is empty, the command is not an
    absolute path, or the resolved path is not listed.
    """
    if not command or not str(command).strip():
        raise ValueError("stdio server requires a non-empty absolute command path")

    cmd_path = Path(str(command).strip()).expanduser()
    if not cmd_path.is_absolute():
        raise ValueError(
            f"stdio command must be an absolute path, got '{command}'. "
            f"Set {STDIO_ALLOWLIST_ENV} to a comma-separated list of allowed binaries."
        )

    try:
        resolved = str(cmd_path.resolve())
    except OSError as exc:
        raise ValueError(
            f"stdio command path could not be resolved: {command}"
        ) from exc

    allowlist = parse_stdio_allowlist()
    if not allowlist:
        raise ValueError(
            f"stdio member servers are disabled until {STDIO_ALLOWLIST_ENV} is set "
            "to a comma-separated list of absolute command paths"
        )
    if resolved not in allowlist:
        raise ValueError(f"stdio command '{resolved}' is not on {STDIO_ALLOWLIST_ENV}")
    return resolved


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

AUTH_TYPE_OAUTH = "oauth"
AUTH_TYPE_NONE = "none"
AUTH_TYPE_CHOICES = (AUTH_TYPE_OAUTH, AUTH_TYPE_NONE)


def normalize_auth_type(auth_type: str | None) -> str | None:
    """
    Normalise a user-supplied ``--auth-type`` value.

    Returns ``"oauth"``, ``"none"`` or ``None`` (unset). Matching is
    case-insensitive and ignores surrounding whitespace; any other value raises
    ``ValueError`` so it can never reach the bind guard or the authenticator.
    """
    if auth_type is None:
        return None
    value = auth_type.strip().lower()
    if not value:
        return None
    if value not in AUTH_TYPE_CHOICES:
        raise ValueError(
            f"Invalid auth type '{auth_type}'. Expected one of: "
            f"{', '.join(AUTH_TYPE_CHOICES)}."
        )
    return value


def auth_type_installs_provider(auth_type: str | None) -> bool:
    """
    Single predicate deciding whether an auth provider is installed.

    Used by both the bind guard and the CLI code that installs the provider,
    so the two can never disagree. The comparison is exact on purpose: callers
    must pass a value already normalised by ``normalize_auth_type``.
    """
    return auth_type == AUTH_TYPE_OAUTH


def assert_auth_installed(auth_type: str | None, provider_installed: bool) -> None:
    """Fail closed when authentication was requested but no provider exists."""
    if auth_type_installs_provider(auth_type) and not provider_installed:
        raise ValueError(
            "Authentication was requested but no auth provider was installed; "
            "refusing to start."
        )


def assert_network_bind_allowed(mode: str, host: str, auth_type: str | None) -> None:
    """
    Refuse non-loopback HTTP/SSE binds when no auth type is configured.

    Raises ``ValueError`` with an operator-facing message.
    """
    mode_l = (mode or "").strip().lower()
    if mode_l not in {"http", "sse"}:
        return
    host_l = (host or "").strip().lower()
    if host_l in LOOPBACK_HOSTS:
        return
    if auth_type_installs_provider(auth_type):
        return
    raise ValueError(
        f"Refusing to bind {host} without authentication. "
        "Pass --auth-type oauth or --host 127.0.0.1."
    )
