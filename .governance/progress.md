# Progress

## 2026-10-07 13:18 UTC — OSS harden + catalog + CVE/deps

- Catalog (skill/workflow/agent/prompt) ported from IBM main without merging later Solis commits
- Stripped Solis/ISV/MCSP/W3/Cloudant/Aspera/watsonx-concert examples; kept IBM doc search
- Stdio RCE: fail-closed bind + `MCP_COMPOSER_STDIO_ALLOWLIST`
- Generic `Makefile` / `Dockerfile` / `Dockerfile.local` / `DOCKER_GUIDE.md`
- Dep bumps: fastmcp 3.4.7, urllib3>=2.8.0, cryptography>=46.0.6, etc.; removed ibmcloudant
- Unit tests: **1162 passed** (`tests/unit`)
- Edit target: `/Users/mansurah/Development/mcp-composer` (not Solis tree)


## 2026-10-07 13:21 UTC — Query-first tool discovery (generic)

- Ported `layered_discovery.py` + `layered_rankers.py` (BM25 / TF-IDF / bm25_fallback)
- Wired into OSS `LayeredMCPFactory` + `LayeredOpenAPIFactory` without IBM/Solis product routing
- Docs: `tool-discovery-ranker.md`, `tool-description-best-practices.md`, design `tool-discovery.md` (scrubbed)
- Config: `MCP_TOOL_DISCOVERY_RANKER` / `tool_discovery_ranker`
- Tests: layered discovery + factory suites green

## 2026-10-07 14:40 UTC — OSS community release prep

- FastMCP-style `CONTRIBUTING.md`, `AGENTS.md`, Contributor Covenant, private `SECURITY.md`, `NOTICE`, `CHANGELOG.md`
- Issue, pull request, release, Dependabot, and unit-test CI templates
- Public README/docs: Apache 2.0 (docs footer had said MIT), `github.com/ibm/mcp-composer`, sample OAuth URLs no longer point at IBM preprod SSO
- Tests: **1189 passed** (`tests/unit`); **17 passed, 1 skipped** on the other non-e2e modules
- Dropped `tests/test_cli.py` and `tests/test_main.py` (imported removed `mcp_composer.core.utils.cli`)
- Moved the manual OAuth script to `modules/mcp_composer/examples/oauth_provider_manual.py`
- Removed `.github/CODEOWNERS`. Maintainer is [mansura-habiba](https://github.com/mansura-habiba) (`MAINTAINERS.md`), matching [IBM/mcp-composer](https://github.com/IBM/mcp-composer)
- Branch `oss-release-prep` pushed to `github.ibm.com/ai-elite/mcp-composer`
- README no longer documents `mcp_composer_app`; that package is removed


