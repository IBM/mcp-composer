# MCP Composer Middleware Examples

This directory contains examples demonstrating various middleware components available in MCP Composer.

## Available Middleware Examples

### 1. Circuit Breaker Middleware
**Files:** `circuit-breaker-server.py`, `circuit-breaker-client.py`

Demonstrates circuit breaker pattern for handling failing services:
- Automatically opens circuit after specified number of failures
- Prevents cascading failures
- Allows service recovery with half-open state

**Usage:**
```bash
# Terminal 1: Start server
uv run python circuit-breaker-server.py

# Terminal 2: Run client
uv run python circuit-breaker-client.py
```

### 2. Concurrency Limiter Middleware
**Files:** `concurrency-server.py`, `concurrency-client.py`

Limits concurrent requests per tool and per tenant:
- Prevents resource exhaustion
- Configurable limits per tool and tenant
- Fail-fast behavior with timeout

**Usage:**
```bash
# Terminal 1: Start server
uv run python concurrency-server.py

# Terminal 2: Run client
uv run python concurrency-client.py
```

### 3. Rate Limiter Middleware
**Files:** `rate-limit-server.py`, `rate-limit-client.py`

Implements token bucket rate limiting:
- Per-tool and per-tenant rate limits
- Daily budget limits
- Configurable cost estimation

**Usage:**
```bash
# Terminal 1: Start server
uv run python rate-limit-server.py

# Terminal 2: Run client
uv run python rate-limit-client.py
```

### 4. Prompt Injection Middleware
**Files:** `promptinjectionserver.py`, `pinj-client.py`

Protects against prompt injection attacks:
- Detects malicious prompts using heuristics
- Blocks high-risk requests
- Sanitizes medium-risk content

**Usage:**
```bash
# Terminal 1: Start server
uv run python promptinjectionserver.py

# Terminal 2: Run client
uv run python pinj-client.py
```

### 5. PII/Secrets Redaction Middleware
**Files:** `pii-stop-server.py`, `pii-stop-client.py`

Automatically redacts sensitive information:
- Detects PII patterns (emails, phones, credit cards)
- Redacts API keys and secrets
- Configurable redaction strategies

**Usage:**
```bash
# Terminal 1: Start server
uv run python pii-stop-server.py

# Terminal 2: Run client
uv run python pii-stop-client.py
```

### 6. XML to JSON Middleware
**Files:** `xml2json-server.py`, `xml2json-client.py`

Converts XML responses to JSON format:
- Automatic XML detection
- Preserves XML structure as JSON
- Handles attributes and nested elements

**Usage:**
```bash
# Terminal 1: Start server
uv run python xml2json-server.py

# Terminal 2: Run client
uv run python xml2json-client.py
```

## Running Examples

1. **Install dependencies:**
   ```bash
   cd /path/to/mcp-composer
   uv sync
   ```

2. **Start a server:**
   ```bash
   cd example/middlewares
   uv run python <server-file>.py
   ```

3. **Run the corresponding client:**
   ```bash
   # In another terminal
   cd example/middlewares
   uv run python <client-file>.py
   ```

## Middleware Configuration

Each middleware can be configured with various parameters:

### Circuit Breaker
- `failure_threshold`: Number of failures before opening circuit
- `open_timeout`: Time to stay open before allowing probes
- `window_seconds`: Rolling window for failure counting

### Concurrency Limiter
- `per_tool_limits`: Max concurrent calls per tool
- `per_tenant_limits`: Max concurrent calls per tenant
- `acquire_timeout`: Timeout for acquiring semaphore

### Rate Limiter
- `per_tool`: Token bucket config per tool (capacity, refill_rate, cost)
- `per_tenant_global`: Global tenant rate limits
- `per_tenant_daily_budget`: Daily cost budget per tenant

### Prompt Injection
- `threshold`: Risk threshold for blocking (0.0-1.0)
- `block_on_high_risk`: Whether to block high-risk requests
- `sanitize_on_medium`: Whether to sanitize medium-risk content

### PII/Secrets Redaction
- `strategy`: Redaction mode (mask, hash, tokenize)
- `allowlist_tools`: Tools exempt from redaction
- `allowlist_fields`: Fields exempt from key-based redaction

## Integration with MCP Composer

To use these middleware components in your MCP Composer application:

```python
from mcp_composer import MCPComposer
from mcp_composer.middleware.circuit_breaker import CircuitBreakerMiddleware
from mcp_composer.middleware.rate_limit import RateLimiterMiddleware

# Create composer instance
composer = MCPComposer("my-app")

# Add middleware
composer.add_middleware(CircuitBreakerMiddleware(failure_threshold=5))
composer.add_middleware(RateLimiterMiddleware(per_tool={"my_tool": (10, 1.0, 1.0)}))

# Start the server
await composer.run_http_async(host="0.0.0.0", port=8000)
```

## Notes

- All examples use FastMCP framework
- Servers run on `http://localhost:8000` by default
- Clients connect to the same endpoint
- Middleware can be combined for comprehensive protection
- Configuration values are examples and should be adjusted for production use
