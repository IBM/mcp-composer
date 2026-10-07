# Tool description best practices

How to write MCP tool / operation descriptions so agents (and the future registry resolver) can tell look-alikes apart when catalogues grow past ~200 tools.

**Full design:** [Intent Resolution & Tool Orchestration at 200+ Tools](../design-doc/design-decisions/intent-resolution-tool-orchestration.md) (companion to Agentic Capability Routing Platform spec v1.0).

## Short rules

1. Name the **product and estate** (e.g. a large API catalog Data Security Center vs GEM a large API catalog).
2. Prefer **`use_when` / `do_not_use_when`** over long marketing prose.
3. One description = **one operation** (or one native tool), not the whole server.
4. Put discriminators in **typed fields** (product, variant, action, resource, side effect) — not only in free text.
5. Include **example queries** and **hard negatives** from known siblings.
6. Owner-review any LLM-drafted enrichment before it goes live.
7. Do **not** rely on the agent prompt to ignore tools; Composer must enforce scope.

## Checklist

| Check | |
|-------|--|
| Product / variant clear | |
| Use / do-not-use for siblings | |
| Examples + hard negatives | |
| Side effect (read vs write) stated | |
| No duplicate semantics with another live tool | |

## Related

- [Layered MCP server](./layered_mcp_server.md) — query-first `get_service_info`
- [Tool discovery ranker](./tool-discovery-ranker.md) — BM25 / TF-IDF in Composer today
- [Query-first layered discovery (design)](../design-doc/design-decisions/tool-discovery.md)
