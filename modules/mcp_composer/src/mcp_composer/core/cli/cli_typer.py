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
from typer import Option, Argument, Context

from mcp_composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings, SimpleOAuthProvider
from mcp_composer.core.utils import MemberServerType
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.oauth_cli_utils import create_mcp_server, oauth_pkce_login_async, get_issuer

# Import command modules
from mcp_composer.core.cli.commands import middleware_commands, composer_commands

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


def main_callback(
    ctx: typer.Context,
    # Server parameters matching original CLI
    mode: Annotated[Optional[str], Option(
        "--mode",
        help="MCP mode to run (http, sse, or stdio)",
        case_sensitive=False
    )] = None,

    id: Annotated[Optional[str], Option(
        "--id",
        help="Unique ID for this MCP instance"
    )] = None,

    endpoint: Annotated[Optional[str], Option(
        "--endpoint",
        help="Endpoint for HTTP or SSE server running remotely"
    )] = None,

    config_path: Annotated[Optional[str], Option(
        "--config_path",
        help="Path to JSON config for MCP member servers"
    )] = None,

    directory: Annotated[Optional[str], Option(
        "--directory",
        help="Working directory for the uvicorn process (optional)"
    )] = None,

    script_path: Annotated[Optional[str], Option(
        "--script_path",
        help="Path to the script to run in 'stdio' mode"
    )] = None,

    host: Annotated[Optional[str], Option(
        "--host",
        help="Host for SSE or HTTP server"
    )] = None,

    port: Annotated[Optional[int], Option(
        "--port",
        help="Port for SSE or HTTP server"
    )] = None,

    auth_type: Annotated[Optional[str], Option(
        "--auth_type",
        help="Optional auth type. If 'oauth', uses OAuth authentication"
    )] = None,

    sse_url: Annotated[Optional[str], Option(
        "--sse-url",
        help="Langflow compatible URL for remote SSE / HTTP server to connect to"
    )] = None,

    disable_composer_tools: Annotated[Optional[bool], Option(
        "--disable-composer-tools/--enable-composer-tools",
        help="Disable composer tools (disabled by default)"
    )] = None,

    pass_environment: Annotated[Optional[bool], Option(
        "--pass-environment/--no-pass-environment",
        help="Pass through all environment variables when spawning all server processes"
    )] = None,

    remote_auth_type: Annotated[Optional[str], Option(
        "--remote_auth_type",
        help="Authentication type for remote server (oauth or none)"
    )] = None,

    client_auth_type: Annotated[Optional[str], Option(
        "--client_auth_type",
        help="Authentication type for client (oauth or none)"
    )] = None,

    env: Annotated[Optional[List[str]], Option(
        "--env", "-e",
        help="Environment variables (format: KEY=VALUE). Can be used multiple times."
    )] = None,
) -> None:
    """Main callback to handle direct command execution matching original CLI."""
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

    # Set SERVER_CONFIG_FILE_PATH if provided
    if config_path:
        logger.info("Setting SERVER_CONFIG_FILE_PATH to %s", config_path)
        os.environ["SERVER_CONFIG_FILE_PATH"] = config_path

    base_env: Dict[str, str] = {}

    # Add environment variables from --env arguments (preprocessed to KEY=VALUE format)
    if env:
        for env_var in env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                base_env[key] = value
                os.environ[key] = value
                logger.info("Setting environment variable from --env: %s=%s", key, os.environ[key])
            else:
                raise typer.BadParameter(f"Environment variable must be in format KEY=VALUE, got: {env_var}")

    # Pass through all environment variables if requested
    if pass_environment:
        base_env.update(os.environ)
        logger.info("Passing all environment variables to all servers")
        os.environ.update(base_env)

    # Build configuration
    config = []
    try:
        if endpoint or script_path:
            config = build_config_from_args(mode, endpoint, script_path, directory, id)

        # Run the composer
        asyncio.run(run_dynamic_composer(
            mode=mode,
            config=config,
            auth_type=auth_type,
            sse_url=sse_url,
            remote_auth_type=remote_auth_type,
            client_auth_type=client_auth_type,
            disable_composer_tools=disable_composer_tools,
            host=host,
            port=port,
        ))

    except Exception as e:
        logger.error("Error to start MCP: %s", e)
        raise typer.Exit(1)


# Add middleware commands from original CLI
@app.command("validate")
def validate_middleware(
    path: Annotated[str, Argument(help="Path to middleware configuration file")],
    ensure_imports: Annotated[bool, Option("--ensure-imports", help="Ensure all middleware classes can be imported")] = False,
    format: Annotated[str, Option("--format", help="Output format")] = "text",
    show_middlewares: Annotated[bool, Option("--show-middlewares", help="Show enabled middlewares in execution order")] = False,
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
        args.format = format
        args.show_middlewares = show_middlewares
        
        sys.exit(cmd_validate(args))
    except ImportError:
        typer.echo("Middleware CLI functions not available", err=True)
        raise typer.Exit(1)


@app.command("list")
def list_middlewares(
    config: Annotated[str, Argument(help="Path to middleware configuration file")],
    ensure_imports: Annotated[bool, Option("--ensure-imports", help="Ensure all middleware classes can be imported")] = False,
    format: Annotated[str, Option("--format", help="Output format")] = "text",
    all: Annotated[bool, Option("--all", help="Show all middlewares including disabled ones")] = False,
) -> None:
    """List middlewares from configuration file."""
    try:
        from mcp_composer.core.utils.middleware_cli import cmd_list
        import argparse
        
        # Create a mock args object
        args = argparse.Namespace()
        args.config = config
        args.ensure_imports = ensure_imports
        args.format = format
        args.all = all
        
        sys.exit(cmd_list(args))
    except ImportError:
        typer.echo("Middleware CLI functions not available", err=True)
        raise typer.Exit(1)


@app.command("add-middleware")
def add_middleware(
    config: Annotated[str, Option("--config", help="Path to middleware configuration file")],
    name: Annotated[str, Option("--name", help="Name of the middleware")],
    kind: Annotated[str, Option("--kind", help="Python import path to middleware class")],
    description: Annotated[Optional[str], Option("--description", help="Description of the middleware")] = None,
    version: Annotated[Optional[str], Option("--version", help="Version of the middleware")] = None,
    mode: Annotated[str, Option("--mode", help="Middleware mode")] = "enabled",
    priority: Annotated[int, Option("--priority", help="Execution priority")] = 100,
    applied_hooks: Annotated[Optional[str], Option("--applied-hooks", help="Comma-separated list of hooks")] = None,
    include_tools: Annotated[Optional[str], Option("--include-tools", help="Comma-separated list of tools to include")] = None,
    exclude_tools: Annotated[Optional[str], Option("--exclude-tools", help="Comma-separated list of tools to exclude")] = None,
    include_prompts: Annotated[Optional[str], Option("--include-prompts", help="Comma-separated list of prompts to include")] = None,
    exclude_prompts: Annotated[Optional[str], Option("--exclude-prompts", help="Comma-separated list of prompts to exclude")] = None,
    include_server_ids: Annotated[Optional[str], Option("--include-server-ids", help="Comma-separated list of server IDs to include")] = None,
    exclude_server_ids: Annotated[Optional[str], Option("--exclude-server-ids", help="Comma-separated list of server IDs to exclude")] = None,
    config_file: Annotated[Optional[str], Option("--config-file", help="Path to JSON file containing middleware configuration")] = None,
    update: Annotated[bool, Option("--update", help="Update existing middleware if name already exists")] = False,
    ensure_imports: Annotated[bool, Option("--ensure-imports", help="Ensure all middleware classes can be imported after update")] = False,
    dry_run: Annotated[bool, Option("--dry-run", help="Show what would be written without actually writing")] = False,
    show_middlewares: Annotated[bool, Option("--show-middlewares", help="Show enabled middlewares in execution order after update")] = False,
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
    except ImportError:
        typer.echo("Middleware CLI functions not available", err=True)
        raise typer.Exit(1)


# Set the callback
app.callback(invoke_without_command=True)(main_callback)


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


async def run_dynamic_composer(
    mode: str,
    config: List[Dict],
    auth_type: Optional[str] = None,
    sse_url: Optional[str] = None,
    remote_auth_type: str = "none",
    client_auth_type: str = "none",
    disable_composer_tools: bool = False,
    host: str = "0.0.0.0",
    port: int = 9000,
) -> None:
    """Run MCP Composer with dynamically constructed configuration."""
    logger.info("Running MCP Composer with dynamic configuration... %s", auth_type)
    mcp = None

    if auth_type == "oauth":
        logger.info("Detected --auth_type oauth")
        settings = ServerSettings()
        mcp = create_mcp_server(settings)
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
        auth = None
        remote_proxy = None

        if remote_auth_type == "oauth":
            remote_settings = ServerSettings(prefix="REMOTE_OAUTH_")
            auth = SimpleOAuthProvider(remote_settings)
            logger.info("Created remote client with OAuth")
            remote_proxy = MCPComposer("composer", auth=auth)
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

    if mode == MemberServerType.STDIO:
        await mcp.run_stdio_async()
    elif mode == MemberServerType.SSE:
        await mcp.run_sse_async(
            host=host, port=port, log_level="debug", path="/sse"
        )
    elif mode == MemberServerType.HTTP:
        await mcp.run_http_async(
            host=host, port=port, log_level="debug", path="/mcp"
        )
    else:
        raise ValueError(f"Unknown config type: {mode}")


@app.command("run")
def run_composer(
    # Mode and basic configuration
    mode: Annotated[str, Option(
        "--mode", "-m",
        help="MCP mode to run (http, sse, or stdio)",
        case_sensitive=False
    )] = "stdio",

    id: Annotated[str, Option(
        "--id", "-i",
        help="Unique ID for this MCP instance"
    )] = "mcp-local",

    # Endpoint configuration
    endpoint: Annotated[Optional[str], Option(
        "--endpoint", "-e",
        help="Endpoint for HTTP or SSE server running remotely"
    )] = None,

    # Script configuration
    script_path: Annotated[Optional[str], Option(
        "--script-path", "-s",
        help="Path to the script to run in 'stdio' mode"
    )] = None,

    directory: Annotated[Optional[str], Option(
        "--directory", "-d",
        help="Working directory for the uvicorn process (optional)"
    )] = None,

    # Server configuration
    host: Annotated[str, Option(
        "--host",
        help="Host for SSE or HTTP server"
    )] = "0.0.0.0",

    port: Annotated[int, Option(
        "--port", "-p",
        help="Port for SSE or HTTP server"
    )] = 9000,

    # Authentication
    auth_type: Annotated[Optional[str], Option(
        "--auth-type",
        help="Optional auth type. If 'oauth', uses OAuth authentication"
    )] = None,

    # Remote server configuration
    sse_url: Annotated[Optional[str], Option(
        "--sse-url",
        help="Langflow compatible URL for remote SSE / HTTP server to connect to"
    )] = None,

    remote_auth_type: Annotated[str, Option(
        "--remote-auth-type",
        help="Authentication type for remote server (oauth or none)"
    )] = "none",

    client_auth_type: Annotated[str, Option(
        "--client-auth-type",
        help="Authentication type for client (oauth or none)"
    )] = "none",

    # Configuration
    config_path: Annotated[Optional[str], Option(
        "--config-path", "-c",
        help="Path to JSON config for MCP member servers"
    )] = None,

    # Feature flags
    disable_composer_tools: Annotated[bool, Option(
        "--disable-composer-tools/--enable-composer-tools",
        help="Disable composer tools (disabled by default)"
    )] = False,

    # Environment variables
    env: Annotated[List[str], Option(
        "--env", "-E",
        help="Environment variables (format: KEY=VALUE). Can be used multiple times."
    )] = [],

    pass_environment: Annotated[bool, Option(
        "--pass-environment/--no-pass-environment",
        help="Pass through all environment variables when spawning all server processes"
    )] = False,
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
        raise typer.BadParameter(f"Invalid mode '{mode}'. Must be one of: http, sse, stdio")

    # Set SERVER_CONFIG_FILE_PATH if provided
    if config_path:
        logger.info("Setting SERVER_CONFIG_FILE_PATH to %s", config_path)
        os.environ["SERVER_CONFIG_FILE_PATH"] = config_path

    # Handle environment variables
    base_env: Dict[str, str] = {}

    # Add environment variables from --env arguments
    for env_var in env:
        if "=" not in env_var:
            raise typer.BadParameter(f"Environment variable must be in format KEY=VALUE, got: {env_var}")
        key, value = env_var.split("=", 1)
        base_env[key] = value
        os.environ[key] = value
        logger.info("Setting environment variable from --env: %s=%s", key, os.environ[key])

    # Pass through all environment variables if requested
    if pass_environment:
        base_env.update(os.environ)
        logger.info("Passing all environment variables to all servers")
        os.environ.update(base_env)

    # Build configuration
    config = []
    try:
        if endpoint or script_path:
            config = build_config_from_args(mode, endpoint, script_path, directory, id)

        # Run the composer
        asyncio.run(run_dynamic_composer(
            mode=mode,
            config=config,
            auth_type=auth_type,
            sse_url=sse_url,
            remote_auth_type=remote_auth_type,
            client_auth_type=client_auth_type,
            disable_composer_tools=disable_composer_tools,
            host=host,
            port=port,
        ))

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
    typer.echo("Available command groups:")
    typer.echo("  • middleware - Manage middleware configurations")
    typer.echo("  • composer   - Run MCP Composer servers")
    typer.echo()
    typer.echo("Use 'mcp-composer <command> --help' for more information on each command.")


def main() -> None:
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")
    
    # Pre-process command line arguments to handle --env KEY VALUE format
    import sys
    processed_args = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] in ["--env", "-e"] and i + 2 < len(sys.argv):
            # Convert --env KEY VALUE to --env KEY=VALUE
            key = sys.argv[i + 1]
            value = sys.argv[i + 2]
            processed_args.append("--env")
            processed_args.append(f"{key}={value}")
            logger.info(f"Converted --env {key} {value} to --env {key}={value}")
            i += 3
        else:
            processed_args.append(sys.argv[i])
            i += 1
    
    # Update sys.argv with processed arguments
    logger.info(f"Original args: {sys.argv}")
    sys.argv = processed_args
    logger.info(f"Processed args: {sys.argv}")
    
    app()


if __name__ == "__main__":
    main()
