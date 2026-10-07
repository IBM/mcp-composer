"""catalog_manager.py — Shared catalog_resource helpers (version ordering, is_latest)."""

from __future__ import annotations

from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.store.catalog_database import CatalogDatabaseInterface
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, Field


class CatalogResourceListFilter(BaseModel):
    """Query parameters for listing rows in ``catalog_resources`` (all kinds).

    ``kind`` must match the manager you call (e.g. ``SkillManager.list`` requires
    ``kind=RegistryResourceKind.SKILL``).

    ``keywords`` is only used when listing **skills** (product/tag/name metadata search);
    other kinds pass it through as ``None`` or it is ignored by the store.
    """

    kind: RegistryResourceKind
    name_like: str | None = None
    is_latest_only: bool = False
    status_filter: str | None = None
    keywords: list[str] | None = None
    tenant: str | None = None
    #: When set (skill lists only), restrict to ``metadata.category`` for this value.
    #: Use :data:`~mcp_composer.core.models.catalog_constants.SKILL_CATALOG_UNCATEGORIZED`
    #: to match skills with no category.
    category: str | None = None
    start: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=1000)


def expect_catalog_list_filter_kind(
    filter: CatalogResourceListFilter,
    expected: RegistryResourceKind,
) -> None:
    """Raise ``ValueError`` if *filter*.kind does not match *expected*."""
    if filter.kind != expected:
        raise ValueError(f"list filter kind must be {expected.value!r}, got {filter.kind.value!r}")


def normalize_tenant_ids(tenant_ids: list[str] | None) -> list[str]:
    """Deduplicate tenant IDs, strip whitespace, drop empty."""
    return sorted({t.strip() for t in (tenant_ids or []) if t and t.strip()})


def max_catalog_version_string(versions: list[str]) -> str | None:
    """Return the greatest version string using PEP 440 semantics when parseable.

    Unparseable versions are ordered after parseable ones and compared lexicographically
    among themselves.
    """
    if not versions:
        return None

    def _key(v: str) -> tuple[int, Version] | tuple[int, str]:
        try:
            return (0, Version(v))
        except InvalidVersion:
            return (1, v)

    return max(versions, key=_key)


class CatalogManager:
    """Base catalog logic shared across resource kinds (skills, prompts, agents, …).

    Holds the database adapter and common lifecycle; subclasses implement kind-specific
    publish/get flows and call :meth:`recompute_is_latest_for_skill_name` where needed.
    """

    def __init__(self, db: CatalogDatabaseInterface) -> None:
        self._db = db
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self._db.initialize()
            self._initialized = True

    async def close(self) -> None:
        await self._db.close()

    async def recompute_is_latest_for_resource_name(self, kind: str, name: str) -> None:
        """Set ``is_latest`` on all rows for *kind* + *name* so exactly one row is latest.

        The latest row is the greatest **non-deleted** version under
        :func:`max_catalog_version_string` (PEP 440).  Deleted versions are never
        marked as ``is_latest``.  Updates both the ``is_latest`` column and
        ``official_meta["is_latest"]``.

        Non-latest rows are updated before the latest row so filesystem adapters can keep
        the ``latest`` marker consistent.
        """
        await self._ensure_initialized()
        if kind not in ("skill", "prompt", "agent", "workflow"):
            return

        rows = await self._db.list_resource_versions_for_name(kind, name)
        if not rows:
            return

        # Only non-deleted versions are eligible to be "latest".
        active_versions = [
            r["version"]
            for r in rows
            if (r.get("official_meta") or {}).get("status", "active") != "deleted"
        ]
        latest_ver = max_catalog_version_string(active_versions) if active_versions else None

        # Single pass: update all rows in one iteration
        for row in rows:
            ver = row["version"]
            is_latest = latest_ver is not None and ver == latest_ver
            official_meta = dict(row.get("official_meta") or {})
            official_meta["is_latest"] = is_latest
            await self._db.update_resource_row(
                kind,
                name,
                ver,
                {"is_latest": is_latest, "official_meta": official_meta},
            )

    async def recompute_is_latest_for_skill_name(self, name: str) -> None:
        """Set ``is_latest`` on all skill rows for *name* so exactly one row is latest."""
        await self.recompute_is_latest_for_resource_name("skill", name)

    async def recompute_is_latest_for_prompt_name(self, name: str) -> None:
        """Set ``is_latest`` on all prompt rows for *name* (same rules as skills)."""
        await self.recompute_is_latest_for_resource_name("prompt", name)

    async def recompute_is_latest_for_agent_name(self, name: str) -> None:
        """Set ``is_latest`` on all agent rows for *name* (same rules as skills)."""
        await self.recompute_is_latest_for_resource_name("agent", name)

    async def recompute_is_latest_for_workflow_name(self, name: str) -> None:
        """Set ``is_latest`` on all workflow rows for *name* (same rules as skills)."""
        await self.recompute_is_latest_for_resource_name("workflow", name)
