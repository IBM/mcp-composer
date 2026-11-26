# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release notes on GitHub are grouped with [`.github/release.yml`](.github/release.yml).

## [Unreleased]

### Security

- Removed the `add_tools_from_openapi`, `add_tools_from_curl`, `add_tools_from_python`, `rollback_openapi_tool_version` and `rollback_curl_tool_version` tools. `add_tools_from_openapi` was registered by default and fetched caller-supplied `servers[0].url` without the outbound destination guard (SSRF). The `ENABLE_ADD_TOOLS_USING_CURL` and `ENABLE_ADD_TOOLS_USING_PYTHON` environment variables, the `ToolFactory` module, and the `uncurl` dependency are removed with them. Register OpenAPI APIs through `register_mcp_server`, which applies the guard.
- A2A agent cards are now checked against the outbound destination guard for every URL they expose, including `additional_interfaces`, not only the primary `url`. `send_message` re-checks the stored card before connecting, so cards loaded from `a2a_agent_config.json` at startup are covered.
- Removed the unused `ensure_dependencies_installed` and `extract_imported_modules` helpers. The first ran `uv pip install` on package names taken from script imports.
- Stdio member servers fail closed unless the resolved command is on `MCP_COMPOSER_STDIO_ALLOWLIST`.
- Non-loopback HTTP binds require authentication. The default bind is loopback.

### Changed

- **Breaking:** the `tools:` section of a unified configuration (OpenAPI, `tool_type: curl`, `tool_type: script`) is no longer registered; each entry is reported as failed. Tools saved under `custom_tool/` by earlier versions are no longer loaded at startup.
- **SSE transport deprecated** — The legacy SSE transport (`/sse` endpoint) is deprecated in favor of Streamable HTTP (`/mcp` endpoint). Use `--mode http` instead of `--mode sse`, and `--remote-url` instead of `--sse-url`. The `sse` mode and `/sse` endpoint are accepted as deprecated aliases and will be removed in a future release.
- Public community docs follow the FastMCP contribution model: issue-first reports, Apache 2.0, Contributor Covenant, and private vulnerability reporting.
- Continuous integration runs the unit suite on pull requests.
- A GitHub Release tagged `mcp_composer-vX.Y.Z` publishes the package to PyPI.
