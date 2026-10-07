# Docker Guide

Generic images (no private IBM registries). Build from `modules/mcp_composer`.

## Quick start

```bash
# Runtime image
docker build -t mcp-composer:local .

# Or from repo root
make docker-build IMAGE_URI=mcp-composer:local

# Local/dev image
docker build -f Dockerfile.local -t mcp-composer:dev .
```

Run (loopback by default; required without auth):

```bash
docker run --rm -p 9000:9000 mcp-composer:local
```

Expose on all interfaces only with OAuth:

```bash
docker run --rm -p 9000:9000 mcp-composer:local \
  uv run --no-project mcp-composer run --mode http --host 0.0.0.0 --auth-type oauth
```

## Optional extras

Default `uv sync` installs core dependencies only. Add features at build time:

```dockerfile
RUN uv sync --locked --no-install-project --no-dev --extra ai --extra tracing --extra secrets
```

Available extras: `tracing`, `secrets`, `ai`, `search`, `all`.

## Stdio member servers

Set `MCP_COMPOSER_STDIO_ALLOWLIST` to a comma-separated list of absolute command paths before registering `type: stdio` servers.
