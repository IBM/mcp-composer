# Building AI Tools Like Ogres: The Layered MCP Server Architecture

*How to transform complex OpenAPI specifications into LLM-friendly, progressive discovery tools*

---

## The Problem: When APIs Overwhelm AI

Imagine you have a REST API with 162 endpoints. You want to expose it to an AI agent so it can interact with your services. The traditional approach? Generate one tool per endpoint. Result? The AI agent is overwhelmed with 162 tools, struggling to understand what's available, how to use them, and which ones are relevant.

This is exactly the problem the **Layered MCP Server Architecture** solves. Inspired by [Block's Engineering team's "Layered Tool Pattern"](https://engineering.block.xyz/blog/build-mcp-tools-like-ogres-with-layers), this architecture breaks down complex API interactions into three progressive layers that guide AI agents through discovery, planning, and execution.

> "Ogres are like onions. Onions have layers. Ogres have layers." - Shrek

The same principle applies to AI tools. Rather than building monolithic tools that overwhelm LLMs, we use distinct functional layers that work together to guide AI agents through progressive steps.

---

## The Three-Layer Architecture

The Layered MCP Server Architecture consists of three distinct layers, each serving a specific purpose in the AI agent's workflow:

### Layer 1: Discovery (`get_service_info`)

**Purpose**: Help the AI understand what's available

The discovery layer provides a high-level view of all available API operations. Instead of exposing 162 individual tools, it exposes a single `get_service_info` tool that can:

- List all available services
- Provide summaries and descriptions
- Show HTTP methods and paths
- Filter operations based on custom rules

**Example Usage**:
```python
# List all available services
get_service_info()

# Get detailed info about a specific service
get_service_info(service="getApplications")
```

### Layer 2: Planning (`get_type_info`)

**Purpose**: Help the AI understand how to use a specific service

Once the AI knows what's available, it needs to understand the details. The planning layer provides comprehensive schema information:

- Parameter schemas (path, query, header parameters)
- Request body schemas with examples
- Response schemas
- Resolved schema references (no more `$ref` confusion)

**Example Usage**:
```python
# Get detailed schema information
get_type_info(service="getApplications")
```

### Layer 3: Execution (`make_tool_call`)

**Purpose**: Actually execute the API call

Finally, when the AI has discovered what's available and understands how to use it, the execution layer performs the actual HTTP request.

**Example Usage**:
```python
# Execute an API call
make_tool_call(
    service="getApplications",
    request={
        "path_params": {"application_id": "123"},
        "query_params": {"status": "active"},
        "headers": {"Accept": "application/json"}
    }
)
```

---

## Real-World Example: OpenAPI Integration

Let's see how this works with a real OpenAPI specification. We'll use the IBM Hybrid Cloud Mesh API as an example, which has 162 operations across various HTTP methods.

### Step 1: Configuration

First, we configure the MCP Composer to use the layered architecture:

```json
{
  "id": "mcp-hybrid-mesh",
  "type": "openapi",
  "open_api": {
    "endpoint": "https://app.hybridcloudmesh.ibm.com/api/v1",
    "spec_filepath": "./spec/hybrid_mesh.json",
    "layered": true,
    "custom_routes": [
      {
        "methods": ["GET"],
        "pattern": ".*",
        "mcp_type": "TOOL"
      },
      {
        "methods": ["POST", "DELETE", "PUT", "PATCH"],
        "pattern": ".*",
        "mcp_type": "EXCLUDE"
      }
    ]
  }
}
```

**Key Configuration Points**:

- **`layered: true`**: Enables the layered architecture (uses `LayeredOpenAPIFactory`)
- **`custom_routes`**: Defines filtering rules for API operations
- **GET = TOOL**: Include GET operations (read-only, safe operations)
- **POST/DELETE/PUT/PATCH = EXCLUDE**: Exclude write operations for security

### Step 2: What Happens Under the Hood

When `layered: true` is set, the MCP Composer:

1. **Loads the OpenAPI spec** from `hybrid_mesh.json`
2. **Applies custom routes filtering**: Only GET operations are included (58 out of 162)
3. **Resolves schema references**: All `$ref` references are resolved to actual schemas
4. **Enhances metadata**: Adds examples, cleaned schemas, and type information
5. **Registers exactly 3 tools**: `get_service_info`, `get_type_info`, and `make_tool_call`

### Step 3: The AI Agent's Workflow

Here's how an AI agent would interact with this layered server:

```python
# Step 1: Discovery - "What's available?"
services = get_service_info()
# Returns: List of 58 GET operations with summaries

# Step 2: Planning - "How do I use getApplications?"
details = get_type_info(service="getApplications")
# Returns: Complete schema with parameters, request body, responses, examples

# Step 3: Execution - "Let me call it"
result = make_tool_call(
    service="getApplications",
    request={
        "query_params": {"limit": 10, "offset": 0}
    }
)
# Returns: Actual API response
```

---

## Schema Resolution: The Magic Behind the Scenes

One of the most powerful features of the layered architecture is automatic schema resolution. OpenAPI specs often use `$ref` references to avoid duplication:

```json
{
  "parameters": [
    {
      "name": "application_id",
      "schema": {
        "$ref": "#/components/schemas/UUID"
      }
    }
  ]
}
```

The layered architecture automatically resolves these references:

```json
{
  "parameters": [
    {
      "name": "application_id",
      "schema": {
        "type": "string",
        "format": "uuid",
        "description": "Unique identifier for the application"
      },
      "original_ref": "#/components/schemas/UUID"
    }
  ]
}
```

This makes schemas much more LLM-friendly, as the AI doesn't need to navigate complex reference structures.

---

## Benefits of the Layered Architecture

### 1. **Progressive Complexity**

Instead of overwhelming the AI with 162 tools at once, it's guided through three progressive steps:
- First, understand what's available
- Then, understand how to use it
- Finally, execute it

### 2. **Selective API Exposure**

With `custom_routes`, you can:
- Expose only read operations (GET) for safety
- Filter by path patterns
- Control exactly which operations are available

### 3. **Enhanced Schema Information**

- Resolved `$ref` references
- Generated examples
- Cleaned schemas for better LLM understanding
- Type information and descriptions

### 4. **Consistent Interface**

Regardless of the underlying API complexity, the AI always interacts with exactly 3 tools. This consistency makes it easier for the AI to learn and use the system.

### 5. **Security by Design**

By excluding write operations (POST, PUT, DELETE, PATCH) by default, you create a read-only interface that's safe for AI agents to explore.

---

## Comparison: Traditional vs. Layered Approach

### Traditional Approach

```
OpenAPI Spec (162 operations)
    ↓
162 Individual Tools
    ↓
AI Agent: "I'm overwhelmed! Which tool should I use?"
```

**Problems**:
- Too many tools to choose from
- No guidance on usage
- Complex schema references
- All operations exposed (including dangerous ones)

### Layered Approach

```
OpenAPI Spec (162 operations)
    ↓
Custom Routes Filtering (58 GET operations)
    ↓
3 Layered Tools
    ↓
AI Agent: "Let me discover → plan → execute"
```

**Benefits**:
- Progressive discovery
- Clear workflow guidance
- Resolved schemas with examples
- Selective, safe operation exposure

---

## Implementation Details

The layered architecture is implemented in the `LayeredOpenAPIFactory` class, which extends FastMCP:

```python
class LayeredOpenAPIFactory(FastMCP):
    def __init__(
        self,
        openapi_spec: dict[str, Any],
        client: httpx.AsyncClient,
        custom_routes: list[RouteMap] | None = None,
    ):
        super().__init__(
            name="Layered OpenAPI FastMCP",
            instructions="""Three main capabilities:
            1. get_service_info - Discover available operations
            2. get_type_info - Get detailed schema information
            3. make_tool_call - Execute API calls"""
        )
        
        self.openapi_spec = openapi_spec
        self.client = client
        self.custom_routes = custom_routes or []
        self.service_info = self._build_service_metadata()
        
        # Register the three tools
        self.add_tool(Tool.from_function(self.get_service_info))
        self.add_tool(Tool.from_function(self.get_type_info))
        self.add_tool(Tool.from_function(self.make_tool_call))
```

The factory processes the OpenAPI spec, applies custom routes filtering, resolves schema references, and builds enhanced metadata for each operation.

---

## Custom Routes: Fine-Grained Control

Custom routes give you precise control over which operations are exposed:

```json
{
  "custom_routes": [
    {
      "methods": ["GET"],
      "pattern": ".*/applications/.*",
      "mcp_type": "TOOL"
    },
    {
      "methods": ["GET"],
      "pattern": ".*/events/.*",
      "mcp_type": "RESOURCE_TEMPLATE"
    },
    {
      "methods": ["POST", "PUT", "DELETE"],
      "pattern": ".*",
      "mcp_type": "EXCLUDE"
    }
  ]
}
```

**MCP Types**:
- **`TOOL`**: Expose as a callable tool (via `make_tool_call`)
- **`RESOURCE_TEMPLATE`**: Extract reusable schemas
- **`EXCLUDE`**: Completely exclude from the interface

Patterns support regex matching, so you can create sophisticated filtering rules.

---

## Real Results: From 162 to 3

In our Hybrid Cloud Mesh example:

- **Original OpenAPI Spec**: 162 operations (GET, POST, PUT, DELETE, PATCH)
- **After Custom Routes Filtering**: 58 operations (only GET)
- **Final Tool Count**: 3 tools (`get_service_info`, `get_type_info`, `make_tool_call`)

The AI agent now has:
- A clear discovery mechanism
- Detailed planning information
- A safe execution interface
- Enhanced schema understanding

---

## Getting Started

To use the layered architecture in your MCP Composer setup:

1. **Install MCP Composer**:
   ```bash
   pipx install mcp-composer
   ```

2. **Create your configuration** with `layered: true`:
   ```json
   {
     "id": "my-api",
     "type": "openapi",
     "open_api": {
       "endpoint": "https://api.example.com",
       "spec_filepath": "./my-api-spec.json",
       "layered": true,
       "custom_routes": [...]
     }
   }
   ```

3. **Register the server**:
   ```python
   await composer.register_mcp_server(config)
   ```

4. **Use it with your AI agent**:
   The agent will automatically discover the three-layer interface and use it progressively.

---

## Conclusion

The Layered MCP Server Architecture transforms complex OpenAPI specifications into LLM-friendly, progressive discovery tools. By breaking down API interactions into three layers—discovery, planning, and execution—we guide AI agents through a clear workflow instead of overwhelming them with hundreds of individual tools.

This architecture is particularly powerful when combined with:
- **Custom routes filtering** for selective operation exposure
- **Automatic schema resolution** for better LLM understanding
- **Enhanced metadata** with examples and cleaned schemas

Whether you're working with a small API or a massive enterprise specification with hundreds of endpoints, the layered architecture provides a consistent, safe, and AI-friendly interface.

---

## References

- [Block's Layered Tool Pattern](https://engineering.block.xyz/blog/build-mcp-tools-like-ogres-with-layers)
- [MCP Composer Documentation](https://ibm.github.io/mcp-composer/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [OpenAPI Specification](https://swagger.io/specification/)

---

*Have you tried the layered architecture? Share your experiences and use cases in the comments below!*

