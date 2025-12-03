"""
Modern CLI implementation using Typer for MCP Composer.

This module provides a clean, structured CLI interface with:
- Main MCP Composer commands (HTTP, SSE, STDIO modes)
- Middleware management commands
- OAuth integration
- Future-extensible command structure
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Annotated
from dotenv import load_dotenv

import typer
from typer import Option, Argument

from mcp_composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings
from mcp_composer.core.auth_handler.providers import OAuthProviderFactory
from mcp_composer.core.utils import MemberServerType
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.oauth_cli_utils import (
    create_mcp_server,
    oauth_pkce_login_async,
    get_issuer,
)

# Import command modules
from mcp_composer.core.cli.commands import (
    middleware_commands,
    composer_commands,
    config_commands,
    init_commands,
    catalog_commands,
    tag_commands,
)

# Import unified configuration functions
from mcp_composer.core.config.config_loader import ConfigManager
from mcp_composer.core.config.unified_config import ConfigSection, ConfigValidationError


# Load environment variables
load_dotenv()

# Initialize logger
logger = LoggerFactory.get_logger()

# Create main Typer app
app = typer.Typer(
    name="mcp-composer",
    help="Run MCP Composer with dynamically constructed config",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,  # Allow direct command execution
)

# Add command groups
app.add_typer(
    middleware_commands.app,
    name="middleware",
    help="Middleware management commands",
)

app.add_typer(
    composer_commands.app,
    name="composer",
    help="MCP Composer server commands",
)

app.add_typer(
    config_commands.app,
    name="config",
    help="Unified configuration management commands",
)

app.add_typer(
    catalog_commands.app,
    name="catalog",
    help="MCP Composer catalog generation commands",
)

# MCP Tag + Scan + Catalog commands
app.add_typer(
    tag_commands.app,
    name="tag",
    help="MCP Tagging and Catalog generation commands",
)


# Add middleware commands from original CLI
@app.command("validate")
def validate_middleware(
    path: Annotated[str, Argument(help="Path to middleware configuration file")],
    ensure_imports: Annotated[
        bool,
        Option(
            "--ensure-imports", help="Ensure all middleware classes can be imported"
        ),
    ] = False,
    output_format: Annotated[str, Option("--format", help="Output format")] = "text",
    show_middlewares: Annotated[
        bool,
        Option(
            "--show-middlewares", help="Show enabled middlewares in execution order"
        ),
    ] = False,
) -> None:
    """Validate middleware configuration file."""
    # Import the middleware CLI functions
    try:
        from mcp_composer.core.utils.middleware_cli import cmd_validate
        import argparse

        # Create a mock args object
        args = argparse.Namespace()
        args.path = path
        args.ensure_imports = ensure_imports
        args.format = output_format
        args.show_middlewares = show_middlewares

        sys.exit(cmd_validate(args))
    except ImportError as exc:
        typer.echo("Middleware CLI functions not available", err=True)
        raise typer.Exit(1) from exc


@app.command("list")
def list_middlewares(
    config: Annotated[str, Argument(help="Path to middleware configuration file")],
    ensure_imports: Annotated[
        bool,
        Option(
            "--ensure-imports", help="Ensure all middleware classes can be imported"
        ),
    ] = False,
    output_format: Annotated[str, Option("--format", help="Output format")] = "text",
    show_all: Annotated[
        bool, Option("--all", help="Show all middlewares including disabled ones")
    ] = False,
) -> None:
    """List middlewares from configuration file."""
    try:
        from mcp_composer.core.utils.middleware_cli import cmd_list
        import argparse

        # Create a mock args object
        args = argparse.Namespace()
        args.config = config
        args.ensure_imports = ensure_imports
        args.format = output_format
        args.all = show_all

        sys.exit(cmd_list(args))
    except ImportError as exc:
        typer.echo("Middleware CLI functions not available", err=True)
        raise typer.Exit(1) from exc


@app.command("add-middleware")
def add_middleware(
    config: Annotated[
        str, Option("--config", help="Path to middleware configuration file")
    ],
    name: Annotated[str, Option("--name", help="Name of the middleware")],
    kind: Annotated[
        str, Option("--kind", help="Python import path to middleware class")
    ],
    description: Annotated[
        Optional[str], Option("--description", help="Description of the middleware")
    ] = None,
    version: Annotated[  # pylint: disable=redefined-outer-name
        Optional[str], Option("--version", help="Version of the middleware")
    ] = None,
    mode: Annotated[str, Option("--mode", help="Middleware mode")] = "enabled",
    priority: Annotated[int, Option("--priority", help="Execution priority")] = 100,
    applied_hooks: Annotated[
        Optional[str], Option("--applied-hooks", help="Comma-separated list of hooks")
    ] = None,
    include_tools: Annotated[
        Optional[str],
        Option("--include-tools", help="Comma-separated list of tools to include"),
    ] = None,
    exclude_tools: Annotated[
        Optional[str],
        Option("--exclude-tools", help="Comma-separated list of tools to exclude"),
    ] = None,
    include_prompts: Annotated[
        Optional[str],
        Option("--include-prompts", help="Comma-separated list of prompts to include"),
    ] = None,
    exclude_prompts: Annotated[
        Optional[str],
        Option("--exclude-prompts", help="Comma-separated list of prompts to exclude"),
    ] = None,
    include_server_ids: Annotated[
        Optional[str],
        Option(
            "--include-server-ids", help="Comma-separated list of server IDs to include"
        ),
    ] = None,
    exclude_server_ids: Annotated[
        Optional[str],
        Option(
            "--exclude-server-ids", help="Comma-separated list of server IDs to exclude"
        ),
    ] = None,
    config_file: Annotated[
        Optional[str],
        Option(
            "--config-file",
            help="Path to JSON file containing middleware configuration",
        ),
    ] = None,
    update: Annotated[
        bool,
        Option("--update", help="Update existing middleware if name already exists"),
    ] = False,
    ensure_imports: Annotated[
        bool,
        Option(
            "--ensure-imports",
            help="Ensure all middleware classes can be imported after update",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        Option("--dry-run", help="Show what would be written without actually writing"),
    ] = False,
    show_middlewares: Annotated[
        bool,
        Option(
            "--show-middlewares",
            help="Show enabled middlewares in execution order after update",
        ),
    ] = False,
) -> None:
    """Add or update middleware in configuration file."""
    try:
        from mcp_composer.core.utils.middleware_cli import cmd_add_middleware
        import argparse

        # Create a mock args object
        args = argparse.Namespace()
        args.config = config
        args.name = name
        args.kind = kind
        args.description = description
        args.version = version
        args.mode = mode
        args.priority = priority
        args.applied_hooks = applied_hooks
        args.include_tools = include_tools
        args.exclude_tools = exclude_tools
        args.include_prompts = include_prompts
        args.exclude_prompts = exclude_prompts
        args.include_server_ids = include_server_ids
        args.exclude_server_ids = exclude_server_ids
        args.config_file = config_file
        args.update = update
        args.ensure_imports = ensure_imports
        args.dry_run = dry_run
        args.show_middlewares = show_middlewares

        sys.exit(cmd_add_middleware(args))
    except ImportError as exc:
        typer.echo("Middleware CLI functions not available", err=True)
        raise typer.Exit(1) from exc


@app.command("run")
def run_composer(
    # Mode and basic configuration
    mode: Annotated[
        str,
        Option(
            "--mode",
            "-m",
            help="MCP mode to run (http, sse, or stdio)",
            case_sensitive=False,
        ),
    ] = "stdio",
    id: Annotated[
        str, Option("--id", "-i", help="Unique ID for this MCP instance")
    ] = "mcp-local",
    # Endpoint configuration
    endpoint: Annotated[
        Optional[str],
        Option(
            "--endpoint", "-e", help="Endpoint for HTTP or SSE server running remotely"
        ),
    ] = None,
    # Script configuration
    script_path: Annotated[
        Optional[str],
        Option("--script-path", "-s", help="Path to the script to run in 'stdio' mode"),
    ] = None,
    directory: Annotated[
        Optional[str],
        Option(
            "--directory",
            "-d",
            help="Working directory for the uvicorn process (optional)",
        ),
    ] = None,
    # Server configuration
    host: Annotated[
        str, Option("--host", help="Host for SSE or HTTP server")
    ] = "0.0.0.0",
    port: Annotated[
        int, Option("--port", "-p", help="Port for SSE or HTTP server")
    ] = 9000,
    # Authentication
    auth_type: Annotated[
        Optional[str],
        Option(
            "--auth-type",
            help="Optional auth type. If 'oauth', uses OAuth authentication",
        ),
    ] = None,
    auth_provider: Annotated[
        Optional[str],
        Option(
            "--auth_provider",
            help=(
                "Optional auth provider. by default 'IBM W3' is used for OAuth. "
                "Currently only 'oidc' is supported support GitHub, Google, "
                "AWS Cognito and Azure"
            ),
        ),
    ] = "oidc",
    # Remote server configuration
    sse_url: Annotated[
        Optional[str],
        Option(
            "--sse-url",
            help="Langflow compatible URL for remote SSE / HTTP server to connect to",
        ),
    ] = None,
    remote_auth_type: Annotated[
        str,
        Option(
            "--remote-auth-type",
            help="Authentication type for remote server (oauth or none)",
        ),
    ] = "none",
    client_auth_type: Annotated[
        str,
        Option(
            "--client-auth-type", help="Authentication type for client (oauth or none)"
        ),
    ] = "none",
    # Configuration
    config_path: Annotated[
        Optional[str],
        Option(
            "--config-path", "-c", help="Path to JSON config for MCP member servers"
        ),
    ] = None,
    # Feature flags
    disable_composer_tools: Annotated[
        bool,
        Option(
            "--disable-composer-tools/--enable-composer-tools",
            help="Disable composer tools (disabled by default)",
        ),
    ] = False,
    # Environment variables
    env: Annotated[
        List[str],
        Option(
            "--env",
            "-E",
            help="Environment variables (format: KEY=VALUE). Can be used multiple times.",
        ),
    ] = [],
    pass_environment: Annotated[
        bool,
        Option(
            "--pass-environment/--no-pass-environment",
            help="Pass through all environment variables when spawning all server processes",
        ),
    ] = False,
) -> None:
    """
    Run MCP Composer with dynamically constructed configuration.

    Examples:

    \b
    # Run in HTTP mode with endpoint
    mcp-composer run --mode http --endpoint http://api.example.com

    \b
    # Run in SSE mode
    mcp-composer run --mode sse --endpoint http://localhost:8001/sse

    \b
    # Run in STDIO mode with script
    mcp-composer run --mode stdio --script-path /path/to/server.py --id mcp-news

    \b
    # Run with OAuth authentication
    mcp-composer run --mode sse --auth-type oauth --host localhost --port 9000

    \b
    # Run with remote server connection
    mcp-composer run --mode http --sse-url http://localhost:8001/sse --remote-auth-type oauth
    """

    # Validate mode
    if mode not in ["http", "sse", "stdio"]:
        raise typer.BadParameter(
            f"Invalid mode '{mode}'. Must be one of: http, sse, stdio"
        )

    # Set SERVER_CONFIG_FILE_PATH if provided
    if config_path:
        logger.info("Setting SERVER_CONFIG_FILE_PATH to %s", config_path)
        os.environ["SERVER_CONFIG_FILE_PATH"] = config_path

    # Load config from file if provided
    config = None
    if config_path:
        try:
            import json

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(
                "Loaded %d server configurations from %s", len(config), config_path
            )
        except Exception as e:
            logger.error("Failed to load config file %s: %s", config_path, e)
            raise typer.Exit(1)

    # Handle environment variables
    base_env: Dict[str, str] = {}

    # Add environment variables from --env arguments
    for env_var in env:
        if "=" not in env_var:
            raise typer.BadParameter(
                f"Environment variable must be in format KEY=VALUE, got: {env_var}"
            )
        key, value = env_var.split("=", 1)
        base_env[key] = value
        os.environ[key] = value
        logger.info("Setting environment variable from --env: %s=%s", key, value)

    # Pass through all environment variables if requested
    if pass_environment:
        base_env.update(os.environ)
        logger.info("Passing all environment variables to all servers")
        os.environ.update(base_env)

    # Build configuration
    if config is None:
        config = []
    try:
        if endpoint or script_path:
            config = build_config_from_args(mode, endpoint, script_path, directory, id)

        # Run the composer
        asyncio.run(
            run_dynamic_composer(
                mode=mode,
                config=config,
                auth_type=auth_type,
                auth_provider=auth_provider or "oidc",
                sse_url=sse_url,
                remote_auth_type=remote_auth_type,
                client_auth_type=client_auth_type,
                disable_composer_tools=disable_composer_tools,
                host=host,
                port=port,
            )
        )

    except Exception as e:
        logger.error("Error to start MCP: %s", e)
        raise typer.Exit(1)


@app.command("version")
def version() -> None:
    """Show version information."""
    try:
        from mcp_composer import __version__

        typer.echo(f"MCP Composer version: {__version__}")
    except ImportError:
        typer.echo("MCP Composer version: unknown")


@app.command("info")
def info() -> None:
    """Show information about MCP Composer."""
    typer.echo("MCP Composer - A powerful tool for managing MCP servers and middleware")
    typer.echo()
    typer.echo("Available commands:")
    typer.echo("  • init       - Initialize a new MCP Composer workspace")
    typer.echo("  • run        - Run MCP Composer server")
    typer.echo("  • version    - Show version information")
    typer.echo()
    typer.echo("Available command groups:")
    typer.echo("  • middleware - Manage middleware configurations")
    typer.echo("  • composer   - Server management (start, stop, status, logs)")
    typer.echo("  • config     - Unified configuration management")
    typer.echo()
    typer.echo(
        "Use 'mcp-composer <command> --help' for more information on each command."
    )


# Register init command directly
@app.command("init")
def init_command(
    project_name: Annotated[
        Optional[str], Argument(help="Name of the project to initialize")
    ] = None,
    defaults: Annotated[
        bool,
        Option("--defaults", help="Skip interactive prompts and use default values"),
    ] = False,
    with_examples: Annotated[
        bool,
        Option(
            "--with-examples",
            help="Include example files (sample tool, routes, configs)",
        ),
    ] = False,
    with_venv: Annotated[
        bool,
        Option(
            "--with-venv/--no-venv", help="Create a virtual environment in the project"
        ),
    ] = True,
    adapter: Annotated[
        Optional[str],
        Option(
            "--adapter",
            help=(
                "Setup variant: 'local' (stdio/local development), "
                "'cloud' (http/sse deployment), or 'api' (openapi/graphql)"
            ),
            case_sensitive=False,
        ),
    ] = None,
    port: Annotated[
        int, Option("--port", "-p", help="Default port for HTTP/SSE server")
    ] = 9000,
    host: Annotated[
        str, Option("--host", help="Default host for HTTP/SSE server")
    ] = "0.0.0.0",
    server_mode: Annotated[
        Optional[str],
        Option(
            "--server-mode",
            help="Default server mode: http, sse, stdio, openapi, graphql, local, or client",
            case_sensitive=False,
        ),
    ] = None,
    auth_type: Annotated[
        Optional[str],
        Option(
            "--auth-type",
            help="Authentication type: oauth or none",
            case_sensitive=False,
        ),
    ] = None,
    database: Annotated[
        Optional[str],
        Option(
            "--database",
            help="Database type: sqlite, postgres, or none",
            case_sensitive=False,
        ),
    ] = None,
    description: Annotated[
        Optional[str], Option("--description", help="Project description")
    ] = None,
    directory: Annotated[
        Optional[str],
        Option(
            "--directory",
            "-d",
            help="Target directory for project (defaults to project name)",
        ),
    ] = None,
    force: Annotated[
        bool, Option("--force", "-f", help="Overwrite existing directory if it exists")
    ] = False,
) -> None:
    """Initialize a new MCP Composer workspace."""
    # Call the actual implementation from init_commands
    init_commands.init_project(
        project_name=project_name,
        defaults=defaults,
        with_examples=with_examples,
        with_venv=with_venv,
        adapter=adapter,
        port=port,
        host=host,
        server_mode=server_mode,
        auth_type=auth_type,
        database=database,
        description=description,
        directory=directory,
        force=force,
    )


def main_callback(
    ctx: typer.Context,  # pylint: disable=unused-argument
    # Server parameters matching original CLI
    mode: Annotated[
        Optional[str],
        Option(
            "--mode", help="MCP mode to run (http, sse, or stdio)", case_sensitive=False
        ),
    ] = None,
    id: Annotated[
        Optional[str], Option("--id", help="Unique ID for this MCP instance")
    ] = None,
    endpoint: Annotated[
        Optional[str],
        Option("--endpoint", help="Endpoint for HTTP or SSE server running remotely"),
    ] = None,
    config_path: Annotated[
        Optional[str],
        Option("--config_path", help="Path to JSON config for MCP member servers"),
    ] = None,
    directory: Annotated[
        Optional[str],
        Option(
            "--directory", help="Working directory for the uvicorn process (optional)"
        ),
    ] = None,
    script_path: Annotated[
        Optional[str],
        Option("--script_path", help="Path to the script to run in 'stdio' mode"),
    ] = None,
    host: Annotated[
        Optional[str], Option("--host", help="Host for SSE or HTTP server")
    ] = None,
    port: Annotated[
        Optional[int], Option("--port", help="Port for SSE or HTTP server")
    ] = None,
    auth_type: Annotated[
        Optional[str],
        Option(
            "--auth_type",
            help="Optional auth type. If 'oauth', uses OAuth authentication",
        ),
    ] = None,
    auth_provider: Annotated[
        Optional[str],
        Option(
            "--auth_provider",
            help=(
                "Optional auth provider. by default 'IBM W3' is used for OAuth. "
                "Currently only 'oidc' is supported support GitHub, Google, "
                "AWS Cognito and Azure"
            ),
        ),
    ] = "oidc",
    sse_url: Annotated[
        Optional[str],
        Option(
            "--sse-url",
            help="Langflow compatible URL for remote SSE / HTTP server to connect to",
        ),
    ] = None,
    disable_composer_tools: Annotated[
        Optional[bool],
        Option(
            "--disable-composer-tools/--enable-composer-tools",
            help="Disable composer tools (disabled by default)",
        ),
    ] = None,
    pass_environment: Annotated[
        Optional[bool],
        Option(
            "--pass-environment/--no-pass-environment",
            help="Pass through all environment variables when spawning all server processes",
        ),
    ] = None,
    remote_auth_type: Annotated[
        Optional[str],
        Option(
            "--remote_auth_type",
            help="Authentication type for remote server (oauth or none)",
        ),
    ] = None,
    client_auth_type: Annotated[
        Optional[str],
        Option(
            "--client_auth_type", help="Authentication type for client (oauth or none)"
        ),
    ] = None,
    env: Annotated[
        Optional[List[str]],
        Option(
            "--env",
            "-e",
            help="Environment variables (format: KEY=VALUE). Can be used multiple times.",
        ),
    ] = None,
    log_level: Annotated[
        Optional[str],
        Option(
            "--log-level",
            help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        ),
    ] = None,
    timeout: Annotated[
        Optional[int],
        Option(
            "--timeout",
            help="Set timeout in seconds for server operations and connections (optional - no timeout by default)",
        ),
    ] = None,
    version: Annotated[
        Optional[bool],
        Option(
            "--version",
            help="Show version information and exit",
        ),
    ] = False,
    # Unified configuration options
    config: Annotated[
        Optional[str],
        Option(
            "--config",
            help=(
                "Configuration type to load (servers, middleware, prompts, tools, all) "
                "or command (validate, show, apply)"
            ),
        ),
    ] = None,
    configfilepath: Annotated[
        Optional[str], Option("--configfilepath", help="Path to the configuration file")
    ] = None,
    config_format: Annotated[
        Optional[str], Option("--format", help="Output format (table, json)")
    ] = None,
    dry_run: Annotated[
        Optional[bool],
        Option(
            "--dry-run", help="Show what would be applied without actually applying"
        ),
    ] = None,
) -> None:
    """Main callback to handle direct command execution matching original CLI."""

    # Handle version flag
    if version:
        try:
            from mcp_composer import __version__
            typer.echo(f"MCP Composer version: {__version__}")
        except ImportError:
            typer.echo("MCP Composer version: unknown")
        raise typer.Exit(0)

    # Handle unified configuration commands first
    if config is not None:
        # If we have server mode parameters, we need to apply config AND start server
        if mode is not None:
            # Apply configuration first, then start server
            _apply_config_and_start_server(
                config,
                configfilepath,
                config_format,
                dry_run,
                mode,
                id,
                endpoint,
                config_path,
                directory,
                script_path,
                host,
                port,
                auth_type,
                auth_provider or "oidc",
                sse_url,
                disable_composer_tools,
                pass_environment,
                remote_auth_type,
                client_auth_type,
                env,
                log_level,
                timeout,
            )
        else:
            # Just handle configuration commands
            _handle_unified_config_commands(
                config, configfilepath, config_format, dry_run
            )
        return

    # Only run server if mode is provided (direct command execution)
    if mode is None:
        return  # Let subcommands handle their own logic

    # Set defaults for optional parameters
    if id is None:
        id = "mcp-local"
    if host is None:
        host = "0.0.0.0"
    if port is None:
        port = 9000
    if remote_auth_type is None:
        remote_auth_type = "none"
    if client_auth_type is None:
        client_auth_type = "none"
    if disable_composer_tools is None:
        disable_composer_tools = False
    if pass_environment is None:
        pass_environment = False

    # Set timeout if provided
    if timeout is not None:
        if timeout <= 0:
            logger.error("Timeout must be a positive number, got: %s", timeout)
            raise typer.Exit(1)
        logger.info("Set timeout to %d seconds", timeout)
    else:
        logger.info("No timeout specified - server will run indefinitely")

    # Set logging level if provided
    if log_level:
        import logging

        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            logger.error(
                "Invalid log level: %s. Valid levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL",
                log_level,
            )
            raise typer.Exit(1)
        # Set level on the specific logger, not the root logger
        logger.setLevel(numeric_level)
        # Also set the root logger to prevent propagation issues
        logging.getLogger().setLevel(numeric_level)
        logger.info("Set logging level to %s", log_level.upper())

    # Set SERVER_CONFIG_FILE_PATH if provided
    if config_path:
        logger.info("Setting SERVER_CONFIG_FILE_PATH to %s", config_path)
        os.environ["SERVER_CONFIG_FILE_PATH"] = config_path

    # Load config from file if provided
    server_config = None
    if config_path:
        try:
            import json

            with open(config_path, "r", encoding="utf-8") as f:
                server_config = json.load(f)
            logger.info(
                "Loaded %d server configurations from %s",
                len(server_config),
                config_path,
            )
        except Exception as e:
            logger.error("Failed to load config file %s: %s", config_path, e)
            raise typer.Exit(1)

    base_env: Dict[str, str] = {}

    # Add environment variables from --env arguments (preprocessed to KEY=VALUE format)
    if env:
        for env_var in env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                base_env[key] = value
                os.environ[key] = value
                logger.info(
                    "Setting environment variable from --env: %s=%s",
                    key,
                    value,
                )
            else:
                raise typer.BadParameter(
                    f"Environment variable must be in format KEY=VALUE, got: {env_var}"
                )

    # Pass through all environment variables if requested
    if pass_environment:
        base_env.update(os.environ)
        logger.info("Passing all environment variables to all servers")
        os.environ.update(base_env)

    # Build configuration
    if server_config is None:
        server_config = []
    try:
        if endpoint or script_path:
            server_config = build_config_from_args(
                mode, endpoint, script_path, directory, id
            )

        # Run the composer
        asyncio.run(
            run_dynamic_composer(
                mode=mode,
                config=server_config,
                auth_type=auth_type,
                auth_provider=auth_provider or "oidc",
                sse_url=sse_url,
                remote_auth_type=remote_auth_type,
                client_auth_type=client_auth_type,
                disable_composer_tools=disable_composer_tools,
                host=host,
                port=port,
                timeout=timeout,
            )
        )

    except Exception as e:
        logger.error("Error to start MCP: %s", e)
        raise typer.Exit(1)


# Set the callback
app.callback(invoke_without_command=True)(main_callback)


async def run_dynamic_composer(
    mode: str,
    config: List[Dict],
    auth_type: Optional[str] = None,
    auth_provider: str = "oidc",
    sse_url: Optional[str] = None,
    remote_auth_type: str = "none",
    client_auth_type: str = "none",
    disable_composer_tools: bool = False,
    host: str = "localhost",
    port: int = 9000,
    timeout: Optional[int] = None,
) -> None:
    """Run MCP Composer with dynamically constructed configuration."""
    logger.info("Running MCP Composer with dynamic configuration... %s", auth_type)

    # For IBM W3 OAuth, use old server creation method
    # backward compatibility
    if auth_type == "oauth" and auth_provider == "oidc":
        logger.info("Detected --auth_type oauth and --auth_provider oidc")
        settings = ServerSettings()
        mcp = create_mcp_server(settings)

    elif auth_type == "oauth":
        logger.info("Detected --auth_type oauth and provider: %s", auth_provider)
        settings = ServerSettings(provider=auth_provider)
        # 2. Filter out keys whose values are empty strings
        filtered_settings = {
            key: value
            for key, value in settings.model_dump(exclude_none=True).items()
            if value not in ("", b"")  # Also consider bytes if applicable
        }
        filtered_settings["provider"] = auth_provider
        oauth_provider = OAuthProviderFactory(
            **filtered_settings
        ).get_provider_instance()
        mcp = MCPComposer("composer", auth=oauth_provider)
    else:
        logger.info("Running MCP Composer without OAuth")
        mcp = MCPComposer("composer", config=config)  # type: ignore

    # Remove composer tools if disable-composer-tools is set to True
    if disable_composer_tools:
        tools = await mcp.get_tools()
        logger.info("Remove composer tools")
        for name, _ in tools.items():
            mcp.remove_tool(name)

    if sse_url:
        logger.info("mounting Remote server into MCP composer")
        remote_url = sse_url

        remote_proxy = None

        if remote_auth_type == "oauth":
            remote_settings = ServerSettings(
                prefix="REMOTE_OAUTH_", provider=auth_provider
            )
            # 2. Filter out keys whose values are empty strings
            filtered_settings = {
                key: value
                for key, value in remote_settings.model_dump(exclude_none=True).items()
                if value not in ("", b"")  # Also consider bytes if applicable
            }
            filtered_settings["provider"] = auth_provider
            oauth_provider = OAuthProviderFactory(
                **filtered_settings
            ).get_provider_instance()
            logger.info("Created remote client with OAuth")
            remote_proxy = MCPComposer("composer", auth=oauth_provider)
            await remote_proxy._tool_manager.disable_tools(["all"])

        elif client_auth_type == "oauth":
            client_issuer = get_issuer(remote_url)
            client_scope = "openid"
            client_id = None
            token = await oauth_pkce_login_async(client_issuer, client_scope, client_id)
            access_token = token.get("access_token")
            if not access_token:
                raise RuntimeError("OAuth succeeded but no access_token was returned.")

            # Prefer passing Authorization header via ProxyClient if supported
            auth_headers = {"Authorization": f"Bearer {access_token}"}

            # If ProxyClient supports headers:
            from fastmcp.client.transports import SSETransport, StreamableHttpTransport
            from fastmcp.server.proxy import ProxyClient

            # Prefer SSE if you're connecting to /sse
            if remote_url.endswith("/sse"):
                transport = SSETransport(remote_url, headers=auth_headers)
            else:
                transport = StreamableHttpTransport(remote_url, headers=auth_headers)

            # Now create the proxy **from the transport**, not from ProxyClient
            remote_proxy = MCPComposer.as_proxy(transport, name="remote-oauth")
        else:
            logger.info("Created remote client without OAuth")
            from fastmcp.server.proxy import ProxyClient

            remote_proxy = MCPComposer.as_proxy(
                ProxyClient(remote_url), name="local-stdio"
            )

        await mcp.import_server(remote_proxy)

    await mcp.setup_member_servers()

    try:
        if mode == MemberServerType.STDIO:
            if timeout is not None:
                await asyncio.wait_for(mcp.run_stdio_async(), timeout=timeout)
            else:
                await mcp.run_stdio_async()
        elif mode == MemberServerType.SSE:
            if timeout is not None:
                await asyncio.wait_for(
                    mcp.run_sse_async(
                        host=host, port=port, log_level="debug", path="/sse"
                    ),
                    timeout=timeout,
                )
            else:
                await mcp.run_sse_async(
                    host=host, port=port, log_level="debug", path="/sse"
                )
        elif mode == MemberServerType.HTTP:
            if timeout is not None:
                await asyncio.wait_for(
                    mcp.run_http_async(
                        host=host, port=port, log_level="debug", path="/mcp"
                    ),
                    timeout=timeout,
                )
            else:
                await mcp.run_http_async(
                    host=host, port=port, log_level="debug", path="/mcp"
                )
        else:
            raise ValueError(f"Unknown config type: {mode}")
    except asyncio.TimeoutError as exc:
        logger.error("Server operation timed out after %d seconds", timeout)
        raise typer.Exit(1) from exc
    except Exception as e:
        logger.error("Server operation failed: %s", e)
        raise typer.Exit(1) from e


def build_config_from_args(
    mode: str,
    endpoint: Optional[str] = None,
    script_path: Optional[str] = None,
    directory: Optional[str] = None,
    id: str = "mcp-local",
) -> List[Dict]:
    """Build configuration dictionary from command line arguments."""

    if mode in (MemberServerType.SSE, MemberServerType.HTTP):
        if endpoint:
            config = {
                "id": id,
                "type": mode,
                "endpoint": endpoint,
                "_id": id,
            }
        else:
            # For HTTP/SSE mode without endpoint, return empty config
            # The server will be started directly without member servers
            config = {}
    elif mode == MemberServerType.STDIO:
        if not script_path:
            raise typer.BadParameter("--script-path is required for mode 'stdio'")

        config = {
            "id": id,
            "type": MemberServerType.STDIO,
            "command": "uv",
            "args": [
                "--directory",
                directory or str(Path(script_path).parent),
                "run",
                Path(script_path).name,
            ],
            "_id": id,
        }
    else:
        raise typer.BadParameter(f"Unsupported mode '{mode}'")

    server_configs = [config]
    return server_configs


async def _start_server(
    composer: MCPComposer, mode: str, host: str, port: int, log_level: str
) -> None:
    """Start the MCP Composer server."""
    await composer.setup_member_servers()

    if mode == "stdio":
        await composer.run_stdio_async()
    elif mode == "sse":
        await composer.run_sse_async(
            host=host, port=port, log_level=log_level or "debug", path="/sse"
        )
    elif mode == "http":
        await composer.run_http_async(
            host=host, port=port, log_level=log_level or "debug", path="/mcp"
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _apply_config_and_start_server(
    config: str,
    configfilepath: Optional[str],
    config_format: Optional[str],  # pylint: disable=unused-argument
    dry_run: Optional[bool],
    mode: str,
    id: Optional[str],
    endpoint: Optional[str],
    config_path: Optional[str],  # pylint: disable=unused-argument
    directory: Optional[str],
    script_path: Optional[str],
    host: Optional[str],
    port: Optional[int],
    auth_type: Optional[str],
    auth_provider: str,
    sse_url: Optional[str],  # pylint: disable=unused-argument
    disable_composer_tools: Optional[bool],
    pass_environment: Optional[bool],  # pylint: disable=unused-argument
    remote_auth_type: Optional[str],  # pylint: disable=unused-argument
    client_auth_type: Optional[str],  # pylint: disable=unused-argument
    env: Optional[List[str]],  # pylint: disable=unused-argument
    log_level: Optional[str],  # pylint: disable=unused-argument
    timeout: Optional[int],  # pylint: disable=unused-argument
) -> None:
    """Apply configuration and start the server."""
    try:
        # Determine config type and sections to apply
        config_type = config
        sections = None

        # Map config types to sections
        if config_type in ["servers", "middleware", "prompts", "tools"]:
            try:
                sections = [ConfigSection(config_type)]
            except ValueError as exc:
                typer.echo(f"❌ Invalid config type: {config_type}")
                typer.echo("Valid types: servers, middleware, prompts, tools, all")
                raise typer.Exit(1) from exc
        elif config_type == "all":
            sections = None  # Apply all sections
        else:
            typer.echo(f"❌ Invalid config type: {config_type}")
            typer.echo("Valid types: servers, middleware, prompts, tools, all")
            raise typer.Exit(1)

        if dry_run:
            typer.echo("🔍 Dry run mode - showing what would be applied:")
            _show_dry_run(configfilepath, sections, config_type)
            return

        # Load and validate configuration
        config_manager = ConfigManager()

        # Create composer instance
        composer = _create_composer_instance(
            mode,
            id,
            endpoint,
            config_path,
            directory,
            script_path,
            host,
            port,
            auth_type,
            auth_provider,
            sse_url,
            disable_composer_tools,
            pass_environment,
            remote_auth_type,
            client_auth_type,
            env,
            log_level,
            timeout,
        )

        # Apply configuration to composer
        config_manager.loader.composer = composer
        results = asyncio.run(
            config_manager.load_and_apply(configfilepath, sections, config_type)
        )
        _display_apply_results(results)

        typer.echo("\n🚀 Starting MCP Composer server...")

        # Start the server
        asyncio.run(
            _start_server(
                composer, mode, host or "0.0.0.0", port or 9000, log_level or "debug"
            )
        )

    except Exception as e:
        typer.echo(f"❌ Error: {e}")
        raise typer.Exit(1)


def _create_composer_instance(
    mode: str,
    id: Optional[str],
    endpoint: Optional[str],
    config_path: Optional[str],
    directory: Optional[str],
    script_path: Optional[str],
    host: Optional[str],
    port: Optional[int],
    auth_type: Optional[str],
    auth_provider: str,
    sse_url: Optional[str],
    disable_composer_tools: Optional[bool],
    pass_environment: Optional[bool],
    remote_auth_type: Optional[str],
    client_auth_type: Optional[str],
    env: Optional[List[str]],
    log_level: Optional[str],
    timeout: Optional[int],
) -> MCPComposer:
    """Create MCPComposer instance with the given parameters."""
    # Set defaults
    if id is None:
        id = "mcp-local"
    if host is None:
        host = "0.0.0.0"
    if port is None:
        port = 9000

    # Build configuration from args
    config = []
    if endpoint or script_path:
        config = _build_config_from_args(mode, id, endpoint, script_path, directory)

    # Create composer
    if auth_type == "oauth":
        logger.info("Detected --auth_type oauth")
        settings = ServerSettings(provider=auth_provider)
        # 2. Filter out keys whose values are empty strings
        filtered_settings = {
            key: value
            for key, value in settings.model_dump(exclude_none=True).items()
            if value not in ("", b"")  # Also consider bytes if applicable
        }
        filtered_settings["provider"] = auth_provider
        oauth_provider = OAuthProviderFactory(
            **filtered_settings
        ).get_provider_instance()
        composer = MCPComposer("composer", auth=oauth_provider)
    else:
        composer = MCPComposer("composer", config=config)

    # Disable composer tools if requested
    if disable_composer_tools:
        tools = asyncio.run(composer.get_tools())
        for name, _ in tools.items():
            composer.remove_tool(name)

    return composer


def _build_config_from_args(
    mode: str,
    id: str,
    endpoint: Optional[str],
    script_path: Optional[str],
    directory: Optional[str],
) -> List[Dict]:
    """Build configuration from command line arguments."""
    if mode in ["http", "sse"]:
        if endpoint:
            config = {
                "id": id,
                "type": mode,
                "endpoint": endpoint,
                "_id": id,
            }
        else:
            config = {}
    elif mode == "stdio":
        if not script_path:
            raise ValueError("--script_path is required for mode 'stdio'")

        config = {
            "id": id,
            "type": "stdio",
            "command": "uv",
            "args": [
                "--directory",
                directory or str(Path(script_path).parent),
                "run",
                Path(script_path).name,
            ],
            "_id": id,
        }
    else:
        raise ValueError(f"Unsupported mode '{mode}'")

    return [config] if config else []


def _handle_unified_config_commands(
    config: str,
    configfilepath: Optional[str],
    config_format: Optional[str],  # pylint: disable=unused-argument
    dry_run: Optional[bool],
) -> None:
    """Handle unified configuration commands as global options with optimized error handling."""
    if not configfilepath:
        _handle_error("--configfilepath is required when using --config")

    try:
        config_manager = ConfigManager()

        # Command routing with cleaner error handling
        command_handlers = {
            "validate": lambda: _handle_validate_command(
                config_manager, configfilepath
            ),
            "show": lambda: _handle_show_command(config_manager, configfilepath),
        }

        if config in command_handlers:
            command_handlers[config]()
        elif config in ["servers", "middleware", "prompts", "tools", "all"]:
            _handle_apply_command(config_manager, config, configfilepath, dry_run)
        else:
            _handle_error(
                f"Invalid config type: {config}",
                "Valid types: servers, middleware, prompts, tools, all, validate, show",
            )

    except ConfigValidationError as e:
        _handle_error(f"Configuration validation failed: {e}")
    except Exception as e:
        _handle_error(f"Unexpected error: {e}")


def _handle_error(message: str, suggestion: Optional[str] = None) -> None:
    """Handle errors with consistent formatting."""
    typer.echo(f"❌ Error: {message}")
    if suggestion:
        typer.echo(suggestion)
    raise typer.Exit(1)


def _handle_validate_command(
    config_manager: ConfigManager, configfilepath: str
) -> None:
    """Handle validate command."""
    is_valid = config_manager.validate_config_file(configfilepath)
    if is_valid:
        typer.echo("✅ Configuration file is valid")
    else:
        _handle_error("Configuration file is invalid")


def _handle_show_command(config_manager: ConfigManager, configfilepath: str) -> None:
    """Handle show command."""
    # Auto-detect config type first
    config_type = config_manager.loader.detect_config_type(configfilepath)
    config_obj = config_manager.loader.load_from_file(configfilepath, config_type)
    config_dict = config_obj.model_dump()
    _show_all_sections(config_dict)


def _handle_apply_command(
    config_manager: ConfigManager,
    config: str,
    configfilepath: str,
    dry_run: Optional[bool],
) -> None:
    """Handle apply commands."""
    # Parse sections to apply
    sections = None
    if config != "all":
        try:
            sections = [ConfigSection(config)]
        except ValueError:
            _handle_error(
                f"Invalid config type: {config}",
                "Valid types: servers, middleware, prompts, tools, all",
            )

    if dry_run:
        typer.echo("🔍 Dry run mode - showing what would be applied:")
        _show_dry_run(configfilepath, sections, config)
    else:
        # Apply configuration
        results = asyncio.run(
            config_manager.load_and_apply(configfilepath, sections, config)
        )
        _display_apply_results(results)


def _show_servers_table(servers: list) -> None:
    """Show servers in a table format."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Endpoint", style="yellow")
    table.add_column("Label", style="blue")

    for server in servers:
        table.add_row(
            server.get("id", ""),
            server.get("type", ""),
            server.get("endpoint", "N/A"),
            server.get("label", ""),
        )

    console.print(table)


def _show_middleware_table(middleware: list) -> None:
    """Show middleware in a table format."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Mode", style="yellow")
    table.add_column("Priority", style="blue")

    for mw in middleware:
        table.add_row(
            mw.get("name", ""),
            mw.get("kind", ""),
            mw.get("mode", ""),
            str(mw.get("priority", "")),
        )

    console.print(table)


def _show_prompts_table(prompts: list) -> None:
    """Show prompts in a table format."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Template", style="yellow")
    table.add_column("Arguments", style="blue")

    for prompt in prompts:
        args_count = len(prompt.get("arguments", []) or [])
        template_preview = (
            prompt.get("template", "")[:50] + "..."
            if len(prompt.get("template", "")) > 50
            else prompt.get("template", "")
        )
        table.add_row(
            prompt.get("name", ""),
            prompt.get("description", ""),
            template_preview,
            str(args_count),
        )

    console.print(table)


def _show_tools_table(tools: dict) -> None:
    """Show tools in a table format."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("OpenAPI Version", style="yellow")
    table.add_column("Paths", style="blue")

    for tool_name, tool_config in tools.items():
        tool_type = "OpenAPI" if tool_config.get("openapi") else "Custom"
        openapi_version = tool_config.get("openapi", "N/A")
        paths_count = len(tool_config.get("paths", {}))

        table.add_row(tool_name, tool_type, str(openapi_version), str(paths_count))

    console.print(table)


def _show_all_sections(config_dict: dict) -> None:
    """Show all sections of the configuration."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    typer.echo("\n[bold blue]Configuration Overview[/bold blue]")

    # Summary
    summary_table = Table(title="Configuration Summary")
    summary_table.add_column("Section", style="cyan")
    summary_table.add_column("Count", style="magenta")

    for key, value in config_dict.items():
        if isinstance(value, list):
            summary_table.add_row(key.title(), str(len(value)))
        elif isinstance(value, dict):
            summary_table.add_row(key.title(), str(len(value)))
        else:
            summary_table.add_row(key.title(), str(type(value).__name__))

    console.print(summary_table)

    # Show each section
    if config_dict.get("servers"):
        typer.echo("\n[bold green]Servers[/bold green]")
        _show_servers_table(config_dict["servers"])

    if config_dict.get("middleware"):
        typer.echo("\n[bold green]Middleware[/bold green]")
        _show_middleware_table(config_dict["middleware"])

    if config_dict.get("prompts"):
        typer.echo("\n[bold green]Prompts[/bold green]")
        _show_prompts_table(config_dict["prompts"])

    if config_dict.get("tools"):
        typer.echo("\n[bold green]Tools[/bold green]")
        _show_tools_table(config_dict["tools"])


def _show_dry_run(
    configfilepath: str,
    sections: Optional[List[ConfigSection]],
    config_type: str = "all",
) -> None:
    """Show what would be applied in dry run mode."""
    try:
        config_manager = ConfigManager()
        config = config_manager.loader.load_from_file(configfilepath, config_type)

        typer.echo(f"\n[bold]Configuration file:[/bold] {configfilepath}")
        typer.echo(f"[bold]Configuration type:[/bold] {config_type}")

        if sections is None:
            sections = [
                ConfigSection.SERVERS,
                ConfigSection.MIDDLEWARE,
                ConfigSection.PROMPTS,
                ConfigSection.TOOLS,
            ]

        for section in sections:
            if section == ConfigSection.SERVERS and config.servers:
                typer.echo(
                    f"\n[bold green]Would apply {len(config.servers)} servers:[/bold green]"
                )
                for server in config.servers:
                    typer.echo(f"  - {server.id} ({server.type})")

            elif section == ConfigSection.MIDDLEWARE and config.middleware:
                typer.echo(
                    f"\n[bold green]Would apply {len(config.middleware)} middleware:[/bold green]"
                )
                for mw in config.middleware:
                    typer.echo(f"  - {mw.name} ({mw.kind})")

            elif section == ConfigSection.PROMPTS and config.prompts:
                typer.echo(
                    f"\n[bold green]Would apply {len(config.prompts)} prompts:[/bold green]"
                )
                for prompt in config.prompts:
                    typer.echo(f"  - {prompt.name}")

            elif section == ConfigSection.TOOLS and config.tools:
                typer.echo(
                    f"\n[bold green]Would apply {len(config.tools)} tools:[/bold green]"
                )
                for tool_name in config.tools.keys():
                    typer.echo(f"  - {tool_name}")

    except Exception as e:
        typer.echo(f"❌ Error in dry run: {e}")
        raise typer.Exit(1)


def _display_apply_results(results: dict) -> None:
    """Display the results of applying configuration."""
    typer.echo("\n[bold blue]Configuration Applied Successfully[/bold blue]")

    for section, result in results.items():
        typer.echo(f"\n[bold green]{section.title()}:[/bold green]")
        typer.echo(f"  Total: {result.get('total', 0)}")
        typer.echo(f"  Registered: {len(result.get('registered', []))}")
        typer.echo(f"  Failed: {len(result.get('failed', []))}")

        if result.get("failed"):
            typer.echo("  [red]Failures:[/red]")
            for failure in result["failed"]:
                typer.echo(f"    - {failure}")


def main() -> None:
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")

    # Pre-process command line arguments to handle --env KEY VALUE format
    processed_args = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] in ["--env", "-e"] and i + 1 < len(sys.argv):
            # Check if next argument is in KEY=VALUE format
            if "=" in sys.argv[i + 1]:
                # Already in KEY=VALUE format, keep as is
                processed_args.append(sys.argv[i])
                processed_args.append(sys.argv[i + 1])
                i += 2
            elif i + 2 < len(sys.argv):
                # Convert --env KEY VALUE to --env KEY=VALUE
                key = sys.argv[i + 1]
                value = sys.argv[i + 2]
                processed_args.append("--env")
                processed_args.append(f"{key}={value}")
                logger.info("Converted --env %s %s to --env %s=%s", key, value, key, value)
                i += 3
            else:
                # Invalid format, keep as is
                processed_args.append(sys.argv[i])
                i += 1
        else:
            processed_args.append(sys.argv[i])
            i += 1

    # Update sys.argv with processed arguments
    logger.info("Original args: %s", sys.argv)
    sys.argv = processed_args
    logger.info("Processed args: %s", processed_args)

    app()


if __name__ == "__main__":
    main()
