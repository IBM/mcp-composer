.PHONY: format lint type-check security test coverage clean help all check release status build check-release upload docker-build docker-push docker-test help vars usage

REGISTRY_URL ?= icr.io
REGISTRY_NAMESPACE ?= automation-saas-platform
REGISTRY_IMAGE_TAG_SHORT ?= $(shell git rev-parse --abbrev-ref HEAD | sed 's/[^a-zA-Z0-9]/-/g')-$(shell git rev-parse --short HEAD)

ROOT_IMAGE_NAME = mcp-composer-root
SRC_APP_IMAGE_NAME = mcp-composer-app
SRC_CLIENT_IMAGE_NAME = mcp-composer-client
TEST_IMAGE_NAME = mcp-composer-test

ROOT_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(ROOT_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)
SRC_APP_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(SRC_APP_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)
SRC_CLIENT_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(SRC_CLIENT_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)
TEST_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(TEST_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)

BUILD_ENGINE ?= docker
BUILD_ENGINE_ARGS ?= --platform linux/amd64


docker-build: docker-build-root docker-build-app

docker-push:
	$(BUILD_ENGINE) push $(ROOT_IMAGE_URI)
	$(BUILD_ENGINE) push $(SRC_APP_IMAGE_URI)
# 	$(BUILD_ENGINE) push $(SRC_CLIENT_IMAGE_URI)

docker-build-root:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f modules/mcp_composer/Dockerfile -t $(ROOT_IMAGE_URI) modules/mcp_composer

docker-build-app:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) --no-cache $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f modules/mcp_composer_app/Dockerfile -t $(SRC_APP_IMAGE_URI) modules/mcp_composer_app

docker-build-client:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f modules/mcp_composer_client/Dockerfile -t $(SRC_CLIENT_IMAGE_URI) modules/mcp_composer_client

# Deploy the CI build to https://github.ibm.com/automation-paas-cd-pipeline/mcp-composer-cd
.PHONY: deploy
deploy:
	@echo "export GIT_REPO=mcp-composer-cd"
	@echo "export GIT_COMMITTER=\"CI/CD Functional ID <saas-ci1@ibm.com>\""
	@echo "export GIT_BRANCH=dev"
	@echo "export GIT_ORG=automation-paas-cd-pipeline"
	@echo "export PULL_REQUEST_ASSIGNEE=autopaas"
	@echo "export PROMOTION_ENV=development"
	@echo "export ENABLE_DEV_HEAD_USE=true"
	@echo "export GIT_TOKEN=$(GIT_TOKEN)"
	@echo "export PROMOTION_ENV_APP_SET=application-sets/aws-dev/us-east-1/application-set.yaml"
	@echo "export DEVELOPMENT_ENV_APP_SET=application-sets/aws-dev/us-east-1/application-set.yaml"	
	@echo "export REPLACEMENTS=\"resources/values.yaml config.imageTag.app,$(REGISTRY_IMAGE_TAG_SHORT);resources/values.yaml config.imageTag.client,$(REGISTRY_IMAGE_TAG_SHORT);resources/values.yaml config.imageTag.root,$(REGISTRY_IMAGE_TAG_SHORT)\""



vars: 
	@$(foreach V, $(.VARIABLES), echo "$(V) = $($(V))";)

# Default target
all: format lint type-check security test coverage

# Format code with black
format:
	@echo "🔧 Formatting code with black..."
	@if [ -z "$(module)" ]; then \
	  echo "❌ Usage: make test-module module=<module_name>"; exit 1; \
	fi
	@if [ ! -d "modules/$(module)" ]; then \
	  echo "❌ Module '$(module)' not found in modules/ directory"; exit 1; \
	fi
	cd modules/$(module) && uv run black .

# Lint code with ruff
lint:
	@echo "🔍 Linting code with ruff..."
	uv run ruff check . > ./../chroes_output/ruff_output.txt

# Type checking with mypy
type-check:
	@echo "📝 Running type checks with mypy..."
	uv run mypy ./../modules/mcp_composer/ > ./../chroes_output/mypy_output.txt


# Run tests with coverage
test:
	@echo "🧪 Running tests..."
	uv run coverage run -m pytest ./../test/unit/ > ./../chroes_output/test_output.txt

# Run unit tests for a specific module
test-module:
	@if [ -z "$(module)" ]; then \
	  echo "❌ Usage: make test-module module=<module_name>"; exit 1; \
	fi
	@if [ ! -d "modules/$(module)" ]; then \
	  echo "❌ Module '$(module)' not found in modules/ directory"; exit 1; \
	fi
	@echo "🧪 Running unit tests for $(module)..."
	cd modules/$(module) && uv run pytest tests/unit/ -v

# Run all module unit tests
test-modules: test-mcp-composer test-mcp-composer-app test-mcp-composer-client
	@echo "✅ All module unit tests completed"

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
	find . -type d -name "*.pytest*" -exec rm -rf {} +
	rm -rf .coverage dist/ build/ htmlcov/ .pytest_cache/ .mypy_cache/ modules/mcp_composer/dist/
	rm -rf modules/mcp_composer_app/dist/ modules/mcp_composer_client/dist/ modules/mcp_composer/.venv modules/mcp_composer/uv.lock

# PyPI Release Preparation
status:
	@echo "📦 Preparing release for mcp_composer..."
	@echo "📁 Python: $$(python --version)"
	@echo "📂 Virtualenv: $$(which python)"
	@echo "🔧 Uv: $$(uv --version)"

build:
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "❌ Usage: make build module=<module_name> version=<x.y.z>"; exit 1; \
	fi
	@set -e; \
	if git rev-parse "v$(version)" >/dev/null 2>&1; then \
	  echo "⚠️  Git tag v$(version) already exists; building from the tag..."; \
	  git fetch --tags --force --prune; \
	  prev_branch=$$(git rev-parse --abbrev-ref HEAD); \
	  git switch --detach "v$(version)"; \
	  ( cd modules/$(module) && uv sync && uv build --wheel . ); \
	  git switch "$$prev_branch" >/dev/null 2>&1 || git switch -; \
	else \
	  echo "🏷️  Creating git tag v$(version) on current HEAD..."; \
	  git tag -a "v$(version)" -m "$(module) $(version)"; \
	  ( cd modules/$(module) && uv sync && uv build --wheel . ); \
	fi
	@echo "✅ Wheel(s) for $(module) in modules/$(module)/dist/"

check-release:
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "❌ Usage: make check-release module=<module_name> version=<x.y.z>"; exit 1; \
	fi
	@if [ ! -d "modules/$(module)/dist" ]; then \
	  echo "❌ No dist/ directory found for $(module). Run 'make build module=$(module) version=$(version)' first."; \
	  exit 1; \
	fi
	@echo "✅ Checking build artifacts for $(module) v$(version)..."
	@( \
	  cd modules/$(module) && \
	  ARTS="$$(find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' \))"; \
	  if [ -z "$$ARTS" ]; then echo "❌ No files in dist/. Run 'make build …' first."; exit 1; fi; \
	  uv run twine check $$ARTS \
	)


upload-testpypi:
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "❌ Usage: make upload-testpypi module=<module_name> version=<x.y.z>"; exit 1; \
	fi
	@if [ -z "$$TEST_TWINE_USERNAME" ] || [ -z "$$TEST_TWINE_PASSWORD" ]; then \
	  echo "❌ Please export TEST_TWINE_USERNAME and TEST_TWINE_PASSWORD"; exit 1; \
	fi
	@$(MAKE) build module="$(module)" version="$(version)"
	@echo "🚀 Uploading $(module) v$(version) to TestPyPI..."
	@( \
	  cd modules/$(module) && \
	  ARTS="$$(find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' \))"; \
	  if [ -z "$$ARTS" ]; then echo "❌ No files in dist/."; exit 1; fi; \
	  TWINE_USERNAME=$$TEST_TWINE_USERNAME TWINE_PASSWORD=$$TEST_TWINE_PASSWORD \
	    uv run twine upload --repository testpypi $$ARTS \
	)

run-mcp-inspector-local:
	@echo "🔒 Running security checks with safety..."
	npx @modelcontextprotocol/inspector

upload-pypi:
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "❌ Usage: make upload-pypi module=<module_name> version=<x.y.z>"; exit 1; \
	fi
	@if [ -z "$$TWINE_USERNAME" ] || [ -z "$$TWINE_PASSWORD" ]; then \
	  echo "❌ Please export TWINE_USERNAME and TWINE_PASSWORD"; exit 1; \
	fi
	@$(MAKE) build module="$(module)" version="$(version)"
	@echo "🚀 Uploading $(module) v$(version) to PyPI..."
	@( \
	  cd modules/$(module) && \
	  ARTS="$$(find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' \))"; \
	  if [ -z "$$ARTS" ]; then echo "❌ No files in dist/."; exit 1; fi; \
	  TWINE_USERNAME=$$TWINE_USERNAME TWINE_PASSWORD=$$TWINE_PASSWORD \
	    uv run python -m twine upload --repository pypi $$ARTS \
	)

# Docker test target for CI/CD pipeline
docker-test:
	@echo "🧪 Running tests in Docker container..."
	@echo "Building test container with all dependencies..."
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f modules/mcp_composer/Dockerfile.test -t $(TEST_IMAGE_URI) modules/mcp_composer
	@echo "Running test suite in container..."
	$(BUILD_ENGINE) run --rm \
		-w /app \
		$(TEST_IMAGE_URI) \
		uv run pytest tests/unit/ -v --tb=short --ignore=tests/unit/test_oauth_callback.py
	@echo "✅ Docker test execution completed"

# Show help
help:

	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


	@echo ""
	@echo "🛠  Developer Tasks"
	@echo "  format       - Format code with black"
	@echo "  lint         - Lint code with ruff"
	@echo "  type-check   - Run type checks with mypy"
	@echo "  test         - Run tests with coverage"
	@echo "  test-module  - Run unit tests for specific module (module=<name>)"
	@echo "  test-modules - Run unit tests for all modules"
	@echo "  docker-test  - Run tests in Docker container (for CI/CD)"
	@echo "  coverage     - Generate coverage report"
	@echo "  check        - Run all checks in sequence"
	@echo "  clean        - Clean up generated files"
	@echo "  all          - Run all QA steps"
	@echo ""
	@echo "🚀 PyPI Release Tasks"
	@echo "  build        - Build wheel with uv (module=<name> version=<x.y.z>)"
	@echo "  check-release - Verify wheel with twine (module=<name>)"
	@echo "  upload-testpypi - Upload to TestPyPI (module=<name> version=<x.y.z>)"
	@echo "  upload-pypi  - Upload to PyPI (module=<name> version=<x.y.z>)"
	@echo "  status       - Show environment status"
	@echo ""
	@echo "📝 Examples:"
	@echo "  make build module=mcp_composer version=1.0.0"
	@echo "  make test-module module=mcp_composer"
	@echo "  make check-release module=mcp_composer"
	@echo "  make upload-testpypi module=mcp_composer version=1.0.0"
	@echo "  make upload-pypi module=mcp_composer version=1.0.0"

