"""
Middleware management commands for MCP Composer CLI.

This module provides commands for managing middleware configurations:
- validate: Validate middleware configuration files
- list: List middlewares from configuration files
- add: Add or update middleware in configuration files
"""

import importlib
import json
from pathlib import Path
from typing import Optional, List, Annotated

import typer
from typer import Option, Argument
from pydantic import ValidationError

from mcp_composer.core.middleware.middleware_config import (
    load_and_validate_config,
    MiddlewareConfig,
    MiddlewareSettings,
    MiddlewareEntry,
    Conditions,
)
from mcp_composer.core.middleware.middleware_manager import MiddlewareManager
from mcp_composer.core.utils.logger import LoggerFactory

# Initialize logger
logger = LoggerFactory.get_logger()

# Create Typer app for middleware commands
app = typer.Typer(
    name="middleware",
    help="Middleware management commands",
    add_completion=False,
    rich_markup_mode="rich",
)


def _print_error(msg: str) -> None:
    """Print error message to stderr."""
    typer.echo(f"ERROR: {msg}", err=True)


def _print_validation_error(e: ValidationError) -> None:
    """Print validation error details."""
    _print_error("Config validation failed:")
    try:
        details = e.errors()
    except Exception:
        _print_error(str(e))
        return
    for i, err in enumerate(details, start=1):
        loc = ".".join(str(p) for p in err.get("loc", []))
        typ = err.get("type", "value_error")
        msg = err.get("msg", "Invalid value")
        _print_error(f"  {i:02d}. {loc} [{typ}] - {msg}")


def _parse_csv(value: Optional[str]) -> List[str]:
    """Parse comma-separated values."""
    if value is None:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]


def _load_json_file(path: str) -> dict:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json_file(path: str, obj: dict) -> None:
    """Save JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


@app.command("validate")
def validate_middleware(
    path: Annotated[str, Argument(help="Path to middleware configuration file")],
    ensure_imports: Annotated[bool, Option(
        "--ensure-imports",
        help="Ensure all middleware classes can be imported"
    )] = False,
    output_format: Annotated[str, Option(
        "--format", "-f",
        help="Output format",
        case_sensitive=False
    )] = "text",
    show_middlewares: Annotated[bool, Option(
        "--show-middlewares",
        help="Show enabled middlewares in execution order"
    )] = False,
) -> None:
    """
    Validate middleware configuration file.

    This command validates the structure and content of a middleware configuration file,
    ensuring it follows the correct schema and optionally verifying that all middleware
    classes can be imported.

    Examples:

    \b
    # Basic validation
    mcp-composer middleware validate middleware-config.json

    \b
    # Validate with import checking
    mcp-composer middleware validate middleware-config.json --ensure-imports

    \b
    # Validate and show execution order
    mcp-composer middleware validate middleware-config.json --show-middlewares

    \b
    # JSON output format
    mcp-composer middleware validate middleware-config.json --format json
    """

    try:
        load_and_validate_config(path, ensure_imports=ensure_imports)
    except FileNotFoundError as exc:
        _print_error(f"File not found: {path}")
        raise typer.Exit(2) from exc
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {path}: {je}")
        raise typer.Exit(2) from je
    except ValidationError as ve:
        _print_validation_error(ve)
        raise typer.Exit(1) from ve
    except (ImportError, AttributeError) as ie:
        _print_error(f"Import check failed: {ie}")
        raise typer.Exit(1) from ie

    if output_format == "json":
        typer.echo(json.dumps({"status": "ok"}, indent=2))
    else:
        typer.echo("✔ Config is valid")

    if show_middlewares:
        # Show execution order (enabled only), if manager is available
        if MiddlewareManager is not None:
            mgr = MiddlewareManager(path, ensure_imports=False)
            typer.echo("\nEnabled middlewares (in execution order):")
            for info in mgr.describe():
                hooks = ", ".join(info.get("applied_hooks", []))
                typer.echo(f" - {info['name']}  (priority={info['priority']}, hooks=[{hooks}])")
        else:
            typer.echo("\n(Manager not available; cannot compute execution order)")


@app.command("list")
def list_middlewares(
    config: Annotated[str, Argument(help="Path to middleware configuration file")],
    ensure_imports: Annotated[bool, Option(
        "--ensure-imports",
        help="Ensure all middleware classes can be imported"
    )] = False,
    output_format: Annotated[str, Option(
        "--format", "-f",
        help="Output format",
        case_sensitive=False
    )] = "text",
    show_all: Annotated[bool, Option(
        "--all",
        help="Show all middlewares including disabled ones"
    )] = False,
) -> None:
    """
    List middlewares from configuration file.

    This command lists all middlewares defined in a configuration file, showing
    their status, priority, and execution order.

    Examples:

    \b
    # List enabled middlewares
    mcp-composer middleware list middleware-config.json

    \b
    # List all middlewares including disabled
    mcp-composer middleware list middleware-config.json --all

    \b
    # JSON output format
    mcp-composer middleware list middleware-config.json --format json

    \b
    # List with import checking
    mcp-composer middleware list middleware-config.json --ensure-imports
    """

    # Load and validate (optionally ensure imports)
    try:
        cfg = load_and_validate_config(config, ensure_imports=ensure_imports)
    except FileNotFoundError as exc:
        _print_error(f"File not found: {config}")
        raise typer.Exit(2) from exc
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {config}: {je}")
        raise typer.Exit(2) from je
    except ValidationError as ve:
        _print_validation_error(ve)
        raise typer.Exit(1) from ve
    except (ImportError, AttributeError) as ie:
        _print_error(f"Import check failed: {ie}")
        raise typer.Exit(1) from ie

    include_disabled = show_all

    # Prefer manager for true runtime order (enabled only)
    items_out: List[dict] = []
    if MiddlewareManager is not None:
        mgr = MiddlewareManager(config, ensure_imports=False)
        runtime = {d["name"]: d for d in mgr.describe()}  # enabled only, ordered
        # Merge with raw config if --all requested
        if include_disabled:
            for m in sorted(cfg.middleware, key=lambda x: x.priority):
                d = {
                    "name": m.name,
                    "mode": m.mode,
                    "priority": m.priority,
                    "applied_hooks": [getattr(h, "value", h) for h in m.applied_hooks],
                    "kind": m.kind,
                    "attached": runtime.get(m.name, {}).get("attached", False),
                }
                items_out.append(d)
        else:
            # Only enabled ones in execution order
            for d in mgr.describe():  # already ordered
                # find original entry to enrich with mode/kind
                mm = next((m for m in cfg.middleware if m.name == d["name"]), None)
                items_out.append({
                    **d,
                    "mode": getattr(mm, "mode", "enabled"),
                    "kind": getattr(mm, "kind", "<unknown>"),
                })
    else:
        # Fallback: list by priority from config (no runtime wrapping)
        for m in sorted(cfg.middleware, key=lambda x: x.priority):
            if not include_disabled and m.mode != "enabled":
                continue
            items_out.append({
                "name": m.name,
                "mode": m.mode,
                "priority": m.priority,
                "applied_hooks": [getattr(h, "value", h) for h in m.applied_hooks],
                "kind": m.kind,
                "attached": None,
            })

    if output_format == "json":
        typer.echo(json.dumps({"middlewares": items_out}, indent=2))
    else:
        if not items_out:
            typer.echo("(no middlewares)")
            return
        typer.echo("Middlewares" + (" (all)" if include_disabled else " (enabled)") + ":")
        for it in items_out:
            hooks = ", ".join(it.get("applied_hooks", []))
            mode = it.get("mode", "enabled")
            attached = it.get("attached")
            flag = "✓" if (attached or (attached is None and mode == "enabled")) else " "
            typer.echo(f"[{flag}] {it['name']}  prio={it['priority']}  mode={mode}")
            typer.echo(f"     kind={it.get('kind','')}")
            typer.echo(f"     hooks=[{hooks}]")


@app.command("add")
def add_middleware(
    config: Annotated[str, Option(
        "--config", "-c",
        help="Path to middleware configuration file"
    )],
    name: Annotated[str, Option(
        "--name", "-n",
        help="Name of the middleware"
    )],
    kind: Annotated[str, Option(
        "--kind", "-k",
        help="Python import path to middleware class (e.g., module.ClassName)"
    )],
    description: Annotated[Optional[str], Option(
        "--description", "-d",
        help="Description of the middleware"
    )] = None,
    version: Annotated[Optional[str], Option(
        "--version", "-v",
        help="Version of the middleware (default: 0.0.0)"
    )] = None,
    mode: Annotated[str, Option(
        "--mode", "-m",
        help="Middleware mode",
        case_sensitive=False
    )] = "enabled",
    priority: Annotated[int, Option(
        "--priority", "-p",
        help="Execution priority (lower numbers run first, default: 100)"
    )] = 100,
    applied_hooks: Annotated[Optional[str], Option(
        "--applied-hooks",
        help="Comma-separated list of hooks (e.g., on_call_tool,on_list_tools)"
    )] = None,
    include_tools: Annotated[Optional[str], Option(
        "--include-tools",
        help="Comma-separated list of tools to include (default: *)"
    )] = None,
    exclude_tools: Annotated[Optional[str], Option(
        "--exclude-tools",
        help="Comma-separated list of tools to exclude"
    )] = None,
    include_prompts: Annotated[Optional[str], Option(
        "--include-prompts",
        help="Comma-separated list of prompts to include"
    )] = None,
    exclude_prompts: Annotated[Optional[str], Option(
        "--exclude-prompts",
        help="Comma-separated list of prompts to exclude"
    )] = None,
    include_server_ids: Annotated[Optional[str], Option(
        "--include-server-ids",
        help="Comma-separated list of server IDs to include"
    )] = None,
    exclude_server_ids: Annotated[Optional[str], Option(
        "--exclude-server-ids",
        help="Comma-separated list of server IDs to exclude"
    )] = None,
    config_file: Annotated[Optional[str], Option(
        "--config-file",
        help="Path to JSON file containing middleware configuration"
    )] = None,
    update: Annotated[bool, Option(
        "--update",
        help="Update existing middleware if name already exists"
    )] = False,
    ensure_imports: Annotated[bool, Option(
        "--ensure-imports",
        help="Ensure all middleware classes can be imported after update"
    )] = False,
    dry_run: Annotated[bool, Option(
        "--dry-run",
        help="Show what would be written without actually writing"
    )] = False,
    show_middlewares: Annotated[bool, Option(
        "--show-middlewares",
        help="Show enabled middlewares in execution order after update"
    )] = False,
) -> None:
    """
    Add or update middleware in configuration file.

    This command adds a new middleware to a configuration file or updates an existing one.
    It supports comprehensive configuration options for middleware behavior and conditions.

    Examples:

    \b
    # Add a simple middleware
    mcp-composer middleware add --config middleware-config.json \\
        --name Logger \\
        --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware

    \b
    # Add middleware with custom priority and hooks
    mcp-composer middleware add --config middleware-config.json \\
        --name RateLimiter \\
        --kind mcp_composer.middleware.rate_limit_filter.RateLimitingMiddleware \\
        --priority 10 --applied-hooks on_call_tool

    \b
    # Add middleware with tool filtering
    mcp-composer middleware add --config middleware-config.json \\
        --name PIIFilter \\
        --kind mcp_composer.middleware.pii_middleware.SecretsAndPIIMiddleware \\
        --include-tools get_data --exclude-tools get_prompts

    \b
    # Update existing middleware
    mcp-composer middleware add --config middleware-config.json \\
        --name Logger \\
        --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware \\
        --update

    \b
    # Dry run to see what would be added
    mcp-composer middleware add --config middleware-config.json \\
        --name TestMiddleware --kind test.middleware.TestMiddleware --dry-run
    """

    # Validate mode
    if mode not in ["enabled", "disabled"]:
        raise typer.BadParameter(f"Invalid mode '{mode}'. Must be 'enabled' or 'disabled'")

    # Load existing or init new
    try:
        existing = _load_json_file(config)
        cfg = MiddlewareConfig.model_validate(existing)
    except FileNotFoundError:
        cfg = MiddlewareConfig(middleware=[], middleware_settings=MiddlewareSettings())
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {config}: {je}")
        raise typer.Exit(2)
    except ValidationError as ve:
        _print_error("Existing config is invalid; fix it before adding new middleware.")
        _print_validation_error(ve)
        raise typer.Exit(1)

    # Build entry
    applied_hooks_list = _parse_csv(applied_hooks)
    include_tools_list = _parse_csv(include_tools) or ["*"]
    exclude_tools_list = _parse_csv(exclude_tools)
    include_prompts_list = _parse_csv(include_prompts)
    exclude_prompts_list = _parse_csv(exclude_prompts)
    include_server_ids_list = _parse_csv(include_server_ids)
    exclude_server_ids_list = _parse_csv(exclude_server_ids)

    if config_file:
        try:
            entry_config = _load_json_file(config_file)
            if not isinstance(entry_config, dict):
                raise ValueError("config file must contain a JSON object")
        except Exception as e:
            _print_error(f"Could not read --config-file: {e}")
            raise typer.Exit(2)
    else:
        entry_config = {}

    try:
        entry = MiddlewareEntry(
            name=name,
            description=description or "",
            version=version or "0.0.0",
            kind=kind,
            mode=mode,
            priority=priority,
            applied_hooks=applied_hooks_list,
            conditions=Conditions(
                include_tools=include_tools_list,
                exclude_tools=exclude_tools_list,
                include_prompts=include_prompts_list,
                exclude_prompts=exclude_prompts_list,
                include_server_ids=include_server_ids_list,
                exclude_server_ids=exclude_server_ids_list,
            ),
            config=entry_config,
        )
    except ValidationError as ve:
        _print_error("New middleware entry is invalid:")
        _print_validation_error(ve)
        raise typer.Exit(1)

    # Upsert
    items = list(cfg.middleware)
    names = [m.name for m in items]
    if entry.name in names:
        if not update:
            _print_error(
                f"Middleware with name '{entry.name}' already exists. "
                "Use --update to overwrite."
            )
            raise typer.Exit(1)
        idx = names.index(entry.name)
        items[idx] = entry
    else:
        items.append(entry)

    # Revalidate whole config & ensure imports (optional)
    new_cfg = MiddlewareConfig(middleware=items, middleware_settings=cfg.middleware_settings)

    if ensure_imports:
        try:
            for m in new_cfg.middleware:
                mod, clsname = m.kind.rsplit(".", 1)
                module = importlib.import_module(mod)
                getattr(module, clsname)
        except (ImportError, AttributeError) as ie:
            _print_error(f"Import check failed: {ie}")
            raise typer.Exit(1)

    # Sort & write (or dry-run)
    new_cfg.middleware.sort(key=lambda m: m.priority)

    if dry_run:
        typer.echo(json.dumps(new_cfg.model_dump(mode="json"), indent=2))
        return

    _save_json_file(config, new_cfg.model_dump(mode="json"))
    typer.echo(f"✔ Middleware '{entry.name}' {'updated' if entry.name in names and update else 'added'} in {config}")

    if show_middlewares and MiddlewareManager is not None:
        mgr = MiddlewareManager(config, ensure_imports=False)
        typer.echo("\nEnabled middlewares (in execution order):")
        for info in mgr.describe():
            hooks = ", ".join(info.get("applied_hooks", []))
            typer.echo(f" - {info['name']}  (priority={info['priority']}, hooks=[{hooks}])")


@app.command("remove")
def remove_middleware(
    config: Annotated[str, Option(
        "--config", "-c",
        help="Path to middleware configuration file"
    )],
    name: Annotated[str, Option(
        "--name", "-n",
        help="Name of the middleware to remove"
    )],
    dry_run: Annotated[bool, Option(
        "--dry-run",
        help="Show what would be removed without actually removing"
    )] = False,
) -> None:
    """
    Remove middleware from configuration file.

    This command removes a middleware from a configuration file by name.

    Examples:

    \b
    # Remove a middleware
    mcp-composer middleware remove --config middleware-config.json --name Logger

    \b
    # Dry run to see what would be removed
    mcp-composer middleware remove --config middleware-config.json --name Logger --dry-run
    """

    # Load existing config
    try:
        existing = _load_json_file(config)
        cfg = MiddlewareConfig.model_validate(existing)
    except FileNotFoundError as exc:
        _print_error(f"File not found: {config}")
        raise typer.Exit(2) from exc
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {config}: {je}")
        raise typer.Exit(2) from je
    except ValidationError as ve:
        _print_error("Config is invalid; fix it before removing middleware.")
        _print_validation_error(ve)
        raise typer.Exit(1) from ve

    # Find and remove middleware
    items = list(cfg.middleware)
    names = [m.name for m in items]

    if name not in names:
        _print_error(f"Middleware with name '{name}' not found in {config}")
        raise typer.Exit(1)

    idx = names.index(name)
    removed_middleware = items.pop(idx)

    if dry_run:
        typer.echo(f"Would remove middleware: {removed_middleware.name}")
        typer.echo(f"  Kind: {removed_middleware.kind}")
        typer.echo(f"  Priority: {removed_middleware.priority}")
        return

    # Save updated config
    new_cfg = MiddlewareConfig(middleware=items, middleware_settings=cfg.middleware_settings)
    _save_json_file(config, new_cfg.model_dump(mode="json"))
    typer.echo(f"✔ Middleware '{name}' removed from {config}")


@app.command("init")
def init_middleware_config(
    config: Annotated[str, Option(
        "--config", "-c",
        help="Path to middleware configuration file to create"
    )],
    force: Annotated[bool, Option(
        "--force", "-f",
        help="Overwrite existing file if it exists"
    )] = False,
) -> None:
    """
    Initialize a new middleware configuration file.

    This command creates a new middleware configuration file with default settings.

    Examples:

    \b
    # Create a new middleware config file
    mcp-composer middleware init --config middleware-config.json

    \b
    # Overwrite existing file
    mcp-composer middleware init --config middleware-config.json --force
    """

    # Check if file exists
    if Path(config).exists() and not force:
        _print_error(f"File {config} already exists. Use --force to overwrite.")
        raise typer.Exit(1)

    # Create default configuration
    default_config = MiddlewareConfig(
        middleware=[],
        middleware_settings=MiddlewareSettings()
    )

    # Save the file
    _save_json_file(config, default_config.model_dump(mode="json"))
    typer.echo(f"✔ Created new middleware configuration file: {config}")
    typer.echo("You can now add middlewares using the 'add' command.")
