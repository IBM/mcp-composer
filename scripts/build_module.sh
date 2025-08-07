#!/bin/bash
set -e

# Define the module name you want to build (e.g., module1, module2)
MODULE_NAME=$1

if [ -z "$MODULE_NAME" ]; then
  echo "❌ Usage: $0 <module_name>"
  exit 1
fi

echo "🧼 Cleaning old builds..."
rm -rf build dist *.egg-info
find src/$MODULE_NAME -type d -name "__pycache__" -exec rm -rf {} +
find src/$MODULE_NAME -type f -name "*.pyc" -delete

echo "🔨 Building wheel for $MODULE_NAME..."

# Temporary pyproject.toml manipulation (optional)
# If needed, you can dynamically build using a template or monorepo logic

# Restrict wheel build to one module using a dynamic config
uv pip install -r src/$MODULE_NAME/requirements.txt
uv build --wheel .

echo "✅ Wheel build complete for $MODULE_NAME. Output:"
ls dist/$MODULE_NAME/*.whl
