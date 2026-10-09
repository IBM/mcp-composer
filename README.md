# MCP Composer

MCP Composer is a [FastMCP](https://github.com/PrefectHQ/fastmcp) server that mounts other MCP servers and exposes their tools through one endpoint. Register servers at runtime with JSON. Supported member types are HTTP, stdio, OpenAPI, and GraphQL.

## Install

Python 3.11, 3.12, or 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ibm/mcp-composer.git
cd mcp-composer/modules/mcp_composer
uv sync --group dev
```

The package is `mcp-composer`. There is no separate application package.

## Run

```bash
mcp-composer --mode http --host 127.0.0.1 --port 9000
```

HTTP binds to loopback unless you configure authentication. A non-loopback bind without auth is rejected. Stdio member servers run only when the resolved command is listed in `MCP_COMPOSER_STDIO_ALLOWLIST`.

Point the composer at a member list:

```bash
mcp-composer --mode http --host 127.0.0.1 --port 9000 \
  --config_path example/member_servers.json
```

A fuller sample is `example/unified_config.json`. Guides are in [docs/guide](docs/guide/index.md).

## Domain composers

These processes start one tool surface and still mount member servers from the usual config. They bind `127.0.0.1`.

```bash
cd modules/mcp_composer
uv run composers/think_composer.py
uv run composers/catalog_composer.py
```

Think Composer (`think-composer`) exposes `sequential_thinking`. Catalog Composer mounts the skill, agent, and workflow catalogs. See [Think Composer](docs/guide/think-composer.md) and [Catalog Composer](docs/guide/catalog-composer.md).

## Project

| | |
| --- | --- |
| License | [Apache 2.0](LICENSE) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Security | [SECURITY.md](SECURITY.md) |
| Code of conduct | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

Report vulnerabilities privately. See [SECURITY.md](SECURITY.md).
