.PHONY: format lint type-check security test coverage clean help all check release status build check-release upload

# Default target
all: format lint type-check security test coverage

# Format code with black
format:
	@echo "🔧 Formatting code with black..."
	uv run black .

# Lint code with ruff
lint:
	@echo "🔍 Linting code with ruff..."
	uv run ruff check . > ./../chroes_output/ruff_output.txt

# Type checking with mypy
type-check:
	@echo "📝 Running type checks with mypy..."
	uv run mypy ./../src/mcp_composer/ > ./../chroes_output/mypy_output.txt


# Run tests with coverage
test:
	@echo "🧪 Running tests..."
	uv run coverage run -m pytest ./../test/unit/ > ./../chroes_output/test_output.txt

# Generate coverage report
coverage: test
	@echo "📊 Generating coverage report..."
	uv run coverage report -m

# Run all checks in sequence
check: format lint type-check security test coverage

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage dist/ build/ htmlcov/ .pytest_cache/ .mypy_cache/

# PyPI Release Preparation
release: status clean check build check-release
	@echo "🚀 Release preparation complete. Run 'make upload' to publish to PyPI."

status:
	@echo "📦 Preparing release for mcp_composer..."
	@echo "📁 Python: $$(python --version)"
	@echo "📂 Virtualenv: $$(which python)"

build:
	@echo "🔨 Building wheel..."
	uv build --wheel .

check-release:
	@echo "✅ Checking build artifacts..."
	twine check dist/*

upload:
	@echo "🚀 Uploading to PyPI..."
	twine upload dist/*

# Show help
help:
	@echo ""
	@echo "🛠  Developer Tasks"
	@echo "  format       - Format code with black"
	@echo "  lint         - Lint code with ruff"
	@echo "  type-check   - Run type checks with mypy"
	@echo "  security     - Run security checks with bandit"
	@echo "  test         - Run tests with coverage"
	@echo "  coverage     - Generate coverage report"
	@echo "  check        - Run all checks in sequence"
	@echo "  clean        - Clean up generated files"
	@echo "  all          - Run all QA steps"
	@echo ""
	@echo "🚀 PyPI Release Tasks"
	@echo "  release      - Full release prep (QA + build + verify)"
	@echo "  build        - Build wheel with uv"
	@echo "  check-release- Verify wheel with twine"
	@echo "  upload       - Upload to PyPI"
	@echo "  status       - Show environment status"

