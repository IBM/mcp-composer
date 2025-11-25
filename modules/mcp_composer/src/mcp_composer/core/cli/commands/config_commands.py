"""
Unified configuration commands for MCP Composer CLI using Typer.
"""

import asyncio
import json
from typing import Optional, List

import typer
from typer import Option, Argument
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from mcp_composer.core.config.config_loader import ConfigManager
from mcp_composer.core.config.unified_config import ConfigSection, ConfigValidationError
from mcp_composer.core.utils.logger import LoggerFactory

# Initialize logger and console
logger = LoggerFactory.get_logger()
console = Console()

# Create Typer app for config commands
app = typer.Typer(
    name="config",
    help="Unified configuration management commands",
    rich_markup_mode="rich",
)


@app.command("validate")
def validate_config(
    configfilepath: str = Argument(..., help="Path to the configuration file to validate"),
    ensure_imports: bool = Option(False, "--ensure-imports", help="Ensure all middleware classes can be imported")
) -> None:
    """Validate a configuration file for syntax and schema errors."""
    try:
        config_manager = ConfigManager()
        is_valid = config_manager.validate_config_file(configfilepath)

        if is_valid:
            rprint("✅ [green]Configuration file is valid[/green]")
            if ensure_imports:
                rprint("✅ [green]All middleware imports verified[/green]")
        else:
            rprint("❌ [red]Configuration file is invalid[/red]")
            raise typer.Exit(1)

    except ConfigValidationError as e:
        rprint(f"❌ [red]Configuration validation failed: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"❌ [red]Error validating configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command("show")
def show_config(
    configfilepath: str = Argument(..., help="Path to the configuration file to show"),
    section: Optional[str] = Option(None, "--section", "-s", help="Show only a specific section (servers, middleware, prompts, tools)"),
    config_format: str = Option("table", "--format", "-f", help="Output format (table, json)")
) -> None:
    """Show configuration file contents in a formatted way."""
    try:
        config_manager = ConfigManager()
        config = config_manager.loader.load_from_file(configfilepath)

        # Convert to dict for JSON serialization
        config_dict = config.model_dump()

        if config_format == "json":
            rprint(json.dumps(config_dict, indent=2))
            return

        if section:
            _show_section(config_dict, section)
        else:
            _show_all_sections(config_dict)

    except ConfigValidationError as e:
        rprint(f"❌ [red]Configuration validation failed: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"❌ [red]Error showing configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command("apply")
def apply_config(
    configfilepath: str = Argument(..., help="Path to the configuration file to apply"),
    config: str = Option("all", "--config", "-c", help="Which configuration sections to apply (servers, middleware, prompts, tools, all)"),
    dry_run: bool = Option(False, "--dry-run", help="Show what would be applied without actually applying")
) -> None:
    """Apply configuration to MCP Composer."""
    try:
        # Parse sections to apply
        sections = None
        if config != "all":
            try:
                sections = [ConfigSection(config)]
            except ValueError:
                rprint(f"❌ [red]Invalid config section: {config}[/red]")
                rprint(f"Valid sections: {', '.join([s.value for s in ConfigSection])}")
                raise typer.Exit(1)

        if dry_run:
            rprint("🔍 [yellow]Dry run mode - showing what would be applied:[/yellow]")
            _show_dry_run(configfilepath, sections)
            return

        # Create a mock composer for now (in real implementation, this would be passed in)
        config_manager = ConfigManager()

        # Load and apply configuration
        results = asyncio.run(config_manager.load_and_apply(configfilepath, sections))

        # Display results
        _display_apply_results(results)

    except ConfigValidationError as e:
        rprint(f"❌ [red]Configuration validation failed: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"❌ [red]Error applying configuration: {e}[/red]")
        raise typer.Exit(1)


def _show_section(config_dict: dict, section: str) -> None:
    """Show a specific section of the configuration."""
    if section == "servers" and config_dict.get("servers"):
        _show_servers_table(config_dict["servers"])
    elif section == "middleware" and config_dict.get("middleware"):
        _show_middleware_table(config_dict["middleware"])
    elif section == "prompts" and config_dict.get("prompts"):
        _show_prompts_table(config_dict["prompts"])
    elif section == "tools" and config_dict.get("tools"):
        _show_tools_table(config_dict["tools"])
    else:
        rprint(f"❌ [red]No {section} section found in configuration[/red]")
        raise typer.Exit(1)


def _show_all_sections(config_dict: dict) -> None:
    """Show all sections of the configuration."""
    rprint("\n[bold blue]Configuration Overview[/bold blue]")

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
        rprint("\n[bold green]Servers[/bold green]")
        _show_servers_table(config_dict["servers"])

    if config_dict.get("middleware"):
        rprint("\n[bold green]Middleware[/bold green]")
        _show_middleware_table(config_dict["middleware"])

    if config_dict.get("prompts"):
        rprint("\n[bold green]Prompts[/bold green]")
        _show_prompts_table(config_dict["prompts"])

    if config_dict.get("tools"):
        rprint("\n[bold green]Tools[/bold green]")
        _show_tools_table(config_dict["tools"])


def _show_servers_table(servers: list) -> None:
    """Show servers in a table format."""
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
            server.get("label", "")
        )

    console.print(table)


def _show_middleware_table(middleware: list) -> None:
    """Show middleware in a table format."""
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
            str(mw.get("priority", ""))
        )

    console.print(table)


def _show_prompts_table(prompts: list) -> None:
    """Show prompts in a table format."""
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Template", style="yellow")
    table.add_column("Arguments", style="blue")

    for prompt in prompts:
        args_count = len(prompt.get("arguments", []) or [])
        template_preview = prompt.get("template", "")[:50] + "..." if len(prompt.get("template", "")) > 50 else prompt.get("template", "")
        table.add_row(
            prompt.get("name", ""),
            prompt.get("description", ""),
            template_preview,
            str(args_count)
        )

    console.print(table)


def _show_tools_table(tools: dict) -> None:
    """Show tools in a table format."""
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("OpenAPI Version", style="yellow")
    table.add_column("Paths", style="blue")

    for tool_name, tool_config in tools.items():
        tool_type = "OpenAPI" if tool_config.get("openapi") else "Custom"
        openapi_version = tool_config.get("openapi", "N/A")
        paths_count = len(tool_config.get("paths", {}))

        table.add_row(
            tool_name,
            tool_type,
            str(openapi_version),
            str(paths_count)
        )

    console.print(table)


def _show_dry_run(configfilepath: str, sections: Optional[List[ConfigSection]]) -> None:
    """Show what would be applied in dry run mode."""
    try:
        config_manager = ConfigManager()
        config = config_manager.loader.load_from_file(configfilepath)

        rprint(f"\n[bold]Configuration file:[/bold] {configfilepath}")

        if sections is None:
            sections = [ConfigSection.SERVERS, ConfigSection.MIDDLEWARE, ConfigSection.PROMPTS, ConfigSection.TOOLS]

        for section in sections:
            if section == ConfigSection.SERVERS and config.servers:
                rprint(f"\n[bold green]Would apply {len(config.servers)} servers:[/bold green]")
                for server in config.servers:
                    rprint(f"  - {server.id} ({server.type})")

            elif section == ConfigSection.MIDDLEWARE and config.middleware:
                rprint(f"\n[bold green]Would apply {len(config.middleware)} middleware:[/bold green]")
                for mw in config.middleware:
                    rprint(f"  - {mw.name} ({mw.kind})")

            elif section == ConfigSection.PROMPTS and config.prompts:
                rprint(f"\n[bold green]Would apply {len(config.prompts)} prompts:[/bold green]")
                for prompt in config.prompts:
                    rprint(f"  - {prompt.name}")

            elif section == ConfigSection.TOOLS and config.tools:
                rprint(f"\n[bold green]Would apply {len(config.tools)} tools:[/bold green]")
                for tool_name in config.tools.keys():
                    rprint(f"  - {tool_name}")

    except Exception as e:
        rprint(f"❌ [red]Error in dry run: {e}[/red]")
        raise typer.Exit(1)


def _display_apply_results(results: dict) -> None:
    """Display the results of applying configuration."""
    rprint("\n[bold blue]Configuration Applied Successfully[/bold blue]")

    for section, result in results.items():
        rprint(f"\n[bold green]{section.title()}:[/bold green]")
        rprint(f"  Total: {result.get('total', 0)}")
        rprint(f"  Registered: {len(result.get('registered', []))}")
        rprint(f"  Failed: {len(result.get('failed', []))}")

        if result.get('failed'):
            rprint("  [red]Failures:[/red]")
            for failure in result['failed']:
                rprint(f"    - {failure}")


if __name__ == "__main__":
    app()
