"""
Test cases for the new Typer-based CLI implementation.

This module tests the modern CLI structure and ensures all commands work correctly.
"""

import pytest
import os
import sys
import tempfile
import json
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

# Add the src directory to the path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

from mcp_composer.core.cli.cli_typer import (
    build_config_from_args,
    run_dynamic_composer,
    app,
)
from mcp_composer.core.cli.commands.middleware_commands import app as middleware_app
from mcp_composer.core.cli.commands.composer_commands import app as composer_app


class TestTyperCLIStructure:
    """Test the overall CLI structure and command registration."""

    def test_app_creation(self):
        """Test that the main app is created correctly."""
        assert app is not None
        assert app.info.name == "mcp-composer"
        assert "MCP Composer" in app.info.help

    def test_command_registration(self):
        """Test that all command groups are registered."""
        # Check that main commands are registered
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "run" in command_names
        assert "version" in command_names
        assert "info" in command_names
        
        # Check that subcommand groups are registered (they might be in a different structure)
        # Typer subcommands are handled differently, so we'll test them separately

    def test_middleware_commands_registration(self):
        """Test that middleware commands are properly registered."""
        middleware_commands = [cmd.name for cmd in middleware_app.registered_commands]
        assert "validate" in middleware_commands
        assert "list" in middleware_commands
        assert "add" in middleware_commands
        assert "remove" in middleware_commands
        assert "init" in middleware_commands

    def test_composer_commands_registration(self):
        """Test that composer commands are properly registered."""
        composer_commands = [cmd.name for cmd in composer_app.registered_commands]
        assert "start" in composer_commands
        assert "stop" in composer_commands
        assert "status" in composer_commands
        assert "logs" in composer_commands
        assert "restart" in composer_commands


class TestBuildConfigFromArgs:
    """Test the build_config_from_args function."""

    def test_build_config_http_mode(self):
        """Test building config for HTTP mode."""
        config = build_config_from_args(
            mode="http",
            endpoint="http://api.example.com",
            id="test-server"
        )
        
        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "http"
        assert config[0]["endpoint"] == "http://api.example.com"

    def test_build_config_sse_mode(self):
        """Test building config for SSE mode."""
        config = build_config_from_args(
            mode="sse",
            endpoint="http://localhost:8001/sse",
            id="test-server"
        )
        
        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "sse"
        assert config[0]["endpoint"] == "http://localhost:8001/sse"

    def test_build_config_stdio_mode(self):
        """Test building config for STDIO mode."""
        config = build_config_from_args(
            mode="stdio",
            script_path="/path/to/server.py",
            id="test-server"
        )
        
        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"

    def test_build_config_stdio_with_directory(self):
        """Test building config for STDIO mode with custom directory."""
        config = build_config_from_args(
            mode="stdio",
            script_path="/path/to/server.py",
            directory="/custom/directory",
            id="test-server"
        )
        
        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"
        assert "/custom/directory" in config[0]["args"]

    def test_build_config_http_no_endpoint(self):
        """Test building config for HTTP mode without endpoint."""
        config = build_config_from_args(
            mode="http",
            id="test-server"
        )
        
        # Should return empty config when no endpoint
        assert config == [{}]

    def test_build_config_invalid_mode(self):
        """Test building config with invalid mode."""
        with pytest.raises(Exception):  # Typer will raise an exception
            build_config_from_args(
                mode="invalid",
                id="test-server"
            )


class TestRunDynamicComposer:
    """Test the run_dynamic_composer function."""

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_basic(self):
        """Test running composer with basic configuration."""
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(
                mode="http",
                config=config,
                host="localhost",
                port=8080
            )

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_oauth(self):
        """Test running composer with OAuth authentication."""
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.cli.cli_typer.create_mcp_server") as mock_create_server:
            mock_composer = MagicMock()
            mock_create_server.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(
                mode="http",
                config=config,
                auth_type="oauth",
                host="localhost",
                port=8080
            )

            mock_create_server.assert_called_once()
            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_disable_tools(self):
        """Test running composer with disabled composer tools."""
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(
                return_value={"tool1": "desc1", "tool2": "desc2"}
            )
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(
                mode="http",
                config=config,
                disable_composer_tools=True,
                host="localhost",
                port=8080
            )

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()
            mock_composer.get_tools.assert_called_once()
            assert mock_composer.remove_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_stdio_mode(self):
        """Test running composer in STDIO mode."""
        config = [{"id": "test-server", "type": "stdio", "command": "uv"}]

        with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_stdio_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(
                mode="stdio",
                config=config
            )

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_stdio_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_sse_mode(self):
        """Test running composer in SSE mode."""
        config = [{"id": "test-server", "type": "sse", "endpoint": "http://localhost:8001/sse"}]

        with patch("mcp_composer.core.cli.cli_typer.MCPComposer") as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_sse_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(
                mode="sse",
                config=config,
                host="localhost",
                port=8001
            )

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_sse_async.assert_called_once()


class TestMiddlewareCommands:
    """Test middleware command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
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

    def test_middleware_validate_command(self):
        """Test middleware validate command."""
        from mcp_composer.core.cli.commands.middleware_commands import validate_middleware
        
        with patch("mcp_composer.core.cli.commands.middleware_commands.load_and_validate_config") as mock_load:
            mock_load.return_value = MagicMock()
            
            # Test successful validation
            validate_middleware(
                path=self.config_file,
                ensure_imports=False,
                format="text",
                show_middlewares=False
            )
            
            mock_load.assert_called_once_with(self.config_file, ensure_imports=False)

    def test_middleware_list_command(self):
        """Test middleware list command."""
        from mcp_composer.core.cli.commands.middleware_commands import list_middlewares
        
        with patch("mcp_composer.core.cli.commands.middleware_commands.load_and_validate_config") as mock_load:
            mock_middleware = MagicMock()
            mock_middleware.middleware = [MagicMock()]
            mock_load.return_value = mock_middleware
            
            with patch("mcp_composer.core.cli.commands.middleware_commands.MiddlewareManager") as mock_manager:
                mock_mgr = MagicMock()
                mock_mgr.describe.return_value = [{"name": "TestMiddleware", "priority": 100, "applied_hooks": []}]
                mock_manager.return_value = mock_mgr
                
                list_middlewares(
                    config=self.config_file,
                    ensure_imports=False,
                    format="text",
                    all=False
                )

    def test_middleware_add_command(self):
        """Test middleware add command."""
        from mcp_composer.core.cli.commands.middleware_commands import add_middleware
        
        with patch("mcp_composer.core.cli.commands.middleware_commands._load_json_file") as mock_load:
            mock_load.return_value = self.valid_config
            
            with patch("mcp_composer.core.cli.commands.middleware_commands._save_json_file") as mock_save:
                add_middleware(
                    config=self.config_file,
                    name="NewMiddleware",
                    kind="test.middleware.NewMiddleware",
                    description="New test middleware",
                    version="1.0.0",
                    mode="enabled",
                    priority=50,
                    applied_hooks="on_call_tool",
                    include_tools=None,
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
                
                mock_save.assert_called_once()

    def test_middleware_init_command(self):
        """Test middleware init command."""
        from mcp_composer.core.cli.commands.middleware_commands import init_middleware_config
        
        new_config_file = os.path.join(self.temp_dir, "new-config.json")
        
        with patch("mcp_composer.core.cli.commands.middleware_commands._save_json_file") as mock_save:
            init_middleware_config(
                config=new_config_file,
                force=False
            )
            
            mock_save.assert_called_once()


class TestComposerCommands:
    """Test composer command functionality."""

    def test_composer_start_command_structure(self):
        """Test that composer start command has correct structure."""
        from mcp_composer.core.cli.commands.composer_commands import start_composer
        
        # This is a basic test to ensure the function exists and can be called
        # In a real test, we would mock the dependencies and test the actual functionality
        assert start_composer is not None

    def test_composer_stop_command_structure(self):
        """Test that composer stop command has correct structure."""
        from mcp_composer.core.cli.commands.composer_commands import stop_composer
        
        assert stop_composer is not None

    def test_composer_status_command_structure(self):
        """Test that composer status command has correct structure."""
        from mcp_composer.core.cli.commands.composer_commands import status_composer
        
        assert status_composer is not None

    def test_composer_logs_command_structure(self):
        """Test that composer logs command has correct structure."""
        from mcp_composer.core.cli.commands.composer_commands import logs_composer
        
        assert logs_composer is not None

    def test_composer_restart_command_structure(self):
        """Test that composer restart command has correct structure."""
        from mcp_composer.core.cli.commands.composer_commands import restart_composer
        
        assert restart_composer is not None


class TestCLIIntegration:
    """Integration tests for the Typer CLI."""

    def test_cli_help_output(self):
        """Test that CLI help is comprehensive."""
        # This would require running the actual CLI and capturing output
        # For now, we just test that the app structure is correct
        assert app.info.help is not None
        assert "MCP Composer" in app.info.help

    def test_command_help_availability(self):
        """Test that all commands have help available."""
        # Test main commands
        main_commands = [cmd for cmd in app.registered_commands if not hasattr(cmd, 'registered_commands')]
        for cmd in main_commands:
            assert cmd.help is not None or cmd.callback.__doc__ is not None
        
        # Test middleware commands
        middleware_commands = [cmd for cmd in middleware_app.registered_commands]
        for cmd in middleware_commands:
            assert cmd.help is not None or cmd.callback.__doc__ is not None
        
        # Test composer commands
        composer_commands = [cmd for cmd in composer_app.registered_commands]
        for cmd in composer_commands:
            assert cmd.help is not None or cmd.callback.__doc__ is not None

    def test_typer_app_configuration(self):
        """Test that Typer apps are configured correctly."""
        # Test main app
        assert app.info.name == "mcp-composer"
        assert app.info.no_args_is_help is True
        
        # Test middleware app
        assert middleware_app.info.name == "middleware"
        
        # Test composer app
        assert composer_app.info.name == "composer"
