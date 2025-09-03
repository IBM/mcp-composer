"""Test module for __main__.py"""

import pytest
from unittest.mock import patch, MagicMock
from mcp_composer.__main__ import main


class TestMainModule:
    """Test cases for the main module"""

    @patch('mcp_composer.core.utils.cli.run_dynamic_composer')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_module_execution(self, mock_parse_args, mock_build_config, mock_run_composer):
        """Test that main function is called when module is executed"""
        # Mock the parsed arguments
        mock_args = MagicMock()
        mock_args.command = None  # Ensure no middleware command is specified
        mock_args.config_path = None
        mock_args.env = []
        mock_args.pass_environment = False
        mock_args.endpoint = "test-endpoint"  # Provide an endpoint so build_config_from_args is called
        mock_args.script_path = None
        mock_args.mode = "stdio"  # Add mode attribute
        mock_args.auth_type = "none"  # Add auth_type attribute
        mock_args.disable_composer_tools = False  # Add disable_composer_tools attribute
        mock_args.sse_url = None  # Add sse_url attribute
        mock_args.host = "localhost"  # Add host attribute
        mock_args.port = 8080  # Add port attribute
        mock_parse_args.return_value = mock_args
        
        # Mock the config building
        mock_build_config.return_value = []
        
        # Test the main function directly
        main()
        
        # Verify that the functions were called
        mock_parse_args.assert_called_once()
        mock_build_config.assert_called_once_with(mock_args)
        mock_run_composer.assert_called_once()

    def test_main_function_exists(self):
        """Test that main function exists and is callable"""
        assert callable(main)

    @patch('mcp_composer.core.utils.cli.run_dynamic_composer')
    @patch('mcp_composer.core.utils.cli.build_config_from_args')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_module_as_script(self, mock_parse_args, mock_build_config, mock_run_composer):
        """Test that main function is called when module is run as script"""
        # Mock the parsed arguments
        mock_args = MagicMock()
        mock_args.command = None  # Ensure no middleware command is specified
        mock_args.config_path = None
        mock_args.env = []
        mock_args.pass_environment = False
        mock_args.endpoint = "test-endpoint"  # Provide an endpoint so build_config_from_args is called
        mock_args.script_path = None
        mock_args.mode = "stdio"  # Add mode attribute
        mock_args.auth_type = "none"  # Add auth_type attribute
        mock_args.disable_composer_tools = False  # Add disable_composer_tools attribute
        mock_args.sse_url = None  # Add sse_url attribute
        mock_args.host = "localhost"  # Add host attribute
        mock_args.port = 8080  # Add port attribute
        mock_parse_args.return_value = mock_args
        
        # Mock the config building
        mock_build_config.return_value = []
        
        # Test the main function directly (which is what __main__.py calls)
        # This simulates the actual execution path when the module is run as a script
        main()
        
        # Verify that the functions were called
        mock_parse_args.assert_called_once()
        mock_build_config.assert_called_once_with(mock_args)
        mock_run_composer.assert_called_once()
        
        # Also verify the import structure is correct
        import mcp_composer.__main__
        assert hasattr(mcp_composer.__main__, 'main')
        assert callable(mcp_composer.__main__.main)
        
        # Verify that the main function is the same as the one from cli
        from mcp_composer.core.utils.cli import main as cli_main
        assert mcp_composer.__main__.main is cli_main 