"""
Query-first layered tool discovery helpers.

Shared by LayeredOpenAPIFactory and LayeredMCPFactory so large catalogs
never dump unbounded tool lists into agent context.

Ranking adapters live in ``layered_rankers`` (``Bm25Ranker``, ``TfidfRanker``).
``MCP_TOOL_DISCOVERY_RANKER`` (config ``tool_discovery_ranker``) selects the
adapter (default ``bm25_fallback``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp_composer.core.member_servers.layered_rankers import (
    CatalogRanker,
    resolve_ranker,
)

# Catalog size above which no-arg get_service_info returns a tag overview
# instead of the full slim list.
FULL_LIST_MAX = 40
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
SUMMARY_MAX_LEN = 200

DISCOVERY_USAGE = (
    "Call get_service_info(query='...') to search; "
    "get_service_info(service='name') for one service detail; "
    "then get_type_info and make_tool_call."
)

OVERVIEW_USAGE = (
    "Catalog is large, so only tool names are listed. Pick a name from 'names' "
    "and call get_service_info(service='name') for its summary, or "
    "get_service_info(query='...') to search names and descriptions "
    "(optional tags/limit). Summaries and schemas are never returned in bulk."
)


@dataclass
class ToolCatalogEntry:
    """Normalized catalog entry for discovery ranking and slim list responses."""

    name: str
    summary: str = ""
    description: str = ""
    path: str = ""
    http_method: str = ""
    tags: list[str] = field(default_factory=list)
    search_text: str = ""
    # Extra fields preserved for OA operationId keying etc.
    extra: dict[str, Any] = field(default_factory=dict)

    def ensure_search_text(self) -> str:
        if self.search_text:
            return self.search_text
        parts = [
            self.name,
            self.summary,
            self.description,
            self.path,
            self.http_method,
            " ".join(self.tags),
        ]
        self.search_text = " ".join(p for p in parts if p)
        return self.search_text


def clamp_limit(limit: int | None) -> int:
    """Clamp limit to [1, MAX_LIMIT], defaulting to DEFAULT_LIMIT."""
    if limit is None:
        return DEFAULT_LIMIT
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _truncate(text: str, max_len: int = SUMMARY_MAX_LEN) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def slim_entry(entry: ToolCatalogEntry, score: float | None = None) -> dict[str, Any]:
    """Slim list-mode payload — never includes schemas."""
    summary = entry.summary or entry.description
    item: dict[str, Any] = {
        "name": entry.name,
        "summary": _truncate(summary),
        "tags": list(entry.tags),
    }
    if entry.http_method:
        item["http_method"] = entry.http_method
    if entry.path:
        item["path"] = entry.path
    if entry.extra.get("operationId"):
        item["operationId"] = entry.extra["operationId"]
    if score is not None:
        item["score"] = round(float(score), 4)
    return item


def build_tag_index(entries: list[ToolCatalogEntry]) -> list[dict[str, Any]]:
    """Return sorted tag name/count pairs."""
    counts: dict[str, int] = {}
    for entry in entries:
        for tag in entry.tags:
            if not tag:
                continue
            counts[tag] = counts.get(tag, 0) + 1
    return [
        {"name": name, "count": counts[name]}
        for name in sorted(counts.keys(), key=lambda t: (-counts[t], t))
    ]


def build_prefix_index(entries: list[ToolCatalogEntry]) -> list[dict[str, Any]]:
    """Return name-prefix groups (leading token of the tool name) with counts."""
    counts: dict[str, int] = {}
    for entry in entries:
        name = (entry.name or "").strip()
        if not name:
            continue
        prefix = name.replace("-", "_").split("_", 1)[0].lower()
        if not prefix:
            continue
        counts[prefix] = counts.get(prefix, 0) + 1
    return [
        {"name": name, "count": counts[name]}
        for name in sorted(counts.keys(), key=lambda p: (-counts[p], p))
    ]


def _filter_by_tags(
    entries: list[ToolCatalogEntry], tags: list[str] | None
) -> list[ToolCatalogEntry]:
    if not tags:
        return entries
    wanted = {t.lower().strip() for t in tags if t and str(t).strip()}
    if not wanted:
        return entries
    filtered: list[ToolCatalogEntry] = []
    for entry in entries:
        entry_tags = {t.lower() for t in entry.tags}
        if entry_tags & wanted:
            filtered.append(entry)
    return filtered


def rank_entries(
    query: str,
    entries: list[ToolCatalogEntry],
    limit: int | None = None,
    tags: list[str] | None = None,
    *,
    ranker: CatalogRanker | None = None,
) -> list[tuple[ToolCatalogEntry, float]]:
    """
    Rank catalog entries by relevance to query.

    Uses the configured ``CatalogRanker`` adapter (see
    ``tool_discovery_ranker`` / ``MCP_TOOL_DISCOVERY_RANKER``), or an injected
    ``ranker`` for tests.

    Returns up to ``limit`` (entry, score) pairs sorted highest-first.
    Zero-score entries are omitted; if all scores are zero, returns [].
    """
    limit = clamp_limit(limit)
    candidates = _filter_by_tags(entries, tags)
    if not candidates:
        return []

    query = (query or "").strip()
    if not query:
        # Tag-only filter: return first N in stable order with score 1.0
        return [(e, 1.0) for e in candidates[:limit]]

    corpus_texts = [e.ensure_search_text() for e in candidates]
    active = ranker or resolve_ranker()
    scores = active.score(query, corpus_texts)
    scored = [(e, s) for e, s in zip(candidates, scores) if s > 0]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def format_overview_response(
    entries: list[ToolCatalogEntry],
    *,
    total_key: str = "total_services",
) -> dict[str, Any]:
    """Large-catalog no-arg response: name manifest + facets + usage."""
    return {
        total_key: len(entries),
        "names": [e.name for e in entries if e.name],
        "groups": build_prefix_index(entries),
        "tags": build_tag_index(entries),
        "mode": "overview",
        "usage": OVERVIEW_USAGE,
    }


def format_list_response(
    entries: list[ToolCatalogEntry],
    *,
    scored: list[tuple[ToolCatalogEntry, float]] | None = None,
    query: str | None = None,
    tags: list[str] | None = None,
    limit: int | None = None,
    total_key: str = "total_services",
    matches_key: str = "matches",
) -> dict[str, Any]:
    """
    Slim list or search response.

    If ``scored`` is provided, those ranked entries are used; otherwise the
    full (or tag-filtered) entry list is slimmed without scores.
    """
    limit = clamp_limit(limit)
    if scored is not None:
        matches = [slim_entry(e, score=s) for e, s in scored]
        total_matched = len(scored)
    else:
        filtered = _filter_by_tags(entries, tags)
        matches = [slim_entry(e) for e in filtered[:limit]]
        total_matched = len(filtered)

    payload: dict[str, Any] = {
        matches_key: matches,
        "total_matched": total_matched,
        total_key: len(entries),
        "mode": "search" if query else "list",
        "usage": DISCOVERY_USAGE,
    }
    if query:
        payload["query"] = query
    if tags:
        payload["tags_filter"] = tags
    if limit:
        payload["limit"] = limit

    # No match: degrade to the name manifest rather than an empty list.
    if not matches:
        payload["no_matches"] = True
        payload["names"] = [e.name for e in entries if e.name]
        payload["usage"] = (
            "No tool matched that query. 'names' lists every available tool — "
            "pick one and call get_service_info(service='name'), or retry "
            "get_service_info(query='...') with different wording."
        )
    return payload


def resolve_discovery_response(
    entries: list[ToolCatalogEntry],
    *,
    query: str | None = None,
    tags: list[str] | None = None,
    limit: int | None = None,
    total_key: str = "total_services",
    matches_key: str = "matches",
    full_list_max: int = FULL_LIST_MAX,
) -> dict[str, Any]:
    """
    Choose overview / full slim list / ranked search based on args and size.

    - With query (or tags alone): rank / filter and return top-k.
    - No query/tags and N > full_list_max: overview only.
    - No query/tags and N <= full_list_max: slim full list (capped by limit).
    """
    query_clean = (query or "").strip() or None
    tag_list = [t for t in (tags or []) if t]

    if query_clean or tag_list:
        scored = rank_entries(
            query_clean or "",
            entries,
            limit=limit,
            tags=tag_list or None,
        )
        return format_list_response(
            entries,
            scored=scored,
            query=query_clean,
            tags=tag_list or None,
            limit=limit,
            total_key=total_key,
            matches_key=matches_key,
        )

    if len(entries) > full_list_max:
        return format_overview_response(entries, total_key=total_key)

    # Small catalog: return slim list without scores
    filtered = entries
    capped_limit = clamp_limit(limit) if limit is not None else len(filtered)
    capped_limit = min(capped_limit, len(filtered), MAX_LIMIT)
    return {
        matches_key: [slim_entry(e) for e in filtered[:capped_limit]],
        "total_matched": len(filtered),
        total_key: len(entries),
        "mode": "list",
        "usage": DISCOVERY_USAGE,
    }


def suggest_names(
    entries: list[ToolCatalogEntry],
    needle: str,
    *,
    limit: int = 10,
) -> list[str]:
    """Short name suggestions for not-found responses (no full key dump)."""
    ranked = rank_entries(needle, entries, limit=limit)
    if ranked:
        return [e.name for e, _ in ranked]
    # Fallback: prefix / substring on names only
    n = needle.lower()
    hits = [e.name for e in entries if n in e.name.lower()]
    return hits[:limit]


def parse_tags_arg(tags: list[str] | str | None) -> list[str] | None:
    """Normalize tags from list or comma-separated string."""
    if tags is None:
        return None
    if isinstance(tags, str):
        parts = [p.strip() for p in tags.split(",") if p.strip()]
        return parts or None
    cleaned = [str(t).strip() for t in tags if str(t).strip()]
    return cleaned or None
