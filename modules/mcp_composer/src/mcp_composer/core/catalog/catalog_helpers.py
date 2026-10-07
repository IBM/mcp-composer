"""catalog_helpers.py — Shared row mapping and pagination for skill / prompt managers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mcp_composer.core.models.catalog_common import RegistryListMetadata, RegistryOfficialExtensions


def utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string (used for publish timestamps)."""
    return datetime.now(timezone.utc).isoformat()


def registry_official_extensions_from_row(row: dict) -> RegistryOfficialExtensions:
    """Build :class:`RegistryOfficialExtensions` from a ``catalog_resources``-shaped row."""
    official_meta_data: dict = row.get("official_meta") or {}
    published_at_str = (
        official_meta_data.get("published_at") or row.get("created_at") or utc_now_iso()
    )
    updated_at_str = (
        official_meta_data.get("updated_at") or row.get("updated_at") or published_at_str
    )

    # Convert ISO strings to datetime objects
    published_at = (
        datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
        if isinstance(published_at_str, str)
        else published_at_str
    )
    updated_at = (
        datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        if isinstance(updated_at_str, str)
        else updated_at_str
    )

    is_latest_val = official_meta_data.get("is_latest")
    if is_latest_val is None:
        is_latest_val = row.get("is_latest", False)

    return RegistryOfficialExtensions(
        status=official_meta_data.get("status") or "active",
        publishedAt=published_at,
        updatedAt=updated_at,
        isLatest=is_latest_val,
    )


def registry_list_metadata_for_page(
    start: int, items: list[Any], has_more: bool
) -> RegistryListMetadata:
    """Build list pagination metadata (``next_start`` + ``count``)."""
    next_start = start + len(items) if has_more else None
    return RegistryListMetadata(nextStart=next_start, count=len(items))
