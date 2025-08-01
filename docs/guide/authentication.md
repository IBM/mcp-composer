# Authentication

MCP Composer provides comprehensive authentication support for securing your MCP infrastructure and member servers.

## Overview

Authentication in MCP Composer works at multiple levels:

1. **Composer-level authentication** - Secures the MCP Composer itself
2. **Server-level authentication** - Handles authentication for each member server
3. **Tool-level authentication** - Applies specific authentication for individual tools

## 🔐 Authentication Methods

The **Auth Handler** supports the following authentication strategies:

### 1. Bearer Token Authentication

The most common authentication method for API-based services.

```python
# Server configuration with Bearer token
await composer.register_mcp_server({
    "id": "customer-api",
    "type": "http",
    "endpoint": "https://api.customers.com/mcp",
    "auth_strategy": "bearer",
    "auth": {
        "token": "your_bearer_token_here"
    }
})
```

**Features:**
- Automatic token inclusion in Authorization header
- Support for token refresh
- Secure token storage

### 2. API Key Authentication

Simple key-based authentication for APIs.

```python
# Server configuration with API key
await composer.register_mcp_server({
    "id": "product-api",
    "type": "http",
    "endpoint": "https://api.products.com/mcp",
    "auth_strategy": "apikey",
    "auth": {
        "apikey": "your_api_key_here",
        "auth_prefix": "X-API-Key"  # Optional: custom header name
    }
})
```

**Features:**
- Customizable header names
- Support for query parameter authentication
- Simple key management

### 3. OAuth 2.0 Authentication

Full OAuth 2.0 support for enterprise services.

**Recommended:** Use environment variables in an `.env.oauth` file. See `.env.oauth.example` for the required variables. Example variables:

```
OAUTH_HOST=localhost
OAUTH_PORT=8000
OAUTH_SERVER_URL=http://localhost:8000
OAUTH_CLIENT_ID=your_client_id
OAUTH_CLIENT_SECRET=your_client_secret
OAUTH_CALLBACK_PATH=/auth/callback
OAUTH_AUTH_URL=https://provider.com/oauth/authorize
OAUTH_TOKEN_URL=https://provider.com/oauth/token
OAUTH_MCP_SCOPE=user
OAUTH_PROVIDER_SCOPE=openid
```

**Server configuration:**

```python
await composer.register_mcp_server({
    "id": "enterprise-api",
    "type": "http",
    "endpoint": "https://api.enterprise.com/mcp",
    "auth_strategy": "oauth2",
    "auth": {
        "client_id": os.getenv("OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("OAUTH_CLIENT_SECRET"),
        "token_url": os.getenv("OAUTH_TOKEN_URL")
    }
})
```

> **Note:** The actual OAuth2 flow and callback handling is managed by the MCP Composer using the environment variables above. See the README and `.env.oauth.example` for more details.

**Features:**
- Full OAuth 2.0 flow support
- Automatic token refresh
- Scope management
- Authorization code flow

### 4. Dynamic Bearer (IBM IAM-style)

Dynamic token management for cloud services that require token exchange.

```python
await composer.register_mcp_server({
    "id": "ibm-iam-server",
    "type": "http",
    "endpoint": "https://api.ibm.com/mcp",
    "auth_strategy": "dynamic_bearer",
    "auth": {
        "apikey": "your_ibm_cloud_apikey",
        "token_url": "https://iam.cloud.ibm.com/identity/token",
        "media_type": "json"  # Optional
    }
})
```

**Real-world example (IBM Watsonx Orchestrate):**

```python
await composer.register_mcp_server({
    "id": "ibm-watsonx-orchestrate",
    "type": "openapi",
    "open_api": {
        "endpoint": "https://api.dl.watson-orchestrate.ibm.com/instances/{instance-id}/v1/orchestrate/",
        "spec_filepath": "/path/to/wxo-openapi-spec.json",
        "custom_routes": [
            {
                "methods": ["GET"],
                "pattern": "./.",
                "mcp_type": "TOOL"
            },
            {
                "methods": ["POST", "DELETE", "PUT", "PATCH"],
                "pattern": ".*",
                "mcp_type": "EXCLUDE"
            }
        ]
    },
    "auth_strategy": "dynamic_bearer",
    "auth": {
        "apikey": "your_ibm_cloud_apikey",
        "token_url": "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
        "media_type": "json"
    }
})
```

**Template for similar IBM Cloud services:**

```python
await composer.register_mcp_server({
    "id": "ibm-service-name",
    "type": "openapi",
    "open_api": {
        "endpoint": "https://api.service.ibm.com/instances/{instance-id}/v1/",
        "spec_filepath": "/path/to/openapi-spec.json",
        "custom_routes": [
            {
                "methods": ["GET"],
                "pattern": "./.",
                "mcp_type": "TOOL"
            },
            {
                "methods": ["POST", "DELETE", "PUT", "PATCH"],
                "pattern": ".*",
                "mcp_type": "EXCLUDE"
            }
        ]
    },
    "auth_strategy": "dynamic_bearer",
    "auth": {
        "apikey": "your_ibm_cloud_apikey",
        "token_url": "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
        "media_type": "json"
    }
})
```

### 5. Basic Authentication

Username/password authentication for legacy systems.

```python
await composer.register_mcp_server({
    "id": "basic-auth-server",
    "type": "http",
    "endpoint": "https://api.example.com/mcp",
    "auth_strategy": "basic",
    "auth": {
        "username": "your_username",
        "password": "your_password"
    }
})
```

### 6. JSESSIONID Authentication

Session-based authentication for web applications.

```python
await composer.register_mcp_server({
    "id": "jsessionid-server",
    "type": "http",
    "endpoint": "https://api.example.com/mcp",
    "auth_strategy": "jessionid",
    "auth": {
        "auth_prefix": "Cookie",
        "token": "your_token"
    }
})
```

### 7. API Token Authentication

Custom token-based authentication with configurable headers.

```python
await composer.register_mcp_server({
    "id": "apitoken-server",
    "type": "http",
    "endpoint": "https://api.example.com/mcp",
    "auth_strategy": "apiToken",
    "auth": {
        "token": "your_token",
        "auth_prefix": "Bearer"  # Optional
    }
})
```

## 🔧 Advanced Authentication Features

### Multi-Authentication Support

MCP Composer supports multiple authentication methods across different member servers simultaneously.

```python
# Example: Different auth strategies for different servers
await composer.register_mcp_server({
    "id": "customer-api",
    "type": "http",
    "endpoint": "https://api.customers.com/mcp",
    "auth_strategy": "bearer",
    "auth": {"token": "customer_token"}
})

await composer.register_mcp_server({
    "id": "product-api", 
    "type": "http",
    "endpoint": "https://api.products.com/mcp",
    "auth_strategy": "apikey",
    "auth": {"apikey": "product_key"}
})

await composer.register_mcp_server({
    "id": "analytics-api",
    "type": "http", 
    "endpoint": "https://api.analytics.com/mcp",
    "auth_strategy": "oauth2",
    "auth": {
        "client_id": os.getenv("ANALYTICS_CLIENT_ID"),
        "client_secret": os.getenv("ANALYTICS_CLIENT_SECRET"),
        "token_url": os.getenv("ANALYTICS_TOKEN_URL")
    }
})
```

### Dynamic Token Management

MCP Composer supports dynamic token management for scenarios where tokens need to be refreshed or rotated. See the IBM IAM example above for usage.

### OAuth Callback Handling

For OAuth flows that require user interaction, MCP Composer provides callback handling. See the README and `.env.oauth.example` for more details.

## 🔒 Security Best Practices

### 1. Environment Variables

Always store sensitive credentials in environment variables:

```python
import os
await composer.register_mcp_server({
    "id": "secure-server",
    "type": "http",
    "endpoint": "https://api.secure.com/mcp",
    "auth_strategy": "bearer",
    "auth": {
        "token": os.getenv("API_TOKEN")
    }
})
```

### 2. Token Rotation

Implement token rotation for enhanced security. See the README for examples.

### 3. Credential Encryption

Encrypt sensitive credentials before storage. See the README for examples.

## 🔄 Authentication Flow

Here's how authentication flows through MCP Composer's **Auth Handler**:

```
1. Client Request
   └── call_tool("customer-search", {...})
       │
       ▼
2. Tool Manager
   ├── Lookup tool in registry
   ├── Route to appropriate server
   ├── Apply tool filters
   └── Check tool permissions
       │
       ▼
3. Server Manager
   ├── Find target server
   ├── Check server health
   ├── Apply load balancing
   └── Handle failover
       │
       ▼
4. Auth Handler
   ├── Check auth_strategy type
   ├── Apply server-specific auth
   ├── Handle token refresh
   ├── Validate credentials
   └── Manage dynamic tokens
       │
       ▼
5. Server Builder/Transport
   ├── Build server if needed
   ├── Establish connection
   ├── Send request with auth headers
   └── Handle response
       │
       ▼
6. Response Processing
   ├── Apply result filters
   ├── Log audit trail
   ├── Update metrics
   └── Return to client
```

## 🛠️ Configuration Examples

### Development Environment

```python
# Development setup with simple auth
composer = MCPComposer(name="Dev Composer")

await composer.register_mcp_server({
    "id": "dev-server",
    "type": "http",
    "endpoint": "http://localhost:8001",
    "auth_strategy": "apikey",
    "auth": {
        "apikey": "dev_key_123"
    }
})
```

### Production Environment

```python
# Production setup with OAuth
composer = MCPComposer(
    name="Production Composer",
    database_config={
        "type": "cloudant",
        "api_key": os.getenv("CLOUDANT_API_KEY"),
        "service_url": os.getenv("CLOUDANT_SERVICE_URL")
    }
)

await composer.register_mcp_server({
    "id": "prod-server",
    "type": "http",
    "endpoint": "https://api.production.com/mcp",
    "auth_strategy": "oauth2",
    "auth": {
        "client_id": os.getenv("OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("OAUTH_CLIENT_SECRET"),
        "token_url": os.getenv("OAUTH_TOKEN_URL")
    }
})
```

### Multi-Environment Setup

```python
# config.py
import os

def get_auth_config(environment: str):
    if environment == "development":
        return {
            "auth_strategy": "apikey",
            "auth": {"apikey": "dev_key"}
        }
    elif environment == "staging":
        return {
            "auth_strategy": "bearer",
            "auth": {"token": os.getenv("STAGING_TOKEN")}
        }
    elif environment == "production":
        return {
            "auth_strategy": "oauth2",
            "auth": {
                "client_id": os.getenv("PROD_CLIENT_ID"),
                "client_secret": os.getenv("PROD_CLIENT_SECRET"),
                "token_url": os.getenv("PROD_TOKEN_URL")
            }
        }
    
    raise ValueError(f"Unknown environment: {environment}")

# main.py
env = os.getenv("ENVIRONMENT", "development")
auth_config = get_auth_config(env)

await composer.register_mcp_server({
    "id": "multi-env-server",
    "type": "http",
    "endpoint": os.getenv("API_URL"),
    **auth_config
})
```

## 🔍 Troubleshooting

### Common Authentication Issues

1. **Invalid Token**
   ```python
   # Check token validity
   try:
       await composer.member_health()
   except AuthenticationError as e:
       print(f"Authentication failed: {e}")
       # Refresh token or update configuration
   ```

2. **Token Expired**
   ```python
   # Handle token expiration
   async def handle_token_expiration(server_id: str):
       new_token = await refresh_token(server_id)
       await composer.update_mcp_server_config(
           server_id,
           {"auth": {"token": new_token}}
       )
   ```

3. **OAuth Flow Issues**
   ```python
   # Debug OAuth flow
   import logging
   logging.getLogger("mcp_composer.auth_handler.oauth").setLevel(logging.DEBUG)
   ```

### Debugging Authentication

Enable debug logging for authentication:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("mcp_composer.auth_handler").setLevel(logging.DEBUG)
```

## 📚 Next Steps

- **[Examples](/examples)** - Real-world authentication examples
- **[API Reference](/api/)** - Complete API documentation
- **[Configuration Guide](/guide/configuration)** - Learn about configuration options 