#!/usr/bin/env python3
"""
Quick Benchmark Script for MCP Composer

Simplified benchmark script for quick performance checks.
Usage: python quick_benchmark.py http://localhost:9000/mcp
"""

import asyncio
import sys
import time
from benchmark_mcp_composer import MCPComposerBenchmark


async def quick_benchmark(endpoint: str):
    """Run a quick benchmark"""
    print(f"Quick Benchmark: {endpoint}")
    print("=" * 60)

    benchmark = MCPComposerBenchmark(endpoint=endpoint)
    await benchmark.initialize()

    # List tools
    tools = await benchmark.list_tools()
    print(f"\nFound {len(tools)} tools")

    if not tools:
        print("No tools available")
        return

    # Use first available tool
    tool_name = tools[0].get("name", "unknown")
    print(f"\nBenchmarking: {tool_name}")

    # Run 10 quick iterations
    print("\nRunning 10 iterations...")
    results = await benchmark.benchmark_single_tool(tool_name, {}, iterations=10)

    # Calculate quick stats
    successful = [r for r in results if r.success]
    if successful:
        latencies = [r.latency_ms for r in successful]
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        print(f"\nResults:")
        print(f"  Success Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
        print(f"  Avg Latency:  {avg_latency:.2f} ms")
        print(f"  Min Latency:  {min_latency:.2f} ms")
        print(f"  Max Latency:  {max_latency:.2f} ms")
    else:
        print("\nAll requests failed!")

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python quick_benchmark.py <endpoint>")
        print("Example: python quick_benchmark.py http://localhost:9000/mcp")
        sys.exit(1)

    endpoint = sys.argv[1]
    asyncio.run(quick_benchmark(endpoint))
