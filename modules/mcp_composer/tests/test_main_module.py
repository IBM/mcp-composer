"""Test module for __main__.py"""

import pytest
from unittest.mock import patch, MagicMock
from mcp_composer.__main__ import main


class TestMainModule:
    """Test cases for the main module"""

    @patch("mcp_composer.core.cli.cli_typer.run_dynamic_composer")
    @patch("mcp_composer.core.cli.cli_typer.build_config_from_args")
    @patch("sys.argv", ["mcp-composer", "run", "--mode", "http", "--endpoint", "test-endpoint"])
    def test_main_module_execution(
        self, mock_build_config, mock_run_composer
    ):
        """Test that main function is called when module is executed"""
        # Mock the config building
        mock_build_config.return_value = []
        
        # Test the main function directly - catch SystemExit from Typer
        try:
            main()
        except SystemExit:
            pass  # Expected when Typer exits

        # Verify that the functions were called
        mock_build_config.assert_called_once()
        mock_run_composer.assert_called_once()

    def test_main_function_exists(self):
        """Test that main function exists and is callable"""
        assert callable(main)

    @patch("mcp_composer.core.cli.cli_typer.run_dynamic_composer")
    @patch("mcp_composer.core.cli.cli_typer.build_config_from_args")
    @patch("sys.argv", ["mcp-composer", "run", "--mode", "http", "--endpoint", "test-endpoint"])
    def test_main_module_as_script(
        self, mock_build_config, mock_run_composer
    ):
        """Test that main function is called when module is run as script"""
        # Mock the config building
        mock_build_config.return_value = []
        
        # Test the main function directly (which is what __main__.py calls)
        # This simulates the actual execution path when the module is run as a script
        try:
            main()
        except SystemExit:
            pass  # Expected when Typer exits

        # Verify that the functions were called
        mock_build_config.assert_called_once()
        mock_run_composer.assert_called_once()

        # Also verify the import structure is correct
        import mcp_composer.__main__

        assert hasattr(mcp_composer.__main__, "main")
        assert callable(mcp_composer.__main__.main)

        # Verify that the main function is the same as the one from cli
        from mcp_composer.core.cli.cli_typer import main as cli_main

        assert mcp_composer.__main__.main is cli_main
