import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from mcp_composer.core.utils.cli import main, build_config_from_args


@patch("mcp_composer.core.utils.cli._setup_args_parser")
def test_main_runs_with_valid_args(mock_setup_parser):
    mock_parser = MagicMock()
    mock_args = MagicMock()
    mock_args.endpoint = "http://localhost:8000"
    mock_args.script_path = None
    mock_args.config_path = "/tmp/config.json"
    mock_args.pass_environment = False
    mock_args.env = []
    mock_parser.parse_args.return_value = mock_args
    mock_setup_parser.return_value = mock_parser
    with (
        patch(
            "mcp_composer.core.utils.cli.build_config_from_args", return_value=[{"id": "x"}]
        ) as mock_build_config,
        patch("mcp_composer.core.utils.cli.asyncio.run") as mock_asyncio_run,
    ):
        main()
        mock_build_config.assert_called_once_with(mock_args)
        mock_asyncio_run.assert_called()


@patch("mcp_composer.core.utils.cli._setup_args_parser")
def test_main_handles_exception_and_exits(mock_setup_parser):
    mock_parser = MagicMock()
    mock_args = MagicMock()
    mock_args.endpoint = "http://localhost:8000"
    mock_args.script_path = None
    mock_args.config_path = "/tmp/config.json"
    mock_args.pass_environment = False
    mock_args.env = []
    mock_parser.parse_args.return_value = mock_args
    mock_setup_parser.return_value = mock_parser
    with (
        patch(
            "mcp_composer.core.utils.cli.build_config_from_args",
            side_effect=Exception("fail"),
        ),
        patch("mcp_composer.core.utils.cli.logger") as mock_logger,
        patch("sys.exit") as mock_exit,
    ):
        main()
        mock_logger.error.assert_called()
        mock_exit.assert_called_with(1)


def test_build_config_from_args_http():
    class Args:
        mode = "http"
        endpoint = "http://api.example.com"
        id = "testid"
        script_path = None
        directory = None

    args = Args()
    config = build_config_from_args(args)
    assert config[0]["type"] == "http"
    assert config[0]["endpoint"] == "http://api.example.com"


def test_build_config_from_args_stdio():
    class Args:
        mode = "stdio"
        endpoint = None
        id = "testid"
        script_path = "/tmp/server.py"
        directory = None

    args = Args()
    config = build_config_from_args(args)
    assert config[0]["type"] == "stdio"
    assert "args" in config[0]
    assert config[0]["args"][0] == "--directory"


def test_build_config_from_args_missing_script_path():
    class Args:
        mode = "stdio"
        endpoint = None
        id = "testid"
        script_path = None
        directory = None

    args = Args()
    with pytest.raises(ValueError):
        build_config_from_args(args)


def test_build_config_from_args_unsupported_mode():
    class Args:
        mode = "invalid"
        endpoint = None
        id = "testid"
        script_path = None
        directory = None

    args = Args()
    with pytest.raises(ValueError):
        build_config_from_args(args)
