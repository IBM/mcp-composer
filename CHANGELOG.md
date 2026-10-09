# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release notes on GitHub are grouped with [`.github/release.yml`](.github/release.yml).

## [Unreleased]

### Security

- Stdio member servers fail closed unless the resolved command is on `MCP_COMPOSER_STDIO_ALLOWLIST`.
- Non-loopback HTTP binds require authentication. The default bind is loopback.

### Changed

- **SSE transport deprecated** — The legacy SSE transport (`/sse` endpoint) is deprecated in favor of Streamable HTTP (`/mcp` endpoint). Use `--mode http` instead of `--mode sse`, and `--remote-url` instead of `--sse-url`. The `sse` mode and `/sse` endpoint are accepted as deprecated aliases and will be removed in a future release.
- Public community docs follow the FastMCP contribution model: issue-first reports, Apache 2.0, Contributor Covenant, and private vulnerability reporting.
- Continuous integration runs the unit suite on pull requests.
- A GitHub Release tagged `mcp_composer-vX.Y.Z` publishes the package to PyPI.
