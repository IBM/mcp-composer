# Introduction

MCP Composer is a [FastMCP](https://github.com/jlowin/fastmcp)-based orchestrator that manages multiple Model Context Protocol (MCP) servers and tools. It provides a unified interface for dynamic tool registration, authentication handling, and request dispatching across various MCP-compliant services.

## What is MCP Composer?

MCP Composer serves as a central hub that:

- **Discovers and registers** new MCP tools on startup or via API
- **Mounts and unmounts** member servers dynamically
- **Exposes all tools** across registered servers through a single interface
- **Handles authentication** for different upstream services
- **Monitors health** of all member servers

## Key Concepts

### MCP Servers

MCP Composer can work with various types of MCP servers:

- **HTTP/SSE MCP Servers**: Remote servers accessible via HTTP
- **Stdio MCP Servers**: Local servers running as subprocesses
- **OpenAPI-based Servers**: Automatically generated from OpenAPI specifications
- **GraphQL Servers**: Generated from GraphQL schemas

### Tools

Tools are the actual functions that can be invoked. MCP Composer supports:

- **OpenAPI Tools**: REST API endpoints
- **GraphQL Tools**: GraphQL queries and mutations
- **CLI Tools**: Command-line interface tools
- **Custom Scripts**: Python functions and scripts
- **Curl Commands**: HTTP requests via curl

### Authentication

MCP Composer handles authentication for upstream services:

- **OAuth 2.0**: Full OAuth flow support
- **Bearer Tokens**: Simple token-based authentication
- **Basic Auth**: Username/password authentication
- **Custom Auth**: Extensible authentication strategies

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │    │  MCP Inspector  │    │  Chatbot UI     │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │     MCP Composer          │
                    │   (FastMCP Server)        │
                    └─────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
┌─────────▼─────────┐  ┌─────────▼─────────┐  ┌─────────▼─────────┐
│  Member Server 1  │  │  Member Server 2  │  │  Member Server N  │
│  (OpenAPI)        │  │  (GraphQL)        │  │  (Custom)         │
└───────────────────┘  └───────────────────┘  └───────────────────┘
```

## 🏗️ Architecture Overview

MCP Composer extends FastMCP with advanced orchestration capabilities:

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Composer Server                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Tool Manager  │  │ Server Manager  │  │Prompt Manager│ │
│  │                 │  │                 │  │              │ │
│  │ • Tool Routing  │  │ • Registration  │  │ • Dynamic    │ │
│  │ • Filtering     │  │ • Health Check  │  │   Prompts    │ │
│  │ • Validation    │  │ • Load Balance  │  │ • Templates  │ │
│  │ • OpenAPI       │  │ • Discovery     │  │ • Execution  │ │
│  │ • GraphQL       │  │ • Mount/Unmount │  │              │ │
│  │ • Custom Tools  │  │ • Activation    │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Server Builder  │  │ Auth Handler    │  │Middleware    │ │
│  │                 │  │                 │  │              │ │
│  │ • HTTP/SSE      │  │ • Multi-Auth    │  │ • ACL        │ │
│  │ • STDIO         │  │ • OAuth         │  │ • Filtering  │ │
│  │ • OpenAPI       │  │ • Bearer        │  │ • Validation │ │
│  │ • GraphQL       │  │ • API Keys      │  │ • Monitoring │ │
│  │ • Local Files   │  │ • Dynamic Token │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Config Manager  │  │ Database        │  │ Monitoring   │ │
│  │                 │  │ Interface       │  │              │ │
│  │ • Version       │  │ • Cloudant      │  │ • Performance│ │
│  │   Control       │  │ • Local File    │  │ • Health     │ │
│  │ • Validation    │  │ • Custom        │  │ • Audit      │ │
│  │ • Migration     │  │ • Persistence   │  │ • Metrics    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Member MCP Servers                           │
├─────────────────┬─────────────────┬─────────────────────────┤
│ HTTP/SSE        │ STDIO           │ OpenAPI/GraphQL         │
│ • Remote APIs   │ • Local Scripts │ • REST APIs             │
│ • MCP Servers   │ • CLI Tools     │ • GraphQL APIs          │
│ • SSE Streams   │ • Data Process  │ • Custom Endpoints      │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## 🔧 Key Features

### 1. **Dynamic Server Orchestration**

MCP Composer can dynamically add, remove, and configure MCP servers at runtime without restarting the system.

```python
# Add a new server dynamically
await composer.register_mcp_server({
    "id": "new-service",
    "name": "New Service",
    "type": "http",
    "endpoint": "https://api.new-service.com/mcp",
    "auth": {"type": "bearer", "token": "token"}
})

# Remove a server
await composer.delete_mcp_server("old-service")

# Update server configuration
await composer.update_mcp_server_config("service-id", new_config)
```

**Supported Server Types:**

- **HTTP/SSE**: Remote MCP servers via HTTP or Server-Sent Events
- **STDIO**: Local MCP servers via standard input/output
- **OpenAPI**: REST APIs with OpenAPI specifications
- **GraphQL**: GraphQL APIs with schema introspection
- **Local Files**: Python files with custom MCP implementations

### 2. **Multi-Type Tool Management**

Centralized tool management with support for multiple tool types and sources.

```python
# Add custom tools from Python scripts
await composer.add_tools({
    "name": "custom-tool",
    "tool_type": "script",
    "script_config": {
        "value": "def my_tool(param: str) -> str:\n    return f'Processed: {param}'"
    },
    "description": "A custom tool"
})

# Add tools from OpenAPI specifications
await composer.add_tools_from_openapi(
    openapi_spec={...},
    auth_config={"type": "bearer", "token": "token"}
)

# Add tools from curl commands
await composer.add_tools({
    "name": "curl-tool",
    "tool_type": "curl",
    "curl_config": {
        "value": "curl 'https://api.example.com/data' --header 'Authorization: Bearer token'"
    }
})
```

**Tool Types Supported:**

- **OpenAPI**: Automatic tool generation from OpenAPI specs
- **GraphQL**: GraphQL query tools with schema introspection
- **Curl**: Tools based on curl commands
- **Python Scripts**: Custom Python function tools
- **MCP Tools**: Standard MCP tools from member servers

### 3. **Multi-Authentication Support**

Support for multiple authentication methods across different member servers.

```python
# Bearer token authentication
"auth": {"type": "bearer", "token": "your_token"}

# API key authentication
"auth": {"type": "apikey", "key": "your_key", "header": "X-API-Key"}

# OAuth authentication
"auth": {
    "type": "oauth",
    "client_id": "client_id",
    "client_secret": "client_secret",
    "token_url": "https://oauth.com/token"
}

# Dynamic token management
"auth": {
    "type": "dynamic",
    "token_manager": token_manager_instance
}
```

### 4. **Server Builder System**

Flexible server building system that supports multiple server types and configurations.

```python
from mcp_composer.member_servers.builder import MCPServerBuilder

# Build HTTP server
config = {
    "id": "http-server",
    "type": "http",
    "endpoint": "https://api.example.com/mcp",
    "auth": {"type": "bearer", "token": "token"}
}
builder = MCPServerBuilder(config)
server = await builder.build()

# Build OpenAPI server
config = {
    "id": "openapi-server",
    "type": "openapi",
    "open_api": {
        "endpoint": "https://api.example.com",
        "spec_url": "https://api.example.com/openapi.json"
    },
    "auth_strategy": "bearer",
    "auth": {"token": "token"}
}
builder = MCPServerBuilder(config)
server = await builder.build()

# Build GraphQL server
config = {
    "id": "graphql-server",
    "type": "graphql",
    "endpoint": "https://graphql.example.com/graphql"
}
builder = MCPServerBuilder(config)
server = await builder.build()
```

### 5. **Dynamic Prompt Management**

Create, manage, and execute dynamic prompts across multiple servers.

```python
# Add prompts
await composer.add_prompts([
    {
        "name": "customer-analysis",
        "description": "Analyze customer data and generate insights",
        "template": "Analyze the customer data for {customer_id} and provide insights about their behavior and preferences.",
        "arguments": [
            {
                "name": "customer_id",
                "type": "string",
                "required": True,
                "description": "The customer ID to analyze"
            }
        ]
    }
])

# Get all prompts
prompts = await composer.get_all_prompts()
```

### 6. **Health Monitoring & Server Management**

Real-time health monitoring and intelligent server management.

```python
# Check health status
health = await composer.member_health()

# Activate/deactivate servers
await composer.activate_mcp_server("server-id")
await composer.deactivate_mcp_server("server-id")

# List all servers
servers = await composer.list_servers()

# Get tool configurations
tool_config = await composer.get_tool_config_by_name("tool-name")
server_tools = await composer.get_tool_config_by_server("server-id")
```

### 7. **Database-Backed Configuration**

Persistent configuration storage with support for multiple database backends.

```python
# Cloudant database
composer = MCPComposer(
    database_config={
        "type": "cloudant",
        "api_key": "key",
        "service_url": "url",
        "db_name": "mcp_servers"
    }
)

# Local file storage (development)
composer = MCPComposer()  # Uses local file storage by default

# Custom database adapter
class CustomDatabaseAdapter(DatabaseInterface):
    async def save_server_config(self, server_id: str, config: dict):
        # Your implementation
        pass
    
    async def load_server_config(self, server_id: str) -> dict:
        # Your implementation
        pass

composer = MCPComposer(database_config=CustomDatabaseAdapter())
```

### 8. **Tool Filtering and Management**

Advanced tool filtering, enabling/disabling, and description management.

```python
# Disable specific tools
await composer.disable_tools(["tool1", "tool2"], "server-id")

# Enable tools
await composer.enable_tools(["tool1", "tool2"], "server-id")

# Update tool descriptions
await composer.update_tool_description("tool-name", "New description", "server-id")

# Get all tools (filtered)
tools = await composer.get_all_tools(server_id="server-id")
```

## 🔄 Request Flow

Here's how a typical request flows through MCP Composer:

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
4. Authentication Handler
   ├── Apply server-specific auth
   ├── Handle token refresh
   ├── Validate credentials
   └── Manage dynamic tokens
       │
       ▼
5. Server Builder/Transport
   ├── Build server if needed
   ├── Establish connection
   ├── Send request
   └── Handle response
       │
       ▼
6. Response Processing
   ├── Apply result filters
   ├── Log audit trail
   ├── Update metrics
   └── Return to client
```

## 🎯 Use Cases

### **Enterprise Integration**

- Orchestrate multiple internal APIs and services
- Provide unified access to customer, product, and analytics data
- Implement enterprise-grade security and monitoring

### **API Aggregation**

- Aggregate tools from multiple REST APIs via OpenAPI
- Provide GraphQL access to REST services
- Handle different authentication methods per service

### **Development & Testing**

- Mock external services for development
- Test different server configurations
- Validate tool integrations

### **Microservices Architecture**

- Aggregate tools from multiple microservices
- Provide consistent interface across services
- Handle service discovery and health monitoring

## 🚀 Performance Features

### **Caching**

- Tool metadata caching
- Authentication token caching
- Server configuration caching

### **Load Balancing**

- Round-robin load balancing
- Health-based server selection
- Automatic failover

### **Monitoring**

- Real-time performance metrics
- Tool call latency tracking
- Error rate monitoring

### **Scalability**

- Horizontal scaling support
- Database-backed configuration
- Stateless design

## 📊 Configuration Management

MCP Composer provides flexible configuration management:

```python
# Environment-based configuration
composer = MCPComposer(
    name=os.getenv("COMPOSER_NAME", "Default Composer"),
    database_config=get_database_config(),
    version_adapter_config=get_version_config()
)

# Dynamic configuration updates
await composer.update_mcp_server_config("server-id", new_config)
```

## 🔒 Security Features

- **Multi-factor authentication** support
- **Dynamic token management** and refresh
- **Tool-level permissions** and filtering
- **Audit logging** for compliance
- **Input validation** and sanitization
- **Secure credential storage**

## 📈 Monitoring & Observability

- **Health checks** for all member servers
- **Performance metrics** collection
- **Error tracking** and alerting
- **Audit trails** for all operations
- **Tool usage analytics**

This comprehensive feature set makes MCP Composer the ideal solution for enterprise-grade MCP server orchestration, providing the flexibility, security, and monitoring capabilities needed for production deployments.

## Next Steps

- [Installation Guide](/guide/installation) - Set up MCP Composer
- [Quick Start](/guide/quick-start) - Get up and running in minutes
- [Configuration](/guide/configuration) - Learn about configuration options
- [Middleware Guide](/guide/middleware) - Create and use middleware components
- [Examples](/examples/) - See practical examples and demos
