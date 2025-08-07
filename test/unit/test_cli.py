import pytest
import os
import sys
from unittest.mock import MagicMock, patch, mock_open
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
        assert parser.prog == "mcp-composer"
        assert parser.description is not None

    def test_add_arguments_to_parser(self):
        """Test adding arguments to the parser."""
        parser = _setup_args_parser()
        _add_arguments_to_parser(parser)
        
        # Check that key arguments are added
        help_text = parser.format_help()
        assert "--config" in help_text
        assert "--mode" in help_text
        assert "--host" in help_text
        assert "--port" in help_text

    def test_build_config_from_args_http_mode(self):
        """Test building config from args in HTTP mode."""
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        config = build_config_from_args(args)
        
        assert config["mode"] == "http"
        assert config["host"] == "localhost"
        assert config["port"] == 8080

    def test_build_config_from_args_sse_mode(self):
        """Test building config from args in SSE mode."""
        args = Namespace(
            config=None,
            mode="sse",
            host="localhost",
            port=8080,
            sse=True,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        config = build_config_from_args(args)
        
        assert config["mode"] == "sse"
        assert config["host"] == "localhost"
        assert config["port"] == 8080

    def test_build_config_from_args_stdio_mode(self):
        """Test building config from args in STDIO mode."""
        args = Namespace(
            config=None,
            mode="stdio",
            host="localhost",
            port=8080,
            sse=False,
            stdio=True,
            env_file=None,
            config_file=None
        )
        
        config = build_config_from_args(args)
        
        assert config["mode"] == "stdio"

    def test_build_config_from_args_with_config_file(self):
        """Test building config from args with config file."""
        mock_config_data = '[{"id": "test_server", "type": "http"}]'
        
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file=None,
            config_file="test_config.json"
        )
        
        with patch('builtins.open') as mock_file:
            mock_file.return_value.__enter__.return_value.read.return_value = mock_config_data
            
            config = build_config_from_args(args)
            
            assert config["mode"] == "http"
            assert "config" in config
            assert len(config["config"]) == 1
            assert config["config"][0]["id"] == "test_server"

    def test_build_config_from_args_with_env_file(self):
        """Test building config from args with environment file."""
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file="test.env",
            config_file=None
        )
        
        with patch('dotenv.load_dotenv') as mock_load_dotenv:
            config = build_config_from_args(args)
            
            assert config["mode"] == "http"
            mock_load_dotenv.assert_called_once_with("test.env")

    def test_build_config_from_args_with_config_list(self):
        """Test building config from args with config list."""
        args = Namespace(
            config=['{"id": "test_server", "type": "http"}'],
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        config = build_config_from_args(args)
        
        assert config["mode"] == "http"
        assert "config" in config
        assert len(config["config"]) == 1
        assert config["config"][0]["id"] == "test_server"

    def test_build_config_from_args_with_multiple_configs(self):
        """Test building config from args with multiple configs."""
        args = Namespace(
            config=[
                '{"id": "server1", "type": "http"}',
                '{"id": "server2", "type": "stdio"}'
            ],
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        config = build_config_from_args(args)
        
        assert config["mode"] == "http"
        assert "config" in config
        assert len(config["config"]) == 2
        assert config["config"][0]["id"] == "server1"
        assert config["config"][1]["id"] == "server2"

    def test_build_config_from_args_invalid_json(self):
        """Test building config from args with invalid JSON."""
        args = Namespace(
            config=['{"id": "test_server", "type": "http"'],  # Invalid JSON
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        with pytest.raises(ValueError) as exc_info:
            build_config_from_args(args)
        assert "Invalid JSON" in str(exc_info.value)

    def test_build_config_from_args_file_not_found(self):
        """Test building config from args with non-existent file."""
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port=8080,
            sse=False,
            stdio=False,
            env_file=None,
            config_file="nonexistent.json"
        )
        
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(FileNotFoundError) as exc_info:
                build_config_from_args(args)
        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_success(self):
        """Test running dynamic composer successfully."""
        config = {
            "mode": "http",
            "host": "localhost",
            "port": 8080
        }
        
        with patch('mcp_composer.core.composer.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run = MagicMock()
            
            await run_dynamic_composer(config)
            
            mock_composer_class.assert_called_once()
            mock_composer.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_with_config(self):
        """Test running dynamic composer with server config."""
        config = {
            "mode": "http",
            "host": "localhost",
            "port": 8080,
            "config": [{"id": "test_server", "type": "http"}]
        }
        
        with patch('mcp_composer.core.composer.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run = MagicMock()
            
            await run_dynamic_composer(config)
            
            mock_composer_class.assert_called_once_with(
                "composer",
                config=[{"id": "test_server", "type": "http"}]
            )
            mock_composer.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dynamic_composer_exception(self):
        """Test running dynamic composer with exception."""
        config = {
            "mode": "http",
            "host": "localhost",
            "port": 8080
        }
        
        with patch('mcp_composer.core.composer.MCPComposer') as mock_composer_class:
            mock_composer = MagicMock()
            mock_composer_class.return_value = mock_composer
            mock_composer.run.side_effect = Exception("Test error")
            
            with pytest.raises(Exception) as exc_info:
                await run_dynamic_composer(config)
            assert "Test error" in str(exc_info.value)

    @patch('mcp_composer.core.utils.cli._setup_args_parser')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    @patch('mcp_composer.core.utils.cli.run_dynamic_composer')
    def test_main_success(self, mock_run_composer, mock_build_config, mock_setup_parser):
        """Test main function success."""
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_setup_parser.return_value = mock_parser
        
        # Mock config
        mock_config = {"mode": "http", "host": "localhost", "port": 8080}
        mock_build_config.return_value = mock_config
        
        # Mock run_composer
        mock_run_composer.return_value = None
        
        # Test main function
        main()
        
        mock_setup_parser.assert_called_once()
        mock_parser.parse_args.assert_called_once()
        mock_build_config.assert_called_once_with(mock_args)
        mock_run_composer.assert_called_once_with(mock_config)

    @patch('mcp_composer.core.utils.cli._setup_args_parser')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    def test_main_build_config_error(self, mock_build_config, mock_setup_parser):
        """Test main function with build_config error."""
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_setup_parser.return_value = mock_parser
        
        # Mock build_config to raise exception
        mock_build_config.side_effect = ValueError("Config error")
        
        # Test main function
        with pytest.raises(ValueError) as exc_info:
            main()
        assert "Config error" in str(exc_info.value)

    @patch('mcp_composer.core.utils.cli._setup_args_parser')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    @patch('mcp_composer.core.utils.cli.run_dynamic_composer')
    def test_main_run_composer_error(self, mock_run_composer, mock_build_config, mock_setup_parser):
        """Test main function with run_composer error."""
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_setup_parser.return_value = mock_parser
        
        # Mock config
        mock_config = {"mode": "http", "host": "localhost", "port": 8080}
        mock_build_config.return_value = mock_config
        
        # Mock run_composer to raise exception
        mock_run_composer.side_effect = Exception("Runtime error")
        
        # Test main function
        with pytest.raises(Exception) as exc_info:
            main()
        assert "Runtime error" in str(exc_info.value)

    def test_build_config_from_args_default_values(self):
        """Test building config from args with default values."""
        args = Namespace(
            config=None,
            mode="http",
            host=None,
            port=None,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        config = build_config_from_args(args)
        
        assert config["mode"] == "http"
        assert config["host"] == "localhost"  # Default value
        assert config["port"] == 8000  # Default value

    def test_build_config_from_args_environment_variables(self):
        """Test building config from args with environment variables."""
        args = Namespace(
            config=None,
            mode="http",
            host=None,
            port=None,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        with patch.dict(os.environ, {
            'MCP_COMPOSER_HOST': 'custom_host',
            'MCP_COMPOSER_PORT': '9000'
        }):
            config = build_config_from_args(args)
            
            assert config["mode"] == "http"
            assert config["host"] == "custom_host"
            assert config["port"] == 9000

    def test_build_config_from_args_priority_order(self):
        """Test building config from args with priority order (args > env > defaults)."""
        args = Namespace(
            config=None,
            mode="http",
            host="arg_host",
            port=7000,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        with patch.dict(os.environ, {
            'MCP_COMPOSER_HOST': 'env_host',
            'MCP_COMPOSER_PORT': '8000'
        }):
            config = build_config_from_args(args)
            
            # Args should take priority over environment variables
            assert config["host"] == "arg_host"
            assert config["port"] == 7000

    def test_build_config_from_args_invalid_port(self):
        """Test building config from args with invalid port."""
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port="invalid_port",
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        with pytest.raises(ValueError) as exc_info:
            build_config_from_args(args)
        assert "Invalid port" in str(exc_info.value)

    def test_build_config_from_args_port_out_of_range(self):
        """Test building config from args with port out of range."""
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port=70000,  # Out of range
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        with pytest.raises(ValueError) as exc_info:
            build_config_from_args(args)
        assert "Port must be between 1 and 65535" in str(exc_info.value)

    def test_build_config_from_args_negative_port(self):
        """Test building config from args with negative port."""
        args = Namespace(
            config=None,
            mode="http",
            host="localhost",
            port=-1,
            sse=False,
            stdio=False,
            env_file=None,
            config_file=None
        )
        
        with pytest.raises(ValueError) as exc_info:
            build_config_from_args(args)
        assert "Port must be between 1 and 65535" in str(exc_info.value) 