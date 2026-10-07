# Feature Design Doc: Query-First Layered Tool Discovery

**Author:** MCP Composer
**Status:** Implemented (v1 + ranker adapters)
**Created:** 2026-08-12
**Last Updated:** 2026-10-06
**Reviewers:** Composer / MCP Composer Team

 **Related Links:**

- Guide: [docs/guide/layered_mcp_server.md](../guide/layered_mcp_server.md)
- Ranker config: [docs/guide/tool-discovery-ranker.md](../guide/tool-discovery-ranker.md)
- Tool descriptions + resolve-at-scale: [intent-resolution-tool-orchestration.md](./intent-resolution-tool-orchestration.md)
- Research brief (overflow + k-NN fallback gap): [layered-tool-discovery-brief.md](../research/layered-tool-discovery-brief.md)
- HF discussion (empty content / max_tokens): [https://huggingface.co/openai/gpt-oss-120b/discussions/67](https://huggingface.co/openai/gpt-oss-120b/discussions/67)
- Branch context: `bug/empty-resposne`

---

## 1. Summary

**Main problem:** Layered member servers expose a **large number of underlying tools/operations** (e.g. large catalogs (~175)). Agents must **select the right tool** for the user intent. Dumping the full catalog into context makes selection unreliable (noise, wrong picks) and can cause empty/truncated model replies when reasoning tokens are exhausted.

**Current solution (v1):** Keep the three-tool layered surface (`get_service_info` → `get_type_info` → `make_tool_call`), but make discovery **query-first**: search/rank a slim top-k, return tag overviews for large catalogs, never ship full schemas in list mode, and cap execution response size. Shared helpers: `layered_discovery.py` + `layered_rankers.py`. Ranking adapters (`Bm25Ranker`, `TfidfRanker`) are selected by `tool_discovery_ranker` / `MCP_TOOL_DISCOVERY_RANKER` (default `bm25_fallback`).

**Open issues:** Semantic (embedding) ranking, cross-server discovery, selection quality metrics, env-tunable size thresholds, OA/MCP response-shape parity, and GitHub tracking .

---

## 2. Background / Context



### Core problem: scale + selection


| Concern | Detail |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Large catalogs** | large catalogs (~175) ops; multi-product mesh historically 100+; MCP layered members can also list many tools |
| **Right tool selection** | Agent must map natural language → exact `operationId` / tool name before planning and execution |
| **Context pressure** | Full dumps flood the prompt; wrong or empty answers become more likely |
| **Wrong layer of filtering** | Composer `filter_tool` only ranks top-level names like `mcp-member_get_service_info`, not the 175 inner ops |


Secondary symptom (same root cause): reasoning models (e.g. gpt-oss) may return **empty** `content` when CoT + huge catalog exhaust `max_tokens` ([HF #67](https://huggingface.co/openai/gpt-oss-120b/discussions/67)). Raising `max_tokens` alone does not fix selection quality.

### Behavior before v1

Layered mode collapsed **N → 3** MCP tools correctly, but Layer 1 still dumped the **entire** inner catalog:

- **OpenAPI:** all ops with description/summary/path/tags on no-arg `get_service_info`
- **MCP:** all tools **plus full** `inputSchema`
- Agent instructions said “list everything first,” which maximized context use and minimized ranking



---

## 3. Requirements

### Functional Requirements (FR)

- [x] **FR-1** Agent can search the inner catalog with `query` / `tags` / `limit` and get ranked slim matches for tool selection.
- [x] **FR-2** Large catalog (N > 40): no-arg `get_service_info` returns tag overview only (no full dump).
- [x] **FR-3** Small catalog (N ≤ 40): no-arg `get_service_info` returns slim full list.
- [x] **FR-4** Exact `service=` / tool name returns concise summary + pointer to `get_type_info` (no full schemas).
- [x] **FR-5** Not-found returns short suggestions (not the full key list).
- [x] **FR-6** MCP list mode never includes `inputSchema`.
- [x] **FR-7** OA and MCP share discovery helpers and LLM instructions.
- [x] **FR-8** OA `make_tool_call` caps agent-facing response size with truncation metadata.



### Non-Functional Requirements (NFR)

- [x] **NFR-1** Ranking is in-process and low-latency (no external embedding call in v1).
- [x] **NFR-2** Substring fallback when sklearn is unavailable (TF-IDF path).
- [x] **NFR-3** No new persistence or data migration.
- [x] **NFR-4** Tool/auth caches must not bleed across users.
- [x] **NFR-5** Authorization debug details stay at DEBUG (not INFO in production).
- [x] **NFR-6** Discovery shortlist bounded (default 20, hard cap 50 matches).
- [x] **NFR-7** Ranker selectable via `tool_discovery_ranker` / `MCP_TOOL_DISCOVERY_RANKER`.



### Out of scope (v1)

Specific items **not** delivered in this design (see also §18 Open Issues for follow-ups):

- Embedding / semantic-tool-filter pipeline as a required dependency
- Composer-wide search across all members’ inner catalogs in one call
- Per-operation entitlement filtering inside the catalog (server-level entitlement only)
- Changing external agent runtime `max_tokens` defaults
- Guaranteed selection accuracy for paraphrased / synonym-heavy queries
- MCP `make_tool_call` response size cap parity with OA
- Env-configurable thresholds (`FULL_LIST_MAX`, etc.)

---



## 4. User Experience / User Flow

Primary actor: **LLM / agent** selecting among many member operations.

```text
User intent ("list large member APIs security policies")
 |
 v
Agent: get_service_info(query="security policy", limit=20)
 |
 v
Ranked shortlist (name, summary, path, tags, score)
 |
 v
Agent picks best match → get_type_info(name)
 |
 v
Schemas / parameters
 |
 v
make_tool_call(name, request) → bounded result
```

Large catalog without query (forces search):

```text
Agent → get_service_info()
 → overview { total_services, tags[], usage }
 → Agent retries with query= and/or tags=
```



### Edge Cases

- Ambiguous query → multiple mid-score matches; agent may refine query or use tags.
- Empty matches → reformulate query / use tag overview.
- Unknown exact name → suggestions list.
- Huge member HTTP body → truncated agent payload (`truncated: true`).

---

## 5. Proposed Design

### Architecture

```text
+------------------+
| Agent / MCP Client|
+---------+--------+
 |
 v
+---------+--------+
| MCP Composer |
| (layered members)|
+---------+--------+
 |
 +------+-------+
 | |
 v v
+--+-----------+ +--+-----------+
| Layered OA | | Layered MCP |
| Factory | | Factory |
+------+-------+ +------+-------+
 | |
 +--------+--------+
 |
 v
 +----------+-----------+
 | layered_discovery.py |
 | (rank / overview / |
 | slim format) |
 +----------------------+
```



### Main Components

#### `layered_discovery.py`

**Responsibility:** Normalize entries; tag index; overview vs list vs search response shapes; call configured `CatalogRanker`. Enforces size limits.

#### `layered_rankers.py`

**Responsibility:** Ranker port (`CatalogRanker`) and adapters — `Bm25Ranker`, `TfidfRanker`, `Bm25FallbackRanker` — resolved from `tool_discovery_ranker` / `MCP_TOOL_DISCOVERY_RANKER`.

#### `LayeredOpenAPIFactory` / `LayeredMCPFactory`

**Responsibility:** Build catalog; expose three tools; call shared discovery; OA also bounds HTTP responses to agents.

#### `layered_constants.py`

**Responsibility:** `LAYERED_DISCOVERY_INSTRUCTIONS`, usage strings, `MAX_TOOL_RESPONSE_CHARS`.

---

## 6. Current Solution (implemented)

This section is the source of truth for **what ships today**.

### 6.1 Selection contract (`get_service_info`)


| Call | Behavior (selection impact) |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `query` + optional `tags` / `limit` | **Primary path:** ranked top-k slim matches for the agent to choose from |
| No args, N ≤ 40 | Slim full list (small catalogs remain browsable) |
| No args, N > 40 | Tag overview only — forces a query before selection |
| `service=` / exact name | Concise summary + `next` → `get_type_info` (not a schema dump) |
| Not found | ≤10 `suggestions` for recovery |


Defaults: `limit=20`, hard cap `50`. Threshold: `FULL_LIST_MAX=40`.

Slim match fields: `name` / `operationId`, `summary`, `http_method`, `path`, `tags`, `score` (when ranked). **Never** `inputSchema` / requestBody / responses in list mode.

### 6.2 Ranking algorithm

Adapters in `layered_rankers.py`; selected by **`tool_discovery_ranker`** / env **`MCP_TOOL_DISCOVERY_RANKER`**:

| Value | Behavior |
|-------|----------|
| `bm25_fallback` (default) | Okapi BM25 first; char n-gram TF-IDF only when BM25 has no positive hits |
| `bm25` | Okapi BM25 only |
| `tfidf` | Char n-gram TF-IDF only (substring if sklearn missing) |

Shared steps for any adapter:

1. Optional tag pre-filter.
2. Build search text: `name + summary + description + path + http_method + tags`.
3. Score with the selected adapter.
4. Return positive scores only, sorted desc, capped by `limit`.

**BM25 details:** camelCase / snake_case / kebab tokenizer (tokens length ≥ 2); Okapi `k1=1.5`, `b=0.75`. Does not import FastMCP’s private BM25 (FastMCP’s `[^\W_]{2,}` tokenizer does not split camelCase).

**TF-IDF details:** sklearn `TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))` + cosine similarity; substring / token-overlap if sklearn is unavailable.

Operator guide: [tool-discovery-ranker.md](../../guide/tool-discovery-ranker.md).



### 6.3 Progressive disclosure

1. **Discover / select** — `get_service_info(query=...)`
2. **Plan** — `get_type_info(name)` for full schemas
3. **Execute** — `make_tool_call(...)` with bounded response (`MAX_TOOL_RESPONSE_CHARS=50_000`)

Shared agent instructions: `LAYERED_DISCOVERY_INSTRUCTIONS` (legacy full-dump instructions kept commented in both factories).

### 6.4 Hardening related to large catalogs

- OA/MCP detail mode does not return full schemas (avoids doubling `get_type_info`).
- OA `make_tool_call` returns `truncated` / `total_chars` when capped; JSON parse failures set `parse_error`.
- MCP tool cache keyed by **auth fingerprint**; auth instance cache keyed by **content hash** (not `id()`).



### 6.5 Key files

- `modules/mcp_composer/src/mcp_composer/core/member_servers/layered_discovery.py`
- `modules/mcp_composer/src/mcp_composer/core/member_servers/layered_rankers.py`
- `modules/mcp_composer/src/mcp_composer/core/member_servers/layered_constants.py`
- `modules/mcp_composer/src/mcp_composer/core/member_servers/layered_factory_oa.py`
- `modules/mcp_composer/src/mcp_composer/core/member_servers/layered_factory_mcp.py`
- Tests: `tests/unit/test_layered_discovery.py` (+ factory test updates)
- Guide: [tool-discovery-ranker.md](../../guide/tool-discovery-ranker.md)



### 6.6 Example search response

```json
{
 "matches": [
 {
 "name": "get_security_policy",
 "summary": "Get security policy",
 "http_method": "GET",
 "path": "/policies/{id}",
 "tags": ["policies"],
 "score": 0.42,
 "operationId": "get_security_policy"
 }
 ],
 "total_matched": 5,
 "total_services": 175,
 "mode": "search",
 "query": "security policy",
 "limit": 20,
 "usage": "..."
}
```

---

## 7. API Changes

Discovery is MCP tools, not REST. See §6 for the live contract.

### Breaking / behavioral changes vs pre-v1

- No-arg full dump removed when N > 40.
- MCP `get_service_info` returns structured dict (was JSON string with schemas).
- OA `make_tool_call` success always includes `truncated` and `total_chars`.



### Error Handling


| Error | Behavior |
| ------------------------ | --------------------------------------------------- |
| No / weak matches | Empty or short `matches`; agent should refine query |
| Service / tool not found | `error` + `suggestions` |
| Unauthorized | Existing IAM / 401 paths |
| Member HTTP failure | `success: false` |
| Non-JSON body | Text `data` + `parse_error` |
| Oversized body | Truncated + `truncated: true` |


---

## 8. Data Model / Storage

No persistent store. In-memory:

```text
ToolCatalogEntry → name, summary, description, path, method, tags, search_text
_cached_tools[auth_fingerprint] → tool list
_auth_cache[instances_content_key] → selected instance
```

No migration. Rollback = revert deploy.

---

## 9. Detailed Flow

### Success (correct selection)

```text
1. User asks a product question.
2. Agent searches with get_service_info(query=...).
3. Ranked shortlist returned.
4. Agent selects best name (optionally confirm via get_type_info).
5. make_tool_call executes; bounded result returned.
```



### Failure / poor selection

```text
1. Query too vague → many mid scores or empty matches.
2. Agent uses tag overview or narrower query.
3. Wrong pick still possible if descriptions are poor (open issue: quality eval).
```

---

## 10. Security & Privacy

- Server-level entitlement / IAM unchanged.
- Per-user tool cache (auth fingerprint).
- Content-keyed auth cache (no `id()` reuse).
- Truncation reduces accidental huge dumps into model context (complements PII middleware).

---

## 11. Performance & Scalability

- Catalogs of tens–~200 ops: TF-IDF per query is acceptable.
- Bottlenecks if catalogs grow to thousands: rebuild vectors every call — consider cached index / embeddings (open).
- Mitigations today: top-k limits, overview mode, slim payloads.

---

## 12. Observability

### Recommended metrics

- Discovery overview vs search counts
- Match-count histogram (selection shortlist size)
- Truncation rate on `make_tool_call`
- **Selection quality** (open): top-1 / top-5 hit rate vs labeled intents



### Logs

- Truncation warnings; tool-fetch failures; JSON parse failures
- Auth debug at DEBUG only

---

## 13. Testing Strategy



### Unit (done)

- [x] Overview / slim list / search modes
- [x] Ranking limit + tags
- [x] No schema in list; slim detail
- [x] Truncation helper; auth cache key / fingerprint



### Still open

- [ ] large member APIs-scale staging harness for selection accuracy
- [ ] E2E agent: query → type_info → call with reasoning model
- [ ] Empty-content regression on large catalog
- [ ] Labeled query→tool golden set for ranking quality

---



## 14. Rollout Plan

1. A test composer with large member APIs and layered OpenAPI servers
2. Watch truncation + tool-call success
3. GA as default layered contract (no feature flag in v1)

---



## 15. Rollback Plan

1. Revert discovery wiring commit/release.
2. Optionally raise `max_tokens` as temporary mitigation.
3. Verify list/call health.

---



## 16. Dependencies


| Dependency | Impact |
| ------------------------- | ---------------------------------------- |
| sklearn (optional) | TF-IDF; substring fallback if absent |
| FastMCP / httpx | Factories / HTTP |
| Member OpenAPI/MCP | Catalog quality drives selection quality |
| Embedding adapters (repo) | Available but **unused in v1** |


---



## 17. Alternatives Considered


| Option | Pros | Cons |
| ---------------------------------------- | ----------------------------- | ------------------------------------ |
| **A. Query-first TF-IDF (chosen)** | Fast, local, simple, testable | Weaker on paraphrases |
| **B. semantic-tool-filter / embeddings** | Better semantic match | Latency, infra, heavier than v1 need |
| **C. Raise max_tokens only** | No API change | Does not improve selection; costly |


**Decision:** A for v1 — fixes unbounded dumps and gives a usable shortlist; B remains an open follow-up for selection quality.

---



## 18. Open Issues

Track these explicitly; v1 does **not** close them. Each item includes **why we need it** for large-catalog tool selection.

### Selection quality

| ID | Issue | Why we need it | Notes |
| -- | ----- | -------------- | ----- |
| OI-1 | **Paraphrase / synonym queries** underperform TF-IDF | Users speak in natural language (“show risky data”), not OpenAPI `operationId`s; without semantic match, agents pick the wrong tool or give up | e.g. “pending approvals” vs `list_tasks`; embeddings or curated aliases |
| OI-2 | **No golden-set eval** for top-k tool hit rate | We cannot prove selection quality improves or regresses across releases without labeled intent→tool cases | Start with large member APIs |
| OI-3 | **Ambiguous shortlists** | Many near-duplicate ops (list/get/update same resource); agents need a clear #1 or a disambiguation step to avoid wrong calls | Re-ranker or LLM-as-judge |
| OI-4 | **Catalog metadata quality** | Ranking only works if summaries/tags describe intent; sparse OpenAPI text makes any algorithm look “broken” | Product docs / tag curation |

### Cross-cutting discovery

| ID | Issue | Why we need it | Notes |
| -- | ----- | -------------- | ----- |
| OI-5 | **Composer-level search** across all members’ inner catalogs | Composer users ask cross-product questions; forcing the agent to know `mcp-member_*` vs `mcp-aspera_*` first causes missed tools | Today search is per layered server |
| OI-6 | **Operation-level entitlement** | Listing tools the user cannot call wastes shortlist slots and causes authorized-looking failures after selection | Server-level entitlement only today |

### Product / platform

| ID | Issue | Why we need it | Notes |
| -- | ----- | -------------- | ----- |
| OI-7 | **Env-tunable thresholds** | large member APIs (~175) vs small APIs need different overview cutoffs / response caps without a code change | `FULL_LIST_MAX`, `DEFAULT_LIMIT`, `MAX_TOOL_RESPONSE_CHARS` |
| OI-8 | **OA vs MCP return-type parity** | Agents and shared clients should parse one shape; mixed dict vs JSON-string increases bugs and wrong parsing | MCP `get_type_info` / `make_tool_call` still strings |
| OI-9 | **MCP `make_tool_call` size cap** | Large MCP tool results can still saturate context the same way OA HTTP dumps did; selection fix is incomplete without it | Cap exists on OA path only |
| OI-10 | **GitHub issue + project board** | Need durable tracking and ownership so open issues above do not get lost after the branch merges | Blocked until `gh` auth to github.com |

### Optional next architecture

| ID | Issue | Why we need it | Notes |
| -- | ----- | -------------- | ----- |
| OI-11 | **Embedding ranking opt-in** | Better natural-language → tool match when TF-IDF fails on synonyms; optional so small deploys stay light | Reuse SentenceTransformer / ModelProviderFactory |
| OI-12 | **Hybrid rank** | Keep TF-IDF speed for candidate gen, then re-rank top candidates with embeddings for precision at scale | semantic-tool-filter-like, in-process |
| OI-13 | **Persistent catalog index** | Rebuilding rank corpora on every query will not scale if catalogs grow to thousands of tools | Rebuild on mount/config change |

### Open questions (decide later)

- [ ] Should overview mode include sample operation names per tag (still bounded)? — **Why:** helps agents form better follow-up queries without dumping the catalog
- [ ] Should agents be blocked from no-arg calls entirely when N > threshold (error vs overview)? — **Why:** overview still costs a turn; hard error may force query-first faster
- [ ] Who owns golden-set maintenance per product MCP? — **Why:** selection quality (OI-2) needs a clear owner or it will rot

---

## 19. Implementation Plan



### Milestone 1 — Foundation (done)

- [x] `layered_discovery.py`
- [x] `layered_rankers.py` (`tool_discovery_ranker` adapters)
- [x] Shared instructions
- [x] Unit tests for modes / ranking



### Milestone 2 — Core (done)

- [x] Wire OA + MCP `get_service_info`
- [x] Slim detail; schemas via `get_type_info`
- [x] OA response size cap; cache/logging hygiene



### Milestone 3 — Hardening / follow-ups (open)

- [ ] Staging selection accuracy on large member APIs-scale catalog
- [ ] Golden-set ranking eval (OI-2)
- [ ] GitHub issue + project card (OI-10)
- [ ] Decide embedding / hybrid path (OI-11/12)
- [ ] Env thresholds + MCP response cap parity (OI-7/9)

---



## 20. Success Metrics


| Metric | Pre-v1 | Target |
| ---------------------------------------------- | -------------- | -------------------------------- |
| Large-catalog no-arg payload | Full inventory | Tag overview only |
| Shortlist size for selection | Unbounded | ≤ 50 (default 20) |
| Wrong-tool / failed-call rate on known intents | Unmeasured | Measure + improve (OI-2) |
| Empty agent replies from discovery dump | Observed | Near-zero attributable to dump |
| Agent payload from make_tool_call | Unbounded | ≤ 50k chars or flagged truncated |


---



## 21. Decision Log


| Date | Decision | Reason |
| ---------- | ------------------------------------------------------------ | ------------------------------------------------------ |
| 2026-08-12 | Primary problem framed as **large N + right tool selection** | Empty replies are a symptom of unbounded discovery |
| 2026-08-12 | Query-first TF-IDF for v1 | Simple, local, enough for name/description match |
| 2026-08-12 | FULL_LIST_MAX = 40 | Small catalogs stay convenient; large ones must search |
| 2026-08-12 | Schemas only in `get_type_info` | Keeps selection shortlist small |
| 2026-08-12 | Embeddings deferred | Tracked as open issues OI-11/12 |
| 2026-10-06 | Local Okapi BM25 + camelCase tokenizer as primary ranker | Char n-grams score almost everything > 0; BM25 zeros cut noise |
| 2026-10-06 | Ranker adapters + `tool_discovery_ranker` config | Hexagonal selectability; default `bm25_fallback` |


---



## 22. Appendix



### Constants


| Constant | Value | Meaning |
| ------------------------- | ------ | -------------------------- |
| `FULL_LIST_MAX` | 40 | Above → overview on no-arg |
| `DEFAULT_LIMIT` | 20 | Default shortlist size |
| `MAX_LIMIT` | 50 | Hard shortlist cap |
| `MAX_TOOL_RESPONSE_CHARS` | 50_000 | Agent-facing execution cap |




### Related docs

- [Layered MCP server guide](../guide/layered_mcp_server.md)
- [Tool discovery ranker](../guide/tool-discovery-ranker.md)
- Guide: [Tool Discovery Ranker](../../guide/tool-discovery-ranker.md)

