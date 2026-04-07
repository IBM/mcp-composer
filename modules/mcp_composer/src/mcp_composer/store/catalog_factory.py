"""catalog_factory.py — Factory for CatalogDatabaseInterface.

Mirrors ServerConfigurationManager.get_database_from_config() but for the
catalog layer.  Returns an *uninitialized* adapter; the caller must do:

    db = get_catalog_db()
    await db.initialize()
    ...
    await db.close()

Selection priority (same logic as the main DB factory):
  1. MCP_DATABASE_TYPE=postgres  → CatalogPostgresAdapter
     (reads MCP_DATABASE_URL  **or**  MCP_DATABASE_HOST / MCP_DATABASE_NAME /
      MCP_DATABASE_USER / MCP_DATABASE_PASSWORD / MCP_DATABASE_PORT)
  2. MCP_USE_LOCAL_FILE_STORAGE=true  → CatalogLocalFileAdapter
  3. Fallback  → CatalogLocalFileAdapter
     (root from MCP_CATALOG_FILE_PATH, default ./catalog)
"""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv

from mcp_composer.core.utils import LoggerFactory
from mcp_composer.store.catalog_database import CatalogDatabaseInterface
from mcp_composer.store.catalog_local_file_adapter import CatalogLocalFileAdapter
from mcp_composer.store.catalog_postgres_adapter import CatalogPostgresAdapter

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()

_TRUTHY = ("true", "1", "yes", "on")


def get_catalog_db() -> CatalogDatabaseInterface:
    """Return an uninitialized CatalogDatabaseInterface chosen from env vars.

    Environment variables read:
      MCP_DATABASE_TYPE         — "postgres" selects CatalogPostgresAdapter
      MCP_DATABASE_URL          — full Postgres URL (preferred)
      MCP_DATABASE_HOST         — Postgres host (if no URL)
      MCP_DATABASE_PORT         — Postgres port (default 5432)
      MCP_DATABASE_NAME         — Postgres database name
      MCP_DATABASE_USER         — Postgres user
      MCP_DATABASE_PASSWORD     — Postgres password
      MCP_USE_LOCAL_FILE_STORAGE — "true" / "1" / "yes" / "on" → local files
      MCP_CATALOG_FILE_PATH     — root dir for local file adapter (default ./catalog)
    """
    db_type = (os.getenv("MCP_DATABASE_TYPE") or "").strip().lower()

    if db_type == "postgres":
        adapter = _build_postgres_adapter()
        logger.info("Catalog DB factory → CatalogPostgresAdapter")
        return adapter

    use_local = os.getenv("MCP_USE_LOCAL_FILE_STORAGE", "false").strip().lower()
    root = os.getenv("MCP_CATALOG_FILE_PATH", "catalog")

    if use_local in _TRUTHY:
        logger.info(
            "Catalog DB factory → CatalogLocalFileAdapter "
            "(MCP_USE_LOCAL_FILE_STORAGE=true, root=%s)",
            root,
        )
        return CatalogLocalFileAdapter(root_path=root)

    # Default fallback: local files, no external service required
    logger.info(
        "Catalog DB factory → CatalogLocalFileAdapter (default fallback, root=%s)", root
    )
    return CatalogLocalFileAdapter(root_path=root)


# ── internal helpers ───────────────────────────────────────────────────────────


def _build_postgres_adapter() -> CatalogPostgresAdapter:
    """Build CatalogPostgresAdapter from MCP_DATABASE_* env vars."""
    url = (os.getenv("MCP_DATABASE_URL") or "").strip()
    if url:
        return CatalogPostgresAdapter(url=url)

    host = (os.getenv("MCP_DATABASE_HOST") or "").strip()
    database = (os.getenv("MCP_DATABASE_NAME") or "").strip()
    user = (os.getenv("MCP_DATABASE_USER") or "").strip()
    password = (os.getenv("MCP_DATABASE_PASSWORD") or "").strip()
    port = int((os.getenv("MCP_DATABASE_PORT") or "5432").strip())

    missing = [
        name
        for name, val in [
            ("MCP_DATABASE_HOST", host),
            ("MCP_DATABASE_NAME", database),
            ("MCP_DATABASE_USER", user),
            ("MCP_DATABASE_PASSWORD", password),
        ]
        if not val
    ]

    if missing:
        raise ValueError(
            "MCP_DATABASE_TYPE=postgres but required vars are missing or empty: "
            f"{', '.join(missing)}. Provide MCP_DATABASE_URL or all individual vars."
        )

    return CatalogPostgresAdapter(
        host=host, port=port, database=database, user=user, password=password
    )