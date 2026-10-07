# Agent notes

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing this repository. The same rules apply to human and agent authors: a short problem statement, a reproduction, a scoped diff, and tests.

## Layout

- Package: `modules/mcp_composer` (`src/mcp_composer`)
- Unit tests: `modules/mcp_composer/tests/unit`
- Docs: `docs/`
- Root `Makefile` targets expect `module=mcp_composer`

## Required checks

From `modules/mcp_composer`:

```bash
uv sync --group dev
uv run pytest tests/unit -q
uv run ruff check .
uv run black --check .
```

Do not treat a green test run as permission to change an intentional security contract. Stdio member servers require `MCP_COMPOSER_STDIO_ALLOWLIST`. Non-loopback HTTP binds require authentication.

## Out of scope for drive-by edits

- Internal deployment hostnames, registries, and private GitHub links do not belong in public docs.
- Do not reintroduce removed product-specific adapters or examples.
- Do not weaken auth, allowlist, or default-bind checks to make a test pass.
