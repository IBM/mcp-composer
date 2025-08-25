from __future__ import annotations
from mcp_composer.core.middleware.middleware_config import (
    load_and_validate_config,
    export_json_schema,
)
from mcp_composer.core.middleware.middleware_manager import MiddlewareManager
from mcp_composer.core.middleware.middleware_config import MiddlewareConfig, MiddlewareSettings, MiddlewareEntry, Conditions
import argparse
import json
from pydantic import ValidationError
import sys


from typing import Any, List
def _print_error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _print_validation_error(e: ValidationError) -> None:
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


def _parse_csv(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        out: List[str] = []
        for v in value:
            out.extend([s.strip() for s in str(v).split(",") if s.strip()])
        return out
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json_file(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


# ---------------------------
# Commands
# ---------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    try:
        cfg = load_and_validate_config(args.path, ensure_imports=args.ensure_imports)
    except FileNotFoundError:
        _print_error(f"File not found: {args.path}")
        return 2
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {args.path}: {je}")
        return 2
    except ValidationError as ve:
        _print_validation_error(ve)
        return 1
    except (ImportError, AttributeError) as ie:
        _print_error(f"Import check failed: {ie}")
        return 1

    if args.format == "json":
        print(json.dumps({"status": "ok"}, indent=2))
    else:
        print("✔ Config is valid")

    if args.show_middlewares:
        # Show execution order (enabled only), if manager is available
        if MiddlewareManager is not None:
            mgr = MiddlewareManager(args.path, ensure_imports=False)
            print("\nEnabled middlewares (in execution order):")
            for info in mgr.describe():
                hooks = ", ".join(info.get("applied_hooks", []))
                print(f" - {info['name']}  (priority={info['priority']}, hooks=[{hooks}])")
        else:
            print("\n(Manager not available; cannot compute execution order)")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    # Load and validate (optionally ensure imports)
    try:
        cfg = load_and_validate_config(args.config, ensure_imports=args.ensure_imports)
    except FileNotFoundError:
        _print_error(f"File not found: {args.config}")
        return 2
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {args.config}: {je}")
        return 2
    except ValidationError as ve:
        _print_validation_error(ve)
        return 1
    except (ImportError, AttributeError) as ie:
        _print_error(f"Import check failed: {ie}")
        return 1

    include_disabled = args.all

    # Prefer manager for true runtime order (enabled only)
    items_out: List[dict] = []
    if MiddlewareManager is not None:
        mgr = MiddlewareManager(args.config, ensure_imports=False)
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

    if args.format == "json":
        print(json.dumps({"middlewares": items_out}, indent=2))
    else:
        if not items_out:
            print("(no middlewares)")
            return 0
        print("Middlewares" + (" (all)" if include_disabled else " (enabled)") + ":")
        for it in items_out:
            hooks = ", ".join(it.get("applied_hooks", []))
            mode = it.get("mode", "enabled")
            attached = it.get("attached")
            flag = "✓" if (attached or (attached is None and mode == "enabled")) else " "
            print(f"[{flag}] {it['name']}  prio={it['priority']}  mode={mode}")
            print(f"     kind={it.get('kind','')}")
            print(f"     hooks=[{hooks}]")
    return 0


def cmd_add_middleware(args: argparse.Namespace) -> int:
    # Load existing or init new
    try:
        existing = _load_json_file(args.config)
        cfg = MiddlewareConfig.model_validate(existing)
    except FileNotFoundError:
        cfg = MiddlewareConfig(middleware=[], middleware_settings=MiddlewareSettings())
    except json.JSONDecodeError as je:
        _print_error(f"Invalid JSON in {args.config}: {je}")
        return 2
    except ValidationError as ve:
        _print_error("Existing config is invalid; fix it before adding new middleware.")
        _print_validation_error(ve)
        return 1

    # Build entry
    applied_hooks = _parse_csv(args.applied_hooks)
    include_tools = _parse_csv(args.include_tools) or ["*"]
    exclude_tools = _parse_csv(args.exclude_tools)
    include_prompts = _parse_csv(args.include_prompts)
    exclude_prompts = _parse_csv(args.exclude_prompts)
    include_server_ids = _parse_csv(args.include_server_ids)
    exclude_server_ids = _parse_csv(args.exclude_server_ids)

    if args.config_file:
        try:
            entry_config = _load_json_file(args.config_file)
            if not isinstance(entry_config, dict):
                raise ValueError("config file must contain a JSON object")
        except Exception as e:
            _print_error(f"Could not read --config-file: {e}")
            return 2
    else:
        entry_config = {}

    try:
        entry = MiddlewareEntry(
            name=args.name,
            description=args.description or "",
            version=args.version or "0.0.0",
            kind=args.kind,
            mode=args.mode,
            priority=args.priority,
            applied_hooks=applied_hooks,
            conditions=Conditions(
                include_tools=include_tools,
                exclude_tools=exclude_tools,
                include_prompts=include_prompts,
                exclude_prompts=exclude_prompts,
                include_server_ids=include_server_ids,
                exclude_server_ids=exclude_server_ids,
            ),
            config=entry_config,
        )
    except ValidationError as ve:
        _print_error("New middleware entry is invalid:")
        _print_validation_error(ve)
        return 1

    # Upsert
    items = list(cfg.middleware)
    names = [m.name for m in items]
    if entry.name in names:
        if not args.update:
            _print_error(
                f"Middleware with name '{entry.name}' already exists. "
                "Use --update to overwrite."
            )
            return 1
        idx = names.index(entry.name)
        items[idx] = entry
    else:
        items.append(entry)

    # Revalidate whole config & ensure imports (optional)
    new_cfg = MiddlewareConfig(middleware=items, middleware_settings=cfg.middleware_settings)

    if args.ensure_imports:
        import importlib
        try:
            for m in new_cfg.middleware:
                mod, clsname = m.kind.rsplit(".", 1)
                module = importlib.import_module(mod)
                getattr(module, clsname)
        except (ImportError, AttributeError) as ie:
            _print_error(f"Import check failed: {ie}")
            return 1

    # Sort & write (or dry-run)
    new_cfg.middleware.sort(key=lambda m: m.priority)

    if args.dry_run:
        print(json.dumps(new_cfg.model_dump(mode="json"), indent=2))
        return 0

    _save_json_file(args.config, new_cfg.model_dump(mode="json"))
    print(f"✔ Middleware '{entry.name}' {'updated' if entry.name in names and args.update else 'added'} in {args.config}")

    if args.show_middlewares and MiddlewareManager is not None:
        mgr = MiddlewareManager(args.config, ensure_imports=False)
        print("\nEnabled middlewares (in execution order):")
        for info in mgr.describe():
            hooks = ", ".join(info.get("applied_hooks", []))
            print(f" - {info['name']}  (priority={info['priority']}, hooks=[{hooks}])")

    return 0

