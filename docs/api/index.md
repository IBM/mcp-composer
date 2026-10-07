# Interface

MCP Composer does not publish a separate REST management API. Clients use the Model Context Protocol on the composer endpoint.

Start the server, then connect with any MCP client:

```bash
mcp-composer --mode http --host 127.0.0.1 --port 9000
```

Management operations (register a server, list tools, add a prompt) are MCP tools on that same endpoint. The command-line interface is documented in [CLI](/guide/cli).
