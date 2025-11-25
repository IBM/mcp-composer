"""CLI commands for unified configuration management."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from mcp_composer.core.config.config_loader import ConfigManager
from mcp_composer.core.config.unified_config import ConfigSection
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def cmd_validate_config(args: argparse.Namespace) -> int:
    """Validate a configuration file."""
    try:
        config_manager = ConfigManager()
        is_valid = config_manager.validate_config_file(args.configfilepath)

        if is_valid:
            print(f"✅ Configuration file '{args.configfilepath}' is valid")
            return 0

        print(f"❌ Configuration file '{args.configfilepath}' is invalid")
        return 1

    except Exception as e:
        print(f"❌ Error validating configuration: {e}")
        return 1


def cmd_show_config(args: argparse.Namespace) -> int:
    """Show configuration file contents in a formatted way."""
    try:
        config_manager = ConfigManager()
        config = config_manager.loader.load_from_file(args.configfilepath)

        # Convert to dict for JSON serialization
        config_dict = config.model_dump()

        if args.section:
            if args.section == "servers" and config_dict.get("servers"):
                print("=== SERVERS ===")
                for server in config_dict["servers"]:
                    print(f"ID: {server['id']}")
                    print(f"Type: {server['type']}")
                    if server.get('endpoint'):
                        print(f"Endpoint: {server['endpoint']}")
                    print("---")
            elif args.section == "middleware" and config_dict.get("middleware"):
                print("=== MIDDLEWARE ===")
                for mw in config_dict["middleware"]:
                    print(f"Name: {mw['name']}")
                    print(f"Kind: {mw['kind']}")
                    print(f"Mode: {mw['mode']}")
                    print(f"Priority: {mw['priority']}")
                    print("---")
            elif args.section == "prompts" and config_dict.get("prompts"):
                print("=== PROMPTS ===")
                for prompt in config_dict["prompts"]:
                    print(f"Name: {prompt['name']}")
                    print(f"Description: {prompt['description']}")
                    print(f"Template: {prompt['template']}")
                    print("---")
            elif args.section == "tools" and config_dict.get("tools"):
                print("=== TOOLS ===")
                for tool_name, tool_config in config_dict["tools"].items():
                    print(f"Name: {tool_name}")
                    print(f"Type: {'OpenAPI' if tool_config.get('openapi') else 'Custom'}")
                    print("---")
            else:
                print(f"No {args.section} section found in configuration")
                return 1
        else:
            # Show all sections
            print(json.dumps(config_dict, indent=2))

        return 0

    except Exception as e:
        print(f"❌ Error showing configuration: {e}")
        return 1


async def cmd_apply_config(args: argparse.Namespace) -> int:
    """Apply configuration to MCP Composer."""
    try:
        # Parse sections to apply
        sections = None
        if args.config:
            if args.config == "all":
                sections = None  # Apply all sections
            else:
                try:
                    sections = [ConfigSection(args.config)]
                except ValueError:
                    print(f"❌ Invalid config section: {args.config}")
                    print(f"Valid sections: {', '.join([s.value for s in ConfigSection])}")
                    return 1

        # Create a mock composer for now (in real implementation, this would be passed in)
        config_manager = ConfigManager()

        # Load and apply configuration
        results = await config_manager.load_and_apply(args.configfilepath, sections)

        # Print results
        print("=== CONFIGURATION APPLIED ===")
        for section, result in results.items():
            print(f"\n{section.upper()}:")
            print(f"  Total: {result.get('total', 0)}")
            print(f"  Registered: {len(result.get('registered', []))}")
            print(f"  Failed: {len(result.get('failed', []))}")

            if result.get('failed'):
                print("  Failures:")
                for failure in result['failed']:
                    print(f"    - {failure}")

        return 0

    except Exception as e:
        print(f"❌ Error applying configuration: {e}")
        return 1


def cmd_apply_config_sync(args: argparse.Namespace) -> int:
    """Synchronous wrapper for apply_config command."""
    return asyncio.run(cmd_apply_config(args))


def add_config_commands(parser: argparse.ArgumentParser) -> None:
    """Add unified configuration commands to the argument parser."""
    subparsers = parser.add_subparsers(dest='config_command', help='Configuration management commands')

    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate a configuration file'
    )
    validate_parser.add_argument(
        'configfilepath',
        help='Path to the configuration file to validate'
    )

    # Show command
    show_parser = subparsers.add_parser(
        'show',
        help='Show configuration file contents'
    )
    show_parser.add_argument(
        'configfilepath',
        help='Path to the configuration file to show'
    )
    show_parser.add_argument(
        '--section',
        choices=['servers', 'middleware', 'prompts', 'tools'],
        help='Show only a specific section'
    )

    # Apply command
    apply_parser = subparsers.add_parser(
        'apply',
        help='Apply configuration to MCP Composer'
    )
    apply_parser.add_argument(
        'configfilepath',
        help='Path to the configuration file to apply'
    )
    apply_parser.add_argument(
        '--config',
        choices=['servers', 'middleware', 'prompts', 'tools', 'all'],
        default='all',
        help='Which configuration sections to apply (default: all)'
    )


def handle_config_commands(args: argparse.Namespace) -> int:
    """Handle unified configuration commands."""
    if args.config_command == 'validate':
        return cmd_validate_config(args)
    if args.config_command == 'show':
        return cmd_show_config(args)
    if args.config_command == 'apply':
        return cmd_apply_config_sync(args)

    print(f"❌ Unknown config command: {args.config_command}")
    return 1


def create_config_parser() -> argparse.ArgumentParser:
    """Create a standalone parser for configuration commands."""
    parser = argparse.ArgumentParser(
        description="MCP Composer Unified Configuration Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcp-composer --config validate --configfilepath config.json
  mcp-composer --config show --configfilepath config.json --section servers
  mcp-composer --config apply --configfilepath config.json --config all
  mcp-composer --config apply --configfilepath config.json --config servers
        """
    )

    # Add the main config argument
    parser.add_argument(
        '--config',
        choices=['validate', 'show', 'apply'],
        help='Configuration command to execute'
    )
    parser.add_argument(
        '--configfilepath',
        help='Path to the configuration file'
    )
    parser.add_argument(
        '--section',
        choices=['servers', 'middleware', 'prompts', 'tools'],
        help='Section to show (for show command)'
    )

    return parser
