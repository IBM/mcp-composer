"""catalog_in_memory_database.py — In-memory implementation of CatalogDatabaseInterface for unit tests (skill + prompt + resource metadata)."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from mcp_composer.core.models.catalog_constants import RegistryResourceKind

from .catalog_database import CatalogDatabaseInterface

_SKILL = RegistryResourceKind.SKILL.value
_PROMPT = RegistryResourceKind.PROMPT.value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_kind(kind: str) -> str:
    if kind not in (_SKILL, _PROMPT):
        raise ValueError(f"unsupported catalog kind: {kind!r}")
    return kind


class CatalogInMemoryDatabase(CatalogDatabaseInterface):
    """Thread-unsafe, in-memory implementation used exclusively in unit tests.

    Storage keys: (name, version) for skills/prompts; resource_id string for metadata.
    """

    def __init__(self) -> None:
        """Initialise empty in-memory storage for all resource kinds."""
        self._skills: dict[tuple[str, str], dict] = {}
        self._prompts: dict[tuple[str, str], dict] = {}
        # catalog_resources.id (string) -> private_meta dict
        self._resource_metadata: dict[str, dict] = {}
        # (kind, name, version) -> raw content string
        self._resource_content: dict[tuple[str, str, str], str] = {}
        self._next_int = 0

    def _uid(self) -> str:
        """Return a deterministic, monotonically increasing fake UUID string."""
        self._next_int += 1
        return f"fake-{self._next_int:04d}"

    def _store(self, kind: str) -> dict[tuple[str, str], dict]:
        _validate_kind(kind)
        return self._skills if kind == _SKILL else self._prompts

    def reset(self) -> None:
        """Clear all stored rows (convenience for test teardown)."""
        self._skills.clear()
        self._prompts.clear()
        self._resource_metadata.clear()
        self._resource_content.clear()
        self._next_int = 0

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """No-op; in-memory storage needs no setup."""

    async def close(self) -> None:
        """No-op; in-memory storage needs no teardown."""

    # ── kind-aware resources ───────────────────────────────────────────────────

    async def save_resource(self, kind: str, row: dict) -> dict:
        """Upsert a row; preserve id and created_at on update."""
        _validate_kind(kind)
        store = self._store(kind)
        key = (row["name"], row["version"])
        existing = store.get(key)
        now = _now_iso()
        stored = {
            "id": existing["id"] if existing else self._uid(),
            "kind": kind,
            "name": row["name"],
            "version": row["version"],
            "payload": copy.deepcopy(row.get("payload", {})),
            "official_meta": copy.deepcopy(row.get("official_meta", {})),
            "is_latest": row.get("is_latest", False),
            "tenant_ids": list(row.get("tenant_ids") or []),
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        store[key] = stored
        if row.get("content") is not None:
            self._resource_content[(kind, row["name"], row["version"])] = row["content"]
        return copy.deepcopy(stored)

    async def get_resource(self, kind: str, name: str, version: str) -> dict | None:
        """Return a deep copy of the stored row, or None if not found."""
        row = self._store(kind).get((name, version))
        return copy.deepcopy(row) if row else None

    async def get_resource_by_filter(
        self, kind: str, name: str, is_latest: bool
    ) -> dict | None:
        """Return the first row matching name and is_latest flag, or None."""
        for row in self._store(kind).values():
            if row["name"] == name and row["is_latest"] == is_latest:
                return copy.deepcopy(row)
        return None

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
        """Return a filtered, sorted, offset-paginated page of rows for ``kind``."""
        rows = list(self._store(kind).values())

        if is_latest_only:
            rows = [r for r in rows if r["is_latest"]]

        if status_filter:
            rows = [
                r
                for r in rows
                if (r.get("official_meta", {}).get("status") or "active") == status_filter
            ]

        if name_like:
            pattern = name_like.lower()
            rows = [r for r in rows if pattern in r["name"].lower()]

        if keywords and kind == _SKILL:

            def _matches_any(r: dict) -> bool:
                meta = r.get("payload", {}).get("metadata") or {}
                products = [str(v).lower() for v in meta.get("products", [])]
                tags = [str(v).lower() for v in meta.get("tags", [])]
                name_lower = r["name"].lower()
                return any(
                    kw in name_lower
                    or any(kw in p for p in products)
                    or any(kw in t for t in tags)
                    for kw in [k.lower() for k in keywords]
                )

            rows = [r for r in rows if _matches_any(r)]

        if tenant:
            rows = [r for r in rows if tenant in (r.get("tenant_ids") or [])]

        rows.sort(key=lambda r: r["name"])
        page = rows[offset : offset + limit]
        has_more = (offset + limit) < len(rows)
        return [copy.deepcopy(r) for r in page], has_more

    async def count_resource_versions(self, kind: str, name: str) -> int:
        """Return the number of stored versions for the given logical name."""
        store = self._store(kind)
        return sum(1 for (n, _) in store if n == name)

    async def delete_resource(self, kind: str, name: str, version: str) -> None:
        """Remove the row for (name, version); silently ignore missing keys."""
        store = self._store(kind)
        row = store.get((name, version))
        if row is not None:
            self._resource_metadata.pop(str(row["id"]), None)
            self._resource_content.pop((kind, name, version), None)
        store.pop((name, version), None)

    async def update_resource_row(
        self, kind: str, name: str, version: str, fields: dict
    ) -> None:
        """Patch the specified fields on the stored row; no-op for empty dict or missing row."""
        if not fields:
            return
        key = (name, version)
        row = self._store(kind).get(key)
        if row is None:
            return
        for k, v in fields.items():
            row[k] = v
        row["updated_at"] = _now_iso()

    async def list_resource_versions_for_name(self, kind: str, name: str) -> list[dict]:
        """Return every stored row for ``kind`` and ``name`` (all versions)."""
        store = self._store(kind)
        rows = [r for (n, _), r in store.items() if n == name]
        rows.sort(key=lambda r: r["version"])
        return [copy.deepcopy(r) for r in rows]

    # ── resource content methods ───────────────────────────────────────────────

    async def get_resource_content(
        self, kind: str, name: str, version: str
    ) -> str | None:
        """Return the raw content string for (kind, name, version), or None if absent."""
        return self._resource_content.get((kind, name, version))

    async def save_resource_content(
        self, kind: str, name: str, version: str, content: str
    ) -> None:
        """Store raw content for a catalog resource."""
        self._resource_content[(kind, name, version)] = content

    # ── resource metadata methods ──────────────────────────────────────────────

    async def save_resource_metadata(self, resource_id: str, private_meta: dict) -> None:
        """Upsert private metadata for a catalog resource row."""
        self._resource_metadata[str(resource_id)] = copy.deepcopy(private_meta)

    async def get_resource_metadata(self, resource_id: str) -> dict | None:
        """Return a deep copy of the metadata dict, or None if absent."""
        data = self._resource_metadata.get(str(resource_id))
        return copy.deepcopy(data) if data is not None else None

    async def delete_resource_metadata(self, resource_id: str) -> None:
        """Delete metadata for ``resource_id``; no-op if absent."""
        self._resource_metadata.pop(str(resource_id), None)
