"""catalog_postgres_adapter.py — asyncpg implementation of CatalogDatabaseInterface (skill + prompt + resource metadata)."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

import asyncpg
from mcp_composer.core.models.catalog_constants import (
    SKILL_CATALOG_UNCATEGORIZED,
    RegistryResourceKind,
)
from mcp_composer.core.utils.logger import LoggerFactory

from .catalog_database import CatalogDatabaseInterface

logger = LoggerFactory.get_logger()

_SKILL_KIND = RegistryResourceKind.SKILL.value
_PROMPT_KIND = RegistryResourceKind.PROMPT.value
_AGENT_KIND = RegistryResourceKind.AGENT.value
_WORKFLOW_KIND = RegistryResourceKind.WORKFLOW.value
_KNOWN_RESOURCE_KINDS = frozenset(
    {_SKILL_KIND, _PROMPT_KIND, _AGENT_KIND, _WORKFLOW_KIND}
)


def _expect_resource_kind(kind: str) -> str:
    if kind not in _KNOWN_RESOURCE_KINDS:
        raise ValueError(f"unsupported catalog kind: {kind!r}")
    return kind


# Columns returned for every resource SELECT
_JSONB_ROW_FIELDS = frozenset({"payload", "official_meta", "agent_card"})


def _row_field_sql_param(key: str, value: Any) -> tuple[Any, str]:
    """Serialize a catalog row UPDATE value; json-encode jsonb columns for asyncpg."""
    if key in _JSONB_ROW_FIELDS and isinstance(value, (dict, list)):
        return json.dumps(value), "::jsonb"
    return value, ""


_SKILL_COLUMNS = """
    id,
    kind,
    name,
    version,
    payload,
    official_meta,
    is_latest,
    tenant_ids,
    agent_card,
    created_at,
    updated_at
"""


def _row_to_dict(record: asyncpg.Record) -> dict:
    """Convert an asyncpg Record to a plain dict, normalising JSON and UUID fields."""
    row = dict(record)
    for key in ("payload", "official_meta", "agent_card"):
        val = row.get(key)
        if isinstance(val, str):
            row[key] = json.loads(val)
    for key in ("id",):
        if row.get(key) is not None:
            row[key] = str(row[key])
    for key in ("created_at", "updated_at"):
        if row.get(key) is not None:
            row[key] = row[key].isoformat()
    if row.get("tenant_ids") is None:
        row["tenant_ids"] = []
    return row


class CatalogPostgresAdapter(CatalogDatabaseInterface):
    """Thin asyncpg adapter for the catalog_resources table (skill operations).

    Pool setup mirrors PostgresAdapter — same __init__ kwargs and
    initialize()/close() lifecycle.
    """

    TABLE = "catalog_resources"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        url: str | None = None,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        """Configure connection parameters; pool is created later in initialize().

        Args:
            host: PostgreSQL host (ignored when url is provided).
            port: PostgreSQL port (default 5432, ignored when url is provided).
            database: PostgreSQL database name (ignored when url is provided).
            user: PostgreSQL username (ignored when url is provided).
            password: PostgreSQL password (ignored when url is provided).
            url: Full postgresql:// connection string (preferred over individual params).
            min_size: Minimum connections kept in the asyncpg pool.
            max_size: Maximum connections allowed in the asyncpg pool.
        """
        self._pool: asyncpg.Pool | None = None
        self._min_size = min_size
        self._max_size = max_size

        self._connection_params: dict[str, Any]
        if url:
            self._connection_params = self._parse_postgres_url(url)
        else:
            if not all([host, database, user, password]):
                raise ValueError(
                    "Either 'url' or all of 'host', 'database', 'user', 'password' must be provided"
                )
            self._connection_params = {
                "host": host,
                "port": port or 5432,
                "database": database,
                "user": user,
                "password": password,
            }

        # JSONB column in catalog_resource_metadata: "data" (current DDL) or legacy "private_meta".
        self._metadata_json_column = self._resolve_metadata_json_column()

    @staticmethod
    def _resolve_metadata_json_column() -> str:
        raw = (os.getenv("CATALOG_RESOURCE_METADATA_JSON_COLUMN") or "data").strip()
        if raw not in ("data", "private_meta"):
            raise ValueError(
                "CATALOG_RESOURCE_METADATA_JSON_COLUMN must be 'data' or 'private_meta', "
                f"not {raw!r}"
            )
        return raw

    # ── lifecycle ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_postgres_url(url: str) -> dict[str, Any]:
        """Parse a postgresql:// URL into a connection-params dict.

        Raises:
            ValueError: If the URL scheme, credentials, or database name are invalid.
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("postgresql", "postgres"):
                raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
            if not parsed.hostname:
                raise ValueError("URL must include hostname")
            if not parsed.path or parsed.path == "/":
                raise ValueError("URL must include database name")
            if not parsed.username:
                raise ValueError("URL must include username")
            if not parsed.password:
                raise ValueError("URL must include password")
            return {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "database": parsed.path.lstrip("/"),
                "user": parsed.username,
                "password": parsed.password,
            }
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Invalid PostgreSQL URL: {exc}") from exc

    async def initialize(self) -> None:
        """Create the asyncpg connection pool and apply schema migrations."""
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            min_size=self._min_size,
            max_size=self._max_size,
            **self._connection_params,
        )
        logger.info("CatalogPostgresAdapter pool created")
        await self._apply_migrations()

    async def _apply_migrations(self) -> None:
        """Idempotent schema migrations — run on every startup."""
        pool = self._get_pool()
        async with pool.acquire() as conn:
            # Add agent_card column if missing (A2A well-known card verbatim storage)
            await conn.execute("""
                ALTER TABLE catalog_resources
                    ADD COLUMN IF NOT EXISTS agent_card JSONB
                """)
        logger.info("CatalogPostgresAdapter migrations applied")

    async def close(self) -> None:
        """Close the asyncpg connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("CatalogPostgresAdapter pool closed")

    def _get_pool(self) -> asyncpg.Pool:
        """Return the active pool, raising RuntimeError if initialize() was not called."""
        if self._pool is None:
            raise RuntimeError(
                "CatalogPostgresAdapter.initialize() has not been called"
            )
        return self._pool

    # ── kind-aware catalog resources ───────────────────────────────────────────

    async def save_resource(self, kind: str, row: dict) -> dict:
        """INSERT … ON CONFLICT (kind, name, version) DO UPDATE. Returns saved row.

        If ``row["content"]`` is present it is written to the ``content`` column
        but is NOT included in the returned row (use ``get_resource_content``).
        If ``row["agent_card"]`` is present it is stored in the ``agent_card`` JSONB column.
        """
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        payload = json.dumps(row.get("payload", {}))
        official_meta = json.dumps(row.get("official_meta", {}))
        tenant_ids = row.get("tenant_ids") or []
        content: str | None = row.get("content")
        agent_card: str | None = (
            json.dumps(row["agent_card"]) if row.get("agent_card") else None
        )

        async with pool.acquire() as conn:
            if content is not None:
                record = await conn.fetchrow(
                    f"""
                    INSERT INTO {self.TABLE}
                        (kind, name, version, payload, official_meta, is_latest, tenant_ids, content, agent_card)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8, $9::jsonb)
                    ON CONFLICT (kind, name, version) DO UPDATE
                        SET payload       = EXCLUDED.payload,
                            official_meta = EXCLUDED.official_meta,
                            is_latest     = EXCLUDED.is_latest,
                            tenant_ids    = EXCLUDED.tenant_ids,
                            content       = EXCLUDED.content,
                            agent_card    = COALESCE(EXCLUDED.agent_card, {self.TABLE}.agent_card),
                            updated_at    = now()
                    RETURNING {_SKILL_COLUMNS}
                    """,
                    kind,
                    row["name"],
                    row["version"],
                    payload,
                    official_meta,
                    row.get("is_latest", False),
                    tenant_ids,
                    content,
                    agent_card,
                )
            else:
                record = await conn.fetchrow(
                    f"""
                    INSERT INTO {self.TABLE}
                        (kind, name, version, payload, official_meta, is_latest, tenant_ids, agent_card)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8::jsonb)
                    ON CONFLICT (kind, name, version) DO UPDATE
                        SET payload       = EXCLUDED.payload,
                            official_meta = EXCLUDED.official_meta,
                            is_latest     = EXCLUDED.is_latest,
                            tenant_ids    = EXCLUDED.tenant_ids,
                            agent_card    = COALESCE(EXCLUDED.agent_card, {self.TABLE}.agent_card),
                            updated_at    = now()
                    RETURNING {_SKILL_COLUMNS}
                    """,
                    kind,
                    row["name"],
                    row["version"],
                    payload,
                    official_meta,
                    row.get("is_latest", False),
                    tenant_ids,
                    agent_card,
                )
        return _row_to_dict(record)

    async def get_resource(self, kind: str, name: str, version: str) -> dict | None:
        """SELECT … WHERE kind=$1 AND name=$2 AND version=$3."""
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                f"""
                SELECT {_SKILL_COLUMNS}
                FROM {self.TABLE}
                WHERE kind=$1 AND name=$2 AND version=$3
                """,
                kind,
                name,
                version,
            )
        return _row_to_dict(record) if record else None

    async def get_resource_by_filter(
        self, kind: str, name: str, is_latest: bool
    ) -> dict | None:
        """SELECT … WHERE kind=$1 AND name=$2 AND is_latest=$3."""
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                f"""
                SELECT {_SKILL_COLUMNS}
                FROM {self.TABLE}
                WHERE kind=$1 AND name=$2 AND is_latest=$3
                """,
                kind,
                name,
                is_latest,
            )
        return _row_to_dict(record) if record else None

    async def list_resources(
        self,
        kind: str,
        *,
        name_like: str | None = None,
        is_latest_only: bool = False,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """Offset-paginated list of rows for ``kind``."""
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        conditions = ["kind = $1"]
        params: list[Any] = [kind]

        if is_latest_only:
            conditions.append("is_latest = TRUE")

        if status_filter:
            params.append(status_filter)
            conditions.append(
                f"(official_meta->>'status' = ${len(params)} OR official_meta->>'status' IS NULL)"
            )

        if name_like:
            params.append(f"%{name_like}%")
            conditions.append(f"name ILIKE ${len(params)}")

        if keywords and kind == _SKILL_KIND:
            kw_clauses = []
            for kw in keywords:
                params.append(f"%{kw.lower()}%")
                n = len(params)
                kw_clauses.append(
                    f"  name ILIKE ${n}"
                    f"  OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(payload->'metadata'->'products') p WHERE lower(p) LIKE ${n})"
                    f"  OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(payload->'metadata'->'tags') t WHERE lower(t) LIKE ${n})"
                )
            conditions.append("(" + " OR ".join(kw_clauses) + ")")

        if category is not None and kind == _SKILL_KIND:
            raw_cat = category.strip()
            if not raw_cat or raw_cat.lower() == SKILL_CATALOG_UNCATEGORIZED.lower():
                conditions.append(
                    "(payload->'metadata'->>'category' IS NULL "
                    "OR TRIM(payload->'metadata'->>'category') = '')"
                )
            else:
                params.append(raw_cat)
                n = len(params)
                conditions.append(
                    f"lower(trim(payload->'metadata'->>'category')) = lower(trim(${n}))"
                )

        if tenant:
            params.append(tenant)
            conditions.append(f"${len(params)} = ANY(tenant_ids)")

        where_clause = " AND ".join(conditions)

        params.append(limit + 1)
        fetch_limit_param = f"${len(params)}"
        params.append(offset)
        offset_param = f"${len(params)}"

        query = f"""
            SELECT {_SKILL_COLUMNS}
            FROM {self.TABLE}
            WHERE {where_clause}
            ORDER BY name ASC
            LIMIT {fetch_limit_param}
            OFFSET {offset_param}
        """

        async with pool.acquire() as conn:
            records = await conn.fetch(query, *params)

        rows = [_row_to_dict(r) for r in records]
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more

    async def list_distinct_skill_categories(
        self,
        *,
        is_latest_only: bool = True,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
    ) -> list[dict[str, Any]]:
        """GROUP BY trimmed ``metadata.category`` for skill rows matching the same filters as list."""
        pool = self._get_pool()
        conditions = ["kind = $1"]
        params: list[Any] = [_SKILL_KIND]

        if is_latest_only:
            conditions.append("is_latest = TRUE")

        if status_filter:
            params.append(status_filter)
            conditions.append(
                f"(official_meta->>'status' = ${len(params)} OR official_meta->>'status' IS NULL)"
            )

        if keywords:
            kw_clauses = []
            for kw in keywords:
                params.append(f"%{kw.lower()}%")
                n = len(params)
                kw_clauses.append(
                    f"  name ILIKE ${n}"
                    f"  OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(payload->'metadata'->'products') p WHERE lower(p) LIKE ${n})"
                    f"  OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(payload->'metadata'->'tags') t WHERE lower(t) LIKE ${n})"
                )
            conditions.append("(" + " OR ".join(kw_clauses) + ")")

        if tenant:
            params.append(tenant)
            conditions.append(f"${len(params)} = ANY(tenant_ids)")

        where_clause = " AND ".join(conditions)
        unc_sql = SKILL_CATALOG_UNCATEGORIZED.replace("'", "''")
        query = f"""
            SELECT cat_label AS name, COUNT(*)::int AS skill_count
            FROM (
                SELECT CASE
                    WHEN NULLIF(TRIM(payload->'metadata'->>'category'), '') IS NULL
                    THEN '{unc_sql}'
                    ELSE TRIM(payload->'metadata'->>'category')
                END AS cat_label
                FROM {self.TABLE}
                WHERE {where_clause}
            ) sub
            GROUP BY cat_label
            ORDER BY cat_label ASC
        """

        async with pool.acquire() as conn:
            records = await conn.fetch(query, *params)

        return [
            {"name": str(r["name"]), "skill_count": int(r["skill_count"])}
            for r in records
        ]

    async def count_resource_versions(self, kind: str, name: str) -> int:
        """SELECT count(*) WHERE kind=$1 AND name=$2."""
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT count(*) FROM {self.TABLE} WHERE kind=$1 AND name=$2",
                kind,
                name,
            )
        return int(count or 0)

    async def delete_resource(self, kind: str, name: str, version: str) -> None:
        """DELETE WHERE kind=$1 AND name=$2 AND version=$3."""
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {self.TABLE} WHERE kind=$1 AND name=$2 AND version=$3",
                kind,
                name,
                version,
            )

    async def update_resource_row(
        self, kind: str, name: str, version: str, fields: dict
    ) -> None:
        """UPDATE SET <only the keys in fields> WHERE kind=$1 AND name=$2 AND version=$3."""
        if not fields:
            return
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()

        set_parts = []
        params: list[Any] = [kind, name, version]
        for key, value in fields.items():
            param_value, cast = _row_field_sql_param(key, value)
            params.append(param_value)
            set_parts.append(f"{key} = ${len(params)}{cast}")
        set_parts.append("updated_at = now()")

        query = (
            f"UPDATE {self.TABLE} SET {', '.join(set_parts)} "
            f"WHERE kind=$1 AND name=$2 AND version=$3"
        )
        async with pool.acquire() as conn:
            await conn.execute(query, *params)

    async def list_resource_versions_for_name(self, kind: str, name: str) -> list[dict]:
        """SELECT all rows for ``kind`` and exact ``name`` (all versions)."""
        kind = _expect_resource_kind(kind)
        pool = self._get_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch(
                f"""
                SELECT {_SKILL_COLUMNS}
                FROM {self.TABLE}
                WHERE kind=$1 AND name=$2
                ORDER BY version ASC
                """,
                kind,
                name,
            )
        return [_row_to_dict(r) for r in records]

    # ── resource content methods ───────────────────────────────────────────────

    async def get_resource_content(
        self, kind: str, name: str, version: str
    ) -> str | None:
        """SELECT content FROM catalog_resources WHERE kind/name/version match."""
        pool = self._get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                f"SELECT content FROM {self.TABLE} WHERE kind=$1 AND name=$2 AND version=$3",
                kind,
                name,
                version,
            )
        return val  # already str or None

    async def save_resource_content(
        self, kind: str, name: str, version: str, content: str
    ) -> None:
        """UPDATE … SET content=$4 for an already-saved resource row."""
        pool = self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {self.TABLE}
                   SET content    = $4,
                       updated_at = now()
                 WHERE kind=$1 AND name=$2 AND version=$3
                """,
                kind,
                name,
                version,
                content,
            )

    # ── resource metadata methods ──────────────────────────────────────────────

    METADATA_TABLE = "catalog_resource_metadata"

    async def save_resource_metadata(
        self, resource_id: str, private_meta: dict
    ) -> None:
        """Upsert private metadata for a catalog resource row (see ``_metadata_json_column``)."""
        pool = self._get_pool()
        col = self._metadata_json_column
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self.METADATA_TABLE} (resource_id, {col})
                VALUES ($1::uuid, $2::jsonb)
                ON CONFLICT (resource_id) DO UPDATE
                    SET {col}       = EXCLUDED.{col},
                        updated_at = now()
                """,
                resource_id,
                json.dumps(private_meta),
            )

    async def get_resource_metadata(self, resource_id: str) -> dict | None:
        """Return the metadata dict for ``resource_id``, or None."""
        pool = self._get_pool()
        col = self._metadata_json_column
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {col} FROM {self.METADATA_TABLE} WHERE resource_id = $1::uuid",
                resource_id,
            )
        if row is None:
            return None
        val = row[col]
        return json.loads(val) if isinstance(val, str) else dict(val)

    async def delete_resource_metadata(self, resource_id: str) -> None:
        """Delete the metadata row for ``resource_id``."""
        pool = self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {self.METADATA_TABLE} WHERE resource_id = $1::uuid",
                resource_id,
            )
