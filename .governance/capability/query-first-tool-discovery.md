# Capability: query-first layered tool discovery

Agents search inner catalogs with `get_service_info(query=..., tags=..., limit=...)`.
Rankers: `Bm25Ranker`, `TfidfRanker`, `Bm25FallbackRanker` via `MCP_TOOL_DISCOVERY_RANKER`.
Large catalogs (N > 40) return name overview only when called with no args.
List/search responses never include full schemas — use `get_type_info`.
