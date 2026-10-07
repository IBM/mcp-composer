"""Load workflow definitions from JSON files and publish them to the workflow catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mcp_composer.core.catalog.workflow_manager import WorkflowManager
from mcp_composer.core.models.catalog_workflow import WorkflowJSON, WorkflowStep
from mcp_composer.core.utils.catalog_validators import validate_skill_or_prompt_name
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()

_DEFAULT_VERSION = "1.0.0"
_INSTRUCTION_TAG_RE = re.compile(r"^\[[^\]]+\]\s*")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _resolve_workflows_dir(path: Path | str | None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[5]
    return (repo_root / "resources" / "workflows").resolve()


def slug_from_instruction(instruction: str, *, max_len: int = 64) -> str:
    """Build a catalog-safe workflow name from the instruction text."""
    text = _INSTRUCTION_TAG_RE.sub("", instruction.strip().lower())
    slug = _SLUG_RE.sub("-", text).strip("-")
    if not slug:
        slug = "workflow"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "workflow"


def resolve_tool_prefix(
    product: str,
    *,
    entry_prefixes: dict[str, str] | None,
    step_prefix: str | None,
) -> str:
    """Resolve the mounted MCP server id used as the tool name prefix."""
    if step_prefix and step_prefix.strip():
        return step_prefix.strip()
    if entry_prefixes and product in entry_prefixes:
        return str(entry_prefixes[product]).strip()
    return product


def prefixed_tool_name(server_prefix: str, tool: str) -> str:
    """Compose the composer-visible tool name (``{server_id}_{tool}``)."""
    if server_prefix.endswith("_") or tool.startswith(f"{server_prefix}_"):
        return (
            tool if tool.startswith(f"{server_prefix}_") else f"{server_prefix}{tool}"
        )
    return f"{server_prefix}_{tool}"


def parse_workflow_file_entries(
    raw: Any,
    *,
    source_file: str,
) -> list[dict[str, Any]]:
    """Parse a workflow JSON file into one or more workflow entry dicts.

    - Single-object files: one workflow (preferred for authoring).
    - Array files (e.g. ``workflows_easy.json``): multiple workflows in one resource file;
      each entry is still published as its own catalog row.
    """
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        entries: list[dict[str, Any]] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"{source_file}: workflow[{idx}] must be a JSON object"
                )
            entries.append(item)
        if not entries:
            raise ValueError(f"{source_file}: workflow array must not be empty")
        return entries
    raise ValueError(
        f"{source_file}: workflow file must be a JSON object or array of workflow objects"
    )


def file_entry_to_workflow_json(
    entry: dict[str, Any],
    *,
    source_file: str,
    used_names: set[str],
    default_name: str | None = None,
) -> WorkflowJSON:
    """Convert one workflow JSON object into a ``WorkflowJSON`` document."""
    instruction = entry.get("instruction") or entry.get("description")
    if not instruction or not str(instruction).strip():
        raise ValueError(f"entry in {source_file} must include non-empty 'instruction'")

    instruction = str(instruction).strip()
    raw_name = entry.get("name") or default_name
    if raw_name and str(raw_name).strip():
        name = validate_skill_or_prompt_name(str(raw_name).strip())
    else:
        base = slug_from_instruction(instruction)
        name = base
        suffix = 2
        while name in used_names:
            candidate = f"{base}-{suffix}"
            if len(candidate) > 64:
                candidate = f"{base[: max(1, 64 - len(str(suffix)) - 1)]}-{suffix}"
            name = validate_skill_or_prompt_name(candidate)
            suffix += 1
    used_names.add(name)

    version = str(entry.get("version") or _DEFAULT_VERSION).strip()
    goal = str(entry.get("goal") or instruction).strip()
    if len(goal) > 500:
        goal = goal[:497] + "..."

    entry_prefixes = entry.get("prefixes")
    if entry_prefixes is not None and not isinstance(entry_prefixes, dict):
        raise ValueError(f"'prefixes' must be an object in {source_file}")

    output = entry.get("output") or entry.get("steps")
    if not isinstance(output, list) or not output:
        raise ValueError(
            f"entry '{name}' in {source_file} must include non-empty 'output'"
        )

    steps: list[WorkflowStep] = []
    for raw_step in output:
        if not isinstance(raw_step, dict):
            raise ValueError(f"invalid step in workflow '{name}'")
        step_no = int(raw_step.get("step", len(steps) + 1))
        product = str(raw_step.get("product") or raw_step.get("toolname") or "").strip()
        tool = str(raw_step.get("tool") or "").strip()
        if not product or not tool:
            raise ValueError(f"step {step_no} in '{name}' needs product and tool")
        server_prefix = resolve_tool_prefix(
            product,
            entry_prefixes=entry_prefixes,
            step_prefix=raw_step.get("tool_prefix"),
        )
        steps.append(
            WorkflowStep(
                step=step_no,
                toolname=server_prefix,
                tool=tool,
                input=raw_step.get("input") or {},
                expected_behaviour=raw_step.get("expected_behaviour"),
            )
        )

    return WorkflowJSON(
        name=name,
        description=instruction,
        version=version,
        goal=goal,
        steps=steps,
        status=str(entry.get("status") or "active"),
    )


def build_workflow_execution_guidance() -> dict[str, Any]:
    """Structured hints returned with every workflow execution plan."""
    return {
        "pattern": "discover_plan_execute_sequentially",
        "phases": [
            {
                "id": "orient",
                "summary": "Read the workflow goal and step list before calling member tools.",
            },
            {
                "id": "resolve_inputs",
                "summary": "Replace {{placeholders}} in step input from prior step outputs.",
            },
            {
                "id": "execute",
                "summary": "Call each step on the composer in order; do not skip ahead.",
            },
            {
                "id": "verify",
                "summary": "Check expected_behaviour when present before continuing.",
            },
        ],
        "invocation_patterns": [
            {
                "id": "direct",
                "when": "Member server exposes prefixed tools",
                "action": "Call mcp_tool_name with resolved input.",
            },
            {
                "id": "layered",
                "when": "Server exposes get_service_info / make_tool_call",
                "action": (
                    "Call layered_make_tool_call with tool_name and arguments; "
                    "use get_type_info when the schema is unclear."
                ),
            },
        ],
    }


def build_execution_plan(workflow: WorkflowJSON) -> dict[str, Any]:
    """Shape catalog workflow steps for LLM execution (includes prefixed MCP tool names)."""
    steps_out: list[dict[str, Any]] = []
    for step in workflow.steps:
        mcp_tool = prefixed_tool_name(step.toolname, step.tool)
        layered_call = prefixed_tool_name(step.toolname, "make_tool_call")
        steps_out.append(
            {
                "step": step.step,
                "server_id": step.toolname,
                "tool": step.tool,
                "mcp_tool_name": mcp_tool,
                "layered_make_tool_call": layered_call,
                "input": step.input,
                "expected_behaviour": step.expected_behaviour,
                "invoke_hint": (
                    f"Prefer {mcp_tool} with input, or {layered_call} with "
                    f'tool_name="{step.tool}" and arguments=<resolved input>.'
                ),
            }
        )
    return {
        "workflow_name": workflow.name,
        "version": workflow.version,
        "goal": workflow.goal,
        "description": workflow.description,
        "steps": steps_out,
        "execution_guidance": build_workflow_execution_guidance(),
        "next_action": (
            "Execute steps sequentially on the composer. For each step use mcp_tool_name "
            "(direct) or layered_make_tool_call with tool_name=tool. Resolve {{placeholders}} "
            "from prior step outputs before calling the next step."
        ),
    }


def load_workflow_entries_from_directory(
    directory: Path | str | None = None,
) -> list[tuple[str, WorkflowJSON, dict[str, Any] | None]]:
    """Parse one workflow per ``*.json`` file under *directory* (flat or nested)."""
    root = _resolve_workflows_dir(directory)
    if not root.is_dir():
        logger.warning("Workflow directory does not exist: %s", root)
        return []

    used_names: set[str] = set()
    results: list[tuple[str, WorkflowJSON, dict[str, Any] | None]] = []

    for path in sorted(root.glob("workflows_*.json")):
        if path.name.startswith("."):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            file_entries = parse_workflow_file_entries(raw, source_file=rel)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Skipping %s: %s", rel, exc)
            continue

        for entry_index, entry in enumerate(file_entries):
            merged = dict(entry)
            default_name = None
            if len(file_entries) == 1:
                default_name = path.stem
            try:
                workflow = file_entry_to_workflow_json(
                    merged,
                    source_file=rel,
                    used_names=used_names,
                    default_name=default_name,
                )
            except ValueError as exc:
                logger.error("Skipping workflow %s in %s: %s", entry_index, rel, exc)
                continue
            resource_meta = {
                "data": {
                    "source_file": rel,
                    "entry_index": entry_index,
                    "instruction": workflow.description,
                    "prefixes": merged.get("prefixes") or {},
                }
            }
            results.append((rel, workflow, resource_meta))

    return results


def workflow_document_from_entry(
    entry: dict[str, Any],
    *,
    used_names: set[str],
    source: str,
) -> WorkflowJSON:
    """Convert one API/file workflow object into ``WorkflowJSON``."""
    steps = entry.get("steps")
    if (
        isinstance(steps, list)
        and steps
        and isinstance(steps[0], dict)
        and "toolname" in steps[0]
    ):
        return WorkflowJSON.model_validate(entry)
    if entry.get("output") is not None or entry.get("instruction"):
        return file_entry_to_workflow_json(
            entry,
            source_file=source,
            used_names=used_names,
        )
    return WorkflowJSON.model_validate(entry)


def parse_workflows_from_json_value(
    raw: Any,
    *,
    source_label: str = "workflow_json",
) -> list[WorkflowJSON]:
    """Parse a workflow document or bundle array for ``add_workflow``."""
    if isinstance(raw, list):
        entries = parse_workflow_file_entries(raw, source_file=source_label)
        used_names: set[str] = set()
        return [
            workflow_document_from_entry(
                entry,
                used_names=used_names,
                source=source_label,
            )
            for entry in entries
        ]
    if isinstance(raw, dict):
        return [
            workflow_document_from_entry(
                raw,
                used_names=set(),
                source=source_label,
            )
        ]
    raise ValueError("workflow_json must be a JSON object or array of workflow objects")


def parse_workflows_from_json_string(
    workflow_json: str,
    *,
    source_label: str = "workflow_json",
) -> list[WorkflowJSON]:
    """Parse ``workflow_json`` string into one or more ``WorkflowJSON`` documents."""
    try:
        raw = json.loads(workflow_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid workflow_json: {exc}") from exc
    return parse_workflows_from_json_value(raw, source_label=source_label)


async def sync_workflow_files_to_catalog(
    directory: Path | str | None = None,
    *,
    workflow_manager: WorkflowManager | None = None,
    tenant_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Publish each workflow file as its own catalog resource (one DB row per workflow).

    PostgreSQL and file catalog both key resources by ``(kind=workflow, name, version)``.
    Each ``*.json`` file yields exactly one ``publish_with_resource_metadata`` call.
    """
    from mcp_composer.store.catalog_factory import get_catalog_db

    mgr = workflow_manager or WorkflowManager(get_catalog_db())
    entries = load_workflow_entries_from_directory(directory)
    published: list[dict[str, str]] = []
    errors: list[str] = []

    for source_file, workflow, resource_meta in entries:
        try:
            await mgr.publish_with_resource_metadata(
                workflow,
                tenant_ids=tenant_ids,
                resource_metadata=resource_meta,
            )
            published.append(
                {
                    "name": workflow.name,
                    "version": workflow.version,
                    "source_file": source_file,
                }
            )
            logger.info(
                "Published workflow '%s' v%s as separate catalog row (from %s)",
                workflow.name,
                workflow.version,
                source_file,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            msg = f"{workflow.name} ({source_file}): {exc}"
            errors.append(msg)
            logger.error("Failed to publish workflow from %s: %s", source_file, exc)

    return {
        "published_count": len(published),
        "published": published,
        "one_row_per_workflow": True,
        "errors": errors,
        "directory": str(_resolve_workflows_dir(directory)),
    }
