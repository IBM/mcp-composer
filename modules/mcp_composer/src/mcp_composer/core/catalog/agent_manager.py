"""agent_manager.py — Business-logic layer for the agent catalog (agentregistry-aligned)."""

from __future__ import annotations

from typing import Any

from mcp_composer.core.catalog.catalog_exceptions import (
    CatalogResourceAlreadyExistsError,
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
    VALID_CATALOG_RESOURCE_STATUSES,
    RegistryResourceKind,
)
from mcp_composer.store.catalog_database import CatalogDatabaseInterface

_AGENT_KIND = RegistryResourceKind.AGENT.value


def _public_resource_metadata(
    private_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not private_meta:
        return None
    out = {k: v for k, v in private_meta.items() if k != "remotes_config"}
    return out if out else None


def _row_to_agent_response(
    row: dict[str, Any], private_meta: dict[str, Any] | None = None
) -> AgentResponse:
    """Map a catalog DB row to an AgentResponse (remotes merged like skills)."""
    agent = AgentJSON(**row["payload"])
    official_meta_data: dict[str, Any] = row.get("official_meta") or {}

    if agent.remotes:
        official_remotes_cfg: dict[str, Any] = official_meta_data.get("remotes_config") or {}
        private_remotes_cfg: dict[str, Any] = (private_meta or {}).get("remotes_config") or {}
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
                    type=transport,
                    url=url or remote.url,
                    headers=private_cfg.get("headers") or remote.headers,
                )
            )
        agent.remotes = enriched

    official = registry_official_extensions_from_row(row)
    meta = AgentResponseMeta.model_validate(
        {
            "official": official,
            "metadata": _public_resource_metadata(private_meta),
        }
    )
    return AgentResponse(agent=agent, _meta=meta)


class AgentManager(CatalogManager):
    """Catalog business logic for agents (``kind`` = ``agent`` in ``catalog_resources``)."""

    def __init__(self, db: CatalogDatabaseInterface) -> None:
        super().__init__(db)

    async def publish(
        self,
        agent_json: AgentJSON,
        tenant_ids: list[str] | None = None,
        agent_card: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Publish (create or update) an agent version; recompute ``is_latest``.

        Args:
            agent_json:  Validated agent payload.
            tenant_ids:  Optional tenant scope.
            agent_card:  Raw A2A well-known agent card dict to store verbatim in
                         the ``agent_card`` JSONB column.  Pass the full dict
                         returned by ``/.well-known/agent-card.json``.
        """
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

        official_remotes_config: dict[str, Any] = {}
        private_remotes_config: dict[str, Any] = {}
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

        # Always force "active" on publish/create — the agent card may carry an
        # arbitrary status value (e.g. "deleted") that must never override the
        # registration lifecycle status.  Status transitions are made exclusively
        # via update_status().
        official_meta: dict[str, Any] = {
            "status": "active",
            "published_at": now,
            "updated_at": now,
            "is_latest": False,
        }
        if official_remotes_config:
            official_meta["remotes_config"] = official_remotes_config
        row: dict[str, Any] = {
            "name": name,
            "version": version,
            "payload": payload,
            "official_meta": official_meta,
            "is_latest": False,
            "tenant_ids": normalised_tenants,
        }
        if agent_card:
            row["agent_card"] = agent_card
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

    async def create(
        self,
        agent_json: AgentJSON,
        tenant_ids: list[str] | None = None,
        agent_card: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Create a new agent version; raise ``CatalogResourceAlreadyExistsError`` if already present.

        Unlike :meth:`publish`, this method is **create-only**: it will not overwrite an
        existing ``name+version`` pair.  Use ``publish`` directly when upsert semantics
        are required (e.g. the catalog MCP tools).

        Exception: if the existing row has ``status="deleted"``, the agent is treated as
        re-registered — the row is overwritten via :meth:`publish` and its status is
        reset to ``"active"``.
        """
        await self._ensure_initialized()
        existing = await self._db.get_resource(_AGENT_KIND, agent_json.name, agent_json.version)
        if existing is not None:
            existing_status = (existing.get("official_meta") or {}).get("status") or "active"
            if existing_status != "deleted":
                raise CatalogResourceAlreadyExistsError(
                    _AGENT_KIND, agent_json.name, agent_json.version
                )
            # Deleted agent — re-registration is allowed; fall through to publish().
        return await self.publish(agent_json, tenant_ids=tenant_ids, agent_card=agent_card)

    async def publish_with_resource_metadata(
        self,
        agent_json: AgentJSON,
        tenant_ids: list[str] | None = None,
        resource_metadata: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Publish an agent and merge optional ``catalog_resource_metadata.data``."""
        await self._ensure_initialized()
        response = await self.publish(agent_json, tenant_ids=tenant_ids)
        if not resource_metadata:
            return response
        row = await self._db.get_resource(_AGENT_KIND, agent_json.name, agent_json.version)
        if row is None:
            raise CatalogResourceNotFoundError(_AGENT_KIND, agent_json.name, agent_json.version)
        existing_raw = await self._db.get_resource_metadata(str(row["id"]))
        existing: dict[str, Any] = dict(existing_raw or {})
        merged: dict[str, Any] = {**existing, **resource_metadata}
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

    async def get_by_url(self, url: str) -> AgentResponse | None:
        """Return the latest active agent whose ``url`` or ``remotes`` URL matches *url*.

        Performs normalised trailing-slash comparison so that ``http://x`` and
        ``http://x/`` match each other.  Returns ``None`` when no matching agent
        is found; never raises.

        This avoids the O(n) full-catalog scan in ``send_message`` and eliminates
        the hard-coded ``limit=200`` ceiling.
        """
        await self._ensure_initialized()
        _norm = url.rstrip("/") if url else url
        rows, _ = await self._db.list_resources(
            _AGENT_KIND,
            name_like=None,
            is_latest_only=True,
            status_filter="active",
            keywords=None,
            tenant=None,
            offset=0,
            limit=1000,
        )
        for row in rows:
            payload = row.get("payload") or {}
            agent_url = (payload.get("url") or "").rstrip("/")
            if agent_url == _norm:
                return _row_to_agent_response(row)
            for remote in payload.get("remotes") or []:
                remote_url = (remote.get("url") or "").rstrip("/")
                if remote_url == _norm:
                    return _row_to_agent_response(row)
        return None

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
        # Recompute is_latest so deleted versions do not remain marked as latest.
        await self.recompute_is_latest_for_agent_name(name)
