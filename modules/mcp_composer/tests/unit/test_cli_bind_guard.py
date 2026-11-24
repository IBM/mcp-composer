"""The `run` command must not start a non-loopback server without an auth provider."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from mcp_composer.core.cli.cli_typer import app


def _invoke(host: str, auth_type: str):
    return CliRunner().invoke(
        app,
        [
            "run",
            "--mode",
            "http",
            "--host",
            host,
            "--port",
            "9255",
            "--auth-type",
            auth_type,
        ],
    )


def test_run_refuses_non_loopback_bind_with_auth_type_none():
    with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer:
        result = _invoke("0.0.0.0", "none")

    composer.assert_not_called()
    assert result.exit_code != 0


@pytest.mark.parametrize("auth_type", ["nope", "oauth2", "false"])
@pytest.mark.parametrize("host", ["0.0.0.0", "127.0.0.1"])
def test_run_rejects_unknown_auth_type_at_parse_time(auth_type, host):
    with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer:
        result = _invoke(host, auth_type)

    composer.assert_not_called()
    assert result.exit_code == 2


@pytest.mark.parametrize("auth_type", ["OAuth", "OAUTH", "oauth "])
def test_run_case_variants_install_oauth_provider(auth_type):
    """Case variants must install the authenticator, never skip it."""
    with (
        patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer,
        patch("mcp_composer.core.cli.cli_typer.OAuthProviderFactory") as factory,
        patch("mcp_composer.core.cli.cli_typer.ServerSettings") as settings,
    ):
        settings.return_value.model_dump.return_value = {}
        provider = MagicMock()
        factory.return_value.get_provider_instance.return_value = provider
        _invoke("0.0.0.0", auth_type)

    factory.assert_called_once()
    composer.assert_called_once()
    assert composer.call_args.kwargs.get("auth") is provider
    assert "config" not in composer.call_args.kwargs


@pytest.mark.asyncio
async def test_run_dynamic_composer_fails_closed_when_provider_missing():
    import typer

    from mcp_composer.core.cli.cli_typer import run_dynamic_composer

    with (
        patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer,
        patch("mcp_composer.core.cli.cli_typer.OAuthProviderFactory") as factory,
        patch("mcp_composer.core.cli.cli_typer.ServerSettings") as settings,
    ):
        settings.return_value.model_dump.return_value = {}
        factory.return_value.get_provider_instance.return_value = MagicMock()
        composer.return_value.auth = None
        with pytest.raises(typer.BadParameter, match="no auth provider"):
            await run_dynamic_composer(
                mode="http", config=[], auth_type="oauth", host="0.0.0.0"
            )


@pytest.mark.parametrize("option", ["--remote-auth-type", "--client-auth-type"])
@pytest.mark.parametrize("value", ["oauth2", "false", "nope"])
def test_run_rejects_unknown_peer_auth_type_at_parse_time(option, value):
    with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer:
        result = CliRunner().invoke(app, ["run", "--mode", "http", option, value])

    composer.assert_not_called()
    assert result.exit_code == 2


@pytest.mark.parametrize("value", ["OAuth", "OAUTH", " oauth "])
def test_peer_auth_type_callback_normalizes_case_variants(value):
    from mcp_composer.core.cli.auth_type import peer_auth_type_callback

    assert peer_auth_type_callback(value) == "oauth"


@pytest.mark.parametrize("value", [None, "", "  ", "none", "NONE"])
def test_peer_auth_type_callback_defaults_to_none(value):
    from mcp_composer.core.cli.auth_type import peer_auth_type_callback

    assert peer_auth_type_callback(value) == "none"


@pytest.mark.asyncio
@pytest.mark.parametrize("remote", ["OAuth", "OAUTH", " oauth "])
async def test_run_dynamic_composer_remote_case_variant_uses_oauth_not_plain_proxy(
    remote,
):
    """A case variant must take the OAuth branch, never the unauthenticated proxy."""
    from mcp_composer.core.cli.cli_typer import run_dynamic_composer

    class _Stop(Exception):
        pass

    with (
        patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer,
        patch("mcp_composer.core.cli.cli_typer.OAuthProviderFactory") as factory,
        patch("mcp_composer.core.cli.cli_typer.ServerSettings") as settings,
    ):
        settings.return_value.model_dump.return_value = {}
        factory.return_value.get_provider_instance.return_value = MagicMock()
        composer.return_value.list_tools = MagicMock(side_effect=_Stop)
        composer.as_proxy = MagicMock()
        try:
            await run_dynamic_composer(
                mode="stdio",
                config=[],
                sse_url="http://example.com/sse",
                remote_auth_type=remote,
            )
        except Exception:  # pylint: disable=broad-except
            pass

    assert factory.called, "OAuth provider was not built for remote_auth_type"
    composer.as_proxy.assert_not_called()
