"""Redact secrets from log records and structured log payloads."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "***REDACTED***"

# Exact key names (case-insensitive, hyphen→underscore) treated as secrets.
_SENSITIVE_EXACT = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "apikey",
        "api_key",
        "authorization",
        "auth_header",
        "client_secret",
        "private_key",
        "refresh_token",
        "access_token",
        "jsessionid",
        "cookie",
        "set_cookie",
        "x_api_key",
    }
)
# Suffixes that imply a credential value (token_url is intentionally excluded).
_SENSITIVE_SUFFIXES = (
    "_password",
    "_passwd",
    "_pwd",
    "_secret",
    "_token",
    "_apikey",
    "_api_key",
)

_PASSWORD_ASSIGN = re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*[^\s,;\"']+")
_CLIENT_SECRET_ASSIGN = re.compile(
    r"(?i)\b(client_secret|clientsecret)\b\s*[:=]\s*[^\s,;\"']+"
)
_API_KEY_ASSIGN = re.compile(r"(?i)\b(api[_-]?key|apikey)\b\s*[:=]\s*[^\s,;\"']+")
_TOKEN_ASSIGN = re.compile(
    r"(?i)\b(access_token|refresh_token|id_token)\b\s*[:=]\s*[^\s,;\"']+"
)
_JSESSIONID = re.compile(r"(?i)\bJSESSIONID\s*=\s*[^\s;,\"']+")
_AUTHORIZATION = re.compile(r"(?i)(Authorization\s*[:=]\s*)\S.*")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-~+/=]{8,}")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_COOKIE_HEADER = re.compile(r"(?i)(Cookie\s*[:=]\s*).+")


def is_sensitive_key(key: str) -> bool:
    """Return True when a mapping/header key looks credential-shaped."""
    lowered = key.lower().replace("-", "_")
    if lowered in _SENSITIVE_EXACT:
        return True
    return any(lowered.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)


def redact_mapping(data: Mapping[Any, Any]) -> dict[Any, Any]:
    """Return a copy of a mapping with sensitive values masked."""
    out: dict[Any, Any] = {}
    for key, value in data.items():
        key_str = str(key)
        if is_sensitive_key(key_str):
            out[key] = REDACTED
        elif isinstance(value, Mapping):
            out[key] = redact_mapping(value)
        elif isinstance(value, list):
            out[key] = [redact_for_log(item) for item in value]
        else:
            out[key] = value
    return out


def redact_headers(headers: Mapping[str, Any] | None) -> dict[str, Any]:
    """Redact HTTP header values that must not appear in logs."""
    if not headers:
        return {}
    return redact_mapping(headers)


def redact_for_log(value: Any) -> Any:
    """Redact nested structures before passing them to a logger."""
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_for_log(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_for_log(item) for item in value)
    if isinstance(value, str):
        return redact_message(value)
    return value


def redact_message(message: str) -> str:
    """Scrub credential-shaped substrings from a formatted log message."""
    redacted = message
    redacted = _PASSWORD_ASSIGN.sub(rf"\1={REDACTED}", redacted)
    redacted = _CLIENT_SECRET_ASSIGN.sub(rf"\1={REDACTED}", redacted)
    redacted = _API_KEY_ASSIGN.sub(rf"\1={REDACTED}", redacted)
    redacted = _TOKEN_ASSIGN.sub(rf"\1={REDACTED}", redacted)
    redacted = _JSESSIONID.sub(f"JSESSIONID={REDACTED}", redacted)
    redacted = _AUTHORIZATION.sub(rf"\1{REDACTED}", redacted)
    redacted = _BEARER.sub(f"Bearer {REDACTED}", redacted)
    redacted = _JWT.sub(REDACTED, redacted)
    redacted = _COOKIE_HEADER.sub(rf"\1{REDACTED}", redacted)
    return redacted


class SecretRedactionFilter(logging.Filter):
    """Logging filter that redacts secrets from the final record message."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                if isinstance(record.args, Mapping):
                    record.args = redact_for_log(record.args)
                elif isinstance(record.args, tuple):
                    record.args = tuple(redact_for_log(arg) for arg in record.args)
                else:
                    record.args = redact_for_log(record.args)

            rendered = record.getMessage()
            scrubbed = redact_message(rendered)
            if scrubbed != rendered:
                record.msg = scrubbed
                record.args = ()
        except Exception:  # noqa: BLE001 — never break logging
            return True
        return True
