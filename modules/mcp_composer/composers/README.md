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
| `MCP_MODE` | `http` | `http` or `stdio` |
| `MCP_ENABLE_SKILL_CATALOG_MCP` | `true` | Mount skill catalog |
| `MCP_ENABLE_AGENT_CATALOG_MCP` | `true` | Mount agent catalog |
| `MCP_ENABLE_WORKFLOW_CATALOG_MCP` | `true` | Mount workflow catalog |
| `MCP_COMPOSER_TENANT_ID` | unset | Optional tenant filter for startup skills |
| `MCP_COMPOSER_ALLOWED_TOOLS` | unset | Optional tool allowlist for startup skills |
| `MCP_COMPOSER_SKILL_REFRESH_INTERVAL_SECS` | `30` | Startup skill poll interval |

HTTP mode binds `127.0.0.1` by default. Use the CLI with `--auth-type oauth` when binding a non-loopback host.

## Think Composer

Sequential thinking process. The server name is `think-composer`. It registers `sequential_thinking`, hides the generic management tools, and still mounts member servers from the usual config. HTTP binds `127.0.0.1`.

```bash
uv run composers/think_composer.py
```

`composers/thinker_composer.py` starts the same process.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_MODE` | `http` | `http` or `stdio` |
| `MCP_HOST` | `127.0.0.1` | Loopback name only |
| `MCP_PORT` | `9000` | Listen port |

## Generic CLI

```bash
mcp-composer run --mode http --host 127.0.0.1
mcp-composer run --mode http --host 0.0.0.0 --auth-type oauth
```
