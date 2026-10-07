# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release notes on GitHub are grouped with [`.github/release.yml`](.github/release.yml).

## [Unreleased]

### Security

- Stdio member servers fail closed unless the resolved command is on `MCP_COMPOSER_STDIO_ALLOWLIST`.
- Non-loopback HTTP and SSE binds require authentication. The default bind is loopback.

### Changed

- Public community docs follow the FastMCP contribution model: issue-first reports, Apache 2.0, Contributor Covenant, and private vulnerability reporting.
- Continuous integration runs the unit suite on pull requests.
