"""Unit tests for catalog_helpers (shared row mapping and list metadata)."""

from mcp_composer.core.catalog.catalog_helpers import (
    registry_list_metadata_for_page,
    registry_official_extensions_from_row,
    utc_now_iso,
)


def test_utc_now_iso_is_non_empty_string() -> None:
    s = utc_now_iso()
    assert isinstance(s, str)
    assert len(s) > 10
    assert "T" in s


def test_registry_official_extensions_from_row_minimal() -> None:
    row = {
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-02T00:00:00+00:00",
        "is_latest": True,
        "official_meta": {
            "status": "draft",
            "published_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-02T00:00:00+00:00",
            "is_latest": True,
        },
    }
    ext = registry_official_extensions_from_row(row)
    assert ext.status == "draft"
    assert ext.is_latest is True


def test_registry_official_extensions_from_row_defaults_status() -> None:
    row = {"created_at": "2024-01-01T00:00:00+00:00", "official_meta": {}}
    ext = registry_official_extensions_from_row(row)
    assert ext.status == "active"


def test_registry_list_metadata_for_page() -> None:
    m = registry_list_metadata_for_page(10, [1, 2], has_more=True)
    assert m.count == 2
    assert m.next_start == 12

    m2 = registry_list_metadata_for_page(0, [], has_more=False)
    assert m2.count == 0
    assert m2.next_start is None
