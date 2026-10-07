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

- Add `member_servers.json` in `config` folder with content below

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
SERVER_CONFIG_FILE_PATH=config/member_servers.json
```

- Start/Restart the Server

```sh
mcp-composer --mode http --port 9000
```

### Custom Python Tool

```python
# Define a custom tool
tool_config = {
    "name": "calculate_distance",
    "tool_type": "script",
    "script_config": {
        "value": """
import math

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    '''Calculate distance between two points using Haversine formula.'''
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c
"""
    },
    "description": "Calculate distance between two geographic coordinates",
    "permission": {
        "user": "execute"
    }
}

await composer.add_tools([tool_config])
```

### Custom Tool using Curl command

```python
curl_config = {
    "name": "event",
    "tool_type": "curl",
    "curl_config": {
        "value": "curl 'https://www.eventbriteapi.com/v3/users/me/organizations/' --header 'Authorization: Bearer XXXXXXXX'"
    },
    "description": "sample test",
    "permission": {
        "role 1": "permission 1 "
    }
}

# Add custom tools from curl command
await composer.add_tools(curl_config)
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

### Tools Configuration

```json
[
  {
    "name": "get_weather",
    "tool_type": "openapi",
    "openapi_config": {
      "operation": "GET /weather",
      "parameters": {
        "city": "string",
        "units": "string"
      }
    },
    "description": "Get current weather for a city",
    "permission": {
      "user": "read"
    }
  },
  {
    "name": "calculate_compound_interest",
    "tool_type": "script",
    "script_config": {
      "value": "def calculate_compound_interest(principal: float, rate: float, time: float, n: int = 1) -> float:\n    return principal * (1 + rate/n)**(n*time)"
    },
    "description": "Calculate compound interest",
    "permission": {
      "user": "execute"
    }
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
