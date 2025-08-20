# Configuration

This guide covers all configuration options for MCP Composer.

## Overview

MCP Composer uses multiple configuration files and environment variables to manage its behavior. The main configuration areas are:

- **Environment Variables**: Runtime configuration
- **Server Configurations**: Member server definitions
- **Tool Configurations**: Custom tool definitions
- **Database Configuration**: Storage settings
- **Authentication**: Auth strategy settings

## Environment Variables

### Basic Configuration

Create your environment file:

```bash
cp src/.env.example src/.env
```

### Core Settings

```env
# Server Configuration
MCP_SERVER_CONFIG_PATH=config/member_servers.json
MCP_TOOL_CONFIG_PATH=config/tools.json
MCP_PROMPT_CONFIG_PATH=config/prompts.json

# Database Configuration
DATABASE_TYPE=local_file
DATABASE_PATH=data/mcp_composer.db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Server Settings
HOST=0.0.0.0
PORT=9000
MCP_PATH=/mcp

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Advanced Settings

```env
# Performance
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=30
HEALTH_CHECK_INTERVAL=60

# Caching
CACHE_ENABLED=true
CACHE_TTL=300
CACHE_MAX_SIZE=1000

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Monitoring
METRICS_ENABLED=true
METRICS_PORT=9090
```

## Server Configurations

### Member Servers File

Location: `config/member_servers.json`

```json
[
  {
    "id": "weather-api",
    "type": "http",
    "endpoint": "https://api.openweathermap.org/data/2.5",
    "auth_strategy": "api_key",
    "auth": {
      "api_key": "your-api-key"
    },
    "timeout": 30,
    "retry_attempts": 3,
    "health_check": {
      "enabled": true,
      "endpoint": "/health",
      "interval": 60
    }
  },
  {
    "id": "local-tools",
    "type": "stdio",
    "command": "python",
    "args": ["local_tools.py"],
    "working_directory": "/path/to/tools",
    "env": {
      "PYTHONPATH": "/path/to/tools"
    }
  }
]
```

### Server Types

#### HTTP/SSE Servers

```json
{
  "id": "remote-server",
  "type": "http",
  "endpoint": "https://api.example.com/mcp",
  "auth_strategy": "bearer",
  "auth": {
    "token": "your-token"
  },
  "headers": {
    "User-Agent": "MCP-Composer/1.0"
  },
  "timeout": 30
}
```

#### Stdio Servers

```json
{
  "id": "local-server",
  "type": "stdio",
  "command": "python",
  "args": ["server.py"],
  "working_directory": "/path/to/server",
  "env": {
    "API_KEY": "your-key"
  }
}
```

#### OpenAPI Servers

```json
{
  "id": "openapi-server",
  "type": "openapi",
  "open_api": {
    "endpoint": "https://api.example.com",
    "spec_url": "https://api.example.com/openapi.json",
    "custom_routes": "path/to/custom_routes.json"
  },
  "auth_strategy": "basic",
  "auth": {
    "username": "user",
    "password": "pass"
  }
}
```

#### GraphQL Servers

```json
{
  "id": "graphql-server",
  "type": "graphql",
  "endpoint": "https://graphql.example.com/graphql",
  "auth_strategy": "bearer",
  "auth": {
    "token": "your-token"
  },
  "introspection": true
}
```

## Tool Configurations

### Tools File

Location: `config/tools.json`

```json
[
  {
    "name": "weather",
    "tool_type": "curl",
    "curl_config": {
      "value": "curl 'https://api.openweathermap.org/data/2.5/weather?q={{city}}&appid=YOUR_API_KEY'"
    },
    "description": "Get weather information for a city",
    "permission": {
      "user": "read"
    },
    "enabled": true
  },
  {
    "name": "calculate",
    "tool_type": "script",
    "script_config": {
      "value": "def add_numbers(a: float, b: float) -> float:\n    return a + b"
    },
    "description": "Add two numbers",
    "permission": {
      "user": "execute"
    },
    "enabled": true
  }
]
```

### Tool Types

#### Curl Tools

```json
{
  "name": "api_call",
  "tool_type": "curl",
  "curl_config": {
    "value": "curl -X GET 'https://api.example.com/data' -H 'Authorization: Bearer {{token}}'"
  },
  "description": "Make API call",
  "permission": {
    "user": "read"
  }
}
```

#### Script Tools

```json
{
  "name": "custom_function",
  "tool_type": "script",
  "script_config": {
    "value": "def process_data(data: str) -> dict:\n    # Your custom logic here\n    return {'result': data.upper()}"
  },
  "description": "Process data with custom logic",
  "permission": {
    "user": "execute"
  }
}
```

#### OpenAPI Tools

```json
{
  "name": "get_user",
  "tool_type": "openapi",
  "openapi_config": {
    "operation": "GET /users/{id}",
    "parameters": {
      "id": "string"
    }
  },
  "description": "Get user by ID",
  "permission": {
    "user": "read"
  }
}
```

## Authentication Configuration

### OAuth Configuration

```env
# OAuth Settings
OAUTH_HOST=localhost
OAUTH_PORT=8080
OAUTH_SERVER_URL=http://localhost:8080
OAUTH_CALLBACK_PATH=/oauth/callback
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_AUTH_URL=https://provider.com/oauth/authorize
OAUTH_TOKEN_URL=https://provider.com/oauth/token
OAUTH_MCP_SCOPE=user
OAUTH_PROVIDER_SCOPE=openid
```

### OAuth Environment File

Location: `src/mcp_composer/.env.oauth`

```env
# OAuth Provider Configuration
OAUTH_PROVIDER=github
OAUTH_CLIENT_ID=your-github-client-id
OAUTH_CLIENT_SECRET=your-github-client-secret
OAUTH_AUTH_URL=https://github.com/login/oauth/authorize
OAUTH_TOKEN_URL=https://github.com/login/oauth/access_token
OAUTH_SCOPE=repo user

# Server Configuration
OAUTH_HOST=localhost
OAUTH_PORT=8080
OAUTH_CALLBACK_PATH=/oauth/callback
```

## Database Configuration

### Local File Database

```env
DATABASE_TYPE=local_file
DATABASE_PATH=data/mcp_composer.db
```

### Cloudant Database

```env
DATABASE_TYPE=cloudant
CLOUDANT_URL=https://your-account.cloudant.com
CLOUDANT_API_KEY=your-api-key
CLOUDANT_DB_NAME=mcp_composer
```

### Database Configuration File

Location: `config/database.json`

```json
{
  "type": "local_file",
  "path": "data/mcp_composer.db",
  "backup_enabled": true,
  "backup_interval": 3600,
  "backup_path": "data/backups/"
}
```

## Logging Configuration

### Log Levels

- `DEBUG`: Detailed debug information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

### Log Format

```env
# JSON format (recommended for production)
LOG_FORMAT=json

# Simple format (good for development)
LOG_FORMAT=simple
```

### Log Configuration File

Location: `config/logging.json`

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "json": {
      "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
      "format": "%(timestamp)s %(level)s %(name)s %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "formatter": "json",
      "level": "INFO"
    },
    "file": {
      "class": "logging.FileHandler",
      "filename": "logs/mcp_composer.log",
      "formatter": "json",
      "level": "DEBUG"
    }
  },
  "root": {
    "level": "INFO",
    "handlers": ["console", "file"]
  }
}
```

## Client Configuration

### MCP Composer Client

Location: `config/mcp_composer_client.yaml`

```yaml
servers:
  - name: "mcp-composer"
    type: "remote"
    enabled: true
    config:
      url: "http://localhost:9000/mcp"
      auth_type: "none"
  
  - name: "sse-server"
    type: "sse"
    enabled: false
    config:
      url: "https://example.com/sse"
      auth_type: "bearer"
      token: "your-token"
  
  - name: "stdio-server"
    type: "stdio"
    enabled: false
    config:
      command: "python"
      args: ["server.py"]

chat_model:
  name: "watsonx"
  config:
    watsonx_url: "https://your-watsonx-instance.com"
    watsonx_api_key: "your-api-key"
    watsonx_project_id: "your-project-id"
    model: "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
```

## Configuration Validation

### Validate Configuration

```bash
# Validate environment variables
mcp-composer --validate-env

# Validate server configurations
mcp-composer --validate-servers

# Validate tool configurations
mcp-composer --validate-tools

# Validate all configurations
mcp-composer --validate-all
```

### Configuration Schema

MCP Composer uses JSON schemas to validate configurations:

- Server Schema: `schemas/server_config.json`
- Tool Schema: `schemas/tool_config.json`
- Environment Schema: `schemas/env_config.json`

## Environment-Specific Configurations

### Development

```env
LOG_LEVEL=DEBUG
DATABASE_TYPE=local_file
CACHE_ENABLED=false
METRICS_ENABLED=true
```

### Production

```env
LOG_LEVEL=INFO
DATABASE_TYPE=cloudant
CACHE_ENABLED=true
METRICS_ENABLED=true
RATE_LIMIT_ENABLED=true
```

### Testing

```env
LOG_LEVEL=WARNING
DATABASE_TYPE=fake
CACHE_ENABLED=false
METRICS_ENABLED=false
```

## Configuration Best Practices

### Security

1. **Never commit secrets** to version control
2. **Use environment variables** for sensitive data
3. **Rotate API keys** regularly
4. **Use least privilege** for permissions
5. **Enable rate limiting** in production

### Performance

1. **Enable caching** for frequently accessed data
2. **Set appropriate timeouts** for external services
3. **Use connection pooling** for databases
4. **Monitor resource usage** with metrics

### Reliability

1. **Enable health checks** for all servers
2. **Configure retry logic** for failed requests
3. **Set up backup** for database
4. **Use circuit breakers** for external services

## Troubleshooting Configuration

### Common Issues

1. **Configuration not found**
   ```bash
   # Check file paths
   ls -la config/
   ls -la src/.env
   ```

2. **Invalid JSON**
   ```bash
   # Validate JSON files
   python -m json.tool config/member_servers.json
   ```

3. **Environment variables not loaded**
   ```bash
   # Check environment file
   cat src/.env
   # Verify variables are set
   env | grep MCP
   ```

### Debug Configuration

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Show configuration on startup
mcp-composer --show-config

# Validate configuration
mcp-composer --validate-config
```

## Next Steps

- [Quick Start Guide](/guide/quick-start) - Get up and running
- [CLI Usage](/guide/cli) - Learn command-line options
- [API Reference](/api/) - Complete API documentation
- [Examples](/examples/) - See configuration examples 