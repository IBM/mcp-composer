"""catalog_database.py — Abstract interface for catalog DB operations (kind-aware resources + metadata)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CatalogDatabaseInterface(ABC):
    """Abstract interface for catalog storage.

    Resource rows are stored by ``kind`` (e.g. ``skill``, ``prompt``) with the same
    logical shape in ``catalog_resources``. Managers hold business logic; the adapter
    is kind-aware so callers do not need separate ``get_skill`` / ``get_prompt`` APIs.

    Lifecycle:
        db = ConcreteCatalogAdapter(...)
        await db.initialize()
        ...
        await db.close()
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Open the connection pool (or prepare in-memory state)."""

    @abstractmethod
    async def close(self) -> None:
        """Close the connection pool (or tear down in-memory state)."""

    # ── catalog resources (``kind`` + name + version — one table / layout) ─────

    @abstractmethod
    async def save_resource(self, kind: str, row: dict) -> dict:
        """Upsert a row for ``kind``; return the saved row (including generated fields).

        If ``row["content"]`` is present it may be stored separately and omitted from
        the returned dict (see adapter docs).
        """

    @abstractmethod
    async def get_resource(self, kind: str, name: str, version: str) -> dict | None:
        """Return the row for (kind, name, version), or None if not found."""

    @abstractmethod
    async def get_resource_by_filter(
        self, kind: str, name: str, is_latest: bool
    ) -> dict | None:
        """Return a row matching ``name`` and ``is_latest``, or None."""

    @abstractmethod
    async def list_resources(
        self,
        kind: str,
        *,
        name_like: str | None = None,
        is_latest_only: bool = False,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """Return a page of rows for ``kind`` and whether more rows exist after the page.

        ``keywords`` is applied only when ``kind`` is skill (metadata search); ignored
        for other kinds.
        """

    @abstractmethod
    async def count_resource_versions(self, kind: str, name: str) -> int:
        """Return the number of stored versions for ``kind`` and logical ``name``."""

    @abstractmethod
    async def delete_resource(self, kind: str, name: str, version: str) -> None:
        """Delete the row for (kind, name, version)."""

    @abstractmethod
    async def update_resource_row(
        self, kind: str, name: str, version: str, fields: dict
    ) -> None:
        """Patch columns on the row for (kind, name, version)."""

    @abstractmethod
    async def list_resource_versions_for_name(self, kind: str, name: str) -> list[dict]:
        """Return all rows for an exact ``kind`` and resource ``name`` (every version)."""

    # ── resource content (raw file body — fetched only on explicit request) ─────

    @abstractmethod
    async def get_resource_content(
        self, kind: str, name: str, version: str
    ) -> str | None:
        """Return the raw content string for (kind, name, version), or None if absent.

        Content is intentionally excluded from all standard list/get queries.
        Call this method only when the caller has explicitly requested the raw
        source (e.g. to render a Markdown skill file).
        """

    @abstractmethod
    async def save_resource_content(
        self, kind: str, name: str, version: str, content: str
    ) -> None:
        """Persist raw content for a catalog resource.

        May be called after ``save_resource``, or ``save_resource`` may persist
        content when ``row["content"]`` is present.
        """

    # ── resource metadata (private — never exposed in API responses) ──────────

    @abstractmethod
    async def save_resource_metadata(self, resource_id: str, private_meta: dict) -> None:
        """Upsert private metadata for a catalog row (Postgres: ``catalog_resource_metadata.data``)."""

    @abstractmethod
    async def get_resource_metadata(self, resource_id: str) -> dict | None:
        """Return the metadata dict for ``resource_id``, or None."""

    @abstractmethod
    async def delete_resource_metadata(self, resource_id: str) -> None:
        """Delete the metadata row for ``resource_id``."""
