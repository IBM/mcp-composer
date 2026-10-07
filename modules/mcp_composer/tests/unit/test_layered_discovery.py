"""Unit tests for query-first layered discovery helpers."""

from unittest.mock import patch

from mcp_composer.core.member_servers.layered_discovery import (
    FULL_LIST_MAX,
    MAX_LIMIT,
    ToolCatalogEntry,
    build_prefix_index,
    build_tag_index,
    clamp_limit,
    parse_tags_arg,
    rank_entries,
    resolve_discovery_response,
    slim_entry,
    suggest_names,
)
from mcp_composer.core.member_servers.layered_rankers import (
    Bm25FallbackRanker,
    Bm25Ranker,
    TfidfRanker,
    _bm25_scores,
    _tokenize_identifier,
    normalize_ranker_name,
    resolve_ranker,
)


def _untagged_entries(n: int) -> list[ToolCatalogEntry]:
    """Entries shaped like an MCP-backed catalog: no tags at all."""
    verbs = ["get", "create", "list", "search", "execute"]
    return [
        ToolCatalogEntry(
            name=f"{verbs[i % len(verbs)]}_resource_{i}",
            summary=f"Summary for resource {i}",
            description=f"Description for resource {i}",
            tags=[],
        )
        for i in range(n)
    ]


def _make_entries(n: int) -> list[ToolCatalogEntry]:
    entries: list[ToolCatalogEntry] = []
    for i in range(n):
        tag = "policies" if i % 3 == 0 else ("reports" if i % 3 == 1 else "users")
        kind = "policy" if i % 3 == 0 else ("report" if i % 3 == 1 else "user")
        entries.append(
            ToolCatalogEntry(
                name=f"list_{kind}_{i}",
                summary=f"List {kind} resources #{i}",
                description=f"Retrieve {kind} catalog items",
                path=f"/api/{kind}s/{i}",
                http_method="GET",
                tags=[tag],
            )
        )
    # Ensure a distinctive entry for ranking
    entries.append(
        ToolCatalogEntry(
            name="get_security_policy",
            summary="Get security policy by id",
            description="Fetch a single data security policy definition",
            path="/api/policies/{id}",
            http_method="GET",
            tags=["policies", "security"],
            extra={"operationId": "get_security_policy"},
        )
    )
    return entries


def test_clamp_limit():
    assert clamp_limit(None) == 20
    assert clamp_limit(5) == 5
    assert clamp_limit(0) == 1
    assert clamp_limit(999) == MAX_LIMIT
    assert clamp_limit("bad") == 20  # type: ignore[arg-type]


def test_parse_tags_arg():
    assert parse_tags_arg(None) is None
    assert parse_tags_arg("a, b") == ["a", "b"]
    assert parse_tags_arg(["x", "y"]) == ["x", "y"]
    assert parse_tags_arg("") is None


def test_build_tag_index():
    entries = _make_entries(9)
    index = build_tag_index(entries)
    names = {t["name"] for t in index}
    assert "policies" in names
    assert "reports" in names
    assert all("count" in t for t in index)


def test_slim_entry_never_has_schema():
    entry = ToolCatalogEntry(
        name="op",
        summary="s",
        path="/p",
        http_method="GET",
        tags=["t"],
        extra={"operationId": "op"},
    )
    slim = slim_entry(entry, score=0.9)
    assert "inputSchema" not in slim
    assert "requestBody" not in slim
    assert slim["score"] == 0.9
    assert slim["operationId"] == "op"


def test_overview_when_catalog_exceeds_threshold():
    entries = _make_entries(FULL_LIST_MAX + 10)
    assert len(entries) > FULL_LIST_MAX
    result = resolve_discovery_response(entries)
    assert result["mode"] == "overview"
    assert "tags" in result
    assert "matches" not in result
    assert result["total_services"] == len(entries)
    assert "query" in result["usage"].lower() or "Catalog is large" in result["usage"]


def test_full_slim_list_when_catalog_small():
    entries = _make_entries(5)
    # _make_entries adds one extra distinctive entry
    result = resolve_discovery_response(entries)
    assert result["mode"] == "list"
    assert "matches" in result
    assert len(result["matches"]) == len(entries)
    assert all("inputSchema" not in m for m in result["matches"])
    assert all("score" not in m for m in result["matches"])


def test_query_returns_top_k_with_scores():
    entries = _make_entries(120)
    result = resolve_discovery_response(entries, query="security policy", limit=10)
    assert result["mode"] == "search"
    assert len(result["matches"]) <= 10
    assert result["query"] == "security policy"
    names = [m["name"] for m in result["matches"]]
    assert "get_security_policy" in names
    assert "score" in result["matches"][0]
    assert all("inputSchema" not in m for m in result["matches"])


def test_tags_filter():
    entries = _make_entries(30)
    result = resolve_discovery_response(entries, tags=["policies"], limit=15)
    assert "matches" in result
    assert all("policies" in (m.get("tags") or []) for m in result["matches"])
    assert len(result["matches"]) <= 15


def test_rank_entries_limit():
    entries = _make_entries(80)
    ranked = rank_entries("report", entries, limit=5)
    assert len(ranked) <= 5
    assert all(score > 0 for _, score in ranked)


def test_suggest_names_not_full_dump():
    entries = _make_entries(100)
    suggestions = suggest_names(entries, "policy", limit=8)
    assert len(suggestions) <= 8
    assert len(suggestions) > 0


def test_large_catalog_no_arg_never_dumps_matches():
    entries = _make_entries(175)
    result = resolve_discovery_response(entries)
    assert result["mode"] == "overview"
    assert "matches" not in result
    # Must not embed a full service map
    assert "available_services" not in result


# --- regression: bug/empty-response -------------------------------------


def test_overview_always_lists_tool_names():
    """
    Overview mode must never return a response with no tool names in it.

    Regression for the empty-response bug: a large MCP-backed catalog got back
    only {total_services, tags: [], mode, usage} — it was told to search a
    catalog it had never been shown.
    """
    entries = _untagged_entries(98)
    result = resolve_discovery_response(entries)

    assert result["mode"] == "overview"
    assert result["total_services"] == 98
    assert len(result["names"]) == 98
    assert "get_resource_0" in result["names"]
    # Names only — never summaries or schemas in bulk.
    assert all(isinstance(n, str) for n in result["names"])


def test_overview_has_a_usable_facet_without_tags():
    """MCP catalogs carry no tags, so prefix groups must stand in."""
    entries = _untagged_entries(98)
    result = resolve_discovery_response(entries)

    assert result["tags"] == []
    groups = {g["name"]: g["count"] for g in result["groups"]}
    assert groups["get"] == 20
    assert sum(groups.values()) == 98


def test_build_prefix_index_orders_by_count():
    entries = _untagged_entries(11)
    index = build_prefix_index(entries)
    counts = [g["count"] for g in index]
    assert counts == sorted(counts, reverse=True)
    assert sum(counts) == 11


def test_zero_score_query_falls_back_to_names():
    """A query matching nothing must not return a bare empty list."""
    entries = _untagged_entries(60)
    result = resolve_discovery_response(
        entries, query="zzzzqqqxxnomatchwhatsoever", limit=10
    )

    if not result["matches"]:
        assert result["no_matches"] is True
        assert len(result["names"]) == 60
        assert "get_service_info" in result["usage"]


def test_successful_query_has_no_names_fallback():
    entries = _untagged_entries(60)
    result = resolve_discovery_response(entries, query="create resource", limit=5)
    assert result["matches"]
    assert "no_matches" not in result
    assert "names" not in result


# --- BM25 primary ranking -----------------------------------------------


def test_tokenize_identifier_splits_camel_and_snake():
    tokens = _tokenize_identifier("getDatabaseSecurityPolicies")
    assert tokens == ["get", "database", "security", "policies"]
    assert _tokenize_identifier("get_security_policy") == [
        "get",
        "security",
        "policy",
    ]
    assert _tokenize_identifier("get-database-security") == [
        "get",
        "database",
        "security",
    ]
    assert "https" in _tokenize_identifier("listHTTPSConnections")
    assert "connections" in _tokenize_identifier("listHTTPSConnections")
    assert _tokenize_identifier("a") == []  # length < 2 dropped
    assert _tokenize_identifier("") == []


def test_bm25_scores_prefer_term_overlap():
    query = _tokenize_identifier("database security")
    docs = [
        _tokenize_identifier("getDatabaseSecurityPolicies"),
        _tokenize_identifier("listUsers"),
    ]
    scores = _bm25_scores(query, docs)
    assert scores[0] > scores[1]
    assert scores[0] > 0
    assert scores[1] == 0.0


def test_bm25_ranks_camelcase_operation_for_nl_query():
    entries = [
        ToolCatalogEntry(
            name="getDatabaseSecurityPolicies",
            summary="Retrieve database security policies",
            description="List security database security policy definitions",
            path="/api/database/security/policies",
            http_method="GET",
            tags=["policies"],
            extra={"operationId": "getDatabaseSecurityPolicies"},
        ),
        ToolCatalogEntry(
            name="listUsers",
            summary="List directory users",
            description="Enumerate IAM user accounts",
            path="/api/users",
            http_method="GET",
            tags=["users"],
        ),
        ToolCatalogEntry(
            name="createReportJob",
            summary="Create a reporting job",
            description="Schedule a batch report export",
            path="/api/reports",
            http_method="POST",
            tags=["reports"],
        ),
    ]
    ranked = rank_entries("database security policies", entries, limit=5)
    assert ranked
    assert ranked[0][0].name == "getDatabaseSecurityPolicies"
    assert ranked[0][1] > 0
    # Unrelated ops share no query tokens → genuine BM25 zeros → omitted.
    assert [e.name for e, _ in ranked] == ["getDatabaseSecurityPolicies"]


def test_bm25_omits_zero_score_entries():
    entries = [
        ToolCatalogEntry(
            name="getsecurityPolicy",
            summary="Get security policy by id",
            description="Fetch a single data security policy definition",
            tags=["policies"],
        ),
        ToolCatalogEntry(
            name="listWidgets",
            summary="List UI widgets",
            description="Return dashboard widget catalog",
            tags=["ui"],
        ),
    ]
    ranked = rank_entries("security policy", entries, limit=10)
    names = [e.name for e, s in ranked]
    assert "getsecurityPolicy" in names
    assert all(s > 0 for _, s in ranked)
    # Widget entry shares no query tokens → BM25 score 0 → omitted.
    assert "listWidgets" not in names


def test_tfidf_fallback_when_bm25_finds_nothing():
    """When BM25 scores are all zero, char TF-IDF / substring still ranks."""
    entries = [
        ToolCatalogEntry(
            name="abcxyz",
            summary="qqq",
            description="zzz",
        ),
        ToolCatalogEntry(
            name="other",
            summary="unrelated",
            description="noise",
        ),
    ]
    with patch(
        "mcp_composer.core.member_servers.layered_rankers._bm25_scores",
        return_value=[0.0, 0.0],
    ):
        ranked = rank_entries("abc", entries, limit=5, ranker=Bm25FallbackRanker())
    assert ranked
    assert ranked[0][0].name == "abcxyz"
    assert ranked[0][1] > 0


def test_tfidf_fallback_on_partial_identifier_without_token_overlap():
    """
    Partial identifier tokens differ from full names (no BM25 hit), but
    char n-grams still surface the right op.
    """
    entries = [
        ToolCatalogEntry(
            name="abcdefghij",
            summary="alpha tool",
            description="zzzz",
        ),
        ToolCatalogEntry(
            name="zzzzzzzzzz",
            summary="noise tool",
            description="qqqq",
        ),
    ]
    # "abcdef" vs "abcdefghij" → different length-≥2 tokens, no BM25 overlap.
    ranked = rank_entries("abcdef", entries, limit=5)
    assert ranked
    assert ranked[0][0].name == "abcdefghij"
    assert ranked[0][1] > 0
    assert "zzzzzzzzzz" not in [e.name for e, _ in ranked]


def test_resolve_discovery_bm25_search_still_slim():
    entries = [
        ToolCatalogEntry(
            name="getDatabaseSecurityPolicies",
            summary="Retrieve database security policies",
            description="List policies",
            tags=["policies"],
            extra={"operationId": "getDatabaseSecurityPolicies"},
        ),
        ToolCatalogEntry(
            name="listUsers",
            summary="List users",
            description="IAM users",
            tags=["users"],
        ),
    ]
    result = resolve_discovery_response(entries, query="database security", limit=10)
    assert result["mode"] == "search"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["name"] == "getDatabaseSecurityPolicies"
    assert "score" in result["matches"][0]
    assert "inputSchema" not in result["matches"][0]


def test_empty_query_with_tags_unchanged():
    entries = _make_entries(12)
    ranked = rank_entries("", entries, limit=5, tags=["policies"])
    assert ranked
    assert len(ranked) <= 5
    assert all(score == 1.0 for _, score in ranked)
    assert all("policies" in e.tags for e, _ in ranked)


def test_resolve_ranker_from_config(monkeypatch):
    monkeypatch.setenv("MCP_TOOL_DISCOVERY_RANKER", "bm25")
    assert isinstance(resolve_ranker(), Bm25Ranker)
    monkeypatch.setenv("MCP_TOOL_DISCOVERY_RANKER", "tfidf")
    assert isinstance(resolve_ranker(), TfidfRanker)
    monkeypatch.setenv("MCP_TOOL_DISCOVERY_RANKER", "bm25_fallback")
    assert isinstance(resolve_ranker(), Bm25FallbackRanker)
    assert isinstance(resolve_ranker("bm25"), Bm25Ranker)
    assert normalize_ranker_name("hybrid") == "bm25_fallback"
    assert normalize_ranker_name("nope") == "bm25_fallback"


def test_rank_entries_respects_injected_tfidf_ranker():
    entries = [
        ToolCatalogEntry(name="getDatabaseSecurityPolicies", summary="db"),
        ToolCatalogEntry(name="listUsers", summary="users"),
    ]
    # Pure BM25: NL tokens match camelCase op only.
    bm25 = rank_entries("database security", entries, limit=5, ranker=Bm25Ranker())
    assert [e.name for e, _ in bm25] == ["getDatabaseSecurityPolicies"]

    # Pure TF-IDF may still surface char-overlap noise; call must succeed.
    tfidf = rank_entries("database", entries, limit=5, ranker=TfidfRanker())
    assert tfidf
    assert all(s > 0 for _, s in tfidf)


def test_bm25_only_skips_tfidf_fallback():
    """bm25 mode must not fall back to char n-grams when scores are zero."""
    entries = [
        ToolCatalogEntry(name="abcdefghij", summary="alpha"),
        ToolCatalogEntry(name="zzzzzzzzzz", summary="noise"),
    ]
    ranked = rank_entries("abcdef", entries, limit=5, ranker=Bm25Ranker())
    assert ranked == []
