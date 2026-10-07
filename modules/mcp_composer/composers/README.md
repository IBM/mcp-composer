# Composer entrypoints

Ready-to-run composer processes for common surfaces.

## Catalog Composer

Mounts the skill, agent, and workflow catalog MCP servers.

```bash
cd modules/mcp_composer
uv run composers/catalog_composer.py
```

Environment:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_MODE` | `sse` | `http`, `sse`, or `stdio` |
| `MCP_ENABLE_SKILL_CATALOG_MCP` | `true` | Mount skill catalog |
| `MCP_ENABLE_AGENT_CATALOG_MCP` | `true` | Mount agent catalog |
| `MCP_ENABLE_WORKFLOW_CATALOG_MCP` | `true` | Mount workflow catalog |
| `MCP_COMPOSER_TENANT_ID` | unset | Optional tenant filter for startup skills |
| `MCP_COMPOSER_ALLOWED_TOOLS` | unset | Optional tool allowlist for startup skills |
| `MCP_COMPOSER_SKILL_REFRESH_INTERVAL_SECS` | `30` | Startup skill poll interval |

HTTP and SSE modes bind `127.0.0.1` by default. Use the CLI with `--auth-type oauth` when binding a non-loopback host.

## Thinker Composer

Specialized composer with sequential thinking and deep research tools.

```bash
uv run composers/thinker_composer.py
```

## Generic CLI

```bash
mcp-composer run --mode http --host 127.0.0.1
mcp-composer run --mode http --host 0.0.0.0 --auth-type oauth
```
