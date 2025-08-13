# Middleware Examples

This document provides practical examples of how to use middleware in MCP Composer. Each example includes complete, runnable code that demonstrates real-world usage patterns.

## Example 1: Logging and Monitoring Middleware

A comprehensive logging middleware that tracks performance metrics and provides observability.

### Complete Example

```python
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


@dataclass
class Metrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration: float = 0.0
    call_durations: list = field(default_factory=list)


class LoggingMiddleware(Middleware):
    """
    Comprehensive logging and monitoring middleware.
    
    Features:
    - Request/response logging
    - Performance metrics
    - Error tracking
    - Custom metrics collection
    """
    
    def __init__(self, 
                 log_arguments: bool = True,
                 log_responses: bool = False,
                 collect_metrics: bool = True):
        self.log_arguments = log_arguments
        self.log_responses = log_responses
        self.collect_metrics = collect_metrics
        self.metrics = Metrics()
        self.lock = asyncio.Lock()
    
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        tool_name = getattr(context.message, "name", "<unknown>")
        arguments = getattr(context.message, "arguments", {})
        start_time = time.time()
        
        # Log request
        logger.info(f"🔄 Starting tool call: {tool_name}")
        if self.log_arguments:
            logger.debug(f"📥 Arguments: {arguments}")
        
        try:
            # Execute the tool
            result = await call_next(context)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log success
            logger.info(f"✅ Tool call completed: {tool_name} in {duration:.3f}s")
            if self.log_responses:
                logger.debug(f"📤 Response: {result}")
            
            # Update metrics
            if self.collect_metrics:
                await self._update_metrics(duration, success=True)
            
            return result
            
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log error
            logger.error(f"❌ Tool call failed: {tool_name} after {duration:.3f}s - {e}")
            
            # Update metrics
            if self.collect_metrics:
                await self._update_metrics(duration, success=False)
            
            # Re-raise the exception
            raise
    
    async def _update_metrics(self, duration: float, success: bool):
        """Thread-safe metrics update."""
        async with self.lock:
            self.metrics.total_calls += 1
            self.metrics.total_duration += duration
            self.metrics.call_durations.append(duration)
            
            if success:
                self.metrics.successful_calls += 1
            else:
                self.metrics.failed_calls += 1
            
            # Keep only last 1000 durations to prevent memory bloat
            if len(self.metrics.call_durations) > 1000:
                self.metrics.call_durations = self.metrics.call_durations[-1000:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        async def _get():
            async with self.lock:
                avg_duration = (self.metrics.total_duration / self.metrics.total_calls 
                              if self.metrics.total_calls > 0 else 0.0)
                
                return {
                    "total_calls": self.metrics.total_calls,
                    "successful_calls": self.metrics.successful_calls,
                    "failed_calls": self.metrics.failed_calls,
                    "success_rate": (self.metrics.successful_calls / self.metrics.total_calls 
                                   if self.metrics.total_calls > 0 else 0.0),
                    "average_duration": avg_duration,
                    "total_duration": self.metrics.total_duration
                }
        
        # Run the async function in the current event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we need to handle this differently
                # For simplicity, we'll return a basic dict
                return {
                    "total_calls": self.metrics.total_calls,
                    "successful_calls": self.metrics.successful_calls,
                    "failed_calls": self.metrics.failed_calls,
                }
            else:
                return loop.run_until_complete(_get())
        except RuntimeError:
            # No event loop, return basic metrics
            return {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
            }


# Example usage
app = FastMCP("Logging Demo")

# Add the logging middleware
logging_middleware = LoggingMiddleware(
    log_arguments=True,
    log_responses=False,
    collect_metrics=True
)
app.add_middleware(logging_middleware)


@app.tool()
async def slow_operation(data: dict) -> dict:
    """Simulate a slow operation."""
    await asyncio.sleep(0.1)  # Simulate work
    return {"result": "success", "processed": data}


@app.tool()
async def fast_operation(data: dict) -> dict:
    """Simulate a fast operation."""
    return {"result": "success", "processed": data}


@app.tool()
async def failing_operation(data: dict) -> dict:
    """Simulate a failing operation."""
    raise ValueError("Simulated error")


if __name__ == "__main__":
    app.run()
```

### Running the Example

```bash
# Start the server
python logging_example.py

# In another terminal, test the tools
curl -X POST http://localhost:8000/tools/slow_operation \
  -H "Content-Type: application/json" \
  -d '{"data": {"test": "value"}}'

# Check metrics
print(logging_middleware.get_metrics())
```

## Example 2: Request Transformation Middleware

A middleware that transforms requests and responses, useful for API versioning, data validation, and format conversion.

### Complete Example

```python
import json
from typing import Any, Dict, Optional
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class RequestTransformationMiddleware(Middleware):
    """
    Transforms requests and responses for API compatibility.
    
    Features:
    - Request validation and sanitization
    - Response formatting
    - API versioning support
    - Data type conversion
    """
    
    def __init__(self,
                 validate_requests: bool = True,
                 format_responses: bool = True,
                 api_version: str = "v1",
                 required_fields: Optional[Dict[str, list]] = None):
        self.validate_requests = validate_requests
        self.format_responses = format_responses
        self.api_version = api_version
        self.required_fields = required_fields or {}
    
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        tool_name = getattr(context.message, "name", "<unknown>")
        arguments = getattr(context.message, "arguments", {})
        
        # Transform request
        transformed_args = await self._transform_request(tool_name, arguments)
        original_args = context.message.arguments
        context.message.arguments = transformed_args
        
        try:
            # Execute the tool
            result = await call_next(context)
            
            # Transform response
            if self.format_responses:
                result = await self._transform_response(tool_name, result)
            
            return result
            
        finally:
            # Restore original arguments
            context.message.arguments = original_args
    
    async def _transform_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Transform and validate the request arguments."""
        transformed = arguments.copy()
        
        # Add API version if not present
        if "api_version" not in transformed:
            transformed["api_version"] = self.api_version
        
        # Validate required fields
        if self.validate_requests and tool_name in self.required_fields:
            missing_fields = []
            for field in self.required_fields[tool_name]:
                if field not in transformed:
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Sanitize string inputs
        for key, value in transformed.items():
            if isinstance(value, str):
                transformed[key] = value.strip()
        
        # Convert data types based on tool
        if tool_name == "process_user_data":
            if "age" in transformed and isinstance(transformed["age"], str):
                try:
                    transformed["age"] = int(transformed["age"])
                except ValueError:
                    raise ValueError("Age must be a valid integer")
        
        logger.debug(f"Transformed request for {tool_name}: {transformed}")
        return transformed
    
    async def _transform_response(self, tool_name: str, result: Any) -> Any:
        """Transform the response."""
        if not isinstance(result, dict):
            return result
        
        transformed = result.copy()
        
        # Add metadata
        transformed["_metadata"] = {
            "api_version": self.api_version,
            "tool_name": tool_name,
            "timestamp": "2024-01-01T00:00:00Z"  # In real app, use actual timestamp
        }
        
        # Format specific responses
        if tool_name == "process_user_data" and "user" in transformed:
            user = transformed["user"]
            if isinstance(user, dict):
                # Ensure consistent user object structure
                user.setdefault("id", None)
                user.setdefault("name", "")
                user.setdefault("email", "")
                user.setdefault("created_at", None)
        
        logger.debug(f"Transformed response for {tool_name}: {transformed}")
        return transformed


# Example usage
app = FastMCP("Transformation Demo")

# Add the transformation middleware
app.add_middleware(
    RequestTransformationMiddleware(
        validate_requests=True,
        format_responses=True,
        api_version="v2",
        required_fields={
            "process_user_data": ["name", "email"],
            "update_user": ["user_id"]
        }
    )
)


@app.tool()
async def process_user_data(name: str, email: str, age: Optional[str] = None) -> dict:
    """Process user data with validation."""
    return {
        "status": "success",
        "user": {
            "name": name,
            "email": email,
            "age": int(age) if age else None,
            "processed": True
        }
    }


@app.tool()
async def update_user(user_id: str, data: dict) -> dict:
    """Update user information."""
    return {
        "status": "success",
        "user_id": user_id,
        "updated_fields": list(data.keys()),
        "message": "User updated successfully"
    }


@app.tool()
async def simple_operation(data: dict) -> dict:
    """Simple operation without special requirements."""
    return {"result": "success", "data": data}


if __name__ == "__main__":
    app.run()
```

### Testing the Transformation Middleware

```bash
# Test with valid data
curl -X POST http://localhost:8000/tools/process_user_data \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com", "age": "30"}'

# Test with missing required field (should fail)
curl -X POST http://localhost:8000/tools/process_user_data \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe"}'

# Test simple operation
curl -X POST http://localhost:8000/tools/simple_operation \
  -H "Content-Type: application/json" \
  -d '{"test": "value"}'
```

## Example 3: Circuit Breaker with Health Check

A practical example showing how to implement a circuit breaker with health checks and graceful degradation.

### Complete Example

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.exceptions import ToolError
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


@dataclass
class CircuitState:
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    failures: list = field(default_factory=list)
    opened_at: Optional[float] = None
    last_success: Optional[float] = None
    health_check_count: int = 0


class AdvancedCircuitBreakerMiddleware(Middleware):
    """
    Advanced circuit breaker with health checks and graceful degradation.
    
    Features:
    - Configurable failure thresholds
    - Health check probes
    - Graceful degradation with fallback responses
    - Detailed monitoring
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 open_timeout: float = 30.0,
                 health_check_interval: float = 10.0,
                 health_check_timeout: float = 5.0,
                 exempt_tools: Optional[Set[str]] = None,
                 fallback_responses: Optional[Dict[str, Any]] = None):
        self.failure_threshold = failure_threshold
        self.open_timeout = open_timeout
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout
        self.exempt_tools = exempt_tools or set()
        self.fallback_responses = fallback_responses or {}
        
        self._circuits: Dict[str, CircuitState] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        tool_name = getattr(context.message, "name", "<unknown>")
        
        # Skip circuit breaker for exempt tools
        if tool_name in self.exempt_tools:
            return await call_next(context)
        
        # Get or create circuit state
        circuit = await self._get_circuit(tool_name)
        
        # Check circuit state
        if circuit.state == "OPEN":
            if self._should_attempt_reset(circuit):
                circuit.state = "HALF_OPEN"
                logger.info(f"Circuit {tool_name} moved to HALF_OPEN")
            else:
                # Return fallback response or raise error
                fallback = self.fallback_responses.get(tool_name)
                if fallback:
                    logger.warning(f"Circuit {tool_name} OPEN, returning fallback response")
                    return fallback
                else:
                    raise ToolError(f"Circuit breaker OPEN for {tool_name}. Try again later.")
        
        # Execute the call
        start_time = time.time()
        try:
            result = await call_next(context)
            
            # Record success
            await self._record_success(tool_name, circuit, start_time)
            return result
            
        except Exception as e:
            # Record failure
            await self._record_failure(tool_name, circuit, start_time, str(e))
            raise
    
    async def _get_circuit(self, tool_name: str) -> CircuitState:
        """Get or create circuit state for a tool."""
        async with self._lock:
            if tool_name not in self._circuits:
                self._circuits[tool_name] = CircuitState()
            return self._circuits[tool_name]
    
    def _should_attempt_reset(self, circuit: CircuitState) -> bool:
        """Check if circuit should attempt to reset."""
        if circuit.opened_at is None:
            return False
        return time.time() - circuit.opened_at >= self.open_timeout
    
    async def _record_success(self, tool_name: str, circuit: CircuitState, start_time: float):
        """Record a successful call."""
        async with self._lock:
            circuit.state = "CLOSED"
            circuit.last_success = time.time()
            circuit.failures.clear()
            circuit.health_check_count = 0
            
            duration = time.time() - start_time
            logger.info(f"Circuit {tool_name} call succeeded in {duration:.3f}s")
    
    async def _record_failure(self, tool_name: str, circuit: CircuitState, 
                            start_time: float, error: str):
        """Record a failed call."""
        async with self._lock:
            circuit.failures.append(time.time())
            
            # Clean old failures
            cutoff = time.time() - 60.0  # 1 minute window
            circuit.failures = [f for f in circuit.failures if f > cutoff]
            
            # Check if circuit should open
            if len(circuit.failures) >= self.failure_threshold and circuit.state == "CLOSED":
                circuit.state = "OPEN"
                circuit.opened_at = time.time()
                logger.warning(f"Circuit {tool_name} opened after {len(circuit.failures)} failures")
            
            duration = time.time() - start_time
            logger.error(f"Circuit {tool_name} call failed in {duration:.3f}s: {error}")
    
    async def start_health_checks(self):
        """Start periodic health checks."""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop_health_checks(self):
        """Stop health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
    
    async def _health_check_loop(self):
        """Periodic health check loop."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks for all circuits."""
        for tool_name, circuit in self._circuits.items():
            if circuit.state == "OPEN":
                await self._check_circuit_health(tool_name, circuit)
    
    async def _check_circuit_health(self, tool_name: str, circuit: CircuitState):
        """Check health of a specific circuit."""
        try:
            # This would typically call a health check endpoint
            # For this example, we'll simulate a health check
            await asyncio.sleep(0.1)  # Simulate health check
            
            # If health check passes, move to HALF_OPEN
            circuit.state = "HALF_OPEN"
            circuit.health_check_count += 1
            logger.info(f"Health check passed for {tool_name}, moved to HALF_OPEN")
            
        except Exception as e:
            logger.warning(f"Health check failed for {tool_name}: {e}")
    
    def get_circuit_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuits."""
        status = {}
        for tool_name, circuit in self._circuits.items():
            status[tool_name] = {
                "state": circuit.state,
                "failure_count": len(circuit.failures),
                "last_success": circuit.last_success,
                "opened_at": circuit.opened_at,
                "health_check_count": circuit.health_check_count
            }
        return status


# Example usage
app = FastMCP("Circuit Breaker Demo")

# Add circuit breaker middleware
circuit_breaker = AdvancedCircuitBreakerMiddleware(
    failure_threshold=3,
    open_timeout=10.0,
    health_check_interval=5.0,
    exempt_tools={"health_check"},
    fallback_responses={
        "unreliable_service": {"status": "degraded", "message": "Service temporarily unavailable"},
        "external_api": {"status": "fallback", "data": "cached_data"}
    }
)

app.add_middleware(circuit_breaker)


@app.tool()
async def reliable_service(data: dict) -> dict:
    """A reliable service that rarely fails."""
    await asyncio.sleep(0.1)
    return {"status": "success", "data": data}


@app.tool()
async def unreliable_service(data: dict) -> dict:
    """An unreliable service that fails frequently."""
    import random
    if random.random() < 0.7:  # 70% failure rate
        raise Exception("Service temporarily unavailable")
    
    await asyncio.sleep(0.1)
    return {"status": "success", "data": data}


@app.tool()
async def external_api(data: dict) -> dict:
    """External API that might be slow or fail."""
    import random
    if random.random() < 0.5:  # 50% failure rate
        await asyncio.sleep(2.0)  # Simulate timeout
        raise Exception("External API timeout")
    
    await asyncio.sleep(0.2)
    return {"status": "success", "external_data": data}


@app.tool()
async def health_check() -> dict:
    """Health check endpoint (exempt from circuit breaker)."""
    return {"status": "healthy", "timestamp": time.time()}


# Start health checks when the app starts
@app.on_startup
async def startup():
    await circuit_breaker.start_health_checks()


@app.on_shutdown
async def shutdown():
    await circuit_breaker.stop_health_checks()


if __name__ == "__main__":
    app.run()
```

### Testing the Circuit Breaker

```bash
# Test reliable service (should work consistently)
for i in {1..10}; do
  curl -X POST http://localhost:8000/tools/reliable_service \
    -H "Content-Type: application/json" \
    -d '{"test": "value"}'
done

# Test unreliable service (should trigger circuit breaker)
for i in {1..10}; do
  curl -X POST http://localhost:8000/tools/unreliable_service \
    -H "Content-Type: application/json" \
    -d '{"test": "value"}'
done

# Check circuit status
print(circuit_breaker.get_circuit_status())
```

## Summary

These examples demonstrate three key middleware patterns:

1. **Logging and Monitoring**: Provides observability and metrics collection
2. **Request Transformation**: Handles data validation, sanitization, and format conversion
3. **Circuit Breaker**: Implements fault tolerance and graceful degradation

Each example includes:
- Complete, runnable code
- Comprehensive error handling
- Configuration options
- Testing instructions
- Best practices

These patterns can be combined and customized to build robust, observable, and fault-tolerant MCP applications.
