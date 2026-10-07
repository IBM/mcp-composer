"""workflow_catalog_mcp.py — Thin MCP tools for the workflow catalog."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from mcp_composer.core.catalog import (
    CatalogResourceNotFoundError,
    CatalogVersionCapError,
    InvalidCatalogResourceStatusError,
)
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.catalog.workflow_manager import WorkflowManager
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.models.catalog_workflow import WorkflowJSON
from mcp_composer.core.workflow_file_loader import (
    parse_workflows_from_json_string,
    sync_workflow_files_to_catalog,
)
from mcp_composer.store.catalog_factory import get_catalog_db
from mcp_composer.store.catalog_workflows_provider import CatalogWorkflowsProvider

_workflow_manager = WorkflowManager(get_catalog_db())
_workflows_provider = CatalogWorkflowsProvider()

workflow_catalog_mcp = FastMCP(
    "workflow-catalog",
    instructions=(
        "Catalog workflows are MCP tools that return a JSON execution plan. "
        "Run each step sequentially on the composer using the tool names in the plan."
    ),
)

try:
    workflow_catalog_mcp.add_provider(_workflows_provider)
except AttributeError:
    import warnings

    warnings.warn(
        "FastMCP < 3.1 — CatalogWorkflowsProvider requires add_provider().",
        stacklevel=2,
    )


def get_workflow_mcp() -> FastMCP:
    """Return the module-level workflow-catalog FastMCP instance."""
    return workflow_catalog_mcp


@workflow_catalog_mcp.tool()
async def list_workflows(
    tenant: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """List active, latest workflows in the catalog."""
    try:
        result = await _workflow_manager.list(
            CatalogResourceListFilter(
                kind=RegistryResourceKind.WORKFLOW,
                name_like=None,
                is_latest_only=True,
                status_filter="active",
                tenant=tenant,
                start=offset,
                limit=limit,
            )
        )
        data = result.model_dump(by_alias=True)
        return {
            "workflows": data["workflows"],
            "metadata": {
                "count": data["metadata"]["count"],
                "next_start": data["metadata"]["nextStart"],
            },
        }
    except Exception as exc:
        return {
            "workflows": [],
            "metadata": {"count": 0, "next_start": None},
            "error": str(exc),
        }


@workflow_catalog_mcp.tool()
async def get_workflow(name: str, version: str | None = None) -> dict:
    """Fetch one workflow by name; omit ``version`` for the latest published version."""
    if not name or not name.strip():
        raise ValueError("name is a required field")
    name = name.strip()
    try:
        if version and version.strip():
            result = await _workflow_manager.get(name, version.strip())
        else:
            result = await _workflow_manager.get_latest(name)
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


def _parse_workflow_bundle(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Split bundle into public workflow document and optional private metadata."""
    meta_keys = (
        "catalog_resource_metadata",
        "private_meta",
        "resource_metadata",
        "data",
    )
    found_keys: list[str] = []
    meta: dict[str, Any] | None = None
    for key in meta_keys:
        if key not in raw:
            continue
        val = raw[key]
        if val is None:
            continue
        if not isinstance(val, dict):
            raise ValueError(f"'{key}' must be a JSON object")
        found_keys.append(key)
        meta = val
    if len(found_keys) > 1:
        raise ValueError(
            "Use only one of: catalog_resource_metadata, private_meta, resource_metadata, data"
        )

    body_keys = ("catalog_resource", "workflow", "payload")
    present = [k for k in body_keys if k in raw and raw[k] is not None]
    if len(present) > 1:
        raise ValueError("Use only one of: catalog_resource, workflow, payload")
    if len(present) == 0:
        raise ValueError(
            "Bundle must include 'catalog_resource' (preferred), 'workflow', or 'payload'"
        )
    key = present[0]
    body = raw[key]
    if not isinstance(body, dict):
        raise ValueError(f"'{key}' must be a JSON object")
    return body, meta


@workflow_catalog_mcp.tool()
async def add_workflow(
    workflow_json: str,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Register or update one or more workflows (POST-style publish).

    Accepts either:

    * A single catalog ``WorkflowJSON`` object
    * A single bundle entry (``instruction`` + ``output`` / ``steps``)
    * An array of bundle entries (same shape as ``workflows_*.json`` files)
    """
    try:
        workflows = parse_workflows_from_json_string(workflow_json)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        raise ValueError(f"Invalid workflow_json: {exc}") from exc

    published: list[dict[str, Any]] = []
    errors: list[str] = []
    for workflow in workflows:
        try:
            result = await _workflow_manager.publish(workflow, tenant_ids=tenant_ids)
            published.append(result.model_dump(by_alias=True))
        except CatalogVersionCapError as exc:
            errors.append(f"{workflow.name}: {exc}")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            errors.append(f"{workflow.name}: {exc}")

    if errors and not published:
        raise ValueError("; ".join(errors))

    await _workflows_provider.refresh()

    if len(workflows) == 1 and len(published) == 1 and not errors:
        return published[0]

    return {
        "published_count": len(published),
        "published": published,
        "errors": errors,
    }


@workflow_catalog_mcp.tool()
async def publish_workflow_bundle(
    bundle_json: str,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Publish workflow payload plus optional ``catalog_resource_metadata`` in one call."""
    try:
        raw = json.loads(bundle_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid bundle_json: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("bundle_json must be a JSON object")

    body, resource_meta = _parse_workflow_bundle(raw)
    try:
        parsed = WorkflowJSON.model_validate(body)
    except Exception as exc:
        raise ValueError(f"Invalid catalog_resource document: {exc}") from exc
    try:
        result = await _workflow_manager.publish_with_resource_metadata(
            parsed,
            tenant_ids=tenant_ids,
            resource_metadata=resource_meta,
        )
    except CatalogVersionCapError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


@workflow_catalog_mcp.tool()
async def delete_workflow(name: str, version: str) -> dict:
    """Delete one workflow version from the catalog.

    ``name`` must match the catalog id exactly (from ``get_workflow`` / ``list_workflows``).
    """
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    name = name.strip()
    version = version.strip()
    try:
        await _workflow_manager.delete(name, version)
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    await _workflows_provider.refresh()
    return {
        "ok": True,
        "name": name,
        "version": version,
        "tools_refreshed": True,
    }


@workflow_catalog_mcp.tool()
async def update_workflow_status(name: str, version: str, status: str) -> dict:
    """Update lifecycle status for a workflow version."""
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    if not status or not status.strip():
        raise ValueError("status is a required field")
    name = name.strip()
    version = version.strip()
    status = status.strip()
    try:
        await _workflow_manager.update_status(name, version, status)
    except (
        CatalogResourceNotFoundError,
        InvalidCatalogResourceStatusError,
    ) as exc:
        raise ValueError(str(exc)) from exc
    await _workflows_provider.refresh()
    return {
        "ok": True,
        "name": name,
        "version": version,
        "status": status,
        "tools_refreshed": True,
    }


@workflow_catalog_mcp.tool()
async def sync_workflows_from_files(
    directory: str | None = None,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Load workflow JSON files from disk, publish to the catalog, and refresh workflow tools."""
    path = Path(directory).expanduser() if directory else None
    result = await sync_workflow_files_to_catalog(
        path,
        workflow_manager=_workflow_manager,
        tenant_ids=tenant_ids,
    )
    await _workflows_provider.refresh()
    result["tools_refreshed"] = True
    result[
        "note"
    ] = "Each JSON file is one workflow object; catalog stores one row per (name, version)."
    return result


async def bootstrap_workflow_catalog_from_env() -> dict[str, Any] | None:
    """If ``MCP_WORKFLOW_FILES_SYNC`` is enabled, sync JSON workflows on startup."""
    raw = (os.getenv("MCP_WORKFLOW_FILES_SYNC") or "true").strip().lower()
    if raw not in ("true", "1", "yes", "on"):
        return None
    directory = os.getenv("MCP_WORKFLOW_FILES_DIR")
    path = Path(directory).expanduser() if directory else None
    result = await sync_workflow_files_to_catalog(
        path,
        workflow_manager=_workflow_manager,
    )
    await _workflows_provider.refresh()
    return result
