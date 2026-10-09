# Middleware Configuration Guide

This document explains how to configure and use middleware in MCP Composer through JSON configuration files. The system provides a declarative way to define, configure, and manage middleware without writing Python code.

## Overview

MCP Composer uses a **MiddlewareManager** that reads JSON configuration files to automatically instantiate, configure, and attach middleware to your MCP server. This approach provides several benefits:

- **Declarative Configuration**: Define middleware behavior in JSON instead of code
- **Dynamic Loading**: Add/remove middleware without restarting the application
- **Priority Control**: Control the execution order of middleware
- **Conditional Application**: Apply middleware only to specific tools or operations
- **Environment-Specific Configs**: Use different configs for development, staging, production

## Configuration File Structure

The middleware configuration is defined in a JSON file with the following structure:

```json
{
  "middleware": [
    {
      "name": "MiddlewareName",
      "kind": "module.path.ClassName",
      "mode": "enabled",
      "priority": 100,
      "applied_hooks": ["on_call_tool"],
      "conditions": { "include_tools": ["*"], "exclude_tools": [] },
      "config": { /* middleware-specific configuration */ }
    }
  ],
  "middleware_settings": {
    "middleware_timeout": 30,
    "fail_on_middleware_error": false,
    "enable_middleware_api": true,
    "middleware_health_check_interval": 60
  }
}
```

## Configuration Fields Explained

### Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier for the middleware |
| `kind` | string | Yes | Python import path to the middleware class |
| `mode` | enum | No | `"enabled"` or `"disabled"` (default: `"enabled"`) |
| `priority` | integer | No | Execution order (lower numbers run first, default: 100) |
| `applied_hooks` | array | Yes | List of FastMCP hooks to apply middleware to |
| `conditions` | object | No | Tool/prompt filtering conditions |
| `config` | object | No | Middleware-specific configuration parameters |

### Applied Hooks

The `applied_hooks` field specifies which FastMCP lifecycle events the middleware should intercept:

- `on_request` - Intercept all MCP requests
- `on_message` - Intercept MCP messages
- `on_list_tools` - Intercept tool listing requests
- `on_list_resources` - Intercept resource listing requests
- `on_read_resource` - Intercept resource read requests
- `on_list_prompts` - Intercept prompt listing requests
- `on_call_tool` - Intercept tool execution requests

### Conditions

The `conditions` field allows you to selectively apply middleware:

```json
"conditions": {
  "include_tools": ["*"],           // Apply to all tools (wildcard)
  "exclude_tools": ["admin_tool"],  // Exclude specific tools
  "include_prompts": ["*"],         // Apply to all prompts
  "exclude_prompts": ["secret_prompt"], // Exclude specific prompts
  "include_server_ids": ["*"],      // Apply to all servers
  "exclude_server_ids": ["legacy"]  // Exclude specific servers
}
```

### Priority System

Middleware are executed in priority order:
- **Lower priority numbers execute first** (e.g., priority 10 runs before priority 100)
- **Recommended ranges**:
  - 1-50: Security middleware (PII filtering, authentication)
  - 51-100: Business logic middleware (rate limiting, validation)
  - 101-200: Observability middleware (logging, metrics)
  - 201+: Utility middleware (formatting, transformation)

## Example Configuration

Here's a complete example from `config/middleware-config.json`:

```json
{
  "middleware": [
    {
      "name": "RateLimiter",
      "kind": "mcp_composer.middleware.rate_limit_filter.RateLimitingMiddleware",
      "mode": "enabled",
      "priority": 20,
      "applied_hooks": ["on_call_tool"],
      "conditions": { "include_tools": ["*"], "exclude_tools": [] },
      "config": {
        "requests_per_minute": 120,
        "burst_limit": 20,
        "scope": "per_client",
        "enforce": true,
        "client_id_field": "client_id"
      }
    },
    {
      "name": "Logger",
      "kind": "mcp_composer.middleware.logging_middleware.LoggingMiddleware",
      "mode": "enabled",
      "priority": 100,
      "applied_hooks": ["on_call_tool","on_list_tools","on_read_resource","on_list_prompts"],
      "conditions": { "include_tools": ["*"], "exclude_tools": [] },
      "config": {
        "log_tools": true,
        "log_resources": false,
        "log_prompts": false,
        "log_args": true,
        "log_results": true,
        "max_payload_length": 800,
        "log_level": "INFO"
      }
    },
    {
      "name": "PIIFilter",
      "kind": "mcp_composer.middleware.pii_middleware.SecretsAndPIIMiddleware",
      "mode": "enabled",
      "priority": 10,
      "applied_hooks": ["on_call_tool","on_read_resource","on_list_prompts"],
      "conditions": { "include_tools": ["get_data"], "exclude_tools": ["get_prompts"] },
      "config": {
        "redact_inputs": true,
        "redact_outputs": true,
        "replace_inputs": false,
        "allowlist_tools": [],
        "allowlist_fields": [],
        "strategy": { "mode": "mask", "redaction_text": "[PII_REDACTED]" },
        "sensitive_keys": { "add": ["x-auth-token"], "remove": [] },
        "patterns": {
          "add": [
            { "tag": "SLACK_BOT", "regex": "xoxb-[A-Za-z0-9-]{20,}", "flags": [] }
          ],
          "remove": []
        }
      }
    }
  ],
  "middleware_settings": {
    "middleware_timeout": 30,
    "fail_on_middleware_error": false,
    "enable_middleware_api": true,
    "middleware_health_check_interval": 60
  }
}
```

## Using MiddlewareManager

### Command Line Interface (CLI)

MCP Composer provides powerful CLI commands for managing middleware configurations:

#### Validate Configuration

```bash
# Basic validation
mcp-composer validate middleware-config.json

# Validate with import checking
mcp-composer validate middleware-config.json --ensure-imports

# Show execution order after validation
mcp-composer validate middleware-config.json --show-middlewares

# Output in JSON format
mcp-composer validate middleware-config.json --format json
```

#### List Middleware

```bash
# List enabled middleware
mcp-composer list middleware-config.json

# List all middleware (including disabled)
mcp-composer list middleware-config.json --all

# Output in JSON format
mcp-composer list middleware-config.json --format json
```

#### Add/Update Middleware

```bash
# Add new middleware
mcp-composer add-middleware \
  --config middleware-config.json \
  --name CircuitBreaker \
  --kind mcp_composer.middleware.circuit_breaker.CircuitBreakerMiddleware \
  --priority 30 \
  --applied-hooks on_call_tool \
  --description "Circuit breaker for tool calls"

# Update existing middleware
mcp-composer add-middleware \
  --config middleware-config.json \
  --name Logger \
  --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware \
  --priority 50 \
  --update

# Dry run (show what would be written)
mcp-composer add-middleware \
  --config middleware-config.json \
  --name TestMiddleware \
  --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware \
  --dry-run
```

### Programmatic Usage

#### Basic Usage

```python
from mcp_composer.core.middleware.middleware_manager import MiddlewareManager

# Load and build middleware from config
mgr = MiddlewareManager("/path/to/middleware-config.json", ensure_imports=True)

# Attach to your MCP server
mgr.attach_to_server(your_mcp_server)

# Optional: inspect what was attached
for info in mgr.describe():
    print(f"[middleware] {info['name']} priority={info['priority']} hooks={info['applied_hooks']}")
```

### Complete Working Example

Here's a complete working example from `test_composer_middleware.py` that demonstrates how to use middleware configuration in a real MCP Composer application:

```python
import os
import sys
import asyncio
from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.middleware.middleware_manager import MiddlewareManager
from mcp_composer.middleware import SecretsAndPIIMiddleware, PromptInjectionMiddleware
import json

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# Create MCP Composer instance
gw = MCPComposer("hello-composer")

# Define a tool that returns sensitive data
@gw.tool()
def get_data():
    form_data = {
        "name": "Alice Example",
        "email": "alice@example.com",
        "password": "SuperSecret123!",
        "credit_card": "4111 1111 1111 1111",
        "note": "Please call me at +1-202-555-0123",
        "public_info": "This is fine to show",
    }
    return form_data

async def main():
    """Main function demonstrating middleware configuration"""
    mode = os.getenv("MCP_MODE", "http").lower()

    # Setup member servers
    await gw.setup_member_servers()

    # Option 1: Add middleware programmatically (commented out)
    # gw.add_middleware(
    #     SecretsAndPIIMiddleware(
    #         strategy=RedactionStrategy(mode="mask"),
    #         allowlist_tools=[],
    #         allowlist_fields=["public_info"],
    #         redact_inputs=True,
    #         redact_outputs=True,
    #     )
    # )

    # Option 2: Add middleware programmatically (active)
    gw.add_middleware(
        PromptInjectionMiddleware(
            block_on_high_risk=True,
            threshold=0.75,
            url_allowlist=["https://safe.example.com/"],
            sanitize_on_medium=True,
            inspect_fields=["query"],
        )
    )

    # Option 3: Load middleware from JSON configuration file
    mgr = MiddlewareManager(
        "/Users/mansurah/GitHub/mcp-composer/config/middleware-config.json", 
        ensure_imports=True
    )
    
    # Attach all middleware from config to the server
    mgr.attach_to_server(gw)
    
    # Print what middleware was attached and in what order
    for info in mgr.describe():
        print(f"[middleware] {info['name']} priority={info['priority']} hooks={info['applied_hooks']}")

    # Run the server based on environment variable
    if mode == "http":
        await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")
    elif mode == "stdio":
        await gw.run_stdio_async()
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")

if __name__ == "__main__":
    asyncio.run(main())
```

### What This Example Demonstrates

1. **Multiple Middleware Addition Methods**:
   - **Programmatic**: Adding middleware directly in code
   - **JSON Configuration**: Loading middleware from configuration files
   - **Hybrid Approach**: Combining both methods

2. **Environment-Based Configuration**:
   - Uses `MCP_MODE` environment variable to determine server mode
   - Supports HTTP and stdio modes

3. **Middleware Inspection**:
   - Uses `mgr.describe()` to see what middleware was loaded
   - Shows priority order and applied hooks

4. **Real-World Tool Definition**:
   - Defines a `get_data()` tool that returns sensitive information
   - Perfect for testing PII filtering middleware

### Running the Example

```bash
# Run in HTTP mode (default)
python example/middlewares/test_composer_middleware.py

# Run in stdio mode
MCP_MODE=stdio python example/middlewares/test_composer_middleware.py

# Run in HTTP mode
MCP_MODE=http python example/middlewares/test_composer_middleware.py
```

### Expected Output

When you run this example, you should see output like:

```
[middleware] PIIFilter priority=10 hooks=['on_call_tool', 'on_read_resource', 'on_list_prompts']
[middleware] RateLimiter priority=20 hooks=['on_call_tool']
[middleware] Logger priority=100 hooks=['on_call_tool', 'on_list_tools', 'on_read_resource', 'on_list_prompts']
```

This shows the middleware loaded from your JSON configuration file, ordered by priority.

## Middleware-Specific Configuration

### PII/Secrets Middleware

```json
{
  "name": "PIIFilter",
  "kind": "mcp_composer.middleware.pii_middleware.SecretsAndPIIMiddleware",
  "priority": 10,
  "applied_hooks": ["on_call_tool", "on_read_resource"],
  "config": {
    "redact_inputs": true,
    "redact_outputs": true,
    "strategy": {
      "mode": "mask",           // "mask", "hash", or "tokenize"
      "redaction_text": "[REDACTED]",
      "salt": "optional_salt_for_hashing"
    },
    "sensitive_keys": {
      "add": ["custom_key", "secret_field"],
      "remove": ["password"]
    },
    "patterns": {
      "add": [
        {
          "tag": "CUSTOM_PATTERN",
          "regex": "\\b\\d{4}-\\d{4}-\\d{4}-\\d{4}\\b",
          "flags": ["IGNORECASE"]
        }
      ],
      "remove": ["PHONE", "IBAN"]
    }
  }
}
```

### Rate Limiting Middleware

```json
{
  "name": "RateLimiter",
  "kind": "mcp_composer.middleware.rate_limit_filter.RateLimitingMiddleware",
  "priority": 20,
  "applied_hooks": ["on_call_tool"],
  "config": {
    "requests_per_minute": 120,
    "burst_limit": 20,
    "scope": "per_client",      // "per_client", "per_tool", or "global"
    "enforce": true,            // true = raise error, false = log warning
    "client_id_field": "client_id"
  }
}
```

### Circuit Breaker Middleware

```json
{
  "name": "CircuitBreaker",
  "kind": "mcp_composer.middleware.circuit_breaker.CircuitBreakerMiddleware",
  "priority": 30,
  "applied_hooks": ["on_call_tool"],
  "config": {
    "failure_threshold": 5,
    "open_timeout": 30.0,
    "window_seconds": 60.0,
    "exempt_tools": ["health_check"]
  }
}
```

### Logging Middleware

```json
{
  "name": "Logger",
  "kind": "mcp_composer.middleware.logging_middleware.LoggingMiddleware",
  "priority": 100,
  "applied_hooks": ["on_call_tool", "on_list_tools"],
  "config": {
    "log_tools": true,
    "log_resources": false,
    "log_prompts": false,
    "log_args": true,
    "log_results": true,
    "max_payload_length": 800,
    "log_level": "INFO"
  }
}
```

### Prompt Injection Middleware

```json
{
  "name": "PromptInjectionGuard",
  "kind": "mcp_composer.middleware.prompt_injection.PromptInjectionMiddleware",
  "priority": 5,
  "applied_hooks": ["on_call_tool", "on_list_prompts"],
  "config": {
    "threshold": 0.75,
    "block_on_high_risk": true,
    "sanitize_on_medium": true,
    "url_allowlist": ["https://safe.example.com/"],
    "inspect_fields": ["query", "prompt"]
  }
}
```

## Advanced Features

### Conditional Logic

You can apply middleware only under specific conditions:

```json
{
  "name": "AdminOnlyLogger",
  "kind": "mcp_composer.middleware.logging_middleware.LoggingMiddleware",
  "priority": 50,
  "applied_hooks": ["on_call_tool"],
  "conditions": {
    "include_tools": ["admin_*"],  // Only admin tools
    "exclude_tools": ["admin_health"]
  },
  "config": {
    "log_tools": true,
    "log_args": true,
    "log_results": true
  }
}
```

### Dynamic Configuration

The `ensure_imports=True` parameter validates that all middleware classes can be imported:

```python
# This will fail fast if middleware classes can't be imported
mgr = MiddlewareManager("/path/to/config.json", ensure_imports=True)
```

### Error Handling

Configure how the system handles middleware errors:

```json
{
  "middleware_settings": {
    "fail_on_middleware_error": false,  // Continue if middleware fails
    "middleware_timeout": 30,           // Timeout for middleware execution
    "enable_middleware_api": true       // Enable middleware management API
  }
}
```

## Best Practices

### 1. **Security First**
- Place security middleware (PII filtering, authentication) at high priority (1-50)
- Use specific tool inclusion/exclusion for sensitive operations

### 2. **Performance Considerations**
- Rate limiting should be early in the chain (priority 20-30)
- Logging should be late in the chain (priority 100+)
- Avoid expensive operations in high-priority middleware

### 3. **Configuration Management**
- Use environment-specific config files
- Validate configurations with `ensure_imports=True`
- Use descriptive names for middleware

### 4. **Monitoring and Debugging**
- Enable middleware API for runtime inspection
- Use logging middleware to track middleware execution
- Set appropriate timeouts for your use case

### 5. **Testing**
- Test middleware configurations in isolation
- Use the `describe()` method to verify middleware attachment
- Test both success and failure scenarios

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `kind` paths are correct and modules are importable
2. **Priority Conflicts**: Check that middleware priorities make logical sense
3. **Hook Mismatches**: Verify that `applied_hooks` match the middleware's capabilities
4. **Configuration Errors**: Validate JSON syntax and required fields

### Debug Commands

#### CLI Debugging

```bash
# Validate configuration with detailed output
mcp-composer validate middleware-config.json --ensure-imports --show-middlewares

# List all middleware with status
mcp-composer list middleware-config.json --all --format json

# Test middleware addition with dry-run
mcp-composer add-middleware \
  --config middleware-config.json \
  --name TestMiddleware \
  --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware \
  --dry-run
```

#### Programmatic Debugging

```python
# Check what middleware was loaded
for info in mgr.describe():
    print(f"{info['name']}: {info['attached']}")

# Verify configuration loading
config = mgr.load("/path/to/config.json")
print(f"Loaded {len(config.middleware)} middleware entries")

# Check for import issues
mgr.load("/path/to/config.json", ensure_imports=True)
```

### CLI Error Examples

#### File Not Found
```bash
$ mcp-composer validate missing-config.json
ERROR: File not found: missing-config.json
```

#### Invalid JSON
```bash
$ mcp-composer validate invalid-config.json
ERROR: Invalid JSON in invalid-config.json: Expecting ',' delimiter
```

#### Import Errors
```bash
$ mcp-composer validate config.json --ensure-imports
ERROR: Import check failed: No module named 'nonexistent_module'
```

#### Validation Errors
```bash
$ mcp-composer validate invalid-config.json
ERROR: Config validation failed:
  01. middleware.0.priority [value_error] - Input should be greater than or equal to 0
  02. middleware.0.applied_hooks [value_error] - applied_hooks cannot be empty
```

## Conclusion

The JSON-based middleware configuration system provides a powerful, flexible way to manage middleware in MCP Composer. By separating configuration from code, you can:

- **Easily modify middleware behavior** without code changes
- **Share configurations** across different environments
- **Dynamically adjust** middleware based on operational needs
- **Maintain consistency** across different MCP server instances

This approach makes it easy to implement security, observability, and operational middleware while keeping your application code clean and focused on business logic.
