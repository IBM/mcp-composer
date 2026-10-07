# FastMCP-based MCP Server Orchestrator

The MCP Composer is a [FastMCP](https://github.com/jlowin/fastmcp) based Composer that manages multiple MCP servers and tools.
Servers and tools can be registered at runtime using structured JSON configurations.

[MCP Composer](https://ibm.github.io/mcp-composer/) serves as an orchestrator for tool execution and forwards tool requests to the correct upstream MCP server or interface.

It supports multiple tool types, such as OpenAPI (REST), GraphQL, CLI-based tools, client SDKs, and nested MCP servers.

Also, you can manage multiple MCP servers and tools with dynamic registration, authentication, and unified interface.

## Features

### Core Capabilities
- **Multi-Server Orchestration**: Manage and coordinate multiple MCP servers simultaneously
- **Dynamic Configuration**: Register servers and tools at runtime using JSON configurations
- **Multiple Transport Modes**: Support for stdio, HTTP, and Server-Sent Events (SSE)
- **Authentication Support**: OAuth integration and dynamic token management
- **Middleware System**: Extensible middleware framework for request/response processing
- **Tool Management**: Support for OpenAPI, GraphQL, CLI tools, and custom implementations
- **Environment Management**: Flexible environment variable handling and inheritance

### Transport Modes
- **stdio**: Direct process communication (default)
- **HTTP**: RESTful API endpoints
- **SSE**: Server-Sent Events for real-time communication

### Middleware Management
- **Validation**: Validate middleware configuration files
- **Listing**: List configured middlewares with filtering options
- **Dynamic Addition**: Add or update middlewares at runtime
- **Import Verification**: Ensure middleware classes can be imported
- **Priority Control**: Execution order management
- **Hook Filtering**: Selective middleware application

## Installation

1. Install using pipx 

    ```
    pipx install mcp-composer
    ```

2. Install using uvx 

    ```
    uvx pip install mcp-composer  

    ## To verify run the following command 
    
    uvx pip show mcp-composer 
    ```

3. Add as dependency to project 

    ```
    uv add mcp-composer
    ```

## Usage

MCP Composer itself acts as an MCP server and can be started on any supported transport.

```bash
# Run with STDIO transport (default)
mcp-composer --mode stdio

# Run with HTTP mode
mcp-composer --mode http --endpoint http://api.example.com --id http-server

# Set custom host and port for HTTP/SSE modes
mcp-composer --mode http --host 127.0.0.1 --port 8080 --endpoint http://api.example.com

# Run with SSE mode
mcp-composer --mode sse --endpoint http://localhost:8001/sse --id sse-server

# Run SSE server as STDIO
mcp-composer --mode stdio --sse-url http://localhost:8001/sse 
```

### Server Configuration

A MCP composer instance can mount different type of mcp server with different authentication mechanism

```bash
# Use custom configuration file
mcp-composer --mode http --endpoint http://localhost:8001/mcp --config_path /path/to/servers.json 
```

A servers.json file can have different type of mcp server 

```
[
  {
    "id": "mcp-countries",
    "type": "graphql",
    "graphql": {
      "endpoint": "https://countries.trevorblades.com/",
      "schema_filepath": "<path to your graphql schema file>/countries.graphql"
    }
  },
  {
    "id": "mcp-pokemon",
    "type": "graphql",
    "graphql": {
      "endpoint": "https://graphqlpokemon.favware.tech/v8",
      "schema_filepath": "<path to your graphql schema file>/pokemon.graphql"
    }
  },
  {
    "id": "sse-server",
    "type": "sse",
    "endpoint": "http://localhost:8001/sse",
  },
  {
    "id": "http-server",
    "type": "http",
    "endpoint": "http://localhost:8002/http",
  },
  {
    "id": "mcp-xxx",
    "type": "openapi",
    "open_api": {
      "endpoint": "<api server endpoint>",
      "spec_filepath": "<path to your openapi spec file>",
      "custom_routes": [
        {
          "methods":["GET"],
          "pattern":".*/users/.*",
          "mcp_type":"RESOURCE_TEMPLATE"
        },
        {
          "methods":["GET"],
          "pattern":".*/events/.*",
          "mcp_type":"TOOL"
        },
        {
          "methods":["POST"],
          "pattern":".*/",
          "mcp_type":"EXCLUDE"
        }
      ]
    },
    "auth_strategy":"bearer",
    "auth":{
      "token":"<your api key>"
    }
   
   }
]
```


### Authentication

```bash
# Enable OAuth authentication
mcp-composer --auth_type oauth --mode http --endpoint http://api.example.com 
```

### Environment Management

```bash
# Set specific environment variables
mcp-composer --env API_KEY mykey --env DEBUG true --mode http --endpoint http://api.example.com 
```

### Composer Tools Control

By default, MCP Composer acts as an MCP management system and exposes the following built-in tools:

#### Server Management Tools
- **register_mcp_server**: Register a new MCP server
- **update_mcp_server_config**: Update existing server configuration
- **delete_mcp_server**: Remove a server from the composer
- **member_health**: Check health status of member servers
- **activate_mcp_server**: Activate a previously deactivated server
- **deactivate_mcp_server**: Deactivate a server temporarily
- **add_tools**: Add individual tools to the composer
- **add_tools_from_openapi**: Import tools from OpenAPI specifications
- **list_member_servers**: List all registered member servers

#### Tool Management Tools
- **get_tool_config_by_name**: Retrieve tool configuration by name of the tool
- **get_tool_config_by_server**: Get tool configuration for a specific server
- **disable_tools**: Disable specific tools
- **enable_tools**: Enable previously disabled tools
- **update_tool_description**: Update tool descriptions and metadata

#### Prompt Management Tools
- **add_prompts**: Add new prompts to the system
- **get_all_prompts**: Retrieve all available prompts
- **list_prompts_per_server**: List prompts for a specific server
- **filter_prompts**: Filter prompts based on criteria
- **disable_prompts**: Disable specific prompts
- **enable_prompts**: Enable previously disabled prompts

#### Resource Management Tools
- **create_resource**: Create new resources
- **create_resource_template**: Create resource templates
- **list_resources**: List all available resources
- **list_resource_templates**: List resource templates
- **list_resources_per_server**: List resources for a specific server
- **filter_resources**: Filter resources based on criteria
- **disable_resources**: Disable specific resources
- **enable_resources**: Enable previously disabled resources

These tools provide comprehensive management capabilities for the MCP Composer ecosystem.


In order to disable the admisnitrative tools start mcp-composer with following tools

```bash
# Disable built-in composer tools
mcp-composer --disable-composer-tools --mode stdio
```

## License

Apache License 2.0. See the repository [LICENSE](https://github.com/ibm/mcp-composer/blob/main/LICENSE).

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](https://github.com/ibm/mcp-composer/blob/main/CONTRIBUTING.md) and report vulnerabilities through [SECURITY.md](https://github.com/ibm/mcp-composer/blob/main/SECURITY.md).