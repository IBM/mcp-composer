# OSS mcp-composer hardening (2026-10-07)

## Trees
- OSS (ai-elite): `/Users/mansurah/Development/mcp-composer` — edit here
- Solis IBM: `/Users/mansurah/Solis-Development/mcp-composer` — do not mix

## Security
- Non-loopback HTTP/SSE requires auth
- Stdio member servers: realpath must be on `MCP_COMPOSER_STDIO_ALLOWLIST`
- Default bind `127.0.0.1`

## Storage
- Supported: postgres, local_file, fake
- Cloudant adapter removed from OSS

## Build
- Generic Python slim Docker; Makefile `IMAGE_NAME`/`IMAGE_URI` overridable
