"""skill_manager.py — Business-logic layer for the skill catalog."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from mcp_composer.core.models.catalog_common import (
    RegistryListMetadata,
    RegistryOfficialExtensions,
)
from mcp_composer.core.models.catalog_constants import MAX_VERSIONS_PER_RESOURCE, RegistryResourceKind
from mcp_composer.core.models.catalog_skill import (
    SkillJSON,
    SkillListResponse,
    SkillRemoteInfo,
    SkillResponse,
    SkillResponseMeta,
)
from mcp_composer.core.catalog.catalog_manager import CatalogManager, normalize_tenant_ids
from mcp_composer.store.catalog_database import CatalogDatabaseInterface

_SKILL_KIND = RegistryResourceKind.SKILL.value

# ── Valid status values ───────────────────────────────────────────────────────

VALID_SKILL_STATUSES: frozenset[str] = frozenset(
    {"active", "draft", "deprecated", "deleted", "load-onstartup"}
)

# ── Exceptions ────────────────────────────────────────────────────────────────


class SkillNotFoundError(KeyError):
    """Raised when a (name, version) pair is absent from the catalog."""

    def __init__(self, name: str, version: str) -> None:
        self.skill_name = name
        self.skill_version = version
        super().__init__(f"Skill not found: {name}@{version}")


class SkillVersionCapError(ValueError):
    """Raised when publishing would exceed MAX_VERSIONS_PER_RESOURCE."""

    def __init__(self, name: str, count: int) -> None:
        self.skill_name = name
        self.count = count
        super().__init__(
            f"Skill '{name}' has reached the maximum version limit "
            f"({count}/{MAX_VERSIONS_PER_RESOURCE})"
        )


class InvalidSkillStatusError(ValueError):
    """Raised when a caller supplies an unrecognised status value."""

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(
            f"Invalid skill status {status!r}. "
            f"Must be one of: {sorted(VALID_SKILL_STATUSES)}"
        )


# ── Input model for list queries ──────────────────────────────────────────────


class SkillListFilter(BaseModel):
    """Query parameters for SkillManager.list()."""

    name_like: Optional[str] = None
    is_latest_only: bool = False
    status_filter: Optional[str] = None
    keywords: Optional[List[str]] = None
    tenant: Optional[str] = None
    start: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=1000)


# ── Private helpers ───────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_resource_metadata(private_meta: dict | None) -> dict | None:
    """Return DB ``data`` keys safe to expose under ``_meta.metadata``.

    ``remotes_config`` is omitted: transport and headers are merged into
    ``skill.remotes`` and may contain secrets.
    """
    if not private_meta:
        return None
    out = {k: v for k, v in private_meta.items() if k != "remotes_config"}
    return out if out else None


def _row_to_skill_response(
    row: dict, private_meta: dict | None = None
) -> SkillResponse:
    """Map a catalog DB row to a SkillResponse.

    Three-layer remote config merge (url-only in payload, transport_type in
    official_meta, headers in catalog_resource_metadata):

    1. ``official_meta.remotes_config`` supplies transport_type — always
       available even in list responses that don't fetch private_meta.
    2. ``private_meta.remotes_config`` overlays headers (and may also carry
       transport_type as the authoritative source when both are present).
    """
    skill = SkillJSON(**row["payload"])

    official_meta_data: dict = row.get("official_meta") or {}

    if skill.remotes:
        official_remotes_cfg: Dict[str, Any] = (
            official_meta_data.get("remotes_config") or {}
        )
        private_remotes_cfg: Dict[str, Any] = (
            (private_meta or {}).get("remotes_config") or {}
        )
        enriched = []
        for remote in skill.remotes:
            url = remote.url
            official_cfg = official_remotes_cfg.get(url) or {}
            private_cfg = private_remotes_cfg.get(url) or {}
            # private_meta is authoritative for transport_type when present
            transport = (
                private_cfg.get("transport_type")
                or official_cfg.get("transport_type")
                or remote.transport_type
            )
            enriched.append(
                SkillRemoteInfo(
                    url=url,
                    type=transport,
                    headers=private_cfg.get("headers") or remote.headers,
                )
            )
        skill.remotes = enriched

    published_at = (
        official_meta_data.get("published_at")
        or row.get("created_at")
        or _now_iso()
    )
    updated_at = (
        official_meta_data.get("updated_at")
        or row.get("updated_at")
        or published_at
    )
    is_latest_val = official_meta_data.get("is_latest")
    if is_latest_val is None:
        is_latest_val = row.get("is_latest", False)

    official = RegistryOfficialExtensions(
        status=official_meta_data.get("status") or "active",
        published_at=published_at,
        updated_at=updated_at,
        is_latest=is_latest_val,
    )

    meta = SkillResponseMeta(
        official=official,
        metadata=_public_resource_metadata(private_meta),
    )
    return SkillResponse(skill=skill, meta=meta)


# ── SkillManager ──────────────────────────────────────────────────────────────


class SkillManager(CatalogManager):
    """Catalog business logic for skills.

    The adapter must be initialised (``await db.initialize()``) before any
    manager method is called.  The manager itself is stateless — all state
    lives in the database.

    Example::

        db = CatalogInMemoryDatabase()
        await db.initialize()
        mgr = SkillManager(db)
        response = await mgr.publish(skill_json, tenant_ids=["team-a"])
    """

    def __init__(self, db: CatalogDatabaseInterface) -> None:
        super().__init__(db)

    # ── publish ───────────────────────────────────────────────────────────────

    async def publish(
        self,
        skill_json: SkillJSON,
        tenant_ids: Optional[List[str]] = None,
    ) -> SkillResponse:
        """Publish (create or update) a skill version.

        Business rules:
        1. Validate name + version — ensured by the ``SkillJSON`` Pydantic model.
        2. Normalise tenant IDs (deduplicate, strip whitespace, drop empty).
        3. Check version cap for genuinely *new* versions.
        4. Upsert the row for ``(name, version)`` — a **new** version always creates a new DB row (new id).
        5. Recompute ``is_latest`` across all versions so the semantically greatest version is latest.

        Returns:
            SkillResponse for the saved row.

        Raises:
            SkillVersionCapError: when a new version would exceed the cap.
        """
        await self._ensure_initialized()
        name = skill_json.name
        version = skill_json.version

        normalised_tenants = normalize_tenant_ids(tenant_ids)

        # Step 3 — version cap (skip for upserts of already-stored versions)
        existing = await self._db.get_skill(name, version)
        if existing is None:
            count = await self._db.count_skill_versions(name)
            if count >= MAX_VERSIONS_PER_RESOURCE:
                raise SkillVersionCapError(name, count)

        # Step 4–5 — build row; strip private remote fields from public payload
        now = _now_iso()
        payload = skill_json.model_dump(
            mode="json", by_alias=False, exclude_none=True
        )

        # Split remotes across three layers:
        #   payload         → [{ url }] only             (agent-readable, spec-aligned)
        #   official_meta   → { url: { transport_type } } (non-sensitive, in _meta response)
        #   resource_metadata → { url: { transport_type, headers } } (private, never in API)
        official_remotes_config: Dict[str, Any] = {}
        private_remotes_config: Dict[str, Any] = {}
        if payload.get("remotes"):
            public_remotes = []
            for r in payload["remotes"]:
                url = r.get("url", "")
                transport_type = r.get("transport_type") or r.get("type")
                if transport_type:
                    official_remotes_config[url] = {"transport_type": transport_type}
                    private_remotes_config[url] = {"transport_type": transport_type}
                if r.get("headers"):
                    private_remotes_config.setdefault(url, {})["headers"] = r["headers"]
                public_remotes.append({"url": url})
            payload["remotes"] = public_remotes

        official_meta: Dict[str, Any] = {
            "status": skill_json.status or "active",
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
        saved = await self._db.save_skill(row)

        # Persist private remote config (transport_type + headers) if any remotes need it.
        if private_remotes_config:
            await self._db.save_resource_metadata(
                str(saved["id"]), {"remotes_config": private_remotes_config}
            )

        await self.recompute_is_latest_for_skill_name(name)

        final_row = await self._db.get_skill(name, version)
        if final_row is None:
            raise SkillNotFoundError(name, version)
        private_meta = await self._db.get_resource_metadata(str(final_row["id"]))
        return _row_to_skill_response(final_row, private_meta)

    async def publish_with_resource_metadata(
        self,
        skill_json: SkillJSON,
        tenant_ids: Optional[List[str]] = None,
        resource_metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResponse:
        """Publish a skill and upsert ``catalog_resource_metadata.data`` in one step.

        Shallow-merges *resource_metadata* onto the existing private row (including
        ``remotes_config`` produced by :meth:`publish`). Later keys overwrite
        earlier ones for the same top-level name.
        """
        await self._ensure_initialized()
        response = await self.publish(skill_json, tenant_ids=tenant_ids)
        if not resource_metadata:
            return response
        row = await self._db.get_skill(skill_json.name, skill_json.version)
        if row is None:
            raise SkillNotFoundError(skill_json.name, skill_json.version)
        existing_raw = await self._db.get_resource_metadata(str(row["id"]))
        existing: Dict[str, Any] = dict(existing_raw or {})
        merged: Dict[str, Any] = {**existing, **resource_metadata}
        await self._db.save_resource_metadata(str(row["id"]), merged)
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_skill_response(row, private_meta)

    # ── get ───────────────────────────────────────────────────────────────────

    async def get(self, name: str, version: str) -> SkillResponse:
        """Return a specific skill version, including private remote config.

        Raises:
            SkillNotFoundError: when no row matches ``(name, version)``.
        """
        await self._ensure_initialized()
        row = await self._db.get_skill(name, version)
        if row is None:
            raise SkillNotFoundError(name, version)
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_skill_response(row, private_meta)

    # ── get_latest ────────────────────────────────────────────────────────────

    async def get_latest(self, name: str) -> SkillResponse:
        """Return the ``is_latest`` version for the given skill name, including private remote config.

        Raises:
            SkillNotFoundError: when no latest version exists for the name.
        """
        await self._ensure_initialized()
        row = await self._db.get_skill_by_filter(name, is_latest=True)
        if row is None:
            raise SkillNotFoundError(name, "latest")
        private_meta = await self._db.get_resource_metadata(str(row["id"]))
        return _row_to_skill_response(row, private_meta)

    # ── list ──────────────────────────────────────────────────────────────────

    async def list(self, filter: SkillListFilter) -> SkillListResponse:
        """Return a paginated list of skills matching *filter*.

        Args:
            filter: Query parameters (name_like, is_latest_only, tenant,
                    after_cursor, limit).

        Returns:
            SkillListResponse with items and pagination metadata.
        """
        await self._ensure_initialized()
        rows, has_more = await self._db.list_skills(
            name_like=filter.name_like,
            is_latest_only=filter.is_latest_only,
            status_filter=filter.status_filter,
            keywords=filter.keywords,
            tenant=filter.tenant,
            offset=filter.start,
            limit=filter.limit,
        )
        skills = [_row_to_skill_response(r) for r in rows]
        next_start = filter.start + len(skills) if has_more else None
        metadata = RegistryListMetadata(
            next_start=next_start, count=len(skills)
        )
        return SkillListResponse(skills=skills, metadata=metadata)

    # ── delete ────────────────────────────────────────────────────────────────

    async def delete(self, name: str, version: str) -> None:
        """Delete a skill version.

        If the deleted version was ``is_latest``, the most-recently-updated
        remaining version for the same name is promoted to ``is_latest``.

        Raises:
            SkillNotFoundError: when no row matches ``(name, version)``.
        """
        await self._ensure_initialized()
        row = await self._db.get_skill(name, version)
        if row is None:
            raise SkillNotFoundError(name, version)

        await self._db.delete_skill(name, version)
        await self.recompute_is_latest_for_skill_name(name)

    # ── get_content ───────────────────────────────────────────────────────────

    async def get_content(
        self, name: str, version: Optional[str] = None
    ) -> str | None:
        """Return the raw content for a skill version, or None if not stored.

        When *version* is omitted the ``is_latest`` version is resolved first.

        Raises:
            SkillNotFoundError: when the skill (or its latest version) does not exist.
        """
        await self._ensure_initialized()
        if version is None:
            row = await self._db.get_skill_by_filter(name, is_latest=True)
            if row is None:
                raise SkillNotFoundError(name, "latest")
            version = row["version"]
        else:
            row = await self._db.get_skill(name, version)
            if row is None:
                raise SkillNotFoundError(name, version)
        return await self._db.get_resource_content(_SKILL_KIND, name, version)

    # ── update_status ─────────────────────────────────────────────────────────

    async def update_status(
        self, name: str, version: str, status: str
    ) -> None:
        """Update the status of a skill version.

        The status is written to both ``payload["status"]`` and
        ``official_meta["status"]`` to keep them consistent.

        Raises:
            InvalidSkillStatusError: when *status* is not in VALID_SKILL_STATUSES.
            SkillNotFoundError: when no row matches ``(name, version)``.
        """
        await self._ensure_initialized()
        if status not in VALID_SKILL_STATUSES:
            raise InvalidSkillStatusError(status)

        row = await self._db.get_skill(name, version)
        if row is None:
            raise SkillNotFoundError(name, version)

        payload = dict(row.get("payload") or {})
        payload["status"] = status

        official_meta = dict(row.get("official_meta") or {})
        official_meta["status"] = status

        await self._db.update_skill_row(
            name, version, {"payload": payload, "official_meta": official_meta}
        )