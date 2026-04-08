"""catalog_manager.py — Shared catalog_resource helpers (version ordering, is_latest)."""

from __future__ import annotations

from typing import List, Optional

from packaging.version import InvalidVersion, Version

from mcp_composer.store.catalog_database import CatalogDatabaseInterface


def normalize_tenant_ids(tenant_ids: Optional[List[str]]) -> List[str]:
    """Deduplicate tenant IDs, strip whitespace, drop empty."""
    return sorted(
        {t.strip() for t in (tenant_ids or []) if t and t.strip()}
    )


def max_catalog_version_string(versions: list[str]) -> str | None:
    """Return the greatest version string using PEP 440 semantics when parseable.

    Unparseable versions are ordered after parseable ones and compared lexicographically
    among themselves.
    """
    if not versions:
        return None

    def _key(v: str) -> tuple:
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

        The latest row is the greatest version under :func:`max_catalog_version_string`
        (PEP 440). Updates both the ``is_latest`` column and ``official_meta["is_latest"]``.

        Non-latest rows are updated before the latest row so filesystem adapters can keep
        the ``latest`` marker consistent.
        """
        await self._ensure_initialized()
        if kind not in ("skill", "prompt"):
            return

        rows = await self._db.list_resource_versions_for_name(kind, name)
        if not rows:
            return

        versions = [r["version"] for r in rows]
        latest_ver = max_catalog_version_string(versions)
        if latest_ver is None:
            return

        for row in rows:
            ver = row["version"]
            if ver == latest_ver:
                continue
            official_meta = dict(row.get("official_meta") or {})
            official_meta["is_latest"] = False
            await self._db.update_resource_row(
                kind,
                name,
                ver,
                {"is_latest": False, "official_meta": official_meta},
            )

        for row in rows:
            ver = row["version"]
            if ver != latest_ver:
                continue
            official_meta = dict(row.get("official_meta") or {})
            official_meta["is_latest"] = True
            await self._db.update_resource_row(
                kind,
                name,
                ver,
                {"is_latest": True, "official_meta": official_meta},
            )

    async def recompute_is_latest_for_skill_name(self, name: str) -> None:
        """Set ``is_latest`` on all skill rows for *name* so exactly one row is latest."""
        await self.recompute_is_latest_for_resource_name("skill", name)

    async def recompute_is_latest_for_prompt_name(self, name: str) -> None:
        """Set ``is_latest`` on all prompt rows for *name* (same rules as skills)."""
        await self.recompute_is_latest_for_resource_name("prompt", name)
