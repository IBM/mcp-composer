"""Business-logic layer for the versioned prompt catalog (``catalog_resources``).

This is distinct from ``MCPPromptManager`` in ``core.prompts``, which handles in-process
FastMCP prompts and ``DatabaseInterface`` persistence. For PostgreSQL, both layers read
the same ``MCP_DATABASE_*`` settings as ``get_catalog_db()``; schemas differ (catalog vs.
composer ``*_prompts`` table).
"""

from __future__ import annotations

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
from mcp_composer.core.models.catalog_constants import (
    MAX_VERSIONS_PER_RESOURCE,
    VALID_CATALOG_RESOURCE_STATUSES,
    RegistryResourceKind,
)
from mcp_composer.core.models.catalog_prompt import (
    PromptJSON,
    PromptListResponse,
    PromptResponse,
    PromptResponseMeta,
)
from mcp_composer.store.catalog_database import CatalogDatabaseInterface
from pydantic import BaseModel, Field

_PROMPT_KIND = RegistryResourceKind.PROMPT.value


class PromptListFilter(BaseModel):
    """Query parameters for PromptManager.list()."""

    name_like: str | None = None
    is_latest_only: bool = False
    status_filter: str | None = None
    tenant: str | None = None
    start: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=1000)


def _row_to_prompt_response(row: dict) -> PromptResponse:
    prompt = PromptJSON(**row["payload"])
    official = registry_official_extensions_from_row(row)
    meta = PromptResponseMeta.model_validate({"official": official})
    return PromptResponse(prompt=prompt, _meta=meta)


class PromptManager(CatalogManager):
    """Catalog business logic for prompts (registry JSON in ``catalog_resources``)."""

    def __init__(self, db: CatalogDatabaseInterface) -> None:
        super().__init__(db)

    async def publish(
        self,
        prompt_json: PromptJSON,
        tenant_ids: list[str] | None = None,
        status: str = "active",
    ) -> PromptResponse:
        """Publish (create or update) a prompt version; recompute semantic ``is_latest``."""
        await self._ensure_initialized()
        name = prompt_json.name
        version = prompt_json.version
        normalised_tenants = normalize_tenant_ids(tenant_ids)

        if status not in VALID_CATALOG_RESOURCE_STATUSES:
            raise InvalidCatalogResourceStatusError(_PROMPT_KIND, status)

        existing = await self._db.get_resource(_PROMPT_KIND, name, version)
        if existing is None:
            count = await self._db.count_resource_versions(_PROMPT_KIND, name)
            if count >= MAX_VERSIONS_PER_RESOURCE:
                raise CatalogVersionCapError(_PROMPT_KIND, name, count)

        now = utc_now_iso()
        payload = prompt_json.model_dump(mode="json", by_alias=False, exclude_none=True)
        official_meta: dict = {
            "status": status,
            "published_at": now,
            "updated_at": now,
            "is_latest": False,
        }
        row = {
            "name": name,
            "version": version,
            "payload": payload,
            "official_meta": official_meta,
            "is_latest": False,
            "tenant_ids": normalised_tenants,
            "content": prompt_json.content,
        }
        await self._db.save_resource(_PROMPT_KIND, row)

        await self.recompute_is_latest_for_prompt_name(name)

        final_row = await self._db.get_resource(_PROMPT_KIND, name, version)
        if final_row is None:
            raise CatalogResourceNotFoundError(_PROMPT_KIND, name, version)
        return _row_to_prompt_response(final_row)

    async def get(self, name: str, version: str) -> PromptResponse:
        await self._ensure_initialized()
        row = await self._db.get_resource(_PROMPT_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_PROMPT_KIND, name, version)
        return _row_to_prompt_response(row)

    async def get_latest(self, name: str) -> PromptResponse:
        await self._ensure_initialized()
        row = await self._db.get_resource_by_filter(_PROMPT_KIND, name, is_latest=True)
        if row is None:
            raise CatalogResourceNotFoundError(_PROMPT_KIND, name, "latest")
        return _row_to_prompt_response(row)

    async def list(self, filter: CatalogResourceListFilter) -> PromptListResponse:
        await self._ensure_initialized()
        expect_catalog_list_filter_kind(filter, RegistryResourceKind.PROMPT)
        rows, has_more = await self._db.list_resources(
            _PROMPT_KIND,
            name_like=filter.name_like,
            is_latest_only=filter.is_latest_only,
            status_filter=filter.status_filter,
            keywords=None,
            tenant=filter.tenant,
            offset=filter.start,
            limit=filter.limit,
        )
        prompts = [_row_to_prompt_response(r) for r in rows]
        metadata = registry_list_metadata_for_page(filter.start, prompts, has_more)
        return PromptListResponse(prompts=prompts, metadata=metadata)

    async def delete(self, name: str, version: str) -> None:
        await self._ensure_initialized()
        row = await self._db.get_resource(_PROMPT_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_PROMPT_KIND, name, version)
        await self._db.delete_resource(_PROMPT_KIND, name, version)
        await self.recompute_is_latest_for_prompt_name(name)

    async def update_status(self, name: str, version: str, status: str) -> None:
        await self._ensure_initialized()
        if status not in VALID_CATALOG_RESOURCE_STATUSES:
            raise InvalidCatalogResourceStatusError(_PROMPT_KIND, status)
        row = await self._db.get_resource(_PROMPT_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_PROMPT_KIND, name, version)
        official_meta = dict(row.get("official_meta") or {})
        official_meta["status"] = status
        await self._db.update_resource_row(
            _PROMPT_KIND,
            name,
            version,
            {"official_meta": official_meta},
        )
