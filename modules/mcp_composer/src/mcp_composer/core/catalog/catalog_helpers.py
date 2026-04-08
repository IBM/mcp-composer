"""catalog_helpers.py — Shared row mapping and pagination for skill / prompt managers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mcp_composer.core.models.catalog_common import (
    RegistryListMetadata,
    RegistryOfficialExtensions,
)


def utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string (used for publish timestamps)."""
    return datetime.now(timezone.utc).isoformat()


def registry_official_extensions_from_row(row: dict) -> RegistryOfficialExtensions:
    """Build :class:`RegistryOfficialExtensions` from a ``catalog_resources``-shaped row."""
    official_meta_data: dict = row.get("official_meta") or {}
    published_at = (
        official_meta_data.get("published_at")
        or row.get("created_at")
        or utc_now_iso()
    )
    updated_at = (
        official_meta_data.get("updated_at")
        or row.get("updated_at")
        or published_at
    )
    is_latest_val = official_meta_data.get("is_latest")
    if is_latest_val is None:
        is_latest_val = row.get("is_latest", False)

    return RegistryOfficialExtensions(
        status=official_meta_data.get("status") or "active",
        published_at=published_at,
        updated_at=updated_at,
        is_latest=is_latest_val,
    )


def registry_list_metadata_for_page(
    start: int, items: list[Any], has_more: bool
) -> RegistryListMetadata:
    """Build list pagination metadata (``next_start`` + ``count``)."""
    next_start = start + len(items) if has_more else None
    return RegistryListMetadata(next_start=next_start, count=len(items))
