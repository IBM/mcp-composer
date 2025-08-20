#!/bin/bash
set -e

echo "🧼 Cleaning old builds..."
rm -rf build dist *.egg-info
find src/mcp_composer -type d -name "__pycache__" -exec rm -rf {} +
find src/mcp_composer_app -type d -name "__pycache__" -exec rm -rf {} +
find src/mcp_composer -type d -name "__pycache__" -exec rm -rf {} +
find src/mcp_composer -type f -name "*.pyc" -delete
find src/mcp_composer_app -type f -name "*.pyc" -delete
find src/mcp_composer_client -type f -name "*.pyc" -delete

echo "🔨 Building wheel for mcp_composer..."
uv build --wheel .

echo "✅ Wheel build complete. Output:"
ls dist/*.whl
