"""
Main entry point for the modern Typer-based MCP Composer CLI.

This module provides the main entry point that can be used to replace the old argparse-based CLI.
"""

import sys
from pathlib import Path

# Add the src directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import after path manipulation to ensure module can be found
from mcp_composer.core.cli.cli_typer import main  # pylint: disable=wrong-import-position

if __name__ == "__main__":
    main()
