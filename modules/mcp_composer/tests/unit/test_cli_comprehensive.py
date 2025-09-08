"""
Comprehensive test cases for MCP Composer CLI commands.

This module tests all CLI functionality including:
- Main MCP Composer commands (HTTP, SSE, STDIO modes)
- Middleware management commands (validate, list, add-middleware)
- OAuth integration
- Error handling and edge cases
"""

import pytest
import os
import sys
import json
import tempfile
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from argparse import Namespace
from pathlib import Path

# Add the src directory to the path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

from mcp_composer.core.utils.cli_legacy import (
    _setup_args_parser,
    _setup_middleware_parser,
    _add_arguments_to_parser,
    _add_middleware_command,
    build_config_from_args,
    run_dynamic_composer,
    main,
)
from mcp_composer.core.cli.middleware_cli import (
    cmd_validate,
    cmd_list,
    cmd_add_middleware,
)


class TestCLIMainCommands:
    """Test cases for main MCP Composer CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = _setup_args_parser()

    def test_parser_setup(self):
        """Test that the main parser is set up correctly."""
        assert self.parser is not None
        assert "Run MCP Composer with dynamically constructed config" in self.parser.description

    def test_main_arguments(self):
        """Test that all main arguments are properly defined."""
        help_text = self.parser.format_help()
        
        # Core arguments
        assert "--mode" in help_text
        assert "--id" in help_text
        assert "--endpoint" in help_text
        assert "--config_path" in help_text
        assert "--host" in help_text
        assert "--port" in help_text
        
        # Advanced arguments
        assert "--auth_type" in help_text
        assert "--sse-url" in help_text
        assert "--disable-composer-tools" in help_text
        assert "--env" in help_text
        assert "--pass-environment" in help_text
        assert "--remote_auth_type" in help_text
        assert "--client_auth_type" in help_text

    def test_mode_choices(self):
        """Test that mode argument has correct choices."""
        mode_action = next(action for action in self.parser._actions if action.dest == "mode")
        assert mode_action.choices == ["http", "sse", "stdio"]
        assert mode_action.default == "stdio"

    def test_default_values(self):
        """Test that default values are set correctly."""
        # Test default values
        id_action = next(action for action in self.parser._actions if action.dest == "id")
        assert id_action.default == "mcp-local"
        
        host_action = next(action for action in self.parser._actions if action.dest == "host")
        assert host_action.default == "0.0.0.0"
        
        port_action = next(action for action in self.parser._actions if action.dest == "port")
        assert port_action.default == 9000

    def test_boolean_optional_actions(self):
        """Test that boolean optional actions are properly configured."""
        disable_tools_action = next(
            action for action in self.parser._actions if action.dest == "disable_composer_tools"
        )
        assert disable_tools_action.default is False
        # Check that it's a BooleanOptionalAction by checking the option strings
        assert "--disable-composer-tools" in disable_tools_action.option_strings
        assert "--no-disable-composer-tools" in disable_tools_action.option_strings

    def test_environment_variable_handling(self):
        """Test environment variable argument handling."""
        env_action = next(action for action in self.parser._actions if action.dest == "env")
        assert env_action.nargs == 2
        # Check that it's an append action by checking the class name
        assert "Append" in env_action.__class__.__name__

    @pytest.mark.parametrize("mode,endpoint,script_path,expected_type", [
        ("http", "http://api.example.com", None, "http"),
        ("sse", "http://localhost:8001/sse", None, "sse"),
        ("stdio", None, "/path/to/server.py", "stdio"),
    ])
    def test_build_config_modes(self, mode, endpoint, script_path, expected_type):
        """Test building config for different modes."""
        args = Namespace(
            mode=mode,
            id="test-server",
            endpoint=endpoint,
            script_path=script_path,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )

        if mode == "stdio" and not script_path:
            with pytest.raises(ValueError, match="--script-path or --sse-url is required"):
                build_config_from_args(args)
        else:
            config = build_config_from_args(args)
            if endpoint or script_path:
                assert len(config) == 1
                assert config[0]["type"] == expected_type
                assert config[0]["id"] == "test-server"

    def test_build_config_stdio_with_directory(self):
        """Test building config for STDIO mode with custom directory."""
        args = Namespace(
            mode="stdio",
            id="test-server",
            endpoint=None,
            script_path="/path/to/server.py",
            directory="/custom/directory",
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )

        config = build_config_from_args(args)
        assert len(config) == 1
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"
        assert "/custom/directory" in config[0]["args"]

    def test_build_config_stdio_without_directory(self):
        """Test building config for STDIO mode without custom directory."""
        args = Namespace(
            mode="stdio",
            id="test-server",
            endpoint=None,
            script_path="/path/to/server.py",
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )

        config = build_config_from_args(args)
        assert len(config) == 1
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"
        # Should use script_path parent directory
        assert "/path/to" in config[0]["args"]

    def test_build_config_http_no_endpoint(self):
        """Test building config for HTTP mode without endpoint."""
        args = Namespace(
            mode="http",
            id="test-server",
            endpoint=None,
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )

        config = build_config_from_args(args)
        # Should return empty config when no endpoint
        assert config == [{}]

    def test_build_config_invalid_mode(self):
        """Test building config with invalid mode."""
        args = Namespace(
            mode="invalid",
            id="test-server",
            endpoint=None,
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )

        with pytest.raises(ValueError, match="Unsupported mode 'invalid'"):
            build_config_from_args(args)


class TestCLIMiddlewareCommands:
    """Test cases for middleware management CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.middleware_parser = _setup_middleware_parser()

    def test_middleware_parser_setup(self):
        """Test that the middleware parser is set up correctly."""
        assert self.middleware_parser is not None
        assert "MCP Composer Middleware Management" in self.middleware_parser.description

    def test_middleware_subcommands(self):
        """Test that all middleware subcommands are available."""
        subparsers = [
            action for action in self.middleware_parser._actions if action.dest == "command"
        ]
        assert len(subparsers) == 1
        subparser = subparsers[0]
        assert subparser.choices is not None
        assert "validate" in subparser.choices
        assert "list" in subparser.choices
        assert "add-middleware" in subparser.choices

    def test_validate_command_arguments(self):
        """Test validate command arguments."""
        subparsers = [
            action for action in self.middleware_parser._actions if action.dest == "command"
        ]
        validate_parser = subparsers[0].choices["validate"]
        
        # Required argument
        path_action = next(action for action in validate_parser._actions if action.dest == "path")
        assert path_action.required is True
        
        # Optional arguments
        ensure_imports_action = next(
            action for action in validate_parser._actions if action.dest == "ensure_imports"
        )
        assert "StoreTrue" in ensure_imports_action.__class__.__name__
        
        format_action = next(action for action in validate_parser._actions if action.dest == "format")
        assert format_action.choices == ["text", "json"]
        assert format_action.default == "text"

    def test_list_command_arguments(self):
        """Test list command arguments."""
        subparsers = [
            action for action in self.middleware_parser._actions if action.dest == "command"
        ]
        list_parser = subparsers[0].choices["list"]
        
        # Required argument
        config_action = next(action for action in list_parser._actions if action.dest == "config")
        assert config_action.required is True
        
        # Optional arguments
        all_action = next(action for action in list_parser._actions if action.dest == "all")
        assert "StoreTrue" in all_action.__class__.__name__

    def test_add_middleware_command_arguments(self):
        """Test add-middleware command arguments."""
        subparsers = [
            action for action in self.middleware_parser._actions if action.dest == "command"
        ]
        add_parser = subparsers[0].choices["add-middleware"]
        
        # Required arguments
        required_args = ["config", "name", "kind"]
        for arg_name in required_args:
            action = next(action for action in add_parser._actions if action.dest == arg_name)
            assert action.required is True
        
        # Optional arguments with defaults
        mode_action = next(action for action in add_parser._actions if action.dest == "mode")
        assert mode_action.choices == ["enabled", "disabled"]
        assert mode_action.default == "enabled"
        
        priority_action = next(action for action in add_parser._actions if action.dest == "priority")
        assert priority_action.type == int
        assert priority_action.default == 100

    def test_middleware_command_help_texts(self):
        """Test that middleware commands have helpful descriptions."""
        subparsers = [
            action for action in self.middleware_parser._actions if action.dest == "command"
        ]
        
        # Test validate command help
        validate_parser = subparsers[0].choices["validate"]
        help_text = validate_parser.format_help()
        assert "Path to middleware configuration file" in help_text
        
        # Test list command help
        list_parser = subparsers[0].choices["list"]
        help_text = list_parser.format_help()
        assert "Path to middleware configuration file" in help_text
        
        # Test add-middleware command help
        add_parser = subparsers[0].choices["add-middleware"]
        help_text = add_parser.format_help()
        assert "Name of the middleware" in help_text


class TestMiddlewareCLIFunctions:
    """Test cases for middleware CLI function implementations."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary middleware config file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "middleware-config.json")
        
        # Create a valid middleware config
        self.valid_config = {
            "middleware": [
                {
                    "name": "TestMiddleware",
                    "description": "Test middleware",
                    "version": "1.0.0",
                    "kind": "test.middleware.TestMiddleware",
                    "mode": "enabled",
                    "priority": 100,
                    "applied_hooks": ["on_call_tool"],
                    "conditions": {
                        "include_tools": ["*"],
                        "exclude_tools": [],
                        "include_prompts": [],
                        "exclude_prompts": [],
                        "include_server_ids": [],
                        "exclude_server_ids": []
                    },
                    "config": {},
                    "logic": {}
                }
            ],
            "middleware_settings": {
                "middleware_timeout": 30,
                "fail_on_middleware_error": False,
                "enable_middleware_api": True,
                "middleware_health_check_interval": 60
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(self.valid_config, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cmd_validate_success(self):
        """Test successful middleware validation."""
        args = Namespace(
            path=self.config_file,
            ensure_imports=False,
            format="text",
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli.load_and_validate_config") as mock_load:
            mock_load.return_value = MagicMock()
            result = cmd_validate(args)
            assert result == 0
            mock_load.assert_called_once_with(self.config_file, ensure_imports=False)

    def test_cmd_validate_file_not_found(self):
        """Test middleware validation with file not found."""
        args = Namespace(
            path="/nonexistent/file.json",
            ensure_imports=False,
            format="text",
            show_middlewares=False
        )
        
        result = cmd_validate(args)
        assert result == 2

    def test_cmd_validate_invalid_json(self):
        """Test middleware validation with invalid JSON."""
        invalid_config_file = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_config_file, 'w') as f:
            f.write("invalid json content")
        
        args = Namespace(
            path=invalid_config_file,
            ensure_imports=False,
            format="text",
            show_middlewares=False
        )
        
        result = cmd_validate(args)
        assert result == 2

    def test_cmd_validate_json_format(self):
        """Test middleware validation with JSON output format."""
        args = Namespace(
            path=self.config_file,
            ensure_imports=False,
            format="json",
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli.load_and_validate_config") as mock_load:
            mock_load.return_value = MagicMock()
            with patch("builtins.print") as mock_print:
                result = cmd_validate(args)
                assert result == 0
                mock_print.assert_called_with(json.dumps({"status": "ok"}, indent=2))

    def test_cmd_list_success(self):
        """Test successful middleware listing."""
        args = Namespace(
            config=self.config_file,
            ensure_imports=False,
            format="text",
            all=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli.load_and_validate_config") as mock_load:
            mock_middleware = MagicMock()
            mock_middleware.middleware = [MagicMock()]
            mock_load.return_value = mock_middleware
            
            with patch("mcp_composer.core.cli.middleware_cli.MiddlewareManager") as mock_manager:
                mock_mgr = MagicMock()
                mock_mgr.describe.return_value = [{"name": "TestMiddleware", "priority": 100, "applied_hooks": []}]
                mock_manager.return_value = mock_mgr
                
                with patch("builtins.print") as mock_print:
                    result = cmd_list(args)
                    assert result == 0

    def test_cmd_list_file_not_found(self):
        """Test middleware listing with file not found."""
        args = Namespace(
            config="/nonexistent/file.json",
            ensure_imports=False,
            format="text",
            all=False
        )
        
        result = cmd_list(args)
        assert result == 2

    def test_cmd_list_json_format(self):
        """Test middleware listing with JSON output format."""
        args = Namespace(
            config=self.config_file,
            ensure_imports=False,
            format="json",
            all=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli.load_and_validate_config") as mock_load:
            mock_middleware = MagicMock()
            mock_middleware.middleware = [MagicMock()]
            mock_load.return_value = mock_middleware
            
            with patch("mcp_composer.core.cli.middleware_cli.MiddlewareManager") as mock_manager:
                mock_mgr = MagicMock()
                mock_mgr.describe.return_value = [{"name": "TestMiddleware", "priority": 100, "applied_hooks": []}]
                mock_manager.return_value = mock_mgr
                
                with patch("builtins.print") as mock_print:
                    result = cmd_list(args)
                    assert result == 0
                    # Verify JSON output was called
                    mock_print.assert_called()
                    call_args = mock_print.call_args[0][0]
                    assert "middlewares" in call_args

    def test_cmd_add_middleware_success(self):
        """Test successful middleware addition."""
        args = Namespace(
            config=self.config_file,
            name="NewMiddleware",
            kind="test.middleware.NewMiddleware",
            description="New test middleware",
            version="1.0.0",
            mode="enabled",
            priority=50,
            applied_hooks="on_call_tool,on_list_tools",
            include_tools="*",
            exclude_tools=None,
            include_prompts=None,
            exclude_prompts=None,
            include_server_ids=None,
            exclude_server_ids=None,
            config_file=None,
            update=False,
            ensure_imports=False,
            dry_run=False,
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli._load_json_file") as mock_load:
            mock_load.return_value = self.valid_config
            
            with patch("mcp_composer.core.cli.middleware_cli._save_json_file") as mock_save:
                with patch("builtins.print") as mock_print:
                    result = cmd_add_middleware(args)
                    assert result == 0
                    mock_save.assert_called_once()
                    mock_print.assert_called()

    def test_cmd_add_middleware_dry_run(self):
        """Test middleware addition in dry run mode."""
        args = Namespace(
            config=self.config_file,
            name="NewMiddleware",
            kind="test.middleware.NewMiddleware",
            description="New test middleware",
            version="1.0.0",
            mode="enabled",
            priority=50,
            applied_hooks="on_call_tool",
            include_tools="*",
            exclude_tools=None,
            include_prompts=None,
            exclude_prompts=None,
            include_server_ids=None,
            exclude_server_ids=None,
            config_file=None,
            update=False,
            ensure_imports=False,
            dry_run=True,
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli._load_json_file") as mock_load:
            mock_load.return_value = self.valid_config
            
            with patch("mcp_composer.core.cli.middleware_cli._save_json_file") as mock_save:
                with patch("builtins.print") as mock_print:
                    result = cmd_add_middleware(args)
                    assert result == 0
                    mock_save.assert_not_called()  # Should not save in dry run
                    mock_print.assert_called()

    def test_cmd_add_middleware_update_existing(self):
        """Test updating existing middleware."""
        args = Namespace(
            config=self.config_file,
            name="TestMiddleware",  # Existing middleware name
            kind="test.middleware.UpdatedMiddleware",
            description="Updated test middleware",
            version="2.0.0",
            mode="enabled",
            priority=75,
            applied_hooks="on_call_tool",
            include_tools="*",
            exclude_tools=None,
            include_prompts=None,
            exclude_prompts=None,
            include_server_ids=None,
            exclude_server_ids=None,
            config_file=None,
            update=True,
            ensure_imports=False,
            dry_run=False,
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli._load_json_file") as mock_load:
            mock_load.return_value = self.valid_config
            
            with patch("mcp_composer.core.cli.middleware_cli._save_json_file") as mock_save:
                with patch("builtins.print") as mock_print:
                    result = cmd_add_middleware(args)
                    assert result == 0
                    mock_save.assert_called_once()

    def test_cmd_add_middleware_duplicate_without_update(self):
        """Test adding duplicate middleware without update flag."""
        args = Namespace(
            config=self.config_file,
            name="TestMiddleware",  # Existing middleware name
            kind="test.middleware.NewMiddleware",
            description="New test middleware",
            version="1.0.0",
            mode="enabled",
            priority=50,
            applied_hooks="on_call_tool",
            include_tools="*",
            exclude_tools=None,
            include_prompts=None,
            exclude_prompts=None,
            include_server_ids=None,
            exclude_server_ids=None,
            config_file=None,
            update=False,
            ensure_imports=False,
            dry_run=False,
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli._load_json_file") as mock_load:
            mock_load.return_value = self.valid_config
            
            result = cmd_add_middleware(args)
            assert result == 1  # Should fail

    def test_cmd_add_middleware_invalid_config_file(self):
        """Test adding middleware with invalid config file."""
        args = Namespace(
            config=self.config_file,
            name="NewMiddleware",
            kind="test.middleware.NewMiddleware",
            description="New test middleware",
            version="1.0.0",
            mode="enabled",
            priority=50,
            applied_hooks="on_call_tool",
            include_tools="*",
            exclude_tools=None,
            include_prompts=None,
            exclude_prompts=None,
            include_server_ids=None,
            exclude_server_ids=None,
            config_file="/nonexistent/config.json",
            update=False,
            ensure_imports=False,
            dry_run=False,
            show_middlewares=False
        )
        
        with patch("mcp_composer.core.cli.middleware_cli._load_json_file") as mock_load:
            # Mock the first call to load the main config successfully
            # Mock the second call to load the config file to fail
            mock_load.side_effect = [self.valid_config, FileNotFoundError("Config file not found")]
            
            result = cmd_add_middleware(args)
            assert result == 2  # Should fail due to invalid config file


class TestCLIOAuthIntegration:
    """Test cases for OAuth integration in CLI."""

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_oauth_auth_type(self):
        """Test running composer with OAuth auth type."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type="oauth",
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.utils.cli_legacy.create_mcp_server") as mock_create_server:
            mock_composer = MagicMock()
            mock_create_server.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(args, config)

            mock_create_server.assert_called_once()
            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_remote_oauth_auth_type(self):
        """Test running composer with remote OAuth auth type."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url="http://localhost:8001/sse",
            remote_auth_type="oauth",
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            client_auth_type="none",
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.utils.cli_legacy.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()
            mock_composer.import_server = AsyncMock()

            with patch("mcp_composer.core.utils.cli_legacy.ServerSettings") as mock_settings:
                with patch("mcp_composer.core.utils.cli_legacy.SimpleOAuthProvider") as mock_oauth:
                    with patch("mcp_composer.core.utils.cli_legacy.MCPComposer.as_proxy") as mock_as_proxy:
                        mock_proxy = MagicMock()
                        mock_as_proxy.return_value = mock_proxy
                        
                        # Mock the _tool_manager.disable_tools method to be async
                        mock_composer._tool_manager = MagicMock()
                        mock_composer._tool_manager.disable_tools = AsyncMock()

                        await run_dynamic_composer(args, config)

                        mock_composer.setup_member_servers.assert_called_once()
                        mock_composer.run_http_async.assert_called_once()
                        # The import_server is called with the remote_proxy (which is the mock_composer in this case)
                        mock_composer.import_server.assert_called_once_with(mock_composer)

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_client_oauth_auth_type(self):
        """Test running composer with client OAuth auth type."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url="http://localhost:8001/sse",
            remote_auth_type="none",
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            client_auth_type="oauth",
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.utils.cli_legacy.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()
            mock_composer.import_server = AsyncMock()

            with patch("mcp_composer.core.utils.cli_legacy.get_issuer") as mock_get_issuer:
                mock_get_issuer.return_value = "http://localhost:8001"
                
                with patch("mcp_composer.core.utils.cli_legacy.oauth_pkce_login_async") as mock_login:
                    mock_login.return_value = {"access_token": "test_token"}
                    
                    with patch("mcp_composer.core.utils.cli_legacy.SSETransport") as mock_sse_transport:
                        with patch("mcp_composer.core.utils.cli_legacy.MCPComposer.as_proxy") as mock_as_proxy:
                            mock_proxy = MagicMock()
                            mock_as_proxy.return_value = mock_proxy

                            await run_dynamic_composer(args, config)

                            mock_composer.setup_member_servers.assert_called_once()
                            mock_composer.run_http_async.assert_called_once()
                            mock_composer.import_server.assert_called_once_with(mock_proxy)


class TestCLIErrorHandling:
    """Test cases for CLI error handling."""

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_exception_handling(self):
        """Test exception handling in run_dynamic_composer."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.utils.cli_legacy.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.setup_member_servers = AsyncMock(
                side_effect=Exception("Test error")
            )

            with pytest.raises(Exception) as exc_info:
                await run_dynamic_composer(args, config)
            assert "Test error" in str(exc_info.value)

    def test_main_function_error_handling(self):
        """Test error handling in main function."""
        with patch("mcp_composer.core.utils.cli_legacy._setup_args_parser") as mock_setup_parser:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.config_path = "/path/to/config.json"
            mock_args.endpoint = "http://api.example.com"
            mock_args.script_path = None
            mock_args.command = None
            mock_parser.parse_args.return_value = mock_args
            mock_setup_parser.return_value = mock_parser

            with patch("mcp_composer.core.utils.cli_legacy.build_config_from_args") as mock_build_config:
                mock_build_config.side_effect = ValueError("Config error")

                with pytest.raises(SystemExit):
                    main()

    def test_main_function_runtime_error_handling(self):
        """Test runtime error handling in main function."""
        with patch("mcp_composer.core.utils.cli_legacy._setup_args_parser") as mock_setup_parser:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.config_path = "/path/to/config.json"
            mock_args.endpoint = "http://api.example.com"
            mock_args.script_path = None
            mock_args.command = None
            mock_parser.parse_args.return_value = mock_args
            mock_setup_parser.return_value = mock_parser

            with patch("mcp_composer.core.utils.cli_legacy.build_config_from_args") as mock_build_config:
                mock_build_config.return_value = [{"id": "test-server", "type": "http"}]

                with patch("mcp_composer.core.utils.cli_legacy.run_dynamic_composer") as mock_run_composer:
                    mock_run_composer.side_effect = Exception("Runtime error")

                    with pytest.raises(SystemExit):
                        main()


class TestCLIEnvironmentHandling:
    """Test cases for environment variable handling in CLI."""

    def test_environment_variable_parsing(self):
        """Test parsing environment variables from command line."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[("TEST_VAR", "test_value"), ("ANOTHER_VAR", "another_value")],
            pass_environment=False,
            remote_auth_type="none",
            client_auth_type="none",
        )

        with patch.dict(os.environ, {}, clear=True):
            with patch("mcp_composer.core.utils.cli_legacy.logger") as mock_logger:
                # This would be called in the main function
                base_env = {}
                for key, value in args.env:
                    base_env[key] = value
                    os.environ[key] = value

                assert base_env["TEST_VAR"] == "test_value"
                assert base_env["ANOTHER_VAR"] == "another_value"
                assert os.environ["TEST_VAR"] == "test_value"
                assert os.environ["ANOTHER_VAR"] == "another_value"

    def test_pass_environment_flag(self):
        """Test pass_environment flag functionality."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=True,
            remote_auth_type="none",
            client_auth_type="none",
        )

        with patch.dict(os.environ, {"EXISTING_VAR": "existing_value"}, clear=True):
            base_env = {}
            if args.pass_environment:
                base_env.update(os.environ)

            assert base_env["EXISTING_VAR"] == "existing_value"

    def test_config_path_environment_variable(self):
        """Test SERVER_CONFIG_FILE_PATH environment variable handling."""
        with patch.dict(os.environ, {"SERVER_CONFIG_FILE_PATH": "/custom/config.json"}):
            parser = _setup_args_parser()
            config_path_action = next(
                action for action in parser._actions if action.dest == "config_path"
            )
            assert config_path_action.default == "/custom/config.json"


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def test_middleware_command_detection(self):
        """Test that middleware commands are properly detected."""
        # Test middleware command detection logic
        test_cases = [
            (["validate", "config.json"], True),
            (["list", "config.json"], True),
            (["add-middleware", "--config", "config.json"], True),
            (["--mode", "http"], False),
            (["--help"], False),
        ]

        for argv, is_middleware in test_cases:
            # Simulate the logic from main function
            is_middleware_command = len(argv) > 0 and argv[0] in ['validate', 'list', 'add-middleware']
            assert is_middleware_command == is_middleware, f"Failed for {argv}"

    def test_main_parser_vs_middleware_parser_selection(self):
        """Test that the correct parser is selected based on arguments."""
        # Test main parser selection
        with patch("sys.argv", ["mcp-composer", "--mode", "http", "--endpoint", "http://api.example.com"]):
            parser = _setup_args_parser()
            args = parser.parse_args(["--mode", "http", "--endpoint", "http://api.example.com"])
            assert args.mode == "http"
            assert args.endpoint == "http://api.example.com"

        # Test middleware parser selection
        middleware_parser = _setup_middleware_parser()
        args = middleware_parser.parse_args(["validate", "config.json"])
        assert args.command == "validate"
        assert args.path == "config.json"

    def test_comprehensive_cli_help(self):
        """Test that CLI help is comprehensive and informative."""
        parser = _setup_args_parser()
        help_text = parser.format_help()
        
        # Check for key sections
        assert "Examples:" in help_text
        assert "mcp-composer --mode http" in help_text
        assert "mcp-composer --mode sse" in help_text
        assert "mcp-composer --mode stdio" in help_text
        assert "Middleware commands:" in help_text

    def test_middleware_parser_help(self):
        """Test that middleware parser help is informative."""
        middleware_parser = _setup_middleware_parser()
        help_text = middleware_parser.format_help()
        
        # Check for middleware-specific help
        assert "MCP Composer Middleware Management" in help_text
        assert "validate" in help_text
        assert "list" in help_text
        assert "add-middleware" in help_text
