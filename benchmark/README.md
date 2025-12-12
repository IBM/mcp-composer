# MCP Composer Benchmark Suite

Comprehensive benchmarking tools for evaluating MCP Composer performance, latency, throughput, and resource usage.

## Installation

Install benchmark dependencies:

```bash
pip install psutil httpx fastmcp
```

Or install from the project root:

```bash
pip install -e ".[benchmark]"
```

## Quick Start

### Basic Latency Benchmark

Benchmark a single tool with 100 iterations:

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-name member_health \
    --iterations 100
```

### Concurrent Request Benchmark

Test concurrent request handling:

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-name member_health \
    --mode concurrent \
    --concurrent 50 \
    --iterations 200
```

### Throughput Benchmark

Measure requests per second over 60 seconds:

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-name member_health \
    --mode throughput \
    --duration 60
```

### Benchmark Multiple Tools

Create a tool list file (`tools.json`):

```json
[
  {
    "name": "member_health",
    "arguments": {}
  },
  {
    "name": "list_servers",
    "arguments": {}
  },
  {
    "name": "get_all_tools",
    "arguments": {}
  }
]
```

Then run:

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-list tools.json \
    --iterations 50 \
    --report benchmark_report.json
```

## Command Line Options

```
--endpoint ENDPOINT      MCP Composer endpoint URL (required)
--transport {http,sse}   Transport type (default: http)
--auth-token TOKEN       Authentication token (Bearer)
--tool-name NAME         Specific tool to benchmark
--tool-list FILE         JSON file with tools to benchmark
--iterations N           Number of iterations (default: 100)
--concurrent N           Concurrent requests (for concurrent mode)
--duration N             Duration in seconds (for throughput mode)
--timeout N              Request timeout in seconds (default: 30.0)
--mode {latency,throughput,concurrent}  Benchmark mode (default: latency)
--report FILE            Output JSON report file
```

## Benchmark Modes

### 1. Latency Mode (default)

Measures latency statistics (P50, P90, P99) for tool calls.

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --mode latency \
    --tool-name member_health \
    --iterations 1000
```

**Output:**
- P50, P90, P99 latencies
- Average, min, max latencies
- Success rate
- Resource usage

### 2. Concurrent Mode

Tests concurrent request handling and measures performance under load.

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --mode concurrent \
    --tool-name member_health \
    --concurrent 100 \
    --iterations 500
```

**Output:**
- Latency statistics under concurrent load
- Throughput (requests/second)
- Success rate under load
- Resource usage

### 3. Throughput Mode

Measures sustained throughput over a duration.

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --mode throughput \
    --tool-name member_health \
    --duration 300
```

**Output:**
- Sustained requests per second
- Latency statistics
- Resource usage over time
- Success rate

## Example Tool List File

Create `example_tools.json`:

```json
[
  {
    "name": "member_health",
    "arguments": {}
  },
  {
    "name": "list_servers",
    "arguments": {}
  },
  {
    "name": "get_all_tools",
    "arguments": {}
  },
  {
    "name": "register_mcp_server",
    "arguments": {
      "server_config": {
        "id": "test-server",
        "type": "http",
        "endpoint": "http://localhost:8001"
      }
    }
  }
]
```

## Report Format

The JSON report includes:

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "endpoint": "http://localhost:9000/mcp",
  "transport": "http",
  "summary": {
    "total_requests": 1000,
    "successful_requests": 995,
    "failed_requests": 5,
    "success_rate": 99.5,
    "p50_latency_ms": 45.2,
    "p90_latency_ms": 120.5,
    "p99_latency_ms": 250.8,
    "avg_latency_ms": 52.3,
    "throughput_rps": 50.2,
    "cpu_usage_percent": 15.3,
    "memory_usage_mb": 256.7
  },
  "results": [
    {
      "tool_name": "member_health",
      "success": true,
      "latency_ms": 45.2,
      "error": null,
      "response_size_bytes": 1024
    }
  ]
}
```

## Benchmarking Best Practices

1. **Warm-up**: Run a few requests before benchmarking to warm up connections
2. **Isolation**: Run benchmarks on dedicated hardware/containers
3. **Multiple Runs**: Run benchmarks multiple times and average results
4. **Baseline**: Establish baseline metrics before optimization
5. **Resource Monitoring**: Monitor CPU, memory, and network during benchmarks

## Example Benchmark Scenarios

### Scenario 1: Quick Health Check

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-name member_health \
    --iterations 10 \
    --mode latency
```

### Scenario 2: Load Testing

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-name member_health \
    --mode concurrent \
    --concurrent 200 \
    --iterations 1000 \
    --report load_test.json
```

### Scenario 3: Sustained Throughput

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-name member_health \
    --mode throughput \
    --duration 600 \
    --report throughput_test.json
```

### Scenario 4: Multi-Tool Benchmark

```bash
python benchmark/benchmark_mcp_composer.py \
    --endpoint http://localhost:9000/mcp \
    --tool-list tools.json \
    --iterations 100 \
    --report multi_tool_benchmark.json
```

## Troubleshooting

### Connection Errors

If you get connection errors:
- Verify MCP Composer is running: `curl http://localhost:9000/mcp`
- Check endpoint URL format
- Verify transport type matches server configuration

### Timeout Errors

If requests timeout:
- Increase `--timeout` value
- Check network latency
- Verify server is not overloaded

### Authentication Errors

If you get authentication errors:
- Provide `--auth-token` if server requires authentication
- Check token format: `Bearer <token>`

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Benchmark

on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -e ".[benchmark]"
      - run: |
          # Start MCP Composer server
          python -m mcp_composer --mode http --port 9000 &
          sleep 10
          
          # Run benchmarks
          python benchmark/benchmark_mcp_composer.py \
            --endpoint http://localhost:9000/mcp \
            --tool-name member_health \
            --iterations 100 \
            --report benchmark_results.json
```

## Performance Targets

Based on the benchmarking report, target metrics:

- **P50 Latency**: <50ms for local tools
- **P90 Latency**: <200ms for local tools
- **P99 Latency**: <500ms for local tools
- **Throughput**: 100-500 RPS (depending on tool complexity)
- **Success Rate**: >99%

## Contributing

When adding new benchmark scenarios:

1. Add test cases to `benchmark/`
2. Update this README with examples
3. Ensure benchmarks are reproducible
4. Document any special requirements
