# Capability: stdio command allowlist

Env: `MCP_COMPOSER_STDIO_ALLOWLIST` (colon/comma-separated absolute paths).
Validation resolves `command` via `which`/`realpath` and fail-closes if not listed.
