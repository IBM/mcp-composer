.PHONY: format lint type-check security quality test coverage clean clean-test clean-all help all check \
	status build \
	docker-build docker-push docker-test vars

# Generic local/registry image names (override as needed)
IMAGE_NAME ?= mcp-composer
IMAGE_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)
IMAGE_URI ?= $(IMAGE_NAME):$(IMAGE_TAG)
TEST_IMAGE_URI ?= mcp-composer-test

BUILD_ENGINE ?= docker
BUILD_ENGINE_ARGS ?=

##@ Docker

docker-build: ## Build the runtime image from modules/mcp_composer/Dockerfile
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) \
		-f modules/mcp_composer/Dockerfile -t $(IMAGE_URI) modules/mcp_composer

docker-build-local: ## Build the local-dev image from Dockerfile.local
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) \
		-f modules/mcp_composer/Dockerfile.local -t $(IMAGE_NAME):dev modules/mcp_composer

docker-push: ## Push IMAGE_URI (set IMAGE_URI=registry/name:tag)
	$(BUILD_ENGINE) push $(IMAGE_URI)

docker-test: ## Run unit tests inside a container built from Dockerfile.local
	@echo "Building test container..."
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) \
		-f modules/mcp_composer/Dockerfile.local -t $(TEST_IMAGE_URI) modules/mcp_composer
	@echo "Running unit tests..."
	$(BUILD_ENGINE) run --rm -w /app $(TEST_IMAGE_URI) \
		uv run pytest tests/unit/ -v --tb=short
	@$(MAKE) clean-test

vars:
	@$(foreach V, $(.VARIABLES), echo "$(V) = $($(V))";)

##@ QA

# QA runs inside the package uv environment. Override with MODULE= or module=.
MODULE ?= mcp_composer
ifdef module
MODULE := $(module)
endif
MODULE_DIR := modules/$(MODULE)

all: format lint type-check security test coverage ## Run full QA suite

_check-module:
	@if [ ! -d "$(MODULE_DIR)" ]; then \
	  echo "Module '$(MODULE)' not found at $(MODULE_DIR)"; exit 1; \
	fi

format: _check-module ## Format with black (MODULE=mcp_composer)
	@mkdir -p ./chroes_output
	cd $(MODULE_DIR) && uv run black .

lint: _check-module ## Lint with ruff inside the module environment
	@mkdir -p ./chroes_output
	cd $(MODULE_DIR) && uv run ruff check src tests composers > ../../chroes_output/ruff_output.txt

type-check: _check-module ## Type-check with mypy inside the module environment
	@mkdir -p ./chroes_output
	cd $(MODULE_DIR) && uv run mypy src/mcp_composer > ../../chroes_output/mypy_output.txt

security: _check-module ## Bandit security scan inside the module environment
	@mkdir -p ./chroes_output
	cd $(MODULE_DIR) && uv run bandit -r src -f txt -o ../../chroes_output/bandit_output.txt || true

quality: ## Local Sonar-style scorecard (bandit + ruff; no SonarQube)
	@python3 scripts/quality_scorecard.py

test: _check-module ## Unit tests with coverage, isolated from a developer .env
	@mkdir -p ./chroes_output
	cd $(MODULE_DIR) && uv run coverage run -m pytest tests/unit/ > ../../chroes_output/test_output.txt

test-with-cleanup: test ## Tests then clean artifacts
	@$(MAKE) clean-test

test-module: ## Unit tests for one module (module=mcp_composer)
	@if [ -z "$(module)" ]; then \
	  echo "Usage: make test-module module=<module_name>"; exit 1; \
	fi
	@if [ ! -d "modules/$(module)" ]; then \
	  echo "Module '$(module)' not found in modules/"; exit 1; \
	fi
	cd modules/$(module) && uv run pytest tests/unit/ -v

coverage: test ## Coverage report
	cd $(MODULE_DIR) && uv run coverage report -m

check: format lint type-check security test coverage ## Alias for full QA

clean-test: ## Remove test artifacts
	@rm -rf .coverage htmlcov/ .pytest_cache/
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name ".coverage.*" -delete 2>/dev/null || true
	@rm -rf ./chroes_output/ 2>/dev/null || true
	@rm -rf modules/*/htmlcov/ modules/*/.coverage modules/*/.pytest_cache/ 2>/dev/null || true

clean: ## Remove build/cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage dist/ build/ htmlcov/ .pytest_cache/ .mypy_cache/ modules/mcp_composer/dist/

clean-all: clean clean-test ## Full cleanup

##@ Build

status: ## Show toolchain versions
	@echo "Python: $$(python3 --version 2>/dev/null || true)"
	@echo "Uv: $$(uv --version 2>/dev/null || true)"

# Local sync/build only. Publishing is not a Make target.
# Cut a GitHub Release (tag mcp_composer-vX.Y.Z) on github.com/IBM/mcp-composer;
# .github/workflows/pypi.yml publishes to PyPI on release: published.
build: ## Sync deps and build wheel/sdist locally (does not publish)
	@module=$${module:-mcp_composer}; \
	if [ ! -d "modules/$$module" ]; then \
	  echo "Module '$$module' not found in modules/"; exit 1; \
	fi; \
	cd modules/$$module && uv sync --group dev && uv build
	@echo "Artifacts in modules/$${module:-mcp_composer}/dist/ — publish via GitHub Release, not Make"

run-mcp-inspector-local: ## Launch MCP Inspector
	npx @modelcontextprotocol/inspector

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make format"
	@echo "  make lint MODULE=mcp_composer"
	@echo "  make test-module module=mcp_composer"
	@echo "  make build"
	@echo "  make docker-build IMAGE_URI=ghcr.io/you/mcp-composer:dev"
	@echo ""
	@echo "Publish: create a GitHub Release for tag mcp_composer-vX.Y.Z on IBM/mcp-composer"
	@echo "         (triggers .github/workflows/pypi.yml). No make upload-* targets."
