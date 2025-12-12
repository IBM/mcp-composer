#!/usr/bin/env python3
"""
MCP Composer Benchmark Script

Comprehensive benchmarking tool for MCP Composer performance evaluation.
Tests latency, throughput, concurrent requests, resource usage, and stability.

Usage:
    python benchmark_mcp_composer.py --endpoint http://localhost:9000/mcp
    python benchmark_mcp_composer.py --endpoint http://localhost:9000/mcp --concurrent 50 --duration 60
    python benchmark_mcp_composer.py --endpoint http://localhost:9000/mcp --tool-list tools.json --report report.json
"""

import asyncio
import argparse
import json
import time
import statistics
import psutil
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import httpx
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport, SSETransport
import sys


@dataclass
class BenchmarkResult:
    """Individual benchmark result"""
    tool_name: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    response_size_bytes: int = 0


@dataclass
class BenchmarkSummary:
    """Summary statistics for benchmark run"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    p50_latency_ms: float
    p90_latency_ms: float
    p99_latency_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_rps: float
    avg_response_size_bytes: int
    cpu_usage_percent: float
    memory_usage_mb: float
    duration_seconds: float


class MCPComposerBenchmark:
    """Benchmark runner for MCP Composer"""

    def __init__(
        self,
        endpoint: str,
        transport: str = "http",
        auth_token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize benchmark runner.

        Args:
            endpoint: MCP Composer endpoint URL
            transport: Transport type (http, sse, stdio)
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint
        self.transport = transport.lower()
        self.auth_token = auth_token
        self.timeout = timeout
        self.client: Optional[Client] = None
        self.results: List[BenchmarkResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.process = psutil.Process(os.getpid())

    async def _create_client(self) -> Client:
        """Create MCP client based on transport type"""
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json, text/event-stream",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        if self.transport == "http":
            # Ensure URL ends with /mcp for HTTP transport
            endpoint = self.endpoint
            if not endpoint.endswith("/mcp"):
                endpoint = f"{endpoint.rstrip('/')}/mcp"
            transport_obj = StreamableHttpTransport(endpoint, headers=headers)
            return Client(transport_obj)
        elif self.transport == "sse":
            # Ensure URL ends with /sse for SSE transport
            endpoint = self.endpoint
            if not endpoint.endswith("/sse"):
                endpoint = f"{endpoint.rstrip('/')}/sse"
            transport_obj = SSETransport(endpoint, headers=headers)
            return Client(transport_obj)
        elif self.transport == "stdio":
            raise NotImplementedError("stdio transport benchmarking not yet implemented")
        else:
            raise ValueError(f"Unsupported transport: {self.transport}")

    async def initialize(self):
        """Initialize client connection"""
        self.client = await self._create_client()
        # Initialize MCP session if needed
        # Note: FastMCP Client may auto-initialize on first use

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP Composer"""
        if not self.client:
            await self.initialize()

        try:
            # Use the client's list_tools method
            tools = await self.client.list_tools()
            # Convert to list of dicts if needed
            if isinstance(tools, list):
                return [tool if isinstance(tool, dict) else {"name": str(tool)} for tool in tools]
            return []
        except Exception as e:
            print(f"Error listing tools: {e}")
            # Fallback: try direct HTTP call
            try:
                endpoint = self.endpoint if self.endpoint.endswith("/mcp") else f"{self.endpoint.rstrip('/')}/mcp"
                headers = {"Content-Type": "application/json"}
                if self.auth_token:
                    headers["Authorization"] = f"Bearer {self.auth_token}"
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{endpoint}/tools/list",
                        json={},
                        headers=headers,
                        timeout=self.timeout
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, dict) and "tools" in data:
                            return data["tools"]
                        elif isinstance(data, list):
                            return data
            except Exception as e2:
                print(f"Fallback HTTP call also failed: {e2}")
            return []

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any] = None
    ) -> BenchmarkResult:
        """
        Call a tool and measure latency.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            BenchmarkResult with latency and success status
        """
        if not self.client:
            await self.initialize()

        arguments = arguments or {}
        start_time = time.time()
        response_size = 0
        error = None
        success = False

        try:
            result = await asyncio.wait_for(
                self.client.call_tool(tool_name, arguments),
                timeout=self.timeout,
            )

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Estimate response size
            if result:
                response_size = len(str(result).encode("utf-8"))

            success = True
        except asyncio.TimeoutError:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            error = "timeout"
        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            error = str(e)

        return BenchmarkResult(
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms,
            error=error,
            response_size_bytes=response_size,
        )

    async def benchmark_single_tool(
        self, tool_name: str, arguments: Dict[str, Any] = None, iterations: int = 100
    ) -> List[BenchmarkResult]:
        """Benchmark a single tool with multiple iterations"""
        results = []
        for i in range(iterations):
            result = await self.call_tool(tool_name, arguments)
            results.append(result)
            if i % 10 == 0:
                print(f"  Completed {i+1}/{iterations} iterations")
        return results

    async def benchmark_concurrent(
        self,
        tool_name: str,
        arguments: Dict[str, Any] = None,
        concurrent: int = 10,
        total_requests: int = 100,
    ) -> List[BenchmarkResult]:
        """Benchmark concurrent tool calls"""
        semaphore = asyncio.Semaphore(concurrent)
        results = []

        async def call_with_semaphore():
            async with semaphore:
                return await self.call_tool(tool_name, arguments)

        tasks = [call_with_semaphore() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        benchmark_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                benchmark_results.append(
                    BenchmarkResult(
                        tool_name=tool_name,
                        success=False,
                        latency_ms=0,
                        error=str(result),
                    )
                )
            else:
                benchmark_results.append(result)

        return benchmark_results

    async def benchmark_throughput(
        self,
        tool_name: str,
        arguments: Dict[str, Any] = None,
        duration_seconds: int = 60,
    ) -> List[BenchmarkResult]:
        """Benchmark throughput over a duration"""
        results = []
        start_time = time.time()
        request_count = 0

        while time.time() - start_time < duration_seconds:
            result = await self.call_tool(tool_name, arguments)
            results.append(result)
            request_count += 1

            if request_count % 10 == 0:
                elapsed = time.time() - start_time
                rps = request_count / elapsed if elapsed > 0 else 0
                print(f"  Throughput: {rps:.2f} RPS ({request_count} requests)")

        return results

    def calculate_statistics(self, results: List[BenchmarkResult]) -> BenchmarkSummary:
        """Calculate summary statistics from results"""
        if not results:
            return BenchmarkSummary(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                success_rate=0.0,
                p50_latency_ms=0.0,
                p90_latency_ms=0.0,
                p99_latency_ms=0.0,
                avg_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                throughput_rps=0.0,
                avg_response_size_bytes=0,
                cpu_usage_percent=0.0,
                memory_usage_mb=0.0,
                duration_seconds=0.0,
            )

        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        latencies = [r.latency_ms for r in successful_results]
        response_sizes = [r.response_size_bytes for r in successful_results]

        duration = (
            self.end_time - self.start_time
            if self.start_time and self.end_time
            else 0.0
        )

        # Calculate percentiles
        p50 = statistics.median(latencies) if latencies else 0.0
        p90 = (
            statistics.quantiles(latencies, n=10)[8] if len(latencies) >= 10 else p50
        )
        p99 = (
            statistics.quantiles(latencies, n=100)[98]
            if len(latencies) >= 100
            else max(latencies) if latencies else 0.0
        )

        # Get CPU and memory usage
        cpu_percent = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024

        return BenchmarkSummary(
            total_requests=len(results),
            successful_requests=len(successful_results),
            failed_requests=len(failed_results),
            success_rate=len(successful_results) / len(results) * 100
            if results
            else 0.0,
            p50_latency_ms=p50,
            p90_latency_ms=p90,
            p99_latency_ms=p99,
            avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
            min_latency_ms=min(latencies) if latencies else 0.0,
            max_latency_ms=max(latencies) if latencies else 0.0,
            throughput_rps=len(results) / duration if duration > 0 else 0.0,
            avg_response_size_bytes=int(statistics.mean(response_sizes))
            if response_sizes
            else 0,
            cpu_usage_percent=cpu_percent,
            memory_usage_mb=memory_mb,
            duration_seconds=duration,
        )

    def print_summary(self, summary: BenchmarkSummary):
        """Print benchmark summary to console"""
        print("\n" + "=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)
        print(f"Total Requests:        {summary.total_requests}")
        print(f"Successful Requests:   {summary.successful_requests}")
        print(f"Failed Requests:       {summary.failed_requests}")
        print(f"Success Rate:          {summary.success_rate:.2f}%")
        print(f"\nLatency Statistics (ms):")
        print(f"  P50 (Median):        {summary.p50_latency_ms:.2f}")
        print(f"  P90:                 {summary.p90_latency_ms:.2f}")
        print(f"  P99:                 {summary.p99_latency_ms:.2f}")
        print(f"  Average:             {summary.avg_latency_ms:.2f}")
        print(f"  Min:                 {summary.min_latency_ms:.2f}")
        print(f"  Max:                 {summary.max_latency_ms:.2f}")
        print(f"\nThroughput:")
        print(f"  Requests/Second:     {summary.throughput_rps:.2f}")
        print(f"\nResource Usage:")
        print(f"  CPU Usage:           {summary.cpu_usage_percent:.2f}%")
        print(f"  Memory Usage:        {summary.memory_usage_mb:.2f} MB")
        print(f"\nDuration:             {summary.duration_seconds:.2f} seconds")
        print("=" * 80)

    def save_report(
        self, summary: BenchmarkSummary, results: List[BenchmarkResult], filename: str
    ):
        """Save benchmark report to JSON file"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": self.endpoint,
            "transport": self.transport,
            "summary": asdict(summary),
            "results": [asdict(r) for r in results],
        }

        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {filename}")


async def main():
    """Main benchmark execution"""
    parser = argparse.ArgumentParser(
        description="Benchmark MCP Composer performance"
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        required=True,
        help="MCP Composer endpoint URL (e.g., http://localhost:9000/mcp)",
    )
    parser.add_argument(
        "--transport",
        type=str,
        default="http",
        choices=["http", "sse"],
        help="Transport type (default: http)",
    )
    parser.add_argument(
        "--auth-token", type=str, help="Authentication token (Bearer)"
    )
    parser.add_argument(
        "--tool-name",
        type=str,
        help="Specific tool name to benchmark (default: list all tools)",
    )
    parser.add_argument(
        "--tool-list",
        type=str,
        help="JSON file with list of tools and arguments to benchmark",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations per tool (default: 100)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        help="Number of concurrent requests (for concurrent benchmark)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="Duration in seconds for throughput benchmark",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Output file for JSON report",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="latency",
        choices=["latency", "throughput", "concurrent"],
        help="Benchmark mode (default: latency)",
    )

    args = parser.parse_args()

    # Create benchmark runner
    benchmark = MCPComposerBenchmark(
        endpoint=args.endpoint,
        transport=args.transport,
        auth_token=args.auth_token,
        timeout=args.timeout,
    )

    print(f"Connecting to MCP Composer at {args.endpoint}...")
    await benchmark.initialize()

    # List available tools
    tools = await benchmark.list_tools()
    print(f"\nFound {len(tools)} available tools")

    if not tools:
        print("No tools available. Exiting.")
        return

    # Determine which tools to benchmark
    tools_to_benchmark = []
    if args.tool_name:
        # Single tool
        tool = next((t for t in tools if t.get("name") == args.tool_name), None)
        if tool:
            tools_to_benchmark = [(tool, {})]
        else:
            print(f"Tool '{args.tool_name}' not found.")
            return
    elif args.tool_list:
        # Load from file
        with open(args.tool_list, "r") as f:
            tool_configs = json.load(f)
            for config in tool_configs:
                tool_name = config.get("name")
                tool = next((t for t in tools if t.get("name") == tool_name), None)
                if tool:
                    tools_to_benchmark.append((tool, config.get("arguments", {})))
    else:
        # Benchmark first few tools (or all if < 5)
        for tool in tools[:5]:
            tools_to_benchmark.append((tool, {}))

    # Run benchmarks
    all_results = []
    benchmark.start_time = time.time()

    for tool, arguments in tools_to_benchmark:
        tool_name = tool.get("name", "unknown")
        print(f"\nBenchmarking tool: {tool_name}")

        if args.mode == "latency":
            results = await benchmark.benchmark_single_tool(
                tool_name, arguments, args.iterations
            )
        elif args.mode == "concurrent":
            if not args.concurrent:
                args.concurrent = 10
            results = await benchmark.benchmark_concurrent(
                tool_name, arguments, args.concurrent, args.iterations
            )
        elif args.mode == "throughput":
            if not args.duration:
                args.duration = 60
            results = await benchmark.benchmark_throughput(
                tool_name, arguments, args.duration
            )

        all_results.extend(results)

    benchmark.end_time = time.time()

    # Calculate and print summary
    summary = benchmark.calculate_statistics(all_results)
    benchmark.print_summary(summary)

    # Save report if requested
    if args.report:
        benchmark.save_report(summary, all_results, args.report)


if __name__ == "__main__":
    asyncio.run(main())
