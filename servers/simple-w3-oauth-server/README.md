# Simple MCP Server with W3 OAuth Authentication

This is a simple example of an MCP server with W3 OAuth authentication. It demonstrates the essential components needed for OAuth integration with just a single tool.

## Overview

This simple demo to show to set up a server with:
- W3 OAuth2 authorization flow
- Single tool: `get_user_profile` to retrieve w3 user profile

## Required Environment Variables

You MUST set these environment variables before running the server:

```bash
export MCP_W3_W3_CLIENT_ID="your_client_id_here"
export MCP_W3_W3_CLIENT_SECRET="your_client_secret_here"
```

The server will not start without these environment variables properly set.


## Running the Server

```bash
# Set environment variables first (see above)

# Run the server
uv run mcp-simple-auth
```

The server will start on `http://localhost:8080`.

### Transport Options

This server supports multiple transport protocols that can run on the same port:

#### SSE (Server-Sent Events) - Default
```bash
uv run mcp-simple-auth
# or explicitly:
uv run mcp-simple-auth --transport sse
```

SSE transport provides endpoint:
- `/sse`

#### Streamable HTTP
```bash
uv run mcp-simple-auth --transport streamable-http
```

Streamable HTTP transport provides endpoint:
- `/mcp`


This ensures backward compatibility without needing multiple server instances. When using SSE transport (`--transport sse`), only the `/sse` endpoint is available.

## Available Tool

### get_user_profile

The only tool in this simple example. Returns the authenticated user's W3 profile information.

**Required scope**: `user`

**Returns**: W3 user profile data including username, email, bio, etc.


## Troubleshooting

If the server fails to start, check:
1. Environment variables `MCP_W3_W3_CLIENT_ID` and `MCP_W3_W3_CLIENT_SECRET` are set
2. The W3 OAuth app callback URL matches `https://localhost:8080/auth/idaas/callback`
3. No other service is using port 8080
4. The transport specified is valid (`sse` or `streamable-http`)

You can use [Inspector](https://github.com/modelcontextprotocol/inspector) to test Auth