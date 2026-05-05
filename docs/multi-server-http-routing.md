# Multi-Server HTTP Routing

## Overview

The Multi-Server HTTP Routing feature allows MCP Composer to expose multiple mounted MCP servers via HTTP, with each server accessible through its own dedicated route. This feature is **disabled by default** and must be explicitly enabled via environment configuration.

## Configuration

### Enabling the Feature

To enable multi-server HTTP routing, set the following environment variable in your `.env` file:

```bash
ENABLE_MULTI_SERVER_HTTP_ROUTING=true
```

By default, this feature is disabled (`false`).

### Example Configuration

```bash
# .env file
MCP_MODE=http
ENABLE_MULTI_SERVER_HTTP_ROUTING=true
```

## How It Works

### When Disabled (Default)

- MCP Composer operates in single-server mode
- All tools and resources are exposed through the main composer endpoint
- Standard FastMCP HTTP behavior is used

### When Enabled

- Each mounted MCP server gets its own HTTP route
- Routes are organized by server ID: `/{server_id}/`
- The composer root endpoint remains available at `/`
- Individual server apps are created and managed separately

## Route Structure

When multi-server routing is enabled:

```
http://localhost:8000/              # Composer root endpoint
http://localhost:8000/server1/      # First mounted server
http://localhost:8000/server2/      # Second mounted server
http://localhost:8000/server3/      # Third mounted server
```

## Implementation Details

### Key Components

1. **`_enable_multi_server_routing`**: Boolean flag set during initialization based on environment variable
2. **`_http_mounted_servers`**: Dictionary tracking all mounted servers for HTTP routing
3. **`get_multi_server_http_app()`**: Creates a Starlette app with individual routes for each server

### Server Registration

When a server is registered:
- If multi-server routing is **enabled**: Server is added to `_http_mounted_servers` tracking
- If multi-server routing is **disabled**: Server is mounted normally without HTTP route tracking

### Server Cleanup

When a server is unmounted:
- It is automatically removed from the `_http_mounted_servers` tracking dictionary
- Its HTTP route is no longer accessible

## Use Cases

### When to Enable

- **API Gateway Pattern**: When you need to expose multiple MCP servers through a single HTTP endpoint
- **Service Isolation**: When different servers should have separate HTTP routes
- **Multi-Tenant Scenarios**: When different clients need access to different server subsets

### When to Keep Disabled (Default)

- **Simple Deployments**: Single MCP server or unified tool exposure
- **Performance**: Slightly lower overhead without multi-server routing logic
- **Backward Compatibility**: Existing deployments that don't need this feature

## Example Usage

### 1. Enable the Feature

```bash
# .env
ENABLE_MULTI_SERVER_HTTP_ROUTING=true
MCP_MODE=http
```

### 2. Register Multiple Servers

```python
from mcp_composer import MCPComposer

composer = MCPComposer(name="multi-server-composer")

# Register first server
await composer.register_mcp_server({
    "id": "weather-server",
    "type": "stdio",
    "command": "python",
    "args": ["-m", "weather_mcp"]
})

# Register second server
await composer.register_mcp_server({
    "id": "database-server",
    "type": "stdio",
    "command": "python",
    "args": ["-m", "database_mcp"]
})

# Start HTTP server with multi-routing
await composer.run_http_async()
```

### 3. Access Individual Servers

```bash
# Access weather server tools
curl http://localhost:8000/weather-server/tools/list

# Access database server tools
curl http://localhost:8000/database-server/tools/list

# Access composer root
curl http://localhost:8000/tools/list
```

## Testing

The feature includes comprehensive test coverage in `test_multi_server_http_routing.py`:

- Server tracking on registration
- Cleanup on unmounting
- Multi-server HTTP app generation
- Route isolation between servers
- Backward compatibility when disabled

## Performance Considerations

- **Minimal Overhead**: When disabled, no performance impact
- **Enabled Overhead**: Slight additional memory for tracking dictionary
- **Scalability**: Designed to handle multiple servers efficiently

## Migration Guide

### Existing Deployments

No action required - the feature is disabled by default and maintains backward compatibility.

### Enabling for Existing Systems

1. Add `ENABLE_MULTI_SERVER_HTTP_ROUTING=true` to your `.env` file
2. Restart the MCP Composer service
3. Verify routes are accessible at `/{server_id}/`

## Troubleshooting

### Routes Not Working

- Verify `ENABLE_MULTI_SERVER_HTTP_ROUTING=true` is set in `.env`
- Check that servers are successfully registered
- Ensure MCP_MODE is set to `http`

### Server Not Tracked

- Confirm the environment variable is set before composer initialization
- Check logs for server registration success messages

## Related Files

- [`composer.py`](../modules/mcp_composer/src/mcp_composer/core/composer.py) - Core implementation
- [`server_manager.py`](../modules/mcp_composer/src/mcp_composer/core/member_servers/server_manager.py) - Server registration logic
- [`test_multi_server_http_routing.py`](../modules/mcp_composer/tests/test_multi_server_http_routing.py) - Test suite