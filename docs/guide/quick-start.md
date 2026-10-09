# Quick Start

Get MCP Composer up and running in minutes with this quick start guide.

## Prerequisites

Make sure you have completed the [Installation Guide](/guide/installation) first.

## Step 1: Basic Setup

### 1. Navigate to Project Directory

```bash
cd mcp-composer
```

### 2. Activate Virtual Environment

```bash
source .venv/bin/activate
```

### 3. Set Up Environment

```bash
cp .env.example .env
```

## Step 2: Start MCP Composer

### Option A: Using CLI (Recommended)

```bash
# Start in HTTP mode (default)
mcp-composer --mode http --port 9000

# Or start in stdio mode
mcp-composer --mode stdio
```

Check more [CLI command options](#cli-options)

### Option B: Using Python Script

```bash
cd modules/mcp_composer
uv run tests/test_composer.py
```

### Option C: Using uv run

```bash
uv run python -m mcp_composer --mode http --port 9000
```

## Step 3: Verify Installation

### Check Server Status

If running in HTTP mode, visit:

- **Health Check**: <http://localhost:9000/health>
- **MCP Endpoint**: <http://localhost:9000/mcp>

> **Note**: These are local development URLs. In production, replace `localhost:9000` with your actual server URL.

### Using MCP Inspector

1. **Install MCP Inspector**:

   ```bash
   npx @modelcontextprotocol/inspector
   ```

2. **Connect to MCP Composer**:
   - Transport Type: `http`
   - URL: `http://localhost:9000/mcp`

3. **List Tools**: You should see the default MCP Composer tools

## Step 4: Register Your First Server

### Example: Register a Stock Info Server

### Registering a Sample Server

Using the **MCP Inspector** or API, register a sample server by using the `register_mcp_server` tool.

```json
{
  "id": "mcp-stock-info",
  "type": "http",
  "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp"
}
```

### Using curl

```bash
curl -X POST http://localhost:9000/mcp/tools/register_mcp_server \
  -H "Content-Type: application/json" \
  -d '{
    "id": "mcp-stock-info",
    "type": "http",
    "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp"
  }'
```

## Step 5: Use Your Tools

### List All Tools

```bash
curl -X POST http://localhost:9000/mcp/tools/list_tools \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Invoke a Tool

```bash
curl -X POST http://localhost:9000/mcp/tools/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_stock_price",
    "arguments": {
      "symbol": "AAPL"
    }
  }'
```

## Step 6: Add Custom Tools

### Add a Curl Tool

```json
{
  "name": "weather",
  "tool_type": "curl",
  "curl_config": {
    "value": "curl 'https://api.openweathermap.org/data/2.5/weather?q={{city}}&appid=YOUR_API_KEY'"
  },
  "description": "Get weather information for a city",
  "permission": {
    "user": "read"
  }
}
```

### Add a Python Script Tool

```json
{
  "name": "calculate",
  "tool_type": "script",
  "script_config": {
    "value": "def add_numbers(a: float, b: float) -> float:\n    return a + b"
  },
  "description": "Add two numbers",
  "permission": {
    "user": "execute"
  }
}
```

Check how to generate tools from an OpenAPI Specification [here](/examples/#generate-tool-from-openapi-specification)  
See more examples [here](/examples/)

## Configuration Examples

### Basic Configuration File

Create a basic configuration file, or start from `example/member_servers.json`:

```json
[
  {
    "id": "example-server",
    "type": "http",
    "endpoint": "https://api.example.com/mcp",
    "auth_strategy": "bearer",
    "auth": {
      "token": "your-token-here"
    }
  }
]
```

Set the path to the basic configuration file in your `.env` file using the `SERVER_CONFIG_FILE_PATH` variable:

```env
SERVER_CONFIG_FILE_PATH=example/member_servers.json
```

### Environment Variables

Update `.env`:

```env
# Server Configuration
####### MCP Composer Server env variables

MCP_BASE_URL=http://127.0.0.1:9000/mcp

# This server and version config file will be automatically created 
# in the root folder when you register a server.
SERVER_CONFIG_FILE_PATH=mcp_servers.json
VERSION_CONFIG_FILE_PATH=versioned_config.json
VERSION_ADAPTER_TYPE=file

# MCP Composer server transport mode
MCP_MODE=http

# by default oauth disabled
ENABLE_OAUTH=False

# if oauth enabled, add below values
# Create an OAuth app with your identity provider
OAUTH_HOST=localhost    
OAUTH_PORT=8080
OAUTH_SERVER_URL=http://localhost:8080
OAUTH_CALLBACK_PATH=https://localhost:8080/callback
OAUTH_CLIENT_ID=<edit-me>
OAUTH_CLIENT_SECRET=<edit-me>
OAUTH_AUTH_URL=https://example.com/authorize
OAUTH_TOKEN_URL=https://example.com/token
OAUTH_MCP_SCOPE=user
OAUTH_PROVIDER_SCOPE=openid
```

## Common Commands

### CLI Options

```bash
# Show help
mcp-composer --help

# Start with custom port
mcp-composer --mode http --port 8080

# Disable composer tools
mcp-composer --mode http --port 9000 --disable-composer-tools

# Start with custom host
mcp-composer --mode http --host 127.0.0.1 --port 9000

# Start with debug logging
mcp-composer --log-level debug

# Start with custom config
mcp-composer --config config/custom_config.json
```

### Health Check

```bash
# Check server health
curl http://localhost:9000/health

# Check member servers health
curl -X POST http://localhost:9000/mcp/tools/member_health \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Next Steps

- [Configuration Guide](/guide/configuration) - Learn about advanced configuration
- [Server Management Guide](/guide/server-management) - Understand server management
- [Examples](/examples/) - See more practical examples
- [API Reference](/api/) - Complete API documentation
