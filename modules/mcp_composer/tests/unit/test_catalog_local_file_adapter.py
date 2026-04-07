"""Unit tests for CatalogLocalFileAdapter and get_catalog_db factory."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_composer.store.catalog_factory import get_catalog_db
from mcp_composer.store.catalog_local_file_adapter import CatalogLocalFileAdapter
from mcp_composer.store.catalog_postgres_adapter import CatalogPostgresAdapter


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def adapter(tmp_path):
    """Initialized CatalogLocalFileAdapter backed by a temporary directory."""
    a = CatalogLocalFileAdapter(root_path=str(tmp_path / "catalog"))
    a._skills_dir.mkdir(parents=True, exist_ok=True)
    return a


def _skill(name="my-skill", version="1.0.0", *, is_latest=False, tenant_ids=None):
    """Build a minimal skill row dict for use in tests."""
    return {
        "name": name,
        "version": version,
        "payload": {"description": f"{name} v{version}"},
        "official_meta": {"status": "active"},
        "is_latest": is_latest,
        "tenant_ids": tenant_ids or [],
    }


# ── folder-layout tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initialize_creates_skills_dir(tmp_path):
    """initialize() creates the skills root directory if it does not exist."""
    a = CatalogLocalFileAdapter(root_path=str(tmp_path / "catalog"))
    assert not (tmp_path / "catalog" / "skills").exists()
    await a.initialize()
    assert (tmp_path / "catalog" / "skills").is_dir()


@pytest.mark.asyncio
async def test_save_creates_version_json(tmp_path, adapter):
    """save_skill writes a <version>.json file under skills/<name>/."""
    await adapter.save_skill(_skill("hello", "1.0.0"))
    version_file = tmp_path / "catalog" / "skills" / "hello" / "1.0.0.json"
    assert version_file.exists()
    row = json.loads(version_file.read_text())
    assert row["name"] == "hello"
    assert row["version"] == "1.0.0"
    assert row["kind"] == "skill"


@pytest.mark.asyncio
async def test_save_latest_creates_marker(tmp_path, adapter):
    """save_skill with is_latest=True writes the 'latest' marker file."""
    await adapter.save_skill(_skill("hello", "2.0.0", is_latest=True))
    marker = tmp_path / "catalog" / "skills" / "hello" / "latest"
    assert marker.exists()
    assert marker.read_text().strip() == "2.0.0"


@pytest.mark.asyncio
async def test_save_non_latest_does_not_create_marker(tmp_path, adapter):
    """save_skill with is_latest=False does not create the 'latest' marker."""
    await adapter.save_skill(_skill("hello", "1.0.0", is_latest=False))
    marker = tmp_path / "catalog" / "skills" / "hello" / "latest"
    assert not marker.exists()


@pytest.mark.asyncio
async def test_delete_removes_version_file_and_dir(tmp_path, adapter):
    """delete_skill removes the version file and the skill directory when empty."""
    await adapter.save_skill(_skill("bye", "1.0.0"))
    await adapter.delete_skill("bye", "1.0.0")
    assert not (tmp_path / "catalog" / "skills" / "bye").exists()


@pytest.mark.asyncio
async def test_delete_latest_clears_marker(tmp_path, adapter):
    """Deleting the latest version also removes the 'latest' marker file."""
    await adapter.save_skill(_skill("s", "1.0.0", is_latest=True))
    await adapter.delete_skill("s", "1.0.0")
    marker = tmp_path / "catalog" / "skills" / "s" / "latest"
    assert not marker.exists()


# ── behavioural tests (same contract as CatalogInMemoryDatabase) ──────────────

@pytest.mark.asyncio
async def test_save_and_get(adapter):
    """save_skill stores a row that can be retrieved by get_skill."""
    saved = await adapter.save_skill(_skill())
    assert saved["id"]
    fetched = await adapter.get_skill("my-skill", "1.0.0")
    assert fetched is not None
    assert fetched["id"] == saved["id"]
    assert fetched["kind"] == "skill"


@pytest.mark.asyncio
async def test_upsert_preserves_id_and_created_at(adapter):
    """A second save_skill for the same key preserves the original id and created_at."""
    first = await adapter.save_skill(_skill())
    second = await adapter.save_skill({**_skill(), "payload": {"description": "new"}})
    assert second["id"] == first["id"]
    assert second["created_at"] == first["created_at"]
    assert second["payload"]["description"] == "new"


@pytest.mark.asyncio
async def test_get_not_found_returns_none(adapter):
    """get_skill returns None when no matching file exists."""
    assert await adapter.get_skill("ghost", "9.9.9") is None


@pytest.mark.asyncio
async def test_get_by_filter_latest(adapter):
    """get_skill_by_filter with is_latest=True returns the version marked latest."""
    await adapter.save_skill(_skill(version="1.0.0", is_latest=False))
    await adapter.save_skill(_skill(version="2.0.0", is_latest=True))
    row = await adapter.get_skill_by_filter("my-skill", is_latest=True)
    assert row is not None
    assert row["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_get_by_filter_not_latest(adapter):
    """get_skill_by_filter with is_latest=False returns a non-latest version."""
    await adapter.save_skill(_skill(version="1.0.0", is_latest=False))
    row = await adapter.get_skill_by_filter("my-skill", is_latest=False)
    assert row is not None
    assert row["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_get_by_filter_no_match(adapter):
    """get_skill_by_filter returns None when the skill directory does not exist."""
    assert await adapter.get_skill_by_filter("ghost", is_latest=True) is None


@pytest.mark.asyncio
async def test_count_versions(adapter):
    """count_skill_versions counts the number of .json files for a skill name."""
    await adapter.save_skill(_skill(version="1.0.0"))
    await adapter.save_skill(_skill(version="2.0.0"))
    assert await adapter.count_skill_versions("my-skill") == 2
    assert await adapter.count_skill_versions("other") == 0


@pytest.mark.asyncio
async def test_list_all(adapter):
    """list_skills with no filters returns all stored rows."""
    await adapter.save_skill(_skill("a-skill", "1.0.0"))
    await adapter.save_skill(_skill("b-skill", "1.0.0"))
    rows, has_more = await adapter.list_skills(
        name_like=None, is_latest_only=False,
        tenant=None, offset=0, limit=100,
    )
    assert len(rows) == 2
    assert has_more is False


@pytest.mark.asyncio
async def test_list_is_latest_only(adapter):
    """is_latest_only=True filters out non-latest versions."""
    await adapter.save_skill(_skill("a", "1.0.0", is_latest=False))
    await adapter.save_skill(_skill("a", "2.0.0", is_latest=True))
    await adapter.save_skill(_skill("b", "1.0.0", is_latest=True))
    rows, _ = await adapter.list_skills(
        name_like=None, is_latest_only=True,
        tenant=None, offset=0, limit=100,
    )
    assert all(r["is_latest"] for r in rows)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_list_name_like(adapter):
    """name_like filters by substring match on skill name."""
    await adapter.save_skill(_skill("alpha-skill", "1.0.0"))
    await adapter.save_skill(_skill("beta-skill", "1.0.0"))
    rows, _ = await adapter.list_skills(
        name_like="alpha", is_latest_only=False,
        tenant=None, offset=0, limit=100,
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "alpha-skill"


@pytest.mark.asyncio
async def test_list_tenant_filter(adapter):
    """tenant filter restricts results to skills whose tenant_ids contains the value."""
    await adapter.save_skill(_skill("a", "1.0.0", tenant_ids=["t1"]))
    await adapter.save_skill(_skill("b", "1.0.0", tenant_ids=["t2"]))
    rows, _ = await adapter.list_skills(
        name_like=None, is_latest_only=False,
        tenant="t2", offset=0, limit=100,
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "b"


@pytest.mark.asyncio
async def test_list_pagination(adapter):
    """Offset-based pagination splits results across two pages correctly."""
    for i in range(5):
        await adapter.save_skill(_skill(f"skill-{i:02d}", "1.0.0", is_latest=True))

    page1, has_more1 = await adapter.list_skills(
        name_like=None, is_latest_only=False,
        tenant=None, offset=0, limit=3,
    )
    assert len(page1) == 3
    assert has_more1 is True

    page2, has_more2 = await adapter.list_skills(
        name_like=None, is_latest_only=False,
        tenant=None, offset=3, limit=3,
    )
    assert len(page2) == 2
    assert has_more2 is False


@pytest.mark.asyncio
async def test_update_skill_row(adapter):
    """update_skill_row patches a field and persists it to the JSON file."""
    await adapter.save_skill(_skill(is_latest=False))
    await adapter.update_skill_row("my-skill", "1.0.0", {"is_latest": True})
    row = await adapter.get_skill("my-skill", "1.0.0")
    assert row["is_latest"] is True


@pytest.mark.asyncio
async def test_update_skill_row_latest_marker_updated(tmp_path, adapter):
    """update_skill_row with is_latest=True writes the 'latest' marker file."""
    await adapter.save_skill(_skill(is_latest=False))
    await adapter.update_skill_row("my-skill", "1.0.0", {"is_latest": True})
    marker = tmp_path / "catalog" / "skills" / "my-skill" / "latest"
    assert marker.exists()
    assert marker.read_text().strip() == "1.0.0"


@pytest.mark.asyncio
async def test_update_skill_row_empty_fields_is_noop(adapter):
    """update_skill_row with empty fields dict leaves updated_at unchanged."""
    saved = await adapter.save_skill(_skill())
    await adapter.update_skill_row("my-skill", "1.0.0", {})
    row = await adapter.get_skill("my-skill", "1.0.0")
    assert row["updated_at"] == saved["updated_at"]


@pytest.mark.asyncio
async def test_update_nonexistent_is_noop(adapter):
    """update_skill_row on a missing (name, version) does not raise."""
    await adapter.update_skill_row("ghost", "9.9.9", {"is_latest": True})


@pytest.mark.asyncio
async def test_delete_nonexistent_is_noop(adapter):
    """delete_skill on a missing (name, version) does not raise."""
    await adapter.delete_skill("ghost", "9.9.9")


# ── factory tests ──────────────────────────────────────────────────────────────

def test_factory_returns_local_file_by_default(monkeypatch, tmp_path):
    """get_catalog_db defaults to CatalogLocalFileAdapter when no DB type is set."""
    monkeypatch.delenv("MCP_DATABASE_TYPE", raising=False)
    monkeypatch.delenv("MCP_USE_LOCAL_FILE_STORAGE", raising=False)
    monkeypatch.setenv("MCP_CATALOG_FILE_PATH", str(tmp_path / "catalog"))

    db = get_catalog_db()
    assert isinstance(db, CatalogLocalFileAdapter)


def test_factory_returns_local_file_when_flag_set(monkeypatch, tmp_path):
    """get_catalog_db returns CatalogLocalFileAdapter when MCP_USE_LOCAL_FILE_STORAGE=true."""
    monkeypatch.delenv("MCP_DATABASE_TYPE", raising=False)
    monkeypatch.setenv("MCP_USE_LOCAL_FILE_STORAGE", "true")
    monkeypatch.setenv("MCP_CATALOG_FILE_PATH", str(tmp_path / "catalog"))

    db = get_catalog_db()
    assert isinstance(db, CatalogLocalFileAdapter)


def test_factory_returns_postgres_when_type_set(monkeypatch):
    """get_catalog_db returns CatalogPostgresAdapter when MCP_DATABASE_TYPE=postgres."""
    monkeypatch.setenv("MCP_DATABASE_TYPE", "postgres")
    monkeypatch.setenv("MCP_DATABASE_HOST", "localhost")
    monkeypatch.setenv("MCP_DATABASE_NAME", "mcp_servers")
    monkeypatch.setenv("MCP_DATABASE_USER", "postgres") # pragma: allowlist secret
    monkeypatch.setenv("MCP_DATABASE_PASSWORD", "postgres") # pragma: allowlist secret
    monkeypatch.setenv("MCP_DATABASE_PORT", "5432")
    monkeypatch.delenv("MCP_DATABASE_URL", raising=False)

    db = get_catalog_db()
    assert isinstance(db, CatalogPostgresAdapter)
    assert db._connection_params["host"] == "localhost"
    assert db._connection_params["database"] == "mcp_servers"


def test_factory_postgres_via_url(monkeypatch):
    """get_catalog_db accepts a full MCP_DATABASE_URL for the Postgres adapter."""
    monkeypatch.setenv("MCP_DATABASE_TYPE", "postgres")
    monkeypatch.setenv("MCP_DATABASE_URL", "postgresql://u:p@localhost:5432/db") # pragma: allowlist secret
    monkeypatch.delenv("MCP_DATABASE_HOST", raising=False)

    db = get_catalog_db()
    assert isinstance(db, CatalogPostgresAdapter)


def test_factory_postgres_missing_vars_raises(monkeypatch):
    """get_catalog_db raises ValueError when Postgres vars are incomplete."""
    monkeypatch.setenv("MCP_DATABASE_TYPE", "postgres")
    monkeypatch.delenv("MCP_DATABASE_URL", raising=False)
    monkeypatch.delenv("MCP_DATABASE_HOST", raising=False)
    monkeypatch.delenv("MCP_DATABASE_USER", raising=False)
    monkeypatch.delenv("MCP_DATABASE_PASSWORD", raising=False)
    monkeypatch.delenv("MCP_DATABASE_NAME", raising=False)

    with pytest.raises(ValueError, match="MCP_DATABASE_TYPE=postgres"):
        get_catalog_db()


def test_factory_local_uses_catalog_file_path(monkeypatch, tmp_path):
    """MCP_CATALOG_FILE_PATH sets the root directory of CatalogLocalFileAdapter."""
    monkeypatch.delenv("MCP_DATABASE_TYPE", raising=False)
    monkeypatch.setenv("MCP_USE_LOCAL_FILE_STORAGE", "true")
    custom_root = str(tmp_path / "my-catalog")
    monkeypatch.setenv("MCP_CATALOG_FILE_PATH", custom_root)

    db = get_catalog_db()
    assert str(db._root) == custom_root