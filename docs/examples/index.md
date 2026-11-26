# Examples

This section provides practical examples and use cases for MCP Composer.

## Overview

The examples demonstrate how to:

- Integrate with different types of APIs and services
- Create custom tools and scripts
- Handle authentication and authorization
- Build real-world applications
- Use MCP Composer with various clients

## Available Examples

### 🧪 Testing and Development

- [MCP Inspector Demo](/examples/mcp-inspector) - Use MCP Inspector for testing and debugging

### 🔧 Middleware Examples

- [Middleware Examples](/examples/middleware-examples) - Comprehensive middleware patterns and implementations

### 🧪 Integration with APIs


## Quick Examples

### Basic Tool Registration

```python
from mcp_composer import MCPComposer

# Initialize composer
composer = MCPComposer()

# Register a simple HTTP server
server_config = {
    "id": "weather-api",
    "type": "http",
    "endpoint": "https://api.openweathermap.org/data/2.5",
    "auth_strategy": "api_key",
    "auth": {
        "api_key": "your-api-key"
    }
}

await composer.register_mcp_server(server_config)
```

### Generate Tool from OpenAPI specification

1. By using the `register_mcp_server`

```python
from mcp_composer import MCPComposer

# Initialize composer
composer = MCPComposer()
openapi_config = {
        "id": "mcp-cp4ba",
        "type": "openapi",
        "open_api": {
            "endpoint": "https://example.com/api",
            "spec_filepath": "spec/openapi.json"
        },
        "auth_strategy": "bearer",
        "auth": {
            "username": "user1",
            "password": "xxxxxxxx"
        }
}

await composer.register_mcp_server(openapi_config)
```

Add the OpenAPI specification file `openapi.json` in `spec` folder

2. By adding the config json directly  

- Copy `example/member_servers.json` and edit it:

```json
[
    {
        "id": "mcp-cp4ba",
        "type": "openapi",
        "open_api": {
            "endpoint": "https://example.com/api",
            "spec_filepath": "spec/openapi.json"
        },
        "auth_strategy": "bearer",
        "auth": {
            "username": "user1",
            "password": "xxxxxxxx"
        }
}
]
```

- Set the path to the basic configuration file in your `.env` file using the `SERVER_CONFIG_FILE_PATH` variable:

```env
SERVER_CONFIG_FILE_PATH=example/member_servers.json
```

- Start/Restart the Server

```sh
mcp-composer --mode http --port 9000
```

### OAuth Integration

```python
# OAuth configuration
oauth_config = {
    "id": "github-api",
    "type": "http",
    "endpoint": "https://api.github.com",
    "auth_strategy": "oauth",
    "auth": {
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "repo user"
    }
}

await composer.register_mcp_server(oauth_config)
```

## Example Configurations

### Member Servers Configuration

```json
[
  {
    "id": "weather-service",
    "type": "http",
    "endpoint": "https://api.openweathermap.org/data/2.5",
    "auth_strategy": "api_key",
    "auth": {
      "api_key": "your-openweathermap-api-key"
    }
  },
  {
    "id": "stock-service",
    "type": "http",
    "endpoint": "https://api.stockdata.org",
    "auth_strategy": "bearer",
    "auth": {
      "token": "your-stock-api-token"
    }
  },
  {
    "id": "local-tools",
    "type": "stdio",
    "command": "python",
    "args": ["local_tools.py"]
  }
]
```

## Running Examples

### 1. Clone and Setup

```bash
git clone https://github.com/ibm/mcp-composer.git
cd mcp-composer
uv venv
source .venv/bin/activate
uv sync --frozen
```

### 2. Configure Environment

```bash
cp src/.env.example src/.env
# Edit src/.env with your configuration
```

### 3. Run Examples

```bash
# Start MCP Composer
mcp-composer --mode http --port 9000

# In another terminal, run example scripts
cd examples
python weather_example.py
```

## Example Projects

### Weather Dashboard

A complete weather dashboard application that demonstrates:

- OpenAPI integration with weather services
- Custom data processing tools
- Real-time data updates
- Web interface integration

### Financial Portfolio Tracker

A financial application showing:

- Multiple API integrations (stocks, crypto, forex)
- Data aggregation and analysis
- Custom calculation tools
- Authentication with financial APIs

### Content Management System

A CMS example featuring:

- Database operations
- File management
- Content processing
- User authentication

## Contributing Examples

We welcome contributions! To add your example:

1. Create a new directory in `examples/`
2. Include a README with setup instructions
3. Provide sample configurations
4. Add tests if applicable
5. Submit a pull request

## Getting Help

- [API Reference](/api/) - Complete API documentation
- [Configuration Guide](/guide/configuration) - Learn about configuration options
- [GitHub Issues](https://github.com/ibm/mcp-composer/issues) - Report bugs or request features

## Next Steps

- [MCP Inspector Demo](/examples/mcp-inspector) - Test your setup
- [API Reference](/api/) - Explore the complete API
- [Quick Start Guide](/guide/quick-start) - Get up and running
