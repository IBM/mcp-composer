"""Tests for CatalogPostgresAdapter helpers."""

from __future__ import annotations

from mcp_composer.store.catalog_postgres_adapter import _row_field_sql_param


def test_row_field_sql_param_json_encodes_jsonb_columns() -> None:
    value, cast = _row_field_sql_param(
        "official_meta",
        {"status": "active", "is_latest": True},
    )
    assert cast == "::jsonb"
    assert '"is_latest": true' in value
    assert isinstance(value, str)


def test_row_field_sql_param_passes_through_scalar_fields() -> None:
    value, cast = _row_field_sql_param("is_latest", True)
    assert value is True
    assert cast == ""
