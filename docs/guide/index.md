# MCP Composer

MCP Composer is a FastMCP server that mounts member servers and forwards tool calls. Clients speak MCP to the composer. The composer speaks MCP, OpenAPI, or GraphQL to the members.

## What you can register

- **HTTP** MCP servers
- **Stdio** local servers, limited to `MCP_COMPOSER_STDIO_ALLOWLIST`
- **OpenAPI** specs, turned into tools
- **GraphQL** schemas, turned into tools
- **Catalog** entries for skills, agents, workflows, and prompts

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   MCP Client    │         │  MCP Inspector  │
└────────┬────────┘         └────────┬────────┘
         └────────────┬──────────────┘
                      │
           ┌──────────▼──────────┐
           │    MCP Composer     │
           └──────────┬──────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   HTTP            OpenAPI       GraphQL
   stdio           catalog
```

## Security defaults

- The CLI binds HTTP to `127.0.0.1`.
- A non-loopback bind requires authentication.
- A stdio `command` must resolve to a path on `MCP_COMPOSER_STDIO_ALLOWLIST`. An empty allowlist fails closed.

## Next steps

- [Installation](./installation.md)
- [Quick start](./quick-start.md)
- [Configuration](./configuration.md)
- [Authentication](./authentication.md)
- [Servers](./server-management.md)
- [Tools](./tool-management.md)
- [Catalog](./catalog-management.md)
- [Think Composer](./think-composer.md)
- [Contributing](https://github.com/ibm/mcp-composer/blob/main/CONTRIBUTING.md)
- [Security](https://github.com/ibm/mcp-composer/blob/main/SECURITY.md)
