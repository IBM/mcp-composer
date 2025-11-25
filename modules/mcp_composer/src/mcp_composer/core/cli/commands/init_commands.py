"""
MCP Composer initialization commands.

This module provides commands for initializing new MCP Composer projects:
- init: Initialize a new MCP Composer workspace
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Annotated

import typer
from typer import Option, Argument
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

from mcp_composer.core.utils.logger import LoggerFactory

# Initialize logger and console
logger = LoggerFactory.get_logger()
console = Console()

# Create Typer app for init commands
app = typer.Typer(
    name="init",
    help="MCP Composer project initialization commands",
    rich_markup_mode="rich",
)


@app.command("init")
def init_project(
    project_name: Annotated[Optional[str], Argument(
        help="Name of the project to initialize"
    )] = None,

    defaults: Annotated[bool, Option(
        "--defaults",
        help="Skip interactive prompts and use default values"
    )] = False,

    with_examples: Annotated[bool, Option(
        "--with-examples",
        help="Include example files (sample tool, routes, configs)"
    )] = False,

    with_venv: Annotated[bool, Option(
        "--with-venv",
        help="Create a virtual environment in the project"
    )] = True,

    adapter: Annotated[Optional[str], Option(
        "--adapter",
        help=(
            "Setup variant: 'local' (stdio/local development), "
            "'cloud' (http/sse deployment), or 'api' (openapi/graphql)"
        ),
        case_sensitive=False
    )] = None,

    port: Annotated[int, Option(
        "--port", "-p",
        help="Default port for HTTP/SSE server"
    )] = 9000,

    host: Annotated[str, Option(
        "--host",
        help="Default host for HTTP/SSE server"
    )] = "0.0.0.0",

    server_mode: Annotated[Optional[str], Option(
        "--server-mode",
        help=(
            "Default server mode: http, sse, stdio, openapi, "
            "graphql, local, or client"
        ),
        case_sensitive=False
    )] = None,

    auth_type: Annotated[Optional[str], Option(
        "--auth-type",
        help="Authentication type: oauth or none",
        case_sensitive=False
    )] = None,

    database: Annotated[Optional[str], Option(
        "--database",
        help="Database type: sqlite, postgres, or none",
        case_sensitive=False
    )] = None,

    description: Annotated[Optional[str], Option(
        "--description",
        help="Project description"
    )] = None,

    directory: Annotated[Optional[str], Option(
        "--directory", "-d",
        help="Target directory for project (defaults to project name)"
    )] = None,

    force: Annotated[bool, Option(
        "--force", "-f",
        help="Overwrite existing directory if it exists"
    )] = False,
) -> None:
    """
    Initialize a new MCP Composer workspace.

    This command creates a ready-to-run MCP Composer project with configuration files,
    project structure, and optional examples.

    Examples:

    \b
    # Interactive setup
    mcp-composer init my-project

    \b
    # Quick setup with defaults
    mcp-composer init my-project --defaults

    \b
    # Setup with examples
    mcp-composer init my-project --with-examples

    \b
    # Cloud deployment setup
    mcp-composer init my-project --adapter cloud --mode http --port 8080 --defaults

    \b
    # Local development setup
    mcp-composer init my-project --adapter local --mode stdio --with-examples --defaults

    \b
    # API server setup (OpenAPI)
    mcp-composer init my-api --adapter api --mode openapi --with-examples --defaults

    \b
    # GraphQL setup
    mcp-composer init my-graphql --adapter api --mode graphql --defaults

    \b
    # Setup with authentication
    mcp-composer init my-project --auth-type oauth --mode http --defaults
    """

    # Import here to avoid circular imports
    from ..generators.project_generator import ProjectGenerator

    # Show welcome banner
    if not defaults:
        _show_welcome_banner()

    # Interactive prompts if not using --defaults
    if not defaults:
        config = _interactive_setup(
            project_name, adapter, port, host, server_mode, auth_type, database, description
        )
    else:
        # Use provided values or defaults
        # Determine default mode based on adapter
        default_mode = "stdio"
        if adapter == "local":
            default_mode = "stdio"
        elif adapter == "cloud":
            default_mode = "http"
        elif adapter == "api":
            default_mode = "openapi"

        config = {
            "project_name": project_name or "mcp-project",
            "description": description or "A new MCP Composer project",
            "adapter": adapter or "local",
            "port": port,
            "host": host,
            "mode": server_mode or default_mode,
            "auth_type": auth_type or "none",
            "database": database or "none",
            "with_examples": with_examples,
            "with_venv": with_venv,
        }

    # Determine target directory
    target_dir = Path(directory) if directory else Path(config["project_name"])

    # Check if directory exists
    if target_dir.exists():
        if not force:
            if not defaults and not Confirm.ask(
                f"[yellow]Directory {target_dir} already exists. Overwrite?[/yellow]",
                default=False
            ):
                rprint("[red]❌ Initialization cancelled.[/red]")
                raise typer.Exit(0)
            if defaults:
                rprint(f"[red]❌ Directory {target_dir} already exists. Use --force to overwrite.[/red]")
                raise typer.Exit(1)

        # Remove existing directory
        rprint(f"[yellow]⚠️  Removing existing directory: {target_dir}[/yellow]")
        shutil.rmtree(target_dir)

    # Create project
    try:
        generator = ProjectGenerator(config, target_dir)
        generator.generate()

        # Create virtual environment if requested
        venv_created = False
        if config.get("with_venv", True):
            venv_created = _create_virtual_environment(target_dir)

        # Validate environment
        rprint("\n[cyan]🔍 Validating environment...[/cyan]")
        validation_results = _validate_environment(target_dir)
        _display_validation_results(validation_results)

        # Show success message with next steps
        _show_success_message(config, target_dir, validation_results, venv_created)

    except Exception as e:
        rprint(f"[red]❌ Error initializing project: {e}[/red]")
        logger.exception("Project initialization failed")
        raise typer.Exit(1)


def _show_welcome_banner() -> None:
    """Display welcome banner."""
    banner = """
[bold cyan]╔══════════════════════════════════════════════════════════╗
║                                                          ║
║           🚀 MCP Composer Project Initializer            ║
║                                                          ║
║      Bootstrap a ready-to-run MCP Composer setup        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝[/bold cyan]
    """
    console.print(Panel(banner, border_style="cyan"))


def _interactive_setup(
    project_name: Optional[str],
    adapter: Optional[str],
    port: int,
    host: str,
    server_mode: Optional[str],
    auth_type: Optional[str],
    database: Optional[str],
    description: Optional[str],
) -> Dict:
    """Run interactive setup prompts."""

    rprint("\n[bold cyan]Let's set up your MCP Composer project![/bold cyan]\n")

    # Project name
    if not project_name:
        project_name = Prompt.ask(
            "[cyan]Project name[/cyan]",
            default="mcp-project"
        )

    # Description
    if not description:
        description = Prompt.ask(
            "[cyan]Project description[/cyan]",
            default=f"A new MCP Composer project: {project_name}"
        )

    # Adapter type
    if not adapter:
        adapter = Prompt.ask(
            "[cyan]Setup variant[/cyan]",
            choices=["local", "cloud", "api"],
            default="local"
        )

    # Mode
    if not server_mode:
        if adapter == "local":
            server_mode = Prompt.ask(
                "[cyan]Server mode[/cyan]",
                choices=["stdio", "local", "http", "sse"],
                default="stdio"
            )
        elif adapter == "api":
            server_mode = Prompt.ask(
                "[cyan]Server mode[/cyan]",
                choices=["openapi", "graphql", "http", "sse"],
                default="openapi"
            )
        else:
            server_mode = Prompt.ask(
                "[cyan]Server mode[/cyan]",
                choices=["http", "sse", "openapi", "client"],
                default="http"
            )

    # Port (only for http/sse)
    if server_mode in ["http", "sse"]:
        port = int(Prompt.ask(
            "[cyan]Server port[/cyan]",
            default=str(port)
        ))
        host = Prompt.ask(
            "[cyan]Server host[/cyan]",
            default=host
        )

    # Authentication
    if not auth_type:
        auth_type = Prompt.ask(
            "[cyan]Authentication type[/cyan]",
            choices=["none", "oauth"],
            default="none"
        )

    # Database
    if not database:
        database = Prompt.ask(
            "[cyan]Database type[/cyan]",
            choices=["none", "sqlite", "postgres"],
            default="none"
        )

    # Examples
    with_examples = Confirm.ask(
        "[cyan]Include example files?[/cyan]",
        default=True
    )

    return {
        "project_name": project_name,
        "description": description,
        "adapter": adapter,
        "port": port,
        "host": host,
        "mode": server_mode,
        "auth_type": auth_type,
        "database": database,
        "with_examples": with_examples,
    }


def _validate_environment(target_dir: Path) -> Dict[str, Dict]:
    """Validate environment after project creation."""
    results = {
        "dependencies": {},
        "paths": {},
        "permissions": {},
    }

    # Check Python version
    python_version = sys.version_info
    results["dependencies"]["python"] = {
        "status": "ok" if python_version >= (3, 11) else "warning",
        "message": f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
        "required": "Python 3.11+"
    }

    # Check if uv is available
    uv_available = shutil.which("uv") is not None
    results["dependencies"]["uv"] = {
        "status": "ok" if uv_available else "warning",
        "message": "uv package manager" + (" found" if uv_available else " not found"),
        "required": "uv (recommended)"
    }

    # Check if git is available
    git_available = shutil.which("git") is not None
    results["dependencies"]["git"] = {
        "status": "ok" if git_available else "info",
        "message": "git" + (" found" if git_available else " not found"),
        "required": "git (optional)"
    }

    # Check if project directory is writable
    results["paths"]["project_dir"] = {
        "status": "ok" if os.access(target_dir, os.W_OK) else "error",
        "message": f"Project directory: {target_dir}",
        "required": "Writable project directory"
    }

    # Check if config files exist
    config_file = target_dir / "config" / "config.json"
    results["paths"]["config_file"] = {
        "status": "ok" if config_file.exists() else "error",
        "message": f"Config file: {config_file}",
        "required": "Configuration file"
    }

    # Check permissions
    results["permissions"]["read"] = {
        "status": "ok" if os.access(target_dir, os.R_OK) else "error",
        "message": "Read permission",
        "required": "Read access"
    }

    results["permissions"]["write"] = {
        "status": "ok" if os.access(target_dir, os.W_OK) else "error",
        "message": "Write permission",
        "required": "Write access"
    }

    results["permissions"]["execute"] = {
        "status": "ok" if os.access(target_dir, os.X_OK) else "error",
        "message": "Execute permission",
        "required": "Execute access"
    }

    return results


def _display_validation_results(results: Dict[str, Dict]) -> None:
    """Display validation results in a formatted way."""

    def _get_status_icon(status: str) -> str:
        return {
            "ok": "✅",
            "warning": "⚠️",
            "info": "ℹ️",
            "error": "❌"
        }.get(status, "❓")

    for category, checks in results.items():
        rprint(f"\n[bold cyan]{category.title()}:[/bold cyan]")
        for check in checks.values():
            icon = _get_status_icon(check["status"])
            rprint(f"  {icon} {check['message']}")


def _create_virtual_environment(target_dir: Path) -> bool:
    """Create a virtual environment in the project directory."""
    try:
        rprint("\n[cyan]🔧 Creating virtual environment...[/cyan]")

        # Check if uv is available
        if shutil.which("uv"):
            result = subprocess.run(
                ["uv", "venv"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                rprint("[green]  ✅ Virtual environment created with uv[/green]")
                return True
            rprint(f"[yellow]  ⚠️  uv venv failed: {result.stderr}[/yellow]")
            return False

        # Fallback to python -m venv
        result = subprocess.run(
            ["python3", "-m", "venv", ".venv"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            rprint("[green]  ✅ Virtual environment created with python3 -m venv[/green]")
            return True
        rprint(f"[yellow]  ⚠️  venv creation failed: {result.stderr}[/yellow]")
        return False
    except Exception as e:
        rprint(f"[yellow]  ⚠️  Could not create virtual environment: {e}[/yellow]")
        return False


def _show_success_message(config: Dict, target_dir: Path, validation_results: Dict, venv_created: bool = False) -> None:
    """Display success message with next steps."""

    # Check if there were any errors
    has_errors = any(
        check["status"] == "error"
        for category in validation_results.values()
        for check in category.values()
    )

    if has_errors:
        rprint(
            "\n[yellow]⚠️  Project initialized with some issues. "
            "Please review the validation results above.[/yellow]"
        )
    else:
        rprint("\n[bold green]✅ Project initialized successfully![/bold green]")

    # Build next steps
    next_steps = []

    # Step 1: Navigate to project
    next_steps.append(f"cd {target_dir}")

    # Step 2: Create/activate virtual environment
    if venv_created:
        next_steps.append(
            "source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate"
        )
        next_steps.append("uv pip install -e .")
    else:
        next_steps.append("# Create virtual environment:")
        if validation_results["dependencies"]["uv"]["status"] == "ok":
            next_steps.append("uv venv")
            next_steps.append(
                "source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate"
            )
            next_steps.append("uv pip install -e .")
        else:
            next_steps.append("python3 -m venv .venv")
            next_steps.append(
                "source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate"
            )
            next_steps.append("pip install -r requirements.txt")

    # Step 4: Start the server
    mode = config.get("mode", "http")
    if mode == "stdio":
        next_steps.append(
            "mcp-composer run --mode stdio --script-path server.py "
            "--config-path config/config.json"
        )
    elif mode == "sse":
        next_steps.append(
            f"mcp-composer run --mode sse --host {config['host']} "
            f"--port {config['port']} --config-path config/config.json"
        )
    else:  # http
        next_steps.append(
            f"mcp-composer run --mode http --host {config['host']} "
            f"--port {config['port']} --config-path config/config.json"
        )

    # Step 5: Additional info
    if config.get("mode") in ["http", "sse"]:
        next_steps.append(f"# Visit: http://{config['host']}:{config['port']}")

    if config.get("with_examples"):
        next_steps.append("# Check examples/ directory for sample configurations")

    # Display next steps
    steps_text = "\n".join(
        f"  {i}. {step}" if not step.startswith("#") else f"     {step}"
        for i, step in enumerate([s for s in next_steps if not s.startswith("#")], 1)
    )

    # Add comments
    for step in next_steps:
        if step.startswith("#"):
            steps_text += f"\n     {step}"

    panel = Panel(
        f"""[bold cyan]Next steps:[/bold cyan]

{steps_text}

[bold cyan]Project Details:[/bold cyan]
  • Name: {config['project_name']}
  • Mode: {config['mode']}
  • Adapter: {config['adapter']}
  • Auth: {config['auth_type']}
  • Database: {config['database']}
  • Examples: {"Yes" if config.get('with_examples') else "No"}

[dim]Need help? Run: mcp-composer --help[/dim]
        """,
        title="🎉 Setup Complete",
        border_style="green",
        padding=(1, 2)
    )

    console.print(panel)


if __name__ == "__main__":
    app()
