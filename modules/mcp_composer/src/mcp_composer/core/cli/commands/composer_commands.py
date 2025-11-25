"""
MCP Composer server commands.

This module provides commands for managing MCP Composer servers:
- start: Start MCP Composer servers
- stop: Stop running servers
- status: Check server status
- logs: View server logs
"""

import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Annotated, Dict, List, Optional, TYPE_CHECKING

import typer
from typer import Option

from mcp_composer.core.utils.logger import LoggerFactory

# Initialize logger
logger = LoggerFactory.get_logger()

# Create Typer app for composer commands
app = typer.Typer(
    name="composer",
    help="MCP Composer server management commands",
    add_completion=False,
    rich_markup_mode="rich",
)


# Lazy import helper to avoid circular dependencies
if TYPE_CHECKING:
    from mcp_composer.core.cli import cli_typer as cli_helpers_module


def _get_cli_helpers():
    """Return cli_typer module without creating circular imports."""
    # pylint: disable=import-outside-toplevel
    from mcp_composer.core.cli import cli_typer as cli_helpers_module  # type: ignore

    return cli_helpers_module


@app.command("start")
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def start_composer(
    # Mode and basic configuration
    mode: Annotated[str, Option(
        "--mode", "-m",
        help="MCP mode to run (http, sse, or stdio)",
        case_sensitive=False
    )] = "stdio",

    instance_id: Annotated[str, Option(
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
    env: Annotated[Optional[List[str]], Option(
        "--env", "-E",
        help="Environment variables (format: KEY=VALUE). Can be used multiple times."
    )] = None,

    pass_environment: Annotated[bool, Option(
        "--pass-environment/--no-pass-environment",
        help="Pass through all environment variables when spawning all server processes"
    )] = False,

    # Process management
    daemon: Annotated[bool, Option(
        "--daemon", "-D",
        help="Run as daemon process"
    )] = False,

    pid_file: Annotated[Optional[str], Option(
        "--pid-file",
        help="Path to PID file for daemon mode"
    )] = None,

    log_file: Annotated[Optional[str], Option(
        "--log-file",
        help="Path to log file for daemon mode"
    )] = None,
) -> None:
    """
    Start MCP Composer server.

    This command starts an MCP Composer server with the specified configuration.
    It's an alias for the main 'run' command with additional process management options.

    Examples:

    \b
    # Start in HTTP mode
    mcp-composer composer start --mode http --endpoint http://api.example.com

    \b
    # Start in SSE mode with OAuth
    mcp-composer composer start --mode sse --auth-type oauth --host localhost --port 9000

    \b
    # Start as daemon
    mcp-composer composer start --mode sse --daemon --pid-file /var/run/mcp-composer.pid

    \b
    # Start with custom environment variables
    mcp-composer composer start --mode stdio --script-path server.py --env DEBUG=true --env LOG_LEVEL=debug
    """

    cli_helpers = _get_cli_helpers()

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
    env_values = env or []
    for env_var in env_values:
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
            config = cli_helpers.build_config_from_args(
                mode, endpoint, script_path, directory, instance_id
            )

        if daemon:
            # Run as daemon
            _run_as_daemon(
                mode=mode,
                config=config,
                auth_type=auth_type,
                sse_url=sse_url,
                remote_auth_type=remote_auth_type,
                client_auth_type=client_auth_type,
                disable_composer_tools=disable_composer_tools,
                host=host,
                port=port,
                pid_file=pid_file,
                log_file=log_file,
            )
        else:
            # Run in foreground
            asyncio.run(cli_helpers.run_dynamic_composer(
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


def _run_as_daemon(
    mode: str,
    config: List[Dict],
    auth_type: Optional[str] = None,
    sse_url: Optional[str] = None,
    remote_auth_type: str = "none",
    client_auth_type: str = "none",
    disable_composer_tools: bool = False,
    host: str = "0.0.0.0",
    port: int = 9000,
    pid_file: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """Run MCP Composer as a daemon process."""
    # pylint: disable=import-outside-toplevel
    import daemon
    from daemon.pidfile import TimeoutPIDLockFile

    # Default PID file location
    if not pid_file:
        pid_file = f"/tmp/mcp-composer-{port}.pid"

    # Default log file location
    if not log_file:
        log_file = f"/tmp/mcp-composer-{port}.log"

    # Create PID file
    pid_lock = TimeoutPIDLockFile(pid_file, timeout=5)

    def run_server():
        """Function to run inside daemon context."""
        cli_helpers = _get_cli_helpers()
        asyncio.run(cli_helpers.run_dynamic_composer(
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

    try:
        with open(log_file, "w", encoding="utf-8") as stdout_handle, open(
            log_file, "a", encoding="utf-8"
        ) as stderr_handle:
            context = daemon.DaemonContext(
                pidfile=pid_lock,
                stdout=stdout_handle,
                stderr=stderr_handle,
                working_directory=os.getcwd(),
            )
            with context:
                typer.echo(f"MCP Composer daemon started with PID {os.getpid()}")
                typer.echo(f"PID file: {pid_file}")
                typer.echo(f"Log file: {log_file}")
                run_server()
    except Exception as e:
        logger.error("Daemon error: %s", e)
        raise typer.Exit(1)


@app.command("stop")
def stop_composer(
    pid_file: Annotated[Optional[str], Option(
        "--pid-file",
        help="Path to PID file"
    )] = None,

    port: Annotated[Optional[int], Option(
        "--port", "-p",
        help="Port number to find PID file automatically"
    )] = None,

    force: Annotated[bool, Option(
        "--force", "-f",
        help="Force stop the process"
    )] = False,
) -> None:
    """
    Stop MCP Composer daemon.

    This command stops a running MCP Composer daemon process.

    Examples:

    \b
    # Stop using PID file
    mcp-composer composer stop --pid-file /var/run/mcp-composer.pid

    \b
    # Stop using port number
    mcp-composer composer stop --port 9000

    \b
    # Force stop
    mcp-composer composer stop --port 9000 --force
    """

    # Determine PID file location
    if not pid_file and not port:
        raise typer.BadParameter("Either --pid-file or --port must be specified")

    if not pid_file:
        pid_file = f"/tmp/mcp-composer-{port}.pid"

    # Check if PID file exists
    if not Path(pid_file).exists():
        typer.echo(f"PID file not found: {pid_file}")
        raise typer.Exit(1)

    # Read PID
    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (ValueError, IOError) as e:
        typer.echo(f"Error reading PID file: {e}")
        raise typer.Exit(1)

    # Check if process exists
    try:
        os.kill(pid, 0)  # Check if process exists
    except OSError:
        typer.echo(f"Process with PID {pid} is not running")
        # Remove stale PID file
        Path(pid_file).unlink(missing_ok=True)
        return

    # Stop the process
    try:
        signal_to_send: signal.Signals = (
            signal.SIGTERM if not force else signal.SIGKILL
        )
        os.kill(pid, signal_to_send)
        typer.echo(f"Sent {signal_to_send.name} to process {pid}")

        # Wait for process to stop
        if not force:
            for _ in range(10):  # Wait up to 10 seconds
                try:
                    os.kill(pid, 0)
                    time.sleep(1)
                except OSError:
                    break
            else:
                typer.echo("Process did not stop gracefully, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)

        # Remove PID file
        Path(pid_file).unlink(missing_ok=True)
        typer.echo("MCP Composer daemon stopped")

    except OSError as e:
        typer.echo(f"Error stopping process: {e}")
        raise typer.Exit(1)


@app.command("status")
def status_composer(
    pid_file: Annotated[Optional[str], Option(
        "--pid-file",
        help="Path to PID file"
    )] = None,

    port: Annotated[Optional[int], Option(
        "--port", "-p",
        help="Port number to find PID file automatically"
    )] = None,

    output_format: Annotated[str, Option(
        "--format", "-f",
        help="Output format",
        case_sensitive=False
    )] = "text",
) -> None:
    """
    Check MCP Composer daemon status.

    This command checks the status of a running MCP Composer daemon process.

    Examples:

    \b
    # Check status using PID file
    mcp-composer composer status --pid-file /var/run/mcp-composer.pid

    \b
    # Check status using port number
    mcp-composer composer status --port 9000

    \b
    # JSON output format
    mcp-composer composer status --port 9000 --format json
    """

    # Determine PID file location
    if not pid_file and not port:
        raise typer.BadParameter("Either --pid-file or --port must be specified")

    if not pid_file:
        pid_file = f"/tmp/mcp-composer-{port}.pid"

    # Check if PID file exists
    if not Path(pid_file).exists():
        status_info = {
            "status": "stopped",
            "pid": None,
            "pid_file": pid_file,
            "message": "PID file not found"
        }
    else:
        # Read PID
        try:
            with open(pid_file, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
        except (ValueError, IOError) as e:
            status_info = {
                "status": "error",
                "pid": None,
                "pid_file": pid_file,
                "message": f"Error reading PID file: {e}"
            }
        else:
            # Check if process exists
            try:
                os.kill(pid, 0)  # Check if process exists
                status_info = {
                    "status": "running",
                    "pid": pid,
                    "pid_file": pid_file,
                    "message": "Process is running"
                }
            except OSError:
                status_info = {
                    "status": "stopped",
                    "pid": pid,
                    "pid_file": pid_file,
                    "message": "Process is not running (stale PID file)"
                }

    # Output status
    if output_format == "json":
        typer.echo(json.dumps(status_info, indent=2))
    else:
        typer.echo(f"Status: {status_info['status']}")
        typer.echo(f"PID: {status_info['pid']}")
        typer.echo(f"PID file: {status_info['pid_file']}")
        typer.echo(f"Message: {status_info['message']}")


@app.command("logs")
def logs_composer(
    log_file: Annotated[Optional[str], Option(
        "--log-file",
        help="Path to log file"
    )] = None,

    port: Annotated[Optional[int], Option(
        "--port", "-p",
        help="Port number to find log file automatically"
    )] = None,

    lines: Annotated[int, Option(
        "--lines", "-n",
        help="Number of lines to show from the end of the log file"
    )] = 50,

    follow: Annotated[bool, Option(
        "--follow", "-f",
        help="Follow log file (like tail -f)"
    )] = False,
) -> None:
    """
    View MCP Composer daemon logs.

    This command displays logs from a running MCP Composer daemon.

    Examples:

    \b
    # View last 50 lines of logs
    mcp-composer composer logs --port 9000

    \b
    # View last 100 lines of logs
    mcp-composer composer logs --port 9000 --lines 100

    \b
    # Follow logs in real-time
    mcp-composer composer logs --port 9000 --follow

    \b
    # View specific log file
    mcp-composer composer logs --log-file /var/log/mcp-composer.log
    """

    # Determine log file location
    if not log_file and not port:
        raise typer.BadParameter("Either --log-file or --port must be specified")

    if not log_file:
        log_file = f"/tmp/mcp-composer-{port}.log"

    # Check if log file exists
    if not Path(log_file).exists():
        typer.echo(f"Log file not found: {log_file}")
        raise typer.Exit(1)

    # Display logs
    try:
        if follow:
            # Follow logs (like tail -f)
            subprocess.run(
                ["tail", "-f", "-n", str(lines), log_file],
                check=False,
            )
        else:
            # Show last N lines
            result = subprocess.run(
                ["tail", "-n", str(lines), log_file],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                typer.echo(result.stdout)
            else:
                typer.echo(f"Error reading log file: {result.stderr}")
                raise typer.Exit(1)
    except FileNotFoundError:
        # Fallback to Python implementation
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            if follow:
                typer.echo("Follow mode not available without 'tail' command")
                typer.echo("Showing last lines:")
            for line in all_lines[-lines:]:
                typer.echo(line.rstrip())


@app.command("restart")
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def restart_composer(
    # All the same options as start command
    mode: Annotated[str, Option(
        "--mode", "-m",
        help="MCP mode to run (http, sse, or stdio)",
        case_sensitive=False
    )] = "stdio",

    instance_id: Annotated[str, Option(
        "--id", "-i",
        help="Unique ID for this MCP instance"
    )] = "mcp-local",

    endpoint: Annotated[Optional[str], Option(
        "--endpoint", "-e",
        help="Endpoint for HTTP or SSE server running remotely"
    )] = None,

    script_path: Annotated[Optional[str], Option(
        "--script-path", "-s",
        help="Path to the script to run in 'stdio' mode"
    )] = None,

    directory: Annotated[Optional[str], Option(
        "--directory", "-d",
        help="Working directory for the uvicorn process (optional)"
    )] = None,

    host: Annotated[str, Option(
        "--host",
        help="Host for SSE or HTTP server"
    )] = "0.0.0.0",

    port: Annotated[int, Option(
        "--port", "-p",
        help="Port for SSE or HTTP server"
    )] = 9000,

    auth_type: Annotated[Optional[str], Option(
        "--auth-type",
        help="Optional auth type. If 'oauth', uses OAuth authentication"
    )] = None,

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

    config_path: Annotated[Optional[str], Option(
        "--config-path", "-c",
        help="Path to JSON config for MCP member servers"
    )] = None,

    disable_composer_tools: Annotated[bool, Option(
        "--disable-composer-tools/--enable-composer-tools",
        help="Disable composer tools (disabled by default)"
    )] = False,

    env: Annotated[Optional[List[str]], Option(
        "--env", "-E",
        help="Environment variables (format: KEY=VALUE). Can be used multiple times."
    )] = None,

    pass_environment: Annotated[bool, Option(
        "--pass-environment/--no-pass-environment",
        help="Pass through all environment variables when spawning all server processes"
    )] = False,

    force: Annotated[bool, Option(
        "--force", "-f",
        help="Force stop the process before restarting"
    )] = False,
) -> None:
    """
    Restart MCP Composer daemon.

    This command stops a running MCP Composer daemon and starts it again with the same configuration.

    Examples:

    \b
    # Restart daemon on port 9000
    mcp-composer composer restart --port 9000

    \b
    # Force restart
    mcp-composer composer restart --port 9000 --force

    \b
    # Restart with new configuration
    mcp-composer composer restart --mode sse --auth-type oauth --port 9000
    """

    # First, try to stop the existing daemon
    typer.echo("Stopping existing MCP Composer daemon...")
    try:
        stop_composer(port=port, force=force)
    except typer.Exit as e:
        if e.exit_code != 0:
            typer.echo("Warning: Could not stop existing daemon")

    # Wait a moment
    time.sleep(1)

    # Start the daemon again
    typer.echo("Starting MCP Composer daemon...")
    start_composer(
        mode=mode,
        instance_id=instance_id,
        endpoint=endpoint,
        script_path=script_path,
        directory=directory,
        host=host,
        port=port,
        auth_type=auth_type,
        sse_url=sse_url,
        remote_auth_type=remote_auth_type,
        client_auth_type=client_auth_type,
        config_path=config_path,
        disable_composer_tools=disable_composer_tools,
        env=env,
        pass_environment=pass_environment,
        daemon=True,
        pid_file=f"/tmp/mcp-composer-{port}.pid",
        log_file=f"/tmp/mcp-composer-{port}.log",
    )
