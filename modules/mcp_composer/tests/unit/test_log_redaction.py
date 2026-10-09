"""Tests for secret redaction in logs."""

from __future__ import annotations

import logging

import pytest

from mcp_composer.core.utils.log_redaction import (
    REDACTED,
    SecretRedactionFilter,
    is_sensitive_key,
    redact_for_log,
    redact_headers,
    redact_mapping,
    redact_message,
)
from mcp_composer.core.utils.logger import LoggerFactory


class TestLogRedactionHelpers:
    def test_sensitive_keys(self):
        assert is_sensitive_key("password")
        assert is_sensitive_key("Authorization")
        assert is_sensitive_key("access_token")
        assert is_sensitive_key("client_secret")
        assert is_sensitive_key("X-API-Key")
        assert not is_sensitive_key("token_url")
        assert not is_sensitive_key("auth_strategy")
        assert not is_sensitive_key("username")

    def test_redact_mapping_keeps_non_secrets(self):
        payload = {
            "username": "alice",
            "password": "s3cret",
            "token_url": "https://example.com/token",
            "auth": {"client_secret": "top-secret", "client_id": "app"},
        }
        redacted = redact_mapping(payload)
        assert redacted["username"] == "alice"
        assert redacted["password"] == REDACTED
        assert redacted["token_url"] == "https://example.com/token"
        assert redacted["auth"]["client_secret"] == REDACTED
        assert redacted["auth"]["client_id"] == "app"

    def test_redact_headers(self):
        headers = {
            "Authorization": "Bearer abc.def.ghi",
            "Content-Type": "application/json",
            "Cookie": "JSESSIONID=abc123",
        }
        redacted = redact_headers(headers)
        assert redacted["Authorization"] == REDACTED
        assert redacted["Content-Type"] == "application/json"
        assert redacted["Cookie"] == REDACTED

    def test_redact_message_patterns(self):
        assert REDACTED in redact_message("login password=super-secret-value")
        assert "super-secret-value" not in redact_message(
            "login password=super-secret-value"
        )
        assert "abc123" not in redact_message("cookie JSESSIONID=abc123; Path=/")
        assert "secret-token" not in redact_message(
            "Authorization: Bearer secret-token-value"
        )
        assert REDACTED in redact_message("Bearer secret-token-value")


class TestSecretRedactionFilter:
    def test_filter_redacts_format_args_dict(self, caplog):
        logger = logging.getLogger("test-secret-filter-dict")
        logger.handlers.clear()
        logger.filters.clear()
        logger.addFilter(SecretRedactionFilter())
        logger.setLevel(logging.INFO)
        logger.propagate = True

        with caplog.at_level(logging.INFO, logger="test-secret-filter-dict"):
            logger.info("auth payload %s", {"password": "do-not-log", "user": "a"})

        text = " ".join(r.message for r in caplog.records)
        assert "do-not-log" not in text
        assert REDACTED in text
        assert "user" in text or "'user'" in text

    def test_filter_redacts_password_in_message(self, caplog):
        logger = logging.getLogger("test-secret-filter-msg")
        logger.handlers.clear()
        logger.filters.clear()
        logger.addFilter(SecretRedactionFilter())
        logger.setLevel(logging.INFO)
        logger.propagate = True

        with caplog.at_level(logging.INFO, logger="test-secret-filter-msg"):
            logger.info("pwd=hunter2")

        text = " ".join(r.message for r in caplog.records)
        assert "pwd=hunter2" not in text
        assert f"pwd={REDACTED}" in text


@pytest.mark.asyncio
async def test_jsessionid_login_does_not_log_password(caplog):
    from unittest.mock import AsyncMock, Mock, patch

    import httpx

    from mcp_composer.core.auth_handler.dynamic_token_manager import DynamicTokenManager
    from mcp_composer.core.utils import AuthStrategy, ConfigKey

    # Ensure factory logger has the redaction filter.
    LoggerFactory.get_logger()

    manager = DynamicTokenManager(
        base_url="https://api.example.com",
        **{
            ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID,
            ConfigKey.LOGIN_URL: "/login",
            ConfigKey.USERNAME: "testuser",
            ConfigKey.PASSWORD: "very-secret-password",
        },
    )

    mock_response = Mock()
    mock_response.cookies = {"JSESSIONID": "session-secret-id"}
    mock_response.raise_for_status.return_value = None
    mock_temp_client = AsyncMock()
    mock_temp_client.post.return_value = mock_response
    mock_temp_client.base_url = "https://api.example.com"
    mock_authenticated_client = Mock(spec=httpx.AsyncClient)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.side_effect = [mock_temp_client, mock_authenticated_client]
        with (
            patch.object(mock_temp_client, "__aenter__", return_value=mock_temp_client),
            patch.object(mock_temp_client, "__aexit__", return_value=None),
            caplog.at_level(logging.INFO),
        ):
            await manager.get_authenticated_http_client_for_jessonid()

    text = " ".join(r.message for r in caplog.records)
    assert "very-secret-password" not in text
    assert "session-secret-id" not in text


def test_logger_factory_attaches_filter():
    logger = LoggerFactory.get_logger("mcp-composer-redaction-check")
    assert any(isinstance(f, SecretRedactionFilter) for f in logger.filters)


def test_redact_for_log_leaves_primitives():
    assert redact_for_log(3) == 3
    assert redact_for_log(None) is None


def test_api_key_identity_is_not_logged(caplog):
    from mcp_composer.middleware.acl.policy.config import IdentityMode, Settings
    from mcp_composer.middleware.acl.policy.identity_manager import IdentityManager

    api_key = "live-api-key-do-not-log"
    manager = IdentityManager(
        Settings(identity_mode=IdentityMode.keyed, api_key_header="X-API-Key")
    )
    context = type("Ctx", (), {"headers": {"X-API-Key": api_key}})()
    log = logging.getLogger("mcp-composer")
    log.propagate = True

    with caplog.at_level(logging.DEBUG, logger="mcp-composer"):
        user_id, attributes = manager.extract_identity(context)

    assert user_id == api_key
    assert attributes["api_key"] == api_key
    text = " ".join(record.getMessage() for record in caplog.records)
    assert api_key not in text
    assert "Extracted API key identity" in text


def test_load_jwt_provider_does_not_log_secret(caplog, monkeypatch):
    from mcp_composer.core.auth.jwt.jwt_utils import load_jwt_provider

    secret = "jwt-key-material-do-not-log-0123456789abcdef"
    monkeypatch.setenv(
        "JWT_SECRET", f"-----BEGIN PUBLIC KEY-----\n{secret}\n-----END PUBLIC KEY-----"
    )
    log = logging.getLogger("mcp-composer")
    log.propagate = True

    with caplog.at_level(logging.DEBUG, logger="mcp-composer"):
        provider = load_jwt_provider()

    assert provider is not None
    text = " ".join(record.getMessage() for record in caplog.records)
    assert secret not in text
    # CodeQL treats the env-var name as sensitive; do not log JWT_SECRET.
    assert "JWT_SECRET" not in text
    assert "configured environment variable" in text


def test_load_jwt_provider_failure_does_not_log_secret(caplog, monkeypatch):
    from mcp_composer.core.auth.jwt.jwt_utils import load_jwt_provider

    secret = "jwt-failure-key-material-do-not-log"
    monkeypatch.setenv("JWT_SECRET", secret)
    log = logging.getLogger("mcp-composer")
    log.propagate = True

    with caplog.at_level(logging.DEBUG, logger="mcp-composer"):
        with pytest.raises(Exception):
            load_jwt_provider()

    text = " ".join(record.getMessage() for record in caplog.records)
    assert secret not in text
    assert "JWT_SECRET" not in text
    assert "environment secret variable" in text
    assert "ValidationError" in text or "ValueError" in text
