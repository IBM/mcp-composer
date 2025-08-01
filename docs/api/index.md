# API Reference

This section provides comprehensive documentation for the MCP Composer API.

## Overview

MCP Composer exposes a RESTful API that follows the Model Context Protocol (MCP) specification. The API allows you to:

- Register and manage MCP servers
- List and invoke tools
- Monitor server health
- Manage authentication
- Handle prompts and configurations

## Base URL

- **Development**: `http://localhost:9000`
- **Production**: Configure based on your deployment

## Authentication

Most endpoints require authentication. MCP Composer supports multiple authentication strategies:

- **Bearer Token**: `Authorization: Bearer <token>`
- **API Key**: `X-API-Key: <key>`
- **Session-based**: Uses cookies/session tokens

## Common Response Format

All API responses follow this structure:

```json
{
  "success": true,
  "data": {
    // Response data
  },
  "error": null,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

Error responses:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": {}
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Health Endpoints

### GET /health

Check the health status of the MCP Composer server.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "0.1.0",
  "uptime": 3600
}
```

### GET /health/detailed

Get detailed health information including member servers.

**Response:**
```json
{
  "status": "healthy",
  "composer": {
    "status": "running",
    "uptime": 3600,
    "version": "0.1.0"
  },
  "member_servers": [
    {
      "id": "server-1",
      "status": "healthy",
      "last_check": "2024-01-01T00:00:00Z",
      "response_time": 150
    }
  ]
}
```

## MCP Endpoints

All MCP-compliant endpoints are available under `/mcp/`.

### POST /mcp/tools/list_tools

List all available tools across all registered servers.

**Request:**
```json
{
  "arguments": {}
}
```

**Response:**
```json
{
  "content": [
    {
      "name": "tool_name",
      "description": "Tool description",
      "inputSchema": {
        "type": "object",
        "properties": {
          "param1": {
            "type": "string",
            "description": "Parameter description"
          }
        }
      }
    }
  ]
}
```

### POST /mcp/tools/call_tool

Invoke a specific tool.

**Request:**
```json
{
  "name": "tool_name",
  "arguments": {
    "param1": "value1"
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Tool execution result"
    }
  ]
}
```

## Server Management

### POST /mcp/tools/register_mcp_server

Register a new MCP server.

**Request:**
```json
{
  "arguments": {
    "id": "server-id",
    "type": "http",
    "endpoint": "https://api.example.com/mcp",
    "auth_strategy": "bearer",
    "auth": {
      "token": "your-token"
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Server registered successfully"
    }
  ]
}
```

### POST /mcp/tools/delete_mcp_server

Delete an MCP server.

**Request:**
```json
{
  "arguments": {
    "server_id": "server-id"
  }
}
```

### POST /mcp/tools/activate_mcp_server

Activate a previously deactivated server.

**Request:**
```json
{
  "arguments": {
    "server_id": "server-id"
  }
}
```

### POST /mcp/tools/deactivate_mcp_server

Deactivate a server.

**Request:**
```json
{
  "arguments": {
    "server_id": "server-id"
  }
}
```

### POST /mcp/tools/list_member_servers

List all member servers and their status.

**Request:**
```json
{
  "arguments": {}
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "JSON string of server statuses"
    }
  ]
}
```

### POST /mcp/tools/member_health

Get health status of all member servers.

**Request:**
```json
{
  "arguments": {}
}
```

## Tool Management

### POST /mcp/tools/get_tool_config_by_name

Get configuration for a specific tool.

**Request:**
```json
{
  "arguments": {
    "tool_name": "tool-name"
  }
}
```

### POST /mcp/tools/get_tool_config_by_server

Get all tool configurations for a specific server.

**Request:**
```json
{
  "arguments": {
    "server_id": "server-id"
  }
}
```

### POST /mcp/tools/disable_tools

Disable specific tools.

**Request:**
```json
{
  "arguments": {
    "tool_names": ["tool1", "tool2"]
  }
}
```

### POST /mcp/tools/enable_tools

Enable specific tools.

**Request:**
```json
{
  "arguments": {
    "tool_names": ["tool1", "tool2"]
  }
}
```

### POST /mcp/tools/update_tool_description

Update tool description.

**Request:**
```json
{
  "arguments": {
    "tool_name": "tool-name",
    "description": "New description"
  }
}
```

## Tool Registration

### POST /mcp/tools/add_tools

Add new tools to the composer.

**Request:**
```json
{
  "arguments": {
    "tools": [
      {
        "name": "weather",
        "tool_type": "curl",
        "curl_config": {
          "value": "curl 'https://api.openweathermap.org/data/2.5/weather?q={{city}}&appid=YOUR_API_KEY'"
        },
        "description": "Get weather information",
        "permission": {
          "user": "read"
        }
      }
    ]
  }
}
```

### POST /mcp/tools/add_tools_from_openapi

Add tools from OpenAPI specification.

**Request:**
```json
{
  "arguments": {
    "openapi_spec": {
      "openapi": "3.0.1",
      "info": {
        "title": "Example API",
        "version": "1.0.0"
      }
    },
    "auth_config": {
      "auth_strategy": "bearer",
      "auth": {
        "token": "your-token"
      }
    }
  }
}
```

## Prompt Management

### POST /mcp/tools/add_prompts

Add prompts to the composer.

**Request:**
```json
{
  "arguments": {
    "prompt_config": [
      {
        "name": "prompt_name",
        "description": "Prompt description",
        "template": "Template with {{variable}}",
        "arguments": [
          {
            "name": "variable",
            "type": "string",
            "required": true,
            "description": "Variable description"
          }
        ]
      }
    ]
  }
}
```

### POST /mcp/tools/get_all_prompts

Get all registered prompts.

**Request:**
```json
{
  "arguments": {}
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `SERVER_NOT_FOUND` | The specified server does not exist |
| `TOOL_NOT_FOUND` | The specified tool does not exist |
| `AUTHENTICATION_FAILED` | Authentication failed |
| `INVALID_CONFIGURATION` | Invalid configuration provided |
| `SERVER_CONNECTION_FAILED` | Failed to connect to member server |
| `TOOL_EXECUTION_FAILED` | Tool execution failed |
| `PERMISSION_DENIED` | Insufficient permissions |

## Rate Limiting

API requests are rate-limited to prevent abuse:

- **Default**: 100 requests per minute per IP
- **Authenticated**: 1000 requests per minute per user
- **Headers**: Rate limit information is included in response headers

## SDKs and Libraries

### Python

```python
import requests

# List tools
response = requests.post(
    "http://localhost:9000/mcp/tools/list_tools",
    json={"arguments": {}}
)

# Call tool
response = requests.post(
    "http://localhost:9000/mcp/tools/call_tool",
    json={
        "name": "tool_name",
        "arguments": {"param": "value"}
    }
)
```

### JavaScript/Node.js

```javascript
// List tools
const response = await fetch('http://localhost:9000/mcp/tools/list_tools', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ arguments: {} })
});

// Call tool
const response = await fetch('http://localhost:9000/mcp/tools/call_tool', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'tool_name',
    arguments: { param: 'value' }
  })
});
```

## Next Steps

- [Examples](/examples/) - Practical API usage examples
- [Quick Start Guide](/guide/quick-start) - Get up and running
- [Configuration Guide](/guide/configuration) - Learn about configuration options 