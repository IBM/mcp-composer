"""agent_catalog_mcp.py — Thin MCP tools for the agent catalog (agentregistry-aligned)."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from mcp_composer.core.catalog import (
    CatalogResourceNotFoundError,
    CatalogVersionCapError,
    InvalidCatalogResourceStatusError,
)
from mcp_composer.core.catalog.agent_manager import AgentManager
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_agent import AgentJSON
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.store.catalog_factory import get_catalog_db

_agent_manager = AgentManager(get_catalog_db())

agent_catalog_mcp = FastMCP(
    "agent-catalog",
    instructions="MCP tools for listing, publishing, and managing agents in the catalog.",
)


def get_agent_mcp() -> FastMCP:
    """Return the module-level agent-catalog FastMCP instance."""
    return agent_catalog_mcp


@agent_catalog_mcp.tool()
async def list_agents(
    tenant: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """List active, latest agents in the catalog (mirrors skill list semantics).

    Returns only **active** rows with ``is_latest`` for each agent name.
    """
    try:
        result = await _agent_manager.list(
            CatalogResourceListFilter(
                kind=RegistryResourceKind.AGENT,
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
            "agents": data["agents"],
            "metadata": {
                "count": data["metadata"]["count"],
                "next_start": data["metadata"]["nextStart"],
            },
        }
    except Exception as exc:
        return {
            "agents": [],
            "metadata": {"count": 0, "next_start": None},
            "error": str(exc),
        }


@agent_catalog_mcp.tool()
async def get_agent(name: str, version: str | None = None) -> dict:
    """Fetch one agent by name; omit ``version`` for the latest published version."""
    if not name or not name.strip():
        raise ValueError("name is a required field")
    name = name.strip()
    try:
        if version and version.strip():
            result = await _agent_manager.get(name, version.strip())
        else:
            result = await _agent_manager.get_latest(name)
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


def _parse_agent_bundle(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Split bundle into public agent document and optional private metadata."""
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

    body_keys = ("catalog_resource", "agent", "payload")
    present = [k for k in body_keys if k in raw and raw[k] is not None]
    if len(present) > 1:
        raise ValueError("Use only one of: catalog_resource, agent, payload")
    if len(present) == 0:
        raise ValueError(
            "Bundle must include 'catalog_resource' (preferred), 'agent', or 'payload'"
        )
    key = present[0]
    agent_obj = raw[key]
    if not isinstance(agent_obj, dict):
        raise ValueError(f"'{key}' must be a JSON object")
    return agent_obj, meta


@agent_catalog_mcp.tool()
async def add_agent(
    agent_json: str,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Register or update an agent (POST-style publish to ``catalog_resources``)."""
    try:
        parsed = AgentJSON.model_validate_json(agent_json)
    except Exception as exc:
        raise ValueError(f"Invalid agent_json: {exc}") from exc
    try:
        result = await _agent_manager.publish(parsed, tenant_ids=tenant_ids)
    except CatalogVersionCapError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


@agent_catalog_mcp.tool()
async def publish_agent_bundle(
    bundle_json: str,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Publish agent payload plus optional ``catalog_resource_metadata`` in one call."""
    try:
        raw = json.loads(bundle_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid bundle_json: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("bundle_json must be a JSON object")

    agent_obj, resource_meta = _parse_agent_bundle(raw)
    try:
        parsed = AgentJSON.model_validate(agent_obj)
    except Exception as exc:
        raise ValueError(f"Invalid catalog_resource document: {exc}") from exc
    try:
        result = await _agent_manager.publish_with_resource_metadata(
            parsed,
            tenant_ids=tenant_ids,
            resource_metadata=resource_meta,
        )
    except CatalogVersionCapError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


@agent_catalog_mcp.tool()
async def delete_agent(name: str, version: str) -> dict:
    """Delete one agent version from the catalog."""
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    try:
        await _agent_manager.delete(name.strip(), version.strip())
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return {"ok": True, "name": name.strip(), "version": version.strip()}


@agent_catalog_mcp.tool()
async def update_agent_status(name: str, version: str, status: str) -> dict:
    """Update lifecycle status for an agent version."""
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    if not status or not status.strip():
        raise ValueError("status is a required field")
    try:
        await _agent_manager.update_status(name.strip(), version.strip(), status.strip())
    except (
        CatalogResourceNotFoundError,
        InvalidCatalogResourceStatusError,
    ) as exc:
        raise ValueError(str(exc)) from exc
    return {"ok": True, "name": name.strip(), "version": version.strip(), "status": status.strip()}
