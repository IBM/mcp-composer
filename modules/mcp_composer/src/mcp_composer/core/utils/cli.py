"""src/mcp_composer/utils/cli.py"""

import argparse
import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Dict, List
from pydantic import ValidationError
from dotenv import load_dotenv
from fastmcp.server.proxy import ProxyClient

from mcp_composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings
from mcp_composer.core.utils import MemberServerType
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.oauth_cli_utils import create_mcp_server
from mcp_composer.core.utils.middleware_cli import (
    cmd_validate,
    cmd_list,
    cmd_add_middleware,
)

load_dotenv()
logger = LoggerFactory.get_logger()
# pylint: disable=W0718


def _add_middleware_command(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add middleware subcommands to the parser."""
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate middleware configuration file'
    )
    validate_parser.add_argument(
        'path',
        help='Path to middleware configuration file'
    )
    validate_parser.add_argument(
        '--ensure-imports',
        action='store_true',
        help='Ensure all middleware classes can be imported'
    )
    validate_parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format'
    )
    validate_parser.add_argument(
        '--show-middlewares',
        action='store_true',
        help='Show enabled middlewares in execution order'
    )

    # List command
    list_parser = subparsers.add_parser(
        'list',
        help='List middlewares from configuration file'
    )
    list_parser.add_argument(
        'config',
        help='Path to middleware configuration file'
    )
    list_parser.add_argument(
        '--ensure-imports',
        action='store_true',
        help='Ensure all middleware classes can be imported'
    )
    list_parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format'
    )
    list_parser.add_argument(
        '--all',
        action='store_true',
        help='Show all middlewares including disabled ones'
    )

    # Add middleware command
    add_parser = subparsers.add_parser(
        'add-middleware',
        help='Add or update middleware in configuration file'
    )
    add_parser.add_argument(
        '--config',
        required=True,
        help='Path to middleware configuration file'
    )
    add_parser.add_argument(
        '--name',
        required=True,
        help='Name of the middleware'
    )
    add_parser.add_argument(
        '--kind',
        required=True,
        help='Python import path to middleware class (e.g., module.ClassName)'
    )
    add_parser.add_argument(
        '--description',
        help='Description of the middleware'
    )
    add_parser.add_argument(
        '--version',
        help='Version of the middleware (default: 0.0.0)'
    )
    add_parser.add_argument(
        '--mode',
        choices=['enabled', 'disabled'],
        default='enabled',
        help='Middleware mode (default: enabled)'
    )
    add_parser.add_argument(
        '--priority',
        type=int,
        default=100,
        help='Execution priority (lower numbers run first, default: 100)'
    )
    add_parser.add_argument(
        '--applied-hooks',
        help='Comma-separated list of hooks (e.g., on_call_tool,on_list_tools)'
    )
    add_parser.add_argument(
        '--include-tools',
        help='Comma-separated list of tools to include (default: *)'
    )
    add_parser.add_argument(
        '--exclude-tools',
        help='Comma-separated list of tools to exclude'
    )
    add_parser.add_argument(
        '--include-prompts',
        help='Comma-separated list of prompts to include'
    )
    add_parser.add_argument(
        '--exclude-prompts',
        help='Comma-separated list of prompts to exclude'
    )
    add_parser.add_argument(
        '--include-server-ids',
        help='Comma-separated list of server IDs to include'
    )
    add_parser.add_argument(
        '--exclude-server-ids',
        help='Comma-separated list of server IDs to exclude'
    )
    add_parser.add_argument(
        '--config-file',
        help='Path to JSON file containing middleware configuration'
    )
    add_parser.add_argument(
        '--update',
        action='store_true',
        help='Update existing middleware if name already exists'
    )
    add_parser.add_argument(
        '--ensure-imports',
        action='store_true',
        help='Ensure all middleware classes can be imported after update'
    )
    add_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be written without actually writing'
    )
    add_parser.add_argument(
        '--show-middlewares',
        action='store_true',
        help='Show enabled middlewares in execution order after update'
    )

    return parser


def _setup_args_parser() -> argparse.ArgumentParser:
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")

    parser = argparse.ArgumentParser(
        description="Run MCP Composer with dynamically constructed config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        mcp-composer --mode http --endpoint http://api.example.com
        mcp-composer --mode sse --endpoint http://localhost:8001/sse
        mcp-composer --mode stdio --script-path /path/to/server.py --id mcp-news
        
        Middleware commands:
        mcp-composer validate middleware-config.json
        mcp-composer add-middleware --config middleware-config.json --name Logger --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware
        
        Middleware commands:
        mcp-composer validate middleware-config.json
        mcp-composer add-middleware --config middleware-config.json --name Logger --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware
        """,
    )
    _add_arguments_to_parser(parser)
    _add_middleware_command(parser)
    return parser


def _add_arguments_to_parser(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the parser."""
    logger.info("Adding arguments...")
    default_config_path = os.getenv("SERVER_CONFIG_FILE_PATH", "")
    parser.add_argument(
        "--mode",
        choices=["http", "sse", "stdio"],
        default="stdio",
        help="MCP mode to run (http, sse, or stdio)",
    )
    parser.add_argument(
        "--id", default="mcp-local", help="Unique ID for this MCP instance"
    )
    parser.add_argument(
        "--endpoint", help="endpoint for HTTP or SSE server running remotely"
    )
    parser.add_argument(
        "--config_path",
        default=default_config_path,
        help="Path to JSON config for MCP member servers",
    )
    parser.add_argument(
        "--directory", help="Working directory for the uvicorn process (optional)"
    )
    parser.add_argument(
        "--script_path", help="Path to the script to run in 'stdio' mode"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE or HTTP server")
    parser.add_argument(
        "--port", type=int, default=9000, help="Port for SSE or HTTP server"
    )
    parser.add_argument(
        "--auth_type",
        help="Optional auth type. If 'oauth', uses test_composer_oauth.create_mcp_server()",
    )
    parser.add_argument(
        "--sse-url", help="Langflow-compatible SSE URL to convert into stdio"
    )
    parser.add_argument(
        "--disable-composer-tools",
        action=argparse.BooleanOptionalAction,
        default=False,  # Disabled by default
        help="Enable composer tools (disabled by default).",
    )
    parser.add_argument(
        "-e",
        "--env",
        nargs=2,
        action="append",
        metavar=("KEY", "VALUE"),
        help=(
            "Environment variables used when spawning the default server. Can be "
            "used multiple times. For named servers, environment is inherited or "
            "passed via --pass-environment."
        ),
        default=[],
    )
    parser.add_argument(
        "--pass-environment",
        action=argparse.BooleanOptionalAction,
        help="Pass through all environment variables when spawning all server processes.",
        default=False,
    )


def build_config_from_args(args: argparse.Namespace) -> List[Dict]:
    """Build configuration dictionary from command line arguments."""

    if args.mode in (MemberServerType.SSE, MemberServerType.HTTP):
        if args.endpoint:
            config = {
                "id": args.id,
                "type": args.mode,
                "endpoint": args.endpoint,
                "_id": args.id,
            }
        else:
            # For HTTP/SSE mode without endpoint, return empty config
            # The server will be started directly without member servers
            config = {}
    elif args.mode == MemberServerType.STDIO:
        if not args.script_path:
            raise ValueError("--script-path is required for mode 'stdio'")
        config = {
            "id": args.id,
            "type": MemberServerType.STDIO,
            "command": "uv",
            "args": [
                "--directory",
                args.directory or str(Path(args.script_path).parent),
                "run",
                Path(args.script_path).name,
            ],
            "_id": args.id,
        }
    else:
        raise ValueError(f"Unsupported mode '{args.mode}'")
    server_configs = [config]
    return server_configs


async def run_dynamic_composer(args: argparse.Namespace, config: list[Dict]) -> None:
    """Run MCP Composer with dynamically constructed configuration."""
    logger.info("Running MCP Composer with dynamic configuration... %s", args.auth_type)
    mcp = None
    if args.auth_type == "oauth":
        logger.info("Detected --auth_type oauth")
        settings = ServerSettings()
        mcp = await create_mcp_server(settings)
    else:
        logger.info("Running MCP Composer without OAuth")
        mcp = MCPComposer("composer", config=config)  # type: ignore

    # by default expose all composer tools
    # remove composer tools if disable-composer-tools set to True
    if args.disable_composer_tools:
        tools = await mcp.get_tools()
        logger.info("Remove composer tools")
        for name, _ in tools.items():
            mcp.remove_tool(name)

    if args.sse_url:
        logger.info("mounting SSE server into MCP composer")
        remote_proxy = MCPComposer.as_proxy(
            ProxyClient(args.sse_url), name="local-stdio"
        )
        await mcp.import_server(remote_proxy)

    ##mcp.add_middleware(ListFilteredTool(mcp))

    await mcp.setup_member_servers()
    if args.mode == MemberServerType.STDIO:
        await mcp.run_stdio_async()
    elif args.mode == MemberServerType.SSE:
        await mcp.run_sse_async(
            host=args.host, port=args.port, log_level="debug", path="/sse"
        )
    elif args.mode == MemberServerType.HTTP:
        await mcp.run_http_async(
            host=args.host, port=args.port, log_level="debug", path="/mcp"
        )
    else:
        raise ValueError(f"Unknown config type: {args.mode}")


def main() -> None:
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")
    parser = _setup_args_parser()
    args = parser.parse_args()

    # Handle middleware commands
    if args.command == 'validate':
        sys.exit(cmd_validate(args))
    elif args.command == 'list':
        sys.exit(cmd_list(args))
    elif args.command == 'add-middleware':
        sys.exit(cmd_add_middleware(args))
    elif args.command is None:
        # No command specified, run the main MCP Composer
        pass
    else:
        logger.error("Unknown command: %s", args.command)
        sys.exit(1)

    # Set SERVER_CONFIG_FILE_PATH first so it's available for other env vars
    if args.config_path:
        logger.info("Setting SERVER_CONFIG_FILE_PATH to %s", args.config_path)
        os.environ["SERVER_CONFIG_FILE_PATH"] = args.config_path

    base_env: dict[str, str] = {}

    # Add environment variables from --env arguments
    if args.env:
        for key, value in args.env:
            base_env[key] = value
            os.environ[key] = value
            logger.info(
                "Setting environment variable from --env: %s=%s", key, os.environ[key]
            )
        base_env.update(os.environ)
    # Pass through all environment variables if requested
    if args.pass_environment:
        base_env.update(os.environ)
        logger.info("Passing all environment variables to all servers")
        for key, value in base_env.items():
            logger.info("%s=%s", key, value)
        os.environ.update(base_env)

    config = []
    try:
        if args.endpoint or args.script_path:
            config = build_config_from_args(args)
        asyncio.run(run_dynamic_composer(args, config))

    except Exception as e:
        logger.error("Error to start MCP: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
