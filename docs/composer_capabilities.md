# MCPComposer Capabilities and Features

## Overview

`composer.py` defines the `MCPComposer` class, which is the core orchestrator for the MCP system. It extends `FastMCP` to provide dynamic runtime composition, tool management, database-backed configuration, and prompt management. This document explains its main features, how it works, and how to use or extend it.

---

## Key Features

### 1. Dynamic Server Orchestration
- **Mounts and manages multiple member MCP servers** at runtime.
- Supports different server types (OpenAPI, GraphQL, HTTP, SSE, stdio, local, etc.).
- Can load server configurations from files, databases, or at launch.
- Handles activation, deactivation, and removal of member servers.

### 2. Tool Management
- **Registers tools** from member servers and exposes them via API endpoints.
- Supports dynamic tool creation from Python scripts, OpenAPI specs, or GraphQL schemas.
- Centralizes tool management (enable/disable, update description, fetch config by name/server).
- Tools are discoverable and callable via the FastAPI app.

### 3. Configuration Validation
- Validates all server configs at startup or registration using `AllServersValidator` and `ServerConfigValidator`.
- Ensures required fields and correct types for each server type (OpenAPI, GraphQL, etc.).
- Prevents invalid or incomplete configs from being loaded.

### 4. Prompt Management
- Supports adding, listing, and managing prompts for LLM or workflow use.
- Prompts can be loaded from config, files, or added at runtime.
- Exposes prompt management as tools/endpoints.

### 5. Database-Backed State
- Can use local file storage or a database (e.g., Cloudant) for persistent config and server state.
- Supports versioning and rollback of server configs.

### 6. Health and Monitoring
- Aggregates health status of all member servers.
- Exposes health endpoints and tools for monitoring.

---

## How MCPComposer Works

- On startup, loads server configs from file/database and validates them.
- Mounts each member server, registering its tools and prompts.
- Registers management tools (register, update, delete, activate, deactivate servers; tool management; prompt management).
- Exposes all tools and management endpoints via FastAPI.
- Supports dynamic addition/removal of servers and tools at runtime.

---

## Extending MCPComposer

- **Add new server types:** Implement a new builder in `member_servers/builder.py` and update config validation.
- **Add new tool sources:** Extend tool loading logic in `tools/tool_manager.py` or `utils/tools.py`.
- **Customize prompt handling:** Extend prompt management methods or add new prompt sources.
- **Integrate new databases:** Implement a new adapter in `store/` and pass it as `database_config`.

---

## Example Usage

```python
from mcp_composer.composer import MCPComposer

# Load from config file
composer = MCPComposer(config=[...])
await composer.setup_member_servers()

# Register a new server at runtime
await composer.register_mcp_server({...})

# Add a new tool dynamically
await composer.add_tools({...})

# List all available tools
all_tools = await composer._tool_manager.get_all_tools()

# Add a prompt
await composer.add_prompts([...])
```

---

## References
- See also: [test/README.md](../test/README.md) for testing philosophy and E2E coverage.
- For more on config structure, see example configs in `example/`.
- For tool and prompt APIs, see the FastAPI OpenAPI docs when the app is running. 