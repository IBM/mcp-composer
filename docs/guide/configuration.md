# Configuration

This guide covers all configuration options for MCP Composer.

## Overview

MCP Composer uses multiple configuration files and environment variables to manage its behavior. The main configuration areas are:

- **Environment Variables**: Runtime configuration
- **Server Configurations**: Member server definitions
- **Tool Configurations**: Custom tool definitions
- **Database Configuration**: Storage settings
- **Authentication**: Auth strategy settings

## MCP Composer Server Configuration

### `MCP_BASE_URL`

**Description:** Base URL for the MCP Composer server endpoint.

**Type:** URL String

**Default:** `http://0.0.0.0:9000/mcp`

**Example:**

```bash
MCP_BASE_URL=http://127.0.0.1:9000/mcp
# For production
MCP_BASE_URL=https://mcp-composer.example.com/mcp
```

---

### `SERVER_CONFIG_FILE_PATH`

**Description:** Path to the server configuration JSON file. This file is automatically created when you register a server and contains all registered MCP server configurations.

**Type:** File Path

**Default:** `mcp_servers.json` (in root folder)

**Example:**

```bash
SERVER_CONFIG_FILE_PATH=mcp_servers.json
# Custom path
SERVER_CONFIG_FILE_PATH=/etc/mcp-composer/servers.json
```

---

### `VERSION_CONFIG_FILE_PATH`

**Description:** Path to the versioned configuration file that tracks different versions of server configurations.

**Type:** File Path

**Default:** `versioned_config.json` (in root folder)

**Example:**

```bash
VERSION_CONFIG_FILE_PATH=versioned_config.json
# Custom path
VERSION_CONFIG_FILE_PATH=/var/lib/mcp-composer/versions.json
```

---

### `MCP_USE_LOCAL_FILE_STORAGE`

**Description:** Enable or disable local file storage for server configurations. When enabled, configurations are stored in local JSON files instead of a database.

**Type:** Boolean

**Default:** `False`

**Allowed Values:** `True`, `False`

**Example:**

```bash
MCP_USE_LOCAL_FILE_STORAGE=True
```

---

### `VERSION_ADAPTER_TYPE`

**Description:** Specifies the adapter type for version management. Use `file` for local file storage Stored in a local version file.

**Type:** String

**Default:** `file`

**Allowed Values:** `file`

**Example:**

```bash
VERSION_ADAPTER_TYPE=file
```

---

### `MCP_COMPOSER_MODE`

**Description:** Defines the operational mode for MCP Composer. Affects logging levels, error handling, and debugging features.

**Type:** String

**Default:** `dev`

**Allowed Values:** `dev`, `prod`

**Example:**

```bash
# Development mode (verbose logging, detailed errors)
MCP_COMPOSER_MODE=dev

# Production mode (minimal logging, sanitized errors)
MCP_COMPOSER_MODE=prod
```

---

### `MCP_MODE`

**Description:** Transport mode for MCP Composer server communication.

**Type:** String

**Default:** `stdio`

**Allowed Values:** `stdio`, `sse`, `http`

**Example:**

```bash
# Server-Sent Events mode
MCP_MODE=sse

# Standard I/O mode
MCP_MODE=stdio

# HTTP mode
MCP_MODE=http
```

---

## Database Configuration

### `MCP_DATABASE_TYPE`

**Description:** Type of database backend to use for storing MCP configurations.

**Type:** String

**Default:** `local_file`

**Allowed Values:** `local_file`, `postgresql`, `mongodb`, etc.

**Example:**

```bash
# Local file-based storage
MCP_DATABASE_TYPE=local_file

# PostgreSQL database
MCP_DATABASE_TYPE=postgresql
```

---

### `MCP_DATABASE_FILE_PATH`

**Description:** Path to the local database file when using `local_file` database type.

**Type:** File Path

**Default:** `mcp_servers.json`

**Example:**

```bash
MCP_DATABASE_FILE_PATH=mcp_servers.json
# Custom location
MCP_DATABASE_FILE_PATH=/var/lib/mcp-composer/database.json
```

---

## OAuth Authentication

### `ENABLE_OAUTH`

**Description:** Enable or disable OAuth authentication for MCP Composer.

**Type:** Boolean

**Default:** `False`

**Allowed Values:** `True`, `False`

**Example:**

```bash
# Enable OAuth
ENABLE_OAUTH=True

# Disable OAuth
ENABLE_OAUTH=False
```

---

## Composer Initialization Flow

[`MCPComposer.__init__()`](modules/mcp_composer/src/mcp_composer/core/composer.py:93) initializes the runtime in isolated phases so each step can be tested independently and failures are easier to diagnose from logs.

Startup phases:

1. Configuration manager setup via [`MCPComposer._initialize_config_manager()`](modules/mcp_composer/src/mcp_composer/core/composer.py:112)
2. Database resolution via [`MCPComposer._initialize_database()`](modules/mcp_composer/src/mcp_composer/core/composer.py:125)
3. Manager wiring via [`MCPComposer._initialize_managers()`](modules/mcp_composer/src/mcp_composer/core/composer.py:145)
4. Persisted state and config loading via [`MCPComposer._load_initial_state()`](modules/mcp_composer/src/mcp_composer/core/composer.py:167)
5. Tool registration via [`MCPComposer._register_startup_tools()`](modules/mcp_composer/src/mcp_composer/core/composer.py:179)

Each phase emits initialization logs and raises immediately on failure so startup behavior remains unchanged while making the sequence easier to validate in isolation.

---

### GitHub OAuth

#### `OAUTH_PROVIDER`

**Description:** Specifies the OAuth provider.

**Type:** String

**Allowed Values:** `github`, `google`

**Example:**

```bash
OAUTH_PROVIDER=github
```

#### `OAUTH_BASE_URL`

**Description:** Base URL of your application for OAuth callbacks.

**Type:** URL String

**Example:**

```bash
OAUTH_BASE_URL=http://localhost:9000
# Production
OAUTH_BASE_URL=https://mcp-composer.example.com
```

#### `OAUTH_CLIENT_ID`

**Description:** OAuth client ID provided by GitHub.

**Type:** String

**Example:**

```bash
OAUTH_CLIENT_ID=xxxxxxx
```

#### `OAUTH_CLIENT_SECRET`

**Description:** OAuth client secret provided by GitHub.

**Type:** String (Sensitive)

**Example:**

```bash
OAUTH_CLIENT_SECRET=xxxxxxx
```

**Complete GitHub OAuth Example:**

```bash
ENABLE_OAUTH=True
OAUTH_PROVIDER=github
OAUTH_BASE_URL=http://localhost:9000
OAUTH_CLIENT_ID=xxxxxxx
OAUTH_CLIENT_SECRET=xxxxxxx
```

---

### OIDC

#### `OAUTH_CONFIG_URL`

**Description:** OpenID Connect discovery URL.

**Type:** URL String

**Example:**

```bash
OAUTH_CONFIG_URL=https://example.com/.well-known/openid-configuration
```

#### `OAUTH_INTROSPECTION_URL`

**Description:** Token introspection endpoint for validating OAuth tokens.

**Type:** URL String

**Example:**

```bash
OAUTH_INTROSPECTION_URL=https://example.com/introspect
```

**Complete OIDC example:**

```bash
ENABLE_OAUTH=True
OAUTH_CLIENT_ID=xxxxxxx
OAUTH_CLIENT_SECRET=xxxxxxx
OAUTH_BASE_URL=http://localhost:9000
OAUTH_CONFIG_URL=https://example.com/.well-known/openid-configuration
OAUTH_INTROSPECTION_URL=https://example.com/introspect
```

---

### Authorization-code OAuth

#### `OAUTH_HOST`

**Description:** Hostname for OAuth server.

**Type:** String

**Example:**

```bash
OAUTH_HOST=localhost
```

#### `OAUTH_PORT`

**Description:** Port number for OAuth server.

**Type:** Integer

**Example:**

```bash
OAUTH_PORT=9000
```

#### `OAUTH_SERVER_URL`

**Description:** Full server URL for OAuth.

**Type:** URL String

**Example:**

```bash
OAUTH_SERVER_URL=http://localhost:9000
```

#### `OAUTH_CALLBACK_PATH`

**Description:** OAuth callback URL path.

**Type:** URL String

**Example:**

```bash
OAUTH_CALLBACK_PATH=http://localhost:9000/callback
```

#### `OAUTH_AUTH_URL`

**Description:** Authorization endpoint URL.

**Type:** URL String

**Example:**

```bash
OAUTH_AUTH_URL=https://example.com/authorize

# GitHub
OAUTH_AUTH_URL=https://github.com/login/oauth/authorize
```

#### `OAUTH_TOKEN_URL`

**Description:** Token endpoint URL for exchanging authorization codes.

**Type:** URL String

**Example:**

```bash
OAUTH_TOKEN_URL=https://example.com/token

# GitHub
OAUTH_TOKEN_URL=https://github.com/login/oauth/access_token
```

#### `OAUTH_MCP_SCOPE`

**Description:** OAuth scope for MCP Composer.

**Type:** String

**Example:**

```bash
OAUTH_MCP_SCOPE=user
```

#### `OAUTH_PROVIDER_SCOPE`

**Description:** OAuth scope required by the provider.

**Type:** String

**Example:**

```bash
OAUTH_PROVIDER_SCOPE=openid
```

**Complete authorization-code example:**

```bash
ENABLE_OAUTH=True
OAUTH_HOST=localhost
OAUTH_PORT=9000
OAUTH_SERVER_URL=http://localhost:9000
OAUTH_CALLBACK_PATH=http://localhost:9000/callback
OAUTH_CLIENT_ID=xxxxxxx
OAUTH_CLIENT_SECRET=xxxxxxx
OAUTH_AUTH_URL=https://example.com/authorize
OAUTH_TOKEN_URL=https://example.com/token
OAUTH_MCP_SCOPE=user
OAUTH_PROVIDER_SCOPE=openid
```

---

## OpenTelemetry Configuration

### `MCP_TRACING_ENABLED`

**Description:** Enable or disable distributed tracing with OpenTelemetry.

**Type:** Boolean

**Default:** `False`

**Allowed Values:** `true`, `false`

**Example:**

```bash
MCP_TRACING_ENABLED=true
```

---

### `MCP_TRACING_PROTOCOL`

**Description:** Protocol to use for OpenTelemetry tracing.

**Type:** String

**Allowed Values:** `http`, `grpc`

**Example:**

```bash
MCP_TRACING_PROTOCOL=http
# For gRPC
MCP_TRACING_PROTOCOL=grpc
```

---

### `OTEL_SERVICE_NAME`

**Description:** Service name identifier for OpenTelemetry traces.

**Type:** String

**Default:** `mcp-composer`

**Example:**

```bash
OTEL_SERVICE_NAME=mcp-composer
# Custom service name
OTEL_SERVICE_NAME=mcp-composer-production
```

---

### `OTEL_EXPORTER_OTLP_ENDPOINT`

**Description:** OpenTelemetry collector endpoint URL.

**Type:** URL String

**Default:** `http://localhost:4318`

**Example:**

```bash
# Local collector
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# Remote collector
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.example.com:4318
```

---

### `MCP_METRICS_ENABLED`

**Description:** Enable or disable metrics collection with OpenTelemetry.

**Type:** Boolean

**Default:** `False`

**Allowed Values:** `true`, `false`

**Example:**

```bash
MCP_METRICS_ENABLED=true
```

---

### `MCP_ENV`

**Description:** Environment identifier for telemetry data.

**Type:** String

**Allowed Values:** `dev`, `staging`, `prod`

**Example:**

```bash
# Development
MCP_ENV=dev

# Staging
MCP_ENV=staging

# Production
MCP_ENV=prod
```

**Complete OpenTelemetry Configuration Example:**

```bash
MCP_TRACING_ENABLED=true
MCP_TRACING_PROTOCOL=http
OTEL_SERVICE_NAME=mcp-composer
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
MCP_METRICS_ENABLED=true
MCP_ENV=dev
```

---

## Common Configuration Examples

### Development Setup

```bash
# Basic dev configuration
MCP_BASE_URL=http://127.0.0.1:9000/mcp
MCP_COMPOSER_MODE=dev
MCP_MODE=sse
MCP_DATABASE_TYPE=local_file
MCP_DATABASE_FILE_PATH=mcp_servers.json
MCP_USE_LOCAL_FILE_STORAGE=True
ENABLE_OAUTH=False
```

### Production Setup with OAuth

```bash
# Production configuration
MCP_BASE_URL=https://mcp-composer.example.com/mcp
MCP_COMPOSER_MODE=prod
MCP_MODE=sse
MCP_DATABASE_TYPE=postgresql
ENABLE_OAUTH=True

# OIDC
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_BASE_URL=https://mcp-composer.example.com
OAUTH_CONFIG_URL=https://verify.example.com/oidc/endpoint/default/.well-known/openid-configuration
OAUTH_INTROSPECTION_URL=https://verify.example.com/v1.0/endpoint/default/introspect

# OpenTelemetry
MCP_TRACING_ENABLED=true
MCP_TRACING_PROTOCOL=http
OTEL_SERVICE_NAME=mcp-composer-prod
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.example.com:4318
MCP_METRICS_ENABLED=true
MCP_ENV=prod
```

---

## Server Configurations

### Member Servers File

Location: `example/member_servers.json`

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

##### Loading OpenAPI Specs from AWS S3

MCP Composer supports loading OpenAPI specifications directly from AWS S3 buckets. This is useful for centralized spec management, version control, and access control using AWS IAM.

**Installation:**

**Supported S3 URL Formats:**

1. **Virtual-hosted style** (recommended):
   ```
   https://bucket-name.s3.region.amazonaws.com/path/to/spec.json
   ```

2. **Path-style**:
   ```
   https://s3.region.amazonaws.com/bucket-name/path/to/spec.json
   ```

**Authentication:**

S3 access uses the standard AWS credential chain (no additional configuration needed):
- IAM roles (for EC2/ECS/Lambda)
- AWS credentials file (`~/.aws/credentials`)
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS SSO

**Example Configuration:**

```json
{
  "id": "my-service",
  "type": "openapi",
  "open_api": {
    "endpoint": "https://api.example.com",
    "spec_url": "https://bucket-solis-openapi-spec.s3.us-east-1.amazonaws.com/lakehouse-v3-short.json"
  },
  "auth_strategy": "bearer",
  "auth": {
    "token": "${API_TOKEN}"
  }
}
```

**Benefits:**
- **Centralized Management**: Store all OpenAPI specs in a central S3 bucket
- **Version Control**: Use S3 versioning for spec history
- **Access Control**: Leverage AWS IAM for fine-grained permissions
- **Cost-Effective**: S3 storage is cheaper than hosting specs on web servers
- **Scalability**: Better suited for large-scale deployments

**Error Handling:**

The system provides clear error messages for common S3 issues:
- `AccessDenied`: Check IAM permissions
- `NoSuchBucket`: Verify bucket name and region
- `NoSuchKey`: Verify the file path in the bucket
- Invalid JSON: Ensure the S3 object contains valid JSON

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

### Database Configuration Examples

#### Local File Database

```env
DATABASE_TYPE=local_file
DATABASE_PATH=data/mcp_composer.db
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
DATABASE_TYPE=postgres
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
   python -m json.tool example/member_servers.json
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
