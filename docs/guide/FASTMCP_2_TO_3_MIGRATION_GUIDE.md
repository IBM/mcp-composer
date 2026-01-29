# FastMCP 2.x to 3.x Migration Guide

This guide documents the changes needed to migrate MCP Composer from FastMCP 2.x to FastMCP 3.x.

## Table of Contents

1. [Overview](#overview)
2. [Import Path Changes](#import-path-changes)
3. [API Changes](#api-changes)
4. [Tool Access Implementation Analysis](#tool-access-implementation-analysis)
5. [Breaking Changes](#breaking-changes)
6. [New Features](#new-features)
7. [Migration Checklist](#migration-checklist)
8. [Common Issues and Solutions](#common-issues-and-solutions)

---

## Overview

FastMCP 3.0 introduces several structural changes while maintaining backward compatibility where possible. The main changes include:

- **Reorganized module structure** - Some imports have moved to more logical locations
- **Enhanced tool system** - New `FunctionTool` class and `@tool` decorator
- **Improved resource management** - Better resource and template handling
- **Updated middleware system** - Enhanced middleware context and capabilities
- **New exception hierarchy** - More specific exception types

**Current Status**: The codebase is already using `fastmcp==3.0.0b1` (beta), so this guide documents what needs to be verified and potentially updated.

---

## Import Path Changes

### ✅ No Changes Required (Still Valid)

These imports remain the same and continue to work:

```python
# Core classes
from fastmcp import FastMCP, Client, Context
from fastmcp.tools.tool import Tool, ToolResult
from fastmcp.resources.resource import Resource
from fastmcp.resources.template import ResourceTemplate

# Server components
from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.server.openapi import MCPType, RouteMap
from fastmcp.server.openapi import FastMCPOpenAPI, OpenAPITool

# Client components
from fastmcp.client.auth import OAuth
from fastmcp.client.transports import (
    StreamableHttpTransport,
    SSETransport,
    StdioTransport,
)

# Utilities
from fastmcp.utilities.openapi import (
    clean_schema_for_display,
    extract_output_schema_from_responses,
    generate_example_from_schema,
    _combine_schemas,
    format_description_with_responses,
)

# Settings and exceptions
from fastmcp.settings import DuplicateBehavior
from fastmcp.exceptions import (
    ToolError,
    NotFoundError,
    McpError,
    FastMCPError,
    ValidationError,
    ResourceError,
    PromptError,
)

# Prompts
from fastmcp.prompts import PromptManager
from fastmcp.prompts.prompt import Prompt, PromptArgument

# Resources
from fastmcp.resources import ResourceManager, ResourceTemplate
```

### ⚠️ Alternative Import Paths (New Options)

FastMCP 3.0 provides alternative import paths through `__init__.py` files:

```python
# Alternative: Import from package root
from fastmcp.tools import Tool, ToolResult  # Instead of fastmcp.tools.tool
from fastmcp.resources import Resource, ResourceTemplate  # Instead of fastmcp.resources.resource
```

**Recommendation**: Keep using the explicit paths (`fastmcp.tools.tool`) for clarity, but the shorter paths are also valid.

---

## API Changes

### Tool Creation

#### ✅ `Tool.from_function()` - Still Works

```python
from fastmcp.tools.tool import Tool

# Still works as before
tool = Tool.from_function(my_function)
composer.add_tool(tool)
```

#### ✨ New: `FunctionTool` and `@tool` Decorator

FastMCP 3.0 introduces a new `FunctionTool` class and `@tool` decorator:

```python
from fastmcp.tools import FunctionTool, tool

# Option 1: Using the decorator
@tool
def my_tool(param: str) -> str:
    """Tool description"""
    return f"Result: {param}"

# Option 2: Using FunctionTool directly
def my_function(param: str) -> str:
    return f"Result: {param}"

tool = FunctionTool.from_function(my_function)
```

**Current Usage**: The codebase uses `Tool.from_function()` extensively, which continues to work. No changes required unless you want to adopt the new API.

### Resource Creation

#### ✅ `Resource.from_function()` - Still Works

```python
from fastmcp.resources.resource import Resource

# Still works as before
resource = Resource.from_function(
    get_agent_cards,
    uri="resource://agent_cards/list",
    mime_type="application/json",
)
composer.add_resource(resource)
```

#### ✅ `ResourceTemplate.from_function()` - Still Works

```python
from fastmcp.resources.template import ResourceTemplate

# Still works as before
template = ResourceTemplate.from_function(
    get_agent_card,
    uri_template="agent://agent_cards/{card_name}",
    mime_type="application/json",
    description="Retrieves a specific agent card by name.",
)
composer.add_template(template)
```

### Context Usage

#### ✅ `Context` - Still Works

```python
from fastmcp import Context

# Still works as before
def my_tool(context: Context) -> str:
    # Access context properties
    return f"Server: {context.server.name}"
```

### Tool Access Methods

#### ✅ `get_tools()` - Returns List (Not Dict)

According to the [FastMCP upgrade guide](https://gofastmcp.com/development/upgrade-guide), `get_tools()` exists and returns a **list** instead of a dict:

```python
# FastMCP 3.0
tools = await server.get_tools()  # Returns list[Tool], not dict[str, Tool]
tool = next((t for t in tools if t.name == "my_tool"), None)
```

**Note**: Type checkers may not recognize `get_tools()` (type stub issue), but it exists at runtime. Use `# pyright: ignore[reportAttributeAccessIssue]` if needed.

#### ✅ `list_tools()` - Also Available

FastMCP 3.0 also provides `list_tools()` which returns `Sequence[Tool]`:

```python
tools = await server.list_tools()  # Returns Sequence[Tool]
# Both get_tools() and list_tools() return lists/sequences
```

**Implementation Details** (from FastMCP 3.0 source):
- `list_tools()` applies visibility filtering, auth filtering, and middleware execution
- Returns all enabled tools with session transforms applied
- Filters out unauthorized tools based on component-level auth checks

#### ✅ `get_tool(name, version)` - Get Single Tool

FastMCP 3.0 provides `get_tool()` to retrieve a single tool by name:

```python
# Get a specific tool
tool = await server.get_tool("my_tool")
if tool:
    # Use the tool
    pass
```

**Implementation Details**:
- `get_tool(name, version=None)` - Public method with visibility filtering
- `_get_tool(name, version=None)` - Internal method with auth checks
- Both return `Tool | None`
- Applies session transforms and checks if tool is enabled

**Key Differences**:
- `get_tools()` / `list_tools()` - Get all tools as a list
- `get_tool(name)` - Get a single tool by name
- All methods respect visibility, auth, and session transforms

### Middleware

#### ✅ Middleware API - Still Works

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

class MyMiddleware(Middleware):
    async def __call__(
        self,
        context: MiddlewareContext,
        next: CallNext,
    ) -> Any:
        # Pre-processing
        result = await next(context)
        # Post-processing
        return result
```

---

## Tool Access Implementation Analysis

### FastMCP 3.0 Tool Access Architecture

Based on analysis of the FastMCP 3.0 source code (`server.py`), here's how tool access works:

#### 1. `list_tools()` - List All Tools

**Signature**: `async def list_tools(self, *, run_middleware: bool = True) -> Sequence[Tool]`

**Implementation Flow**:
1. Creates a `Context` for the request
2. Runs middleware if `run_middleware=True` (default)
3. Gets all tools from parent provider via `super().list_tools()`
4. Applies session transforms (`apply_session_transforms`)
5. Filters enabled tools (`is_enabled(t)`)
6. Applies component-level auth checks
7. Returns list of authorized, enabled tools

**Key Features**:
- Respects visibility filtering (session transforms can disable tools)
- Applies auth checks per tool
- Runs middleware chain
- Returns `Sequence[Tool]` (list-like)

#### 2. `get_tool(name, version)` - Get Single Tool

**Signature**: `async def get_tool(self, name: str, version: VersionSpec | None = None) -> Tool | None`

**Implementation Flow**:
1. Gets tool from parent provider via `super().get_tool(name, version)`
2. Returns `None` if tool not found
3. Applies session transforms to the single tool
4. Checks if tool is enabled (`is_enabled`)
5. Returns `None` if disabled, otherwise returns the tool

**Key Features**:
- Single tool lookup by name
- Supports version filtering
- Applies session transforms (can override provider-level disables)
- Returns `Tool | None`

#### 3. `_get_tool(name, version)` - Internal Method with Auth

**Signature**: `async def _get_tool(self, name: str, version: VersionSpec | None = None) -> Tool | None`

**Implementation Flow**:
1. Gets tool from `AggregateProvider` (handles aggregation and namespacing)
2. Returns `None` if tool not found
3. **Component-level auth check**:
   - Gets auth context (token, skip_auth flag)
   - If tool has `auth` defined and auth is not skipped:
     - Creates `AuthContext` with token and tool
     - Runs auth checks via `run_auth_checks(tool.auth, ctx)`
     - Returns `None` if unauthorized
4. Returns tool if authorized

**Key Features**:
- Internal method (prefixed with `_`)
- Includes component-level authorization
- Handles namespacing (for mounted servers)
- Returns `None` for unauthorized tools (consistent with `list_tools` filtering)

#### 4. `get_tools()` - Compatibility Method

**Status**: According to [FastMCP upgrade guide](https://gofastmcp.com/development/upgrade-guide), `get_tools()` exists and returns a list.

**Note**: Runtime inspection confirms `get_tools()` exists, but type stubs may not include it. Use `# pyright: ignore[reportAttributeAccessIssue]` if type checker complains.

**Usage**:
```python
# Both work and return lists
tools_list = await server.get_tools()  # May need type ignore
tools_list = await server.list_tools()  # Type-safe alternative
```

### Summary of Tool Access Methods

| Method | Returns | Auth Check | Visibility Filter | Middleware | Use Case |
|--------|---------|------------|-------------------|------------|----------|
| `list_tools()` | `Sequence[Tool]` | ✅ Yes | ✅ Yes | ✅ Yes | Get all tools |
| `get_tools()` | `list[Tool]` | ✅ Yes | ✅ Yes | ✅ Yes | Get all tools (compatibility) |
| `get_tool(name)` | `Tool \| None` | ❌ No | ✅ Yes | ❌ No | Get single tool |
| `_get_tool(name)` | `Tool \| None` | ✅ Yes | ❌ No | ❌ No | Internal, with auth |

**Recommendation**: Use `list_tools()` for getting all tools (type-safe) or `get_tool(name)` for single tool lookup.

---

## Breaking Changes

### 1. ⚠️ Missing Manager Classes

**Issue**: Several manager classes are referenced but don't exist as standalone classes in FastMCP 3.0.

**Locations**:
- `modules/mcp_composer/src/mcp_composer/core/tools/tool_manager.py:40` - `MCPToolManager(ToolManager)`
- `modules/mcp_composer/src/mcp_composer/core/prompts/prompt_manager.py:18` - `MCPPromptManager(PromptManager)`
- `modules/mcp_composer/src/mcp_composer/core/resources/resource_manager.py:17` - `MCPResourceManager(ResourceManager)`

**Current Code**:
```python
# tool_manager.py
from fastmcp.tools.tool import Tool  # ToolManager NOT imported!
class MCPToolManager(ToolManager):  # ❌ ToolManager doesn't exist

# prompt_manager.py  
from fastmcp.prompts import PromptManager  # ⚠️ May not exist
class MCPPromptManager(PromptManager):  # ⚠️ Verify import works

# resource_manager.py
from fastmcp.resources import ResourceManager  # ⚠️ May not exist
class MCPResourceManager(ResourceManager):  # ⚠️ Verify import works
```

**Status**: 
- `ToolManager` - **DOES NOT EXIST** in FastMCP 3.0 (confirmed)
- `PromptManager` - **NOT FOUND** in FastMCP 3.0 exports (needs verification)
- `ResourceManager` - **NOT FOUND** in FastMCP 3.0 exports (needs verification)

**Analysis**: FastMCP 3.0 likely manages tools, prompts, and resources directly through the `FastMCP` server instance rather than through separate manager classes.

**Solution Options**:

**Option A**: Remove inheritance and implement managers directly:
```python
# tool_manager.py
class MCPToolManager:  # No inheritance
    """Manages member servers tools."""
    
    def __init__(
        self,
        composer: MCPComposer,
        server_manager: ServerManager,
        duplicate_behavior: DuplicateBehavior | None = None,
        database: Optional[DatabaseInterface] = None,
    ):
        # Initialize without super()
        self._composer = composer
        self._server_manager = server_manager
        self._database = database
        self._disabled_tools: list[str] = []
        # Implement required methods directly
```

**Option B**: Access managers through FastMCP server instance:
```python
# If FastMCP has internal managers, access them via:
# composer._tool_manager
# composer._prompt_manager  
# composer._resource_manager
```

**Action Required**: ⚠️ **CRITICAL** - These need to be fixed:
1. **ToolManager** - Definitely doesn't exist, must fix
2. **PromptManager** - Verify if import works at runtime
3. **ResourceManager** - Verify if import works at runtime

### 2. ⚠️ Server Proxy API

**Location**: `modules/mcp_composer/src/mcp_composer/core/member_servers/builder.py`

**Current Code**:
```python
from fastmcp.server.proxy import ProxyClient  # Used in cli_typer.py
```

**Status**: Need to verify if `ProxyClient` still exists in FastMCP 3.0.

**Action Required**: Verify import path or find alternative.

### 3. ⚠️ OpenAPI Integration

**Location**: `modules/mcp_composer/src/mcp_composer/core/utils/patch_openapi_tool.py`

**Current Code**:
```python
from fastmcp.server.openapi import FastMCPOpenAPI, OpenAPITool
```

**Status**: These classes exist in FastMCP 3.0, but verify:
- `FastMCPOpenAPI._create_openapi_tool` method signature
- `OpenAPITool` constructor parameters
- Internal attributes like `_client`, `_director`, `_tool_manager`, `_timeout`, `_mcp_component_fn`

**Action Required**: Test the patching mechanism works with FastMCP 3.0.

---

## New Features

### 1. ✨ Enhanced Tool System

FastMCP 3.0 introduces:
- `FunctionTool` class with enhanced metadata support
- `@tool` decorator for easier tool creation
- Better type hints and validation
- Task execution support (SEP-1686)

**Migration**: Optional - can adopt gradually.

### 2. ✨ Improved Error Handling

New exception types:
- `AuthorizationError` - For auth failures
- More specific error types for better debugging

**Migration**: Optional - can catch more specific exceptions.

### 3. ✨ Enhanced Settings

New settings in `fastmcp.settings`:
- Better logging configuration
- Deprecation warnings control
- Docket task queue configuration

**Migration**: Optional - can configure as needed.

---

## Migration Checklist

### Phase 1: Critical Fixes

- [ ] **Fix `ToolManager` inheritance issue**
  - [ ] ✅ **CONFIRMED**: `ToolManager` does NOT exist in FastMCP 3.0
  - [ ] Refactor `MCPToolManager` to not inherit from `ToolManager`
  - [ ] Implement required methods directly in `MCPToolManager`
  - [ ] Test tool management functionality

- [ ] **Verify `PromptManager` import**
  - [ ] Test if `from fastmcp.prompts import PromptManager` works at runtime
  - [ ] If import fails, refactor `MCPPromptManager` to not inherit
  - [ ] If import works, verify API compatibility
  - [ ] Test prompt management functionality

- [ ] **Verify `ResourceManager` import**
  - [ ] Test if `from fastmcp.resources import ResourceManager` works at runtime
  - [ ] If import fails, refactor `MCPResourceManager` to not inherit
  - [ ] If import works, verify API compatibility
  - [ ] Test resource management functionality

- [ ] **Verify `ProxyClient` import**
  - [ ] Check if `fastmcp.server.proxy.ProxyClient` exists
  - [ ] Update import if path changed
  - [ ] Test proxy functionality

- [ ] **Test OpenAPI patching**
  - [ ] Verify `FastMCPOpenAPI` API compatibility
  - [ ] Test `_create_openapi_tool` patching
  - [ ] Verify OpenAPI tool creation works

### Phase 2: Verification

- [ ] **Run test suite**
  - [ ] All unit tests pass
  - [ ] All integration tests pass
  - [ ] Fix any test failures

- [ ] **Verify core functionality**
  - [ ] Server creation and mounting
  - [ ] Tool registration and execution
  - [ ] Resource management
  - [ ] Prompt management
  - [ ] Middleware execution
  - [ ] Authentication flows

- [ ] **Check imports**
  - [ ] All imports resolve correctly
  - [ ] No deprecated warnings (unless expected)
  - [ ] Type hints work correctly

### Phase 3: Optional Enhancements

- [ ] **Adopt new APIs** (if desired)
  - [ ] Consider using `@tool` decorator for new tools
  - [ ] Consider using `FunctionTool` for better type safety
  - [ ] Update error handling to use new exception types

- [ ] **Update documentation**
  - [ ] Update code examples
  - [ ] Document any new patterns
  - [ ] Update README if needed

---

## Common Issues and Solutions

### Issue 1: `ToolManager` Not Found

**Error**: `NameError: name 'ToolManager' is not defined`

**Solution**: 
1. Check if `ToolManager` exists: `grep -r "class ToolManager" fastmcp/`
2. If it doesn't exist, refactor `MCPToolManager` to not inherit from it
3. Implement required methods directly in `MCPToolManager`

### Issue 1a: `get_tools()` Type Checker Error

**Error**: `Cannot access attribute "get_tools" for class "FastMCP[Any]" - Attribute "get_tools" is unknown`

**Solution**:
1. `get_tools()` exists at runtime (confirmed via runtime inspection)
2. According to [FastMCP upgrade guide](https://gofastmcp.com/development/upgrade-guide), `get_tools()` returns a list
3. Type stubs may be incomplete - add type ignore comment:
   ```python
   tools = await server.get_tools()  # pyright: ignore[reportAttributeAccessIssue]
   ```
4. Alternative: Use `list_tools()` which is type-safe and functionally equivalent

### Issue 2: Import Errors

**Error**: `ImportError: cannot import name 'X' from 'fastmcp.Y'`

**Solution**:
1. Check FastMCP 3.0 source code for correct import path
2. Use `fastmcp/__init__.py` to see what's exported
3. Check if the class/function was renamed or moved

### Issue 3: API Signature Changes

**Error**: `TypeError: X() takes Y positional arguments but Z were given`

**Solution**:
1. Check FastMCP 3.0 documentation or source code
2. Update function calls to match new signatures
3. Use type hints to catch issues early

### Issue 4: Deprecated Warnings

**Warning**: `DeprecationWarning: X is deprecated, use Y instead`

**Solution**:
1. Update code to use new API
2. Or suppress warnings if migration is deferred:
   ```python
   import warnings
   warnings.filterwarnings("ignore", category=DeprecationWarning)
   ```

---

## File-by-File Migration Notes

### Files Requiring Attention

1. **`core/tools/tool_manager.py`**
   - ⚠️ Missing `ToolManager` import/inheritance
   - Verify tool management methods work without base class

2. **`core/utils/patch_openapi_tool.py`**
   - ⚠️ Patches internal FastMCP API
   - Verify patching still works with FastMCP 3.0
   - May need updates if internal API changed

3. **`core/member_servers/builder.py`**
   - Uses `FastMCP.as_proxy()` - verify API
   - Uses `FastMCP.from_openapi()` - verify API
   - Uses client transports - verify compatibility

4. **`core/composer.py`**
   - Extends `FastMCP` - verify constructor signature
   - Uses `Tool.from_function()` - ✅ Still works
   - Uses `Resource.from_function()` - ✅ Still works
   - Uses `ResourceTemplate.from_function()` - ✅ Still works

5. **`core/prompts/prompt_manager.py`**
   - Extends `PromptManager` - verify it exists
   - Uses `Prompt` class - verify API

6. **`core/resources/resource_manager.py`**
   - Extends `ResourceManager` - verify it exists
   - Uses `Resource` and `ResourceTemplate` - ✅ Still works

7. **`a2a_service/a2a_mcp.py`**
   - Uses `Context` - ✅ Still works

8. **Middleware files**
   - Use `Middleware`, `MiddlewareContext`, `CallNext` - ✅ Still works
   - Use `ToolError` exception - ✅ Still works

---

## Testing Strategy

### Unit Tests

Run all unit tests to verify core functionality:

```bash
pytest modules/mcp_composer/tests/unit/
```

### Integration Tests

Run integration tests to verify end-to-end functionality:

```bash
pytest modules/mcp_composer/tests/e2e/
```

### Manual Testing

1. **Start the server**:
   ```bash
   python -m mcp_composer.core.cli.cli_main
   ```

2. **Test tool registration**:
   - Register a tool
   - Execute the tool
   - Verify results

3. **Test server mounting**:
   - Mount a member server
   - Verify tools are available
   - Test tool execution

4. **Test resources**:
   - Create a resource
   - List resources
   - Access resources

5. **Test prompts**:
   - Add prompts
   - List prompts
   - Get prompts

---

## Additional Resources

- FastMCP 3.0 Documentation: Check the FastMCP repository for latest docs
- FastMCP 3.0 Source: `/modules/mcp_composer/.venv/lib/python3.12/site-packages/fastmcp/`
- MCP Composer Source: `/modules/mcp_composer/src/mcp_composer/`

---

## Summary

### ✅ What Works Without Changes

- Core imports (`FastMCP`, `Client`, `Context`)
- Tool creation (`Tool.from_function()`)
- Resource creation (`Resource.from_function()`, `ResourceTemplate.from_function()`)
- Middleware system
- Exception handling
- Settings (`DuplicateBehavior`)
- Server mounting and composition

### ⚠️ What Needs Attention

1. **CRITICAL**: `ToolManager` inheritance in `MCPToolManager`
2. **VERIFY**: `ProxyClient` import path
3. **VERIFY**: OpenAPI patching mechanism
4. **TEST**: All functionality end-to-end

### ✨ Optional Enhancements

- Adopt `@tool` decorator for new tools
- Use `FunctionTool` for better type safety
- Update error handling to use new exception types
- Configure new settings as needed

---

**Last Updated**: Based on FastMCP 3.0.0b1 analysis
**Status**: Migration guide created - ready for implementation
