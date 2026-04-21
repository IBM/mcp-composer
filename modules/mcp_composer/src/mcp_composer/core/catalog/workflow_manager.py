"""workflow_manager.py — Business-logic layer for the workflow catalog (``kind`` = ``workflow``)."""

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
from mcp_composer.core.models.catalog_constants import (
    MAX_VERSIONS_PER_RESOURCE,
    RegistryResourceKind,
    VALID_CATALOG_RESOURCE_STATUSES,
)
from mcp_composer.core.models.catalog_workflow import (
    WorkflowJSON,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowResponseMeta,
)
from mcp_composer.store.catalog_database import CatalogDatabaseInterface

_WORKFLOW_KIND = RegistryResourceKind.WORKFLOW.value


def _public_resource_metadata(private_meta: dict | None) -> dict | None:
    if not private_meta:
        return None
    return dict(private_meta) if private_meta else None


def _row_to_workflow_response(row: dict, private_meta: dict | None = None) -> WorkflowResponse:
    workflow = WorkflowJSON(**row["payload"])
    official = registry_official_extensions_from_row(row)
    meta = WorkflowResponseMeta(
        official=official,
        metadata=_public_resource_metadata(private_meta),
    )
    return WorkflowResponse(workflow=workflow, meta=meta)


class WorkflowManager(CatalogManager):
    """Catalog business logic for workflows (``kind`` = ``workflow`` in ``catalog_resources``)."""

    def __init__(self, db: CatalogDatabaseInterface) -> None:
        super().__init__(db)

    async def publish(
        self,
        workflow_json: WorkflowJSON,
        tenant_ids: Optional[List[str]] = None,
    ) -> WorkflowResponse:
        """Publish (create or update) a workflow version; recompute ``is_latest``."""
        await self._ensure_initialized()
        name = workflow_json.name
        version = workflow_json.version
        normalised_tenants = normalize_tenant_ids(tenant_ids)

        existing = await self._db.get_resource(_WORKFLOW_KIND, name, version)
        if existing is None:
            count = await self._db.count_resource_versions(_WORKFLOW_KIND, name)
            if count >= MAX_VERSIONS_PER_RESOURCE:
                raise CatalogVersionCapError(_WORKFLOW_KIND, name, count)

        now = utc_now_iso()
        payload = workflow_json.model_dump(mode="json", by_alias=False, exclude_none=True)

        official_meta: Dict[str, Any] = {
            "status": workflow_json.status or "active",
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
        }
        await self._db.save_resource(_WORKFLOW_KIND, row)

        await self.recompute_is_latest_for_workflow_name(name)

        final_row = await self._db.get_resource(_WORKFLOW_KIND, name, version)
        if final_row is None:
            raise CatalogResourceNotFoundError(_WORKFLOW_KIND, name, version)
        private_meta = await self._db.get_resource_metadata(str(final_row["id"]))
        return _row_to_workflow_response(final_row, private_meta)

    async def publish_with_resource_metadata(
        self,
        workflow_json: WorkflowJSON,
        tenant_ids: Optional[List[str]] = None,
        resource_metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResponse:
        """Publish a workflow and merge optional ``catalog_resource_metadata.data``."""
        await self._ensure_initialized()
        response = await self.publish(workflow_json, tenant_ids=tenant_ids)
        if not resource_metadata:
            return response
        row = await self._db.get_resource(
            _WORKFLOW_KIND, workflow_json.name, workflow_json.version
        )
        if row is None:
            raise CatalogResourceNotFoundError(
                _WORKFLOW_KIND, workflow_json.name, workflow_json.version
            )
        existing_raw = await self._db.get_resource_metadata(str(row["id"]))
        existing: Dict[str, Any] = dict(existing_raw or {})
        merged: Dict[str, Any] = {**existing, **resource_metadata}
        await self._db.save_resource_metadata(str(row["id"]), merged)
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_workflow_response(row, private_meta)

    async def get(self, name: str, version: str) -> WorkflowResponse:
        await self._ensure_initialized()
        row = await self._db.get_resource(_WORKFLOW_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_WORKFLOW_KIND, name, version)
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_workflow_response(row, private_meta)

    async def get_latest(self, name: str) -> WorkflowResponse:
        await self._ensure_initialized()
        row = await self._db.get_resource_by_filter(_WORKFLOW_KIND, name, is_latest=True)
        if row is None:
            raise CatalogResourceNotFoundError(_WORKFLOW_KIND, name, "latest")
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_workflow_response(row, private_meta)

    async def list(self, filter: CatalogResourceListFilter) -> WorkflowListResponse:
        await self._ensure_initialized()
        expect_catalog_list_filter_kind(filter, RegistryResourceKind.WORKFLOW)
        rows, has_more = await self._db.list_resources(
            _WORKFLOW_KIND,
            name_like=filter.name_like,
            is_latest_only=filter.is_latest_only,
            status_filter=filter.status_filter,
            keywords=None,
            tenant=filter.tenant,
            offset=filter.start,
            limit=filter.limit,
        )
        workflows = [_row_to_workflow_response(r) for r in rows]
        metadata = registry_list_metadata_for_page(filter.start, workflows, has_more)
        return WorkflowListResponse(workflows=workflows, metadata=metadata)

    async def delete(self, name: str, version: str) -> None:
        await self._ensure_initialized()
        row = await self._db.get_resource(_WORKFLOW_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_WORKFLOW_KIND, name, version)
        await self._db.delete_resource(_WORKFLOW_KIND, name, version)
        await self.recompute_is_latest_for_workflow_name(name)

    async def update_status(self, name: str, version: str, status: str) -> None:
        await self._ensure_initialized()
        if status not in VALID_CATALOG_RESOURCE_STATUSES:
            raise InvalidCatalogResourceStatusError(_WORKFLOW_KIND, status)
        row = await self._db.get_resource(_WORKFLOW_KIND, name, version)
        if row is None:
            raise CatalogResourceNotFoundError(_WORKFLOW_KIND, name, version)
        payload = dict(row.get("payload") or {})
        payload["status"] = status
        official_meta = dict(row.get("official_meta") or {})
        official_meta["status"] = status
        await self._db.update_resource_row(
            _WORKFLOW_KIND,
            name,
            version,
            {"payload": payload, "official_meta": official_meta},
        )
