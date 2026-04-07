"""catalog_database.py — Abstract interface for catalog DB operations (skill + prompt + resource metadata)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CatalogDatabaseInterface(ABC):
    """Abstract interface for catalog storage.

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

    # ── skill ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_skill(self, row: dict) -> dict:
        """Upsert a skill row; return the saved row (including DB-generated fields)."""

    @abstractmethod
    async def get_skill(self, name: str, version: str) -> dict | None:
        """Return the skill row for (name, version), or None if not found."""

    @abstractmethod
    async def get_skill_by_filter(self, name: str, is_latest: bool) -> dict | None:
        """Return the skill row matching name + is_latest flag, or None."""

    @abstractmethod
    async def list_skills(
        self,
        *,
        name_like: str | None = None,
        is_latest_only: bool = False,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """Return a page of skill rows and a boolean indicating whether more rows exist."""

    @abstractmethod
    async def count_skill_versions(self, name: str) -> int:
        """Return the total number of stored versions for a given skill name."""

    @abstractmethod
    async def list_skill_versions_for_name(self, name: str) -> list[dict]:
        """Return all skill rows for an exact skill *name* (every stored version)."""

    @abstractmethod
    async def delete_skill(self, name: str, version: str) -> None:
        """Delete the row for (name, version)."""

    @abstractmethod
    async def update_skill_row(self, name: str, version: str, fields: dict) -> None:
        """Patch arbitrary columns (by key) on the row for (name, version)."""

    # ── prompt ────────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_prompt(self, row: dict) -> dict:
        """Upsert a prompt row; return the saved row (including DB-generated fields)."""

    @abstractmethod
    async def get_prompt(self, name: str, version: str) -> dict | None:
        """Return the prompt row for (name, version), or None if not found."""

    @abstractmethod
    async def get_prompt_by_filter(self, name: str, is_latest: bool) -> dict | None:
        """Return the prompt row matching name + is_latest flag, or None."""

    @abstractmethod
    async def list_prompts(
        self,
        *,
        name_like: str | None,
        is_latest_only: bool,
        status_filter: str | None,
        tenant: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], bool]:
        """Return a page of prompt rows and a boolean indicating whether more rows exist."""

    @abstractmethod
    async def count_prompt_versions(self, name: str) -> int:
        """Return the total number of stored versions for a given prompt name."""

    @abstractmethod
    async def delete_prompt(self, name: str, version: str) -> None:
        """Delete the prompt row for (name, version)."""

    @abstractmethod
    async def update_prompt_row(self, name: str, version: str, fields: dict) -> None:
        """Patch arbitrary columns (by key) on the prompt row for (name, version)."""

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

        Can be called standalone after ``save_skill`` / ``save_prompt``, or the
        ``save_*`` methods will call it automatically when ``row["content"]`` is
        present.
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