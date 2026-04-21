"""agent_manager.py — Business-logic layer for the agent catalog (agentregistry-aligned)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_composer.core.catalog.catalog_exceptions import (
    CatalogResourceNotFoundError,
    CatalogVersionCapError,
    InvalidCatalogResourceStatusError,
)
from mcp_composer.core.catalog.catalog_helpers import (
    registry_list_metadata_for_page,
    registry_official_extensions_from_row,
    utc_now_iso,
)
from mcp_composer.core.catalog.catalog_manager import (
    CatalogManager,
    CatalogResourceListFilter,
    expect_catalog_list_filter_kind,
    normalize_tenant_ids,
)
from mcp_composer.core.models.catalog_agent import (
    AgentJSON,
    AgentListResponse,
    AgentRegistryTransport,
    AgentResponse,
    AgentResponseMeta,
)
from mcp_composer.core.models.catalog_constants import (
    MAX_VERSIONS_PER_RESOURCE,
    RegistryResourceKind,
    VALID_CATALOG_RESOURCE_STATUSES,
)
from mcp_composer.store.catalog_database import CatalogDatabaseInterface

_AGENT_KIND = RegistryResourceKind.AGENT.value


def _public_resource_metadata(private_meta: dict | None) -> dict | None:
    if not private_meta:
        return None
    out = {k: v for k, v in private_meta.items() if k != "remotes_config"}
    return out if out else None


def _row_to_agent_response(row: dict, private_meta: dict | None = None) -> AgentResponse:
    """Map a catalog DB row to an AgentResponse (remotes merged like skills)."""
    agent = AgentJSON(**row["payload"])
    official_meta_data: dict = row.get("official_meta") or {}

    if agent.remotes:
        official_remotes_cfg: Dict[str, Any] = (
            official_meta_data.get("remotes_config") or {}
        )
        private_remotes_cfg: Dict[str, Any] = (
            (private_meta or {}).get("remotes_config") or {}
        )
        enriched: list[AgentRegistryTransport] = []
        for remote in agent.remotes:
            url = remote.url or ""
            official_cfg = official_remotes_cfg.get(url) or {}
            private_cfg = private_remotes_cfg.get(url) or {}
            transport = (
                private_cfg.get("transport_type")
                or official_cfg.get("transport_type")
                or remote.transport_type
            )
            enriched.append(
                AgentRegistryTransport(
                    transport_type=transport,
                    url=url or remote.url,
                    headers=private_cfg.get("headers") or remote.headers,
                )
            )
        agent.remotes = enriched

    official = registry_official_extensions_from_row(row)
    meta = AgentResponseMeta(
        official=official,
        metadata=_public_resource_metadata(private_meta),
    )
    return AgentResponse(agent=agent, meta=meta)


class AgentManager(CatalogManager):
    """Catalog business logic for agents (``kind`` = ``agent`` in ``catalog_resources``)."""

    def __init__(self, db: CatalogDatabaseInterface) -> None:
        super().__init__(db)

    async def publish(
        self,
        agent_json: AgentJSON,
        tenant_ids: Optional[List[str]] = None,
    ) -> AgentResponse:
        """Publish (create or update) an agent version; recompute ``is_latest``."""
        await self._ensure_initialized()
        name = agent_json.name
        version = agent_json.version
        normalised_tenants = normalize_tenant_ids(tenant_ids)

        existing = await self._db.get_resource(_AGENT_KIND, name, version)
        if existing is None:
            count = await self._db.count_resource_versions(_AGENT_KIND, name)
            if count >= MAX_VERSIONS_PER_RESOURCE:
                raise CatalogVersionCapError(_AGENT_KIND, name, count)

        now = utc_now_iso()
        payload = agent_json.model_dump(mode="json", by_alias=False, exclude_none=True)

        official_remotes_config: Dict[str, Any] = {}
        private_remotes_config: Dict[str, Any] = {}
        if payload.get("remotes"):
            public_remotes = []
            for r in payload["remotes"]:
                url = r.get("url") or ""
                transport_type = r.get("transport_type") or r.get("type")
                tt = transport_type or "stdio"
                official_remotes_config[url] = {"transport_type": tt}
                private_remotes_config[url] = {"transport_type": tt}
                if r.get("headers"):
                    private_remotes_config.setdefault(url, {})["headers"] = r["headers"]
                # AgentRegistryTransport requires ``type`` on each remote; keep in payload.
                public_remotes.append({"url": url, "type": tt})
            payload["remotes"] = public_remotes

        official_meta: Dict[str, Any] = {
            "status": agent_json.status or "active",
            "published_at": now,
            "updated_at": now,
            "is_latest": False,
        }
        if official_remotes_config:
            official_meta["remotes_config"] = official_remotes_config
        row = {
            "name": name,
            "version": version,
            "payload": payload,
            "official_meta": official_meta,
            "is_latest": False,
            "tenant_ids": normalised_tenants,
        }
        saved = await self._db.save_resource(_AGENT_KIND, row)

        if private_remotes_config:
            await self._db.save_resource_metadata(
                str(saved["id"]), {"remotes_config": private_remotes_config}
            )

        await self.recompute_is_latest_for_agent_name(name)

        final_row = await self._db.get_resource(_AGENT_KIND, name, version)
        if final_row is None:
            raise CatalogResourceNotFoundError(_AGENT_KIND, name, version)
        private_meta = await self._db.get_resource_metadata(str(final_row["id"]))
        return _row_to_agent_response(final_row, private_meta)

    async def publish_with_resource_metadata(
        self,
        agent_json: AgentJSON,
        tenant_ids: Optional[List[str]] = None,
        resource_metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Publish an agent and merge optional ``catalog_resource_metadata.data``."""
        await self._ensure_initialized()
        response = await self.publish(agent_json, tenant_ids=tenant_ids)
        if not resource_metadata:
            return response
        row = await self._db.get_resource(_AGENT_KIND, agent_json.name, agent_json.version)
        if row is None:
            raise CatalogResourceNotFoundError(
                _AGENT_KIND, agent_json.name, agent_json.version
            )
        existing_raw = await self._db.get_resource_metadata(str(row["id"]))
        existing: Dict[str, Any] = dict(existing_raw or {})
        merged: Dict[str, Any] = {**existing, **resource_metadata}
        await self._db.save_resource_metadata(str(row["id"]), merged)
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_agent_response(row, private_meta)

    async def get(self, name: str, version: str) -> AgentResponse:
        await self._ensure_initialized()
        row = await self._db.get_resource(_AGENT_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_AGENT_KIND, name, version)
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_agent_response(row, private_meta)

    async def get_latest(self, name: str) -> AgentResponse:
        await self._ensure_initialized()
        row = await self._db.get_resource_by_filter(_AGENT_KIND, name, is_latest=True)
        if row is None:
            raise CatalogResourceNotFoundError(_AGENT_KIND, name, "latest")
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_agent_response(row, private_meta)

    async def list(self, filter: CatalogResourceListFilter) -> AgentListResponse:
        await self._ensure_initialized()
        expect_catalog_list_filter_kind(filter, RegistryResourceKind.AGENT)
        rows, has_more = await self._db.list_resources(
            _AGENT_KIND,
            name_like=filter.name_like,
            is_latest_only=filter.is_latest_only,
            status_filter=filter.status_filter,
            keywords=None,
            tenant=filter.tenant,
            offset=filter.start,
            limit=filter.limit,
        )
        agents = [_row_to_agent_response(r) for r in rows]
        metadata = registry_list_metadata_for_page(filter.start, agents, has_more)
        return AgentListResponse(agents=agents, metadata=metadata)

    async def delete(self, name: str, version: str) -> None:
        await self._ensure_initialized()
        row = await self._db.get_resource(_AGENT_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_AGENT_KIND, name, version)
        await self._db.delete_resource(_AGENT_KIND, name, version)
        await self.recompute_is_latest_for_agent_name(name)

    async def update_status(self, name: str, version: str, status: str) -> None:
        await self._ensure_initialized()
        if status not in VALID_CATALOG_RESOURCE_STATUSES:
            raise InvalidCatalogResourceStatusError(_AGENT_KIND, status)
        row = await self._db.get_resource(_AGENT_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_AGENT_KIND, name, version)
        payload = dict(row.get("payload") or {})
        payload["status"] = status
        official_meta = dict(row.get("official_meta") or {})
        official_meta["status"] = status
        await self._db.update_resource_row(
            _AGENT_KIND,
            name,
            version,
            {"payload": payload, "official_meta": official_meta},
        )
