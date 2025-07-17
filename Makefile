.PHONY: docker-build docker-push help vars usage

REGISTRY_URL ?= icr.io
REGISTRY_NAMESPACE ?= automation-saas-platform
REGISTRY_IMAGE_TAG_SHORT ?= $(shell git rev-parse --abbrev-ref HEAD | sed 's/[^a-zA-Z0-9]/-/g')-$(shell git rev-parse --short HEAD)

ROOT_IMAGE_NAME = mcp-composer-root

ROOT_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(ROOT_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)

BUILD_ENGINE ?= docker
BUILD_ENGINE_ARGS ?= --platform linux/amd64


docker-build: docker-build-root

docker-push:
	$(BUILD_ENGINE) push $(ROOT_IMAGE_URI)

docker-build-root:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f Dockerfile -t $(ROOT_IMAGE_URI) .


help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

vars: 
	@$(foreach V, $(.VARIABLES), echo "$(V) = $($(V))";)

