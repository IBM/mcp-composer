#!/bin/bash
# Quick benchmark runner script

ENDPOINT="${1:-http://localhost:9000/mcp}"
MODE="${2:-latency}"

echo "Running MCP Composer Benchmark"
echo "Endpoint: $ENDPOINT"
echo "Mode: $MODE"
echo ""

python3 benchmark_mcp_composer.py \
    --endpoint "$ENDPOINT" \
    --mode "$MODE" \
    --iterations 100 \
    --report "benchmark_$(date +%Y%m%d_%H%M%S).json"
