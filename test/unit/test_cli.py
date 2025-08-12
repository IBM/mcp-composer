import pytest
import os
import sys
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from argparse import Namespace

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from mcp_composer.core.utils.cli import (
    _setup_args_parser,
    _add_arguments_to_parser,
    build_config_from_args,
    run_dynamic_composer,
    main
)


class TestCLI:
    """Test cases for CLI module."""

    def test_setup_args_parser(self):
        """Test setting up the argument parser."""
        parser = _setup_args_parser()

        assert parser is not None
        assert parser.description is not None

    def test_add_arguments_to_parser(self):
        """Test adding arguments to the parser."""
        parser = _setup_args_parser()

        # Check that key arguments are added
        help_text = parser.format_help()
        assert "--mode" in help_text
        assert "--host" in help_text
        assert "--port" in help_text
        assert "--id" in help_text
        assert "--endpoint" in help_text
        assert "--script_path" in help_text

    def test_build_config_from_args_http_mode(self):
        """Test building config from args in HTTP mode."""
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
            pass_environment=False
        )
        
        config = build_config_from_args(args)
        
        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "http"
        assert config[0]["endpoint"] == "http://api.example.com"

    def test_build_config_from_args_sse_mode(self):
        """Test building config from args in SSE mode."""
        args = Namespace(
            mode="sse",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://localhost:8001/sse",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "sse"
        assert config[0]["endpoint"] == "http://localhost:8001/sse"

    def test_build_config_from_args_stdio_mode(self):
        """Test building config from args in STDIO mode."""
        args = Namespace(
            mode="stdio",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path="/path/to/server.py",
            directory="/path/to",
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"

    def test_build_config_from_args_stdio_mode_no_script_path(self):
        """Test building config from args in STDIO mode without script_path."""
        args = Namespace(
            mode="stdio",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        with pytest.raises(ValueError, match="--script-path is required for mode 'stdio'"):
            build_config_from_args(args)

    def test_build_config_from_args_http_mode_no_endpoint(self):
        """Test building config from args in HTTP mode without endpoint."""
        args = Namespace(
            mode="http",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        # Should return empty config when no endpoint
        assert config == [{}]

    def test_build_config_from_args_sse_mode_no_endpoint(self):
        """Test building config from args in SSE mode without endpoint."""
        args = Namespace(
            mode="sse",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        # Should return empty config when no endpoint
        assert config == [{}]

    def test_build_config_from_args_invalid_mode(self):
        """Test building config from args with invalid mode."""
        args = Namespace(
            mode="invalid",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        with pytest.raises(ValueError, match="Unsupported mode 'invalid'"):
            build_config_from_args(args)

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_success(self):
        """Test running dynamic composer successfully."""
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
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        # Mock the entire MCPComposer class and its methods
        with patch('mcp_composer.core.utils.cli.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(args, config)

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_with_oauth(self):
        """Test running dynamic composer with OAuth auth type."""
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
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        # Mock the create_mcp_server function to return a mock composer
        with patch('mcp_composer.core.utils.cli.create_mcp_server') as mock_create_server:
            mock_composer = MagicMock()
            mock_create_server.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(args, config)

            mock_create_server.assert_called_once()
            mock_composer.setup_member_servers.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_exception(self):
        """Test running dynamic composer with exception."""
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
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch('mcp_composer.core.utils.cli.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.setup_member_servers = AsyncMock(side_effect=Exception("Test error"))

            with pytest.raises(Exception) as exc_info:
                await run_dynamic_composer(args, config)
            assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_stdio_mode(self):
        """Test running dynamic composer in STDIO mode."""
        args = Namespace(
            mode="stdio",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path="/path/to/server.py",
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "stdio", "command": "uv"}]

        with patch('mcp_composer.core.utils.cli.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_stdio_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(args, config)

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_stdio_async.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_sse_mode(self):
        """Test running dynamic composer in SSE mode."""
        args = Namespace(
            mode="sse",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint="http://localhost:8001/sse",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "sse", "endpoint": "http://localhost:8001/sse"}]

        with patch('mcp_composer.core.utils.cli.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_sse_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(args, config)

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_sse_async.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_with_sse_url(self):
        """Test running dynamic composer with SSE URL."""
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
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch('mcp_composer.core.utils.cli.MCPComposer') as mock_composer_class, \
             patch('mcp_composer.core.utils.cli.ProxyClient') as mock_proxy_client, \
             patch('mcp_composer.core.utils.cli.MCPComposer.as_proxy') as mock_as_proxy:

            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={})
            mock_composer.remove_tool = MagicMock()
            mock_composer.import_server = AsyncMock()

            mock_proxy = MagicMock()
            mock_as_proxy.return_value = mock_proxy

            await run_dynamic_composer(args, config)

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()
            mock_as_proxy.assert_called_once()
            mock_composer.import_server.assert_called_once_with(mock_proxy)

    @pytest.mark.asyncio
    @pytest.mark.timeout(5)  # 5 second timeout
    async def test_run_dynamic_composer_disable_composer_tools(self):
        """Test running dynamic composer with composer tools disabled."""
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
            disable_composer_tools=True,
            env=[],
            pass_environment=False
        )
        config = [{"id": "test-server", "type": "http", "endpoint": "http://api.example.com"}]

        with patch('mcp_composer.core.utils.cli.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run_http_async = AsyncMock()
            mock_composer.setup_member_servers = AsyncMock()
            mock_composer.get_tools = AsyncMock(return_value={"tool1": "desc1", "tool2": "desc2"})
            mock_composer.remove_tool = MagicMock()

            await run_dynamic_composer(args, config)

            mock_composer.setup_member_servers.assert_called_once()
            mock_composer.run_http_async.assert_called_once()
            mock_composer.get_tools.assert_called_once()
            assert mock_composer.remove_tool.call_count == 2

    @patch('mcp_composer.core.utils.cli._setup_args_parser')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    @patch('mcp_composer.core.utils.cli.run_dynamic_composer')
    def test_main_success(self, mock_run_composer, mock_build_config, mock_setup_parser):
        """Test main function success."""
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.config_path = "/path/to/config.json"
        mock_args.endpoint = "http://api.example.com"
        mock_args.script_path = None
        mock_parser.parse_args.return_value = mock_args
        mock_setup_parser.return_value = mock_parser

        # Mock config
        mock_config = [{"id": "test-server", "type": "http"}]
        mock_build_config.return_value = mock_config

        # Mock run_composer
        mock_run_composer.return_value = None

        # Test main function
        main()

        mock_build_config.assert_called_once()
        mock_run_composer.assert_called_once()

    @patch('mcp_composer.core.utils.cli._setup_args_parser')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    def test_main_build_config_error(self, mock_build_config, mock_setup_parser):
        """Test main function with build_config error."""
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.config_path = "/path/to/config.json"
        mock_args.endpoint = "http://api.example.com"
        mock_args.script_path = None
        mock_parser.parse_args.return_value = mock_args
        mock_setup_parser.return_value = mock_parser

        # Mock build_config to raise exception
        mock_build_config.side_effect = ValueError("Config error")

        # Test main function
        with pytest.raises(SystemExit):
            main()

    @patch('mcp_composer.core.utils.cli._setup_args_parser')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    @patch('mcp_composer.core.utils.cli.run_dynamic_composer')
    def test_main_run_composer_error(self, mock_run_composer, mock_build_config, mock_setup_parser):
        """Test main function with run_composer error."""
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.config_path = "/path/to/config.json"
        mock_args.endpoint = "http://api.example.com"
        mock_args.script_path = None
        mock_parser.parse_args.return_value = mock_args
        mock_setup_parser.return_value = mock_parser

        # Mock config
        mock_config = [{"id": "test-server", "type": "http"}]
        mock_build_config.return_value = mock_config

        # Mock run_composer to raise exception
        mock_run_composer.side_effect = Exception("Runtime error")

        # Test main function
        with pytest.raises(SystemExit):
            main()

    def test_build_config_from_args_default_values(self):
        """Test building config from args with default values."""
        args = Namespace(
            mode="stdio",
            host="0.0.0.0",
            port=9000,
            id="mcp-local",
            endpoint=None,
            script_path="/path/to/server.py",
            directory=None,
            config_path="",
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        assert len(config) == 1
        assert config[0]["id"] == "mcp-local"
        assert config[0]["type"] == "stdio"

    def test_build_config_from_args_environment_variables(self):
        """Test building config from args with environment variables."""
        args = Namespace(
            mode="http",
            host=None,
            port=None,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        with patch.dict(os.environ, {
            'MCP_COMPOSER_HOST': 'custom_host',
            'MCP_COMPOSER_PORT': '9000'
        }):
            config = build_config_from_args(args)

            assert len(config) == 1
            assert config[0]["endpoint"] == "http://api.example.com"

    def test_build_config_from_args_priority_order(self):
        """Test building config from args with priority order (args > env > defaults)."""
        args = Namespace(
            mode="http",
            host="arg_host",
            port=7000,
            id="test-server",
            endpoint="http://api.example.com",
            script_path=None,
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        with patch.dict(os.environ, {
            'MCP_COMPOSER_HOST': 'env_host',
            'MCP_COMPOSER_PORT': '8000'
        }):
            config = build_config_from_args(args)

            assert len(config) == 1
            assert config[0]["endpoint"] == "http://api.example.com"

    def test_build_config_from_args_stdio_with_directory(self):
        """Test building config from args in STDIO mode with custom directory."""
        args = Namespace(
            mode="stdio",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path="/path/to/server.py",
            directory="/custom/directory",
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"
        assert "/custom/directory" in config[0]["args"]

    def test_build_config_from_args_stdio_without_directory(self):
        """Test building config from args in STDIO mode without custom directory."""
        args = Namespace(
            mode="stdio",
            host="localhost",
            port=8080,
            id="test-server",
            endpoint=None,
            script_path="/path/to/server.py",
            directory=None,
            config_path=None,
            auth_type=None,
            sse_url=None,
            disable_composer_tools=False,
            env=[],
            pass_environment=False
        )

        config = build_config_from_args(args)

        assert len(config) == 1
        assert config[0]["id"] == "test-server"
        assert config[0]["type"] == "stdio"
        assert config[0]["command"] == "uv"
        # Should use script_path parent directory
        assert "/path/to" in config[0]["args"] 