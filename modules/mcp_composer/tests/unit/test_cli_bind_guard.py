"""The `run` command must not start a non-loopback server without an auth provider."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mcp_composer.core.cli.cli_typer import app


@pytest.mark.parametrize("auth_type", ["none", "nope", "OAuth"])
def test_run_refuses_non_loopback_bind_when_auth_type_installs_no_provider(auth_type):
    with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as composer:
        result = CliRunner().invoke(
            app,
            [
                "run",
                "--mode",
                "http",
                "--host",
                "0.0.0.0",
                "--port",
                "9255",
                "--auth-type",
                auth_type,
            ],
        )

    composer.assert_not_called()
    assert result.exit_code != 0
