"""workflow_catalog_mcp.py — Thin MCP tools for the workflow catalog."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from mcp_composer.core.catalog import (
    CatalogResourceNotFoundError,
    CatalogVersionCapError,
    InvalidCatalogResourceStatusError,
)
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.catalog.workflow_manager import WorkflowManager
from mcp_composer.core.models.catalog_workflow import WorkflowJSON
from mcp_composer.store.catalog_factory import get_catalog_db

_workflow_manager = WorkflowManager(get_catalog_db())

workflow_catalog_mcp = FastMCP(
    "workflow-catalog",
    instructions="MCP tools for listing, publishing, and managing workflows in the catalog.",
)


def get_workflow_mcp() -> FastMCP:
    """Return the module-level workflow-catalog FastMCP instance."""
    return workflow_catalog_mcp


@workflow_catalog_mcp.tool()
async def list_workflows(
    tenant: str | None = None,
    start: int = 0,
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
                start=start,
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
    """Register or update a workflow (POST-style publish to ``catalog_resources``)."""
    try:
        parsed = WorkflowJSON.model_validate_json(workflow_json)
    except Exception as exc:
        raise ValueError(f"Invalid workflow_json: {exc}") from exc
    try:
        result = await _workflow_manager.publish(parsed, tenant_ids=tenant_ids)
    except CatalogVersionCapError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


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
    """Delete one workflow version from the catalog."""
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    try:
        await _workflow_manager.delete(name.strip(), version.strip())
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return {"ok": True, "name": name.strip(), "version": version.strip()}


@workflow_catalog_mcp.tool()
async def update_workflow_status(name: str, version: str, status: str) -> dict:
    """Update lifecycle status for a workflow version."""
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    if not status or not status.strip():
        raise ValueError("status is a required field")
    try:
        await _workflow_manager.update_status(name.strip(), version.strip(), status.strip())
    except (
        CatalogResourceNotFoundError,
        InvalidCatalogResourceStatusError,
    ) as exc:
        raise ValueError(str(exc)) from exc
    return {"ok": True, "name": name.strip(), "version": version.strip(), "status": status.strip()}
