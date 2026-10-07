# Middleware Guide

Middleware in MCP Composer provides a powerful way to intercept, modify, and enhance tool calls, resource operations, and other MCP interactions. This guide covers how to create custom middleware and describes the available built-in middleware components.

## Overview

Middleware follows a chain-of-responsibility pattern where each middleware can:
- Process requests before they reach the target handler
- Modify responses after they're generated
- Add cross-cutting concerns like logging, authentication, rate limiting, etc.
- Handle errors and exceptions

## Creating Custom Middleware

### Basic Middleware Structure

All middleware must inherit from the `Middleware` base class and implement the appropriate hook methods:

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from typing import Any

class MyCustomMiddleware(Middleware):
    def __init__(self, config_param: str = "default"):
        super().__init__()
        self.config_param = config_param
    
    async def on_call_tool(
        self, 
        context: MiddlewareContext, 
        call_next: CallNext
    ) -> Any:
        # Pre-processing logic
        print(f"Before calling tool: {context.message.name}")
        
        # Call the next middleware or handler
        result = await call_next(context)
        
        # Post-processing logic
        print(f"After calling tool: {context.message.name}")
        
        return result
```

### Available Hook Methods

Middleware can implement these hook methods:

#### `on_call_tool(context, call_next)`
Called before and after tool execution.

```python
async def on_call_tool(self, context, call_next):
    # Pre-processing
    tool_name = getattr(context.message, "name", "<unknown>")
    arguments = getattr(context.message, "arguments", {})
    
    # Modify arguments if needed
    # context.message.arguments = modified_arguments
    
    # Call next middleware/handler
    result = await call_next(context)
    
    # Post-processing
    # Modify result if needed
    
    return result
```

#### `on_list_tools(context, call_next)`
Called when listing available tools.

```python
async def on_list_tools(self, context, call_next):
    result = await call_next(context)
    
    # Modify tool list if needed
    # for tool in result.tools:
    #     tool.description = "Modified description"
    
    return result
```

#### `on_read_resource(context, call_next)`
Called when reading resources.

```python
async def on_read_resource(self, context, call_next):
    result = await call_next(context)
    
    # Modify resource content if needed
    
    return result
```

### Adding Middleware to Your Application

```python
from fastmcp import FastMCP
from mcp_composer.middleware import MyCustomMiddleware

app = FastMCP("My App")

# Add middleware
app.add_middleware(MyCustomMiddleware(config_param="my_value"))

# Add multiple middleware (order matters)
app.add_middleware(AnotherMiddleware())
app.add_middleware(YetAnotherMiddleware())
```

## Built-in Middleware

MCP Composer provides several built-in middleware components for common use cases.

### Circuit Breaker Middleware

Prevents cascading failures by temporarily stopping calls to failing services.

```python
from mcp_composer.middleware import CircuitBreakerMiddleware

app.add_middleware(
    CircuitBreakerMiddleware(
        failure_threshold=5,      # Number of failures to trip
        open_timeout=30.0,        # Seconds to stay OPEN
        window_seconds=60.0,      # Rolling failure window
        exempt_tools={"health_check"}  # Tools to exempt
    )
)
```

**States:**
- **CLOSED**: Normal operation, calls pass through
- **OPEN**: Circuit is open, calls are blocked
- **HALF_OPEN**: Allows one probe call to test recovery

### Rate Limiting Middleware

Controls the rate of requests to prevent abuse.

```python
from mcp_composer.middleware import RateLimiterMiddleware

app.add_middleware(
    RateLimiterMiddleware(
        per_tool_limits={
            "expensive_tool": 10,    # 10 calls per minute
            "search_api": 100        # 100 calls per minute
        },
        per_tenant_limits={
            "tenant_a": 50,          # 50 calls per minute per tenant
            "tenant_b": 100
        },
        acquire_timeout=2.0,         # Fail fast if queue exceeds 2s
        get_tenant=lambda ctx: getattr(ctx, "tenant_id", "unknown")
    )
)
```

### Concurrency Limiting Middleware

Limits concurrent executions using semaphores (bulkhead pattern).

```python
from mcp_composer.middleware import ConcurrencyLimiterMiddleware

app.add_middleware(
    ConcurrencyLimiterMiddleware(
        per_tool_limits={
            "ask_llm": 8,            # Max 8 concurrent calls
            "search_docs": 16
        },
        per_tenant_limits={
            "tenant_a": 10,          # Max 10 concurrent per tenant
        },
        acquire_timeout=1.5,         # Fail fast if queue exceeds 1.5s
        get_tenant=lambda ctx: getattr(ctx, "tenant_id", "unknown")
    )
)
```

### Prompt Injection Protection Middleware

Detects and prevents prompt injection attacks.

```python
from mcp_composer.middleware import PromptInjectionMiddleware

app.add_middleware(
    PromptInjectionMiddleware(
        block_on_high_risk=True,     # Block high-risk calls
        threshold=0.75,              # Risk threshold (0-1)
        url_allowlist=[              # Allowed URL prefixes
            "https://docs.company.com/",
            "https://api.company.com/"
        ],
        sanitize_on_medium=True,     # Sanitize medium-risk calls
        inspect_fields=["query", "prompt"]  # Fields to inspect
    )
)
```

### PII and Secrets Redaction Middleware

Automatically redacts sensitive information from inputs and outputs.

```python
from mcp_composer.middleware import SecretsAndPIIMiddleware, RedactionStrategy

app.add_middleware(
    SecretsAndPIIMiddleware(
        strategy=RedactionStrategy(
            mode="mask",             # "mask", "hash", or "tokenize"
            salt="optional_salt"     # For hash mode
        ),
        allowlist_tools=["decrypt_tool"],  # Tools to exempt
        allowlist_fields=["public_info"],  # Fields to exempt
        redact_inputs=True,          # Redact arguments
        redact_outputs=True          # Redact responses
    )
)
```

**Redaction Modes:**
- **mask**: `[REDACTED:EMAIL]`
- **hash**: `[HASH:EMAIL:a1b2c3d4e5f6]`
- **tokenize**: `<EMAIL_1>`

### XML to JSON Conversion Middleware

Automatically converts XML responses to JSON format.

```python
from mcp_composer.middleware import FormatXml2Json

app.add_middleware(FormatXml2Json(mcp_composer=app))
```

### Policy/ACL Middleware

Enforces access control policies using various backends.

```python
from mcp_composer.middleware.acl.policy import PolicyMiddleware
from mcp_composer.middleware.acl.policy.file_enforcer import FilePolicyEnforcer

app.add_middleware(
    PolicyMiddleware(
        policy_enforcer=FilePolicyEnforcer(
            policy_file="policies/basic_policy.json"
        ),
        identity_manager=YourIdentityManager(),
        enable_audit_logging=True
    )
)
```

## Middleware Best Practices

### 1. Order Matters
Middleware is executed in the order it's added. Consider the execution order:

```python
# Add authentication first
app.add_middleware(AuthMiddleware())

# Then rate limiting
app.add_middleware(RateLimiterMiddleware(...))

# Then business logic middleware
app.add_middleware(CustomBusinessLogicMiddleware())
```

### 2. Error Handling
Always handle exceptions gracefully:

```python
async def on_call_tool(self, context, call_next):
    try:
        result = await call_next(context)
        return result
    except Exception as e:
        # Log the error
        logger.error(f"Middleware error: {e}")
        # Re-raise or handle appropriately
        raise
```

### 3. Performance Considerations
- Keep middleware lightweight
- Use async operations when possible
- Cache expensive operations
- Avoid blocking operations

### 4. Configuration
Make middleware configurable:

```python
class ConfigurableMiddleware(Middleware):
    def __init__(self, 
                 enabled: bool = True,
                 timeout: float = 30.0,
                 max_retries: int = 3):
        self.enabled = enabled
        self.timeout = timeout
        self.max_retries = max_retries
```

### 5. Logging and Monitoring
Add observability to your middleware:

```python
import logging
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()

class LoggingMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        start_time = time.time()
        tool_name = getattr(context.message, "name", "<unknown>")
        
        logger.info(f"Starting tool call: {tool_name}")
        
        try:
            result = await call_next(context)
            duration = time.time() - start_time
            logger.info(f"Tool call completed: {tool_name} in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Tool call failed: {tool_name} after {duration:.2f}s - {e}")
            raise
```

## Testing Middleware

Test your middleware in isolation:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_my_middleware():
    middleware = MyCustomMiddleware()
    context = MagicMock()
    context.message.name = "test_tool"
    context.message.arguments = {"param": "value"}
    
    call_next = AsyncMock(return_value={"result": "success"})
    
    result = await middleware.on_call_tool(context, call_next)
    
    assert result == {"result": "success"}
    call_next.assert_called_once_with(context)
```

## Common Patterns

### Request/Response Transformation
```python
async def on_call_tool(self, context, call_next):
    # Transform request
    original_args = context.message.arguments
    context.message.arguments = self.transform_request(original_args)
    
    try:
        result = await call_next(context)
        # Transform response
        return self.transform_response(result)
    finally:
        # Restore original arguments
        context.message.arguments = original_args
```

### Conditional Processing
```python
async def on_call_tool(self, context, call_next):
    tool_name = getattr(context.message, "name", "")
    
    if tool_name in self.exempt_tools:
        return await call_next(context)
    
    # Apply middleware logic only to non-exempt tools
    return await self.process_with_middleware(context, call_next)
```

### State Management
```python
class StatefulMiddleware(Middleware):
    def __init__(self):
        self.request_count = 0
        self.lock = asyncio.Lock()
    
    async def on_call_tool(self, context, call_next):
        async with self.lock:
            self.request_count += 1
        
        return await call_next(context)
```

This guide provides the foundation for creating and using middleware in MCP Composer. For more specific examples, see the [Middleware Examples](../examples/middleware-examples.md) documentation.


For more details on middleware configuration, see the [Middleware Configuration](./middleware-configuration.md)