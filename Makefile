.PHONY: format lint type-check security quality test coverage clean clean-test clean-all help all check \
	status build check-release upload-testpypi upload-pypi \
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

all: format lint type-check security test coverage ## Run full QA suite

format: ## Format with black (module=mcp_composer)
	@if [ -z "$(module)" ]; then \
	  echo "Usage: make format module=<module_name>"; exit 1; \
	fi
	@if [ ! -d "modules/$(module)" ]; then \
	  echo "Module '$(module)' not found in modules/"; exit 1; \
	fi
	cd modules/$(module) && uv run black .

lint: ## Lint with ruff
	@mkdir -p ./chroes_output
	uv run ruff check . > ./chroes_output/ruff_output.txt

type-check: ## Type-check with mypy
	@mkdir -p ./chroes_output
	uv run mypy ./modules/mcp_composer/ > ./chroes_output/mypy_output.txt

security: ## Bandit security scan
	@mkdir -p ./chroes_output
	uv run bandit -r ./modules/mcp_composer/src -f txt -o ./chroes_output/bandit_output.txt || true

quality: ## Local Sonar-style scorecard (bandit + ruff; no SonarQube)
	@python3 scripts/quality_scorecard.py

test: ## Unit tests with coverage
	@mkdir -p ./chroes_output
	uv run coverage run -m pytest ./modules/mcp_composer/tests/unit/ > ./chroes_output/test_output.txt

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
	uv run coverage report -m

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

##@ Release

status: ## Show toolchain versions
	@echo "Python: $$(python3 --version 2>/dev/null || true)"
	@echo "Uv: $$(uv --version 2>/dev/null || true)"

build: ## Build wheel (module=mcp_composer version=x.y.z)
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "Usage: make build module=<module_name> version=<x.y.z>"; exit 1; \
	fi
	@set -e; \
	if git rev-parse "v$(version)" >/dev/null 2>&1; then \
	  echo "Tag v$(version) exists; building from tag..."; \
	  git fetch --tags --force --prune; \
	  prev_branch=$$(git rev-parse --abbrev-ref HEAD); \
	  git switch --detach "v$(version)"; \
	  ( cd modules/$(module) && uv sync && uv build --wheel . ); \
	  git switch "$$prev_branch" >/dev/null 2>&1 || git switch -; \
	else \
	  echo "Creating tag v$(version)..."; \
	  git tag -a "v$(version)" -m "$(module) $(version)"; \
	  ( cd modules/$(module) && uv sync && uv build --wheel . ); \
	fi
	@echo "Wheel(s) in modules/$(module)/dist/"

check-release: ## Twine check (module=mcp_composer version=x.y.z)
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "Usage: make check-release module=<module_name> version=<x.y.z>"; exit 1; \
	fi
	@if [ ! -d "modules/$(module)/dist" ]; then \
	  echo "No dist/ for $(module). Run make build first."; exit 1; \
	fi
	@( \
	  cd modules/$(module) && \
	  ARTS="$$(find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' \))"; \
	  if [ -z "$$ARTS" ]; then echo "No files in dist/."; exit 1; fi; \
	  uv run twine check $$ARTS \
	)

# Legacy local twine uploads. OSS / public releases must use GitHub Actions instead:
# tag mcp_composer-vX.Y.Z on github.com/IBM/mcp-composer, create a GitHub Release,
# and let .github/workflows/pypi.yml publish via trusted publishing.
upload-testpypi: ## (Legacy) Upload to TestPyPI via twine — prefer GitHub Actions pypi.yml
	@echo "Deprecated for OSS release: use GitHub Release + .github/workflows/pypi.yml on IBM/mcp-composer"
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "Usage: make upload-testpypi module=<name> version=<x.y.z>"; exit 1; \
	fi
	@if [ -z "$$TEST_TWINE_USERNAME" ] || [ -z "$$TEST_TWINE_PASSWORD" ]; then \
	  echo "Export TEST_TWINE_USERNAME and TEST_TWINE_PASSWORD"; exit 1; \
	fi
	@$(MAKE) build module="$(module)" version="$(version)"
	@( \
	  cd modules/$(module) && \
	  ARTS="$$(find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' \))"; \
	  TWINE_USERNAME=$$TEST_TWINE_USERNAME TWINE_PASSWORD=$$TEST_TWINE_PASSWORD \
	    uv run twine upload --repository testpypi $$ARTS \
	)

upload-pypi: ## (Legacy) Upload to PyPI via twine — prefer GitHub Actions pypi.yml
	@echo "Deprecated for OSS release: use GitHub Release + .github/workflows/pypi.yml on IBM/mcp-composer"
	@if [ -z "$(module)" ] || [ -z "$(version)" ]; then \
	  echo "Usage: make upload-pypi module=<name> version=<x.y.z>"; exit 1; \
	fi
	@if [ -z "$$TWINE_USERNAME" ] || [ -z "$$TWINE_PASSWORD" ]; then \
	  echo "Export TWINE_USERNAME and TWINE_PASSWORD"; exit 1; \
	fi
	@$(MAKE) build module="$(module)" version="$(version)"
	@( \
	  cd modules/$(module) && \
	  ARTS="$$(find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' \))"; \
	  TWINE_USERNAME=$$TWINE_USERNAME TWINE_PASSWORD=$$TWINE_PASSWORD \
	    uv run python -m twine upload --repository pypi $$ARTS \
	)

run-mcp-inspector-local: ## Launch MCP Inspector
	npx @modelcontextprotocol/inspector

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make format module=mcp_composer"
	@echo "  make test-module module=mcp_composer"
	@echo "  make docker-build IMAGE_URI=ghcr.io/you/mcp-composer:dev"
	@echo "  make build module=mcp_composer version=0.1.1"
