"""Tests for stdio command allowlist and network bind guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_composer.core.utils.stdio_allowlist import (
    STDIO_ALLOWLIST_ENV,
    assert_network_bind_allowed,
    assert_stdio_command_allowed,
    parse_stdio_allowlist,
)
from mcp_composer.core.utils.validator import (
    ConfigKey,
    MemberServerType,
    ServerConfigValidator,
    ValidationError,
)


def test_parse_stdio_allowlist_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(STDIO_ALLOWLIST_ENV, raising=False)
    assert parse_stdio_allowlist("") == set()
    assert parse_stdio_allowlist(None) == set()


def test_assert_stdio_denied_when_allowlist_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(STDIO_ALLOWLIST_ENV, raising=False)
    with pytest.raises(ValueError, match="disabled until"):
        assert_stdio_command_allowed("/bin/sh")


def test_assert_stdio_rejects_relative_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    allowed = tmp_path / "allowed-bin"
    allowed.write_text("#!/bin/sh\n")
    monkeypatch.setenv(STDIO_ALLOWLIST_ENV, str(allowed.resolve()))
    with pytest.raises(ValueError, match="absolute path"):
        assert_stdio_command_allowed("sh")


def test_assert_stdio_rejects_command_not_on_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed-bin"
    allowed.write_text("#!/bin/sh\n")
    other = tmp_path / "other-bin"
    other.write_text("#!/bin/sh\n")
    monkeypatch.setenv(STDIO_ALLOWLIST_ENV, str(allowed.resolve()))
    with pytest.raises(ValueError, match="not on"):
        assert_stdio_command_allowed(str(other.resolve()))


def test_assert_stdio_allows_exact_realpath(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed-bin"
    allowed.write_text("#!/bin/sh\n")
    resolved = str(allowed.resolve())
    monkeypatch.setenv(STDIO_ALLOWLIST_ENV, resolved)
    assert assert_stdio_command_allowed(resolved) == resolved


def test_validator_stdio_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "mcp-server"
    allowed.write_text("#!/bin/sh\n")
    resolved = str(allowed.resolve())
    monkeypatch.setenv(STDIO_ALLOWLIST_ENV, resolved)

    config = {
        ConfigKey.ID: "s1",
        ConfigKey.TYPE: MemberServerType.STDIO,
        ConfigKey.COMMAND: resolved,
        ConfigKey.ARGS: ["--help"],
    }
    ServerConfigValidator(config).validate()
    assert config[ConfigKey.COMMAND] == resolved

    monkeypatch.delenv(STDIO_ALLOWLIST_ENV, raising=False)
    with pytest.raises(ValidationError):
        ServerConfigValidator(
            {
                ConfigKey.ID: "s2",
                ConfigKey.TYPE: MemberServerType.STDIO,
                ConfigKey.COMMAND: resolved,
                ConfigKey.ARGS: ["--help"],
            }
        ).validate()


def test_bind_guard_allows_loopback_without_auth() -> None:
    assert_network_bind_allowed("http", "127.0.0.1", None)
    assert_network_bind_allowed("sse", "localhost", None)
    assert_network_bind_allowed("http", "::1", None)


def test_bind_guard_rejects_non_loopback_without_auth() -> None:
    with pytest.raises(ValueError, match="Refusing to bind"):
        assert_network_bind_allowed("http", "0.0.0.0", None)
    with pytest.raises(ValueError, match="Refusing to bind"):
        assert_network_bind_allowed("sse", "192.168.1.10", None)


def test_bind_guard_allows_non_loopback_with_oauth() -> None:
    assert_network_bind_allowed("http", "0.0.0.0", "oauth")


def test_bind_guard_ignores_stdio_mode() -> None:
    assert_network_bind_allowed("stdio", "0.0.0.0", None)
