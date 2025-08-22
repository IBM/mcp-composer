.PHONY: docker-build docker-push help vars usage

REGISTRY_URL ?= icr.io
REGISTRY_NAMESPACE ?= automation-saas-platform
REGISTRY_IMAGE_TAG_SHORT ?= $(shell git rev-parse --abbrev-ref HEAD | sed 's/[^a-zA-Z0-9]/-/g')-$(shell git rev-parse --short HEAD)

ROOT_IMAGE_NAME = mcp-composer-root
SRC_APP_IMAGE_NAME = mcp-composer-app
SRC_CLIENT_IMAGE_NAME = mcp-composer-client

ROOT_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(ROOT_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)
SRC_APP_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(SRC_APP_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)
SRC_CLIENT_IMAGE_URI = $(REGISTRY_URL)/$(REGISTRY_NAMESPACE)/$(SRC_CLIENT_IMAGE_NAME):$(REGISTRY_IMAGE_TAG_SHORT)

BUILD_ENGINE ?= docker
BUILD_ENGINE_ARGS ?= --platform linux/amd64


docker-build: docker-build-root docker-build-app

docker-push:
	$(BUILD_ENGINE) push $(ROOT_IMAGE_URI)
	$(BUILD_ENGINE) push $(SRC_APP_IMAGE_URI)
# 	$(BUILD_ENGINE) push $(SRC_CLIENT_IMAGE_URI)

docker-build-root:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f Dockerfile -t $(ROOT_IMAGE_URI) .

docker-build-app:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f Dockerfile-Composer-App -t $(SRC_APP_IMAGE_URI) .

docker-build-client:
	$(BUILD_ENGINE) build $(BUILD_ENGINE_ARGS) $(BUILD_ARGS) $(DREADNOUGHT_DOCKER_BUILD_ARGS) \
		-f Dockerfile_Client -t $(SRC_CLIENT_IMAGE_URI) .

# Deploy the CI build to https://github.ibm.com/automation-paas-cd-pipeline/mcp-composer-cd
.PHONY: post-deploy
post-deploy:
	@echo "export GIT_REPO=mcp-composer-cd”
	@echo "export GIT_COMMITTER=\"CI/CD Functional ID <saas-ci1@ibm.com>\""
	@echo "export GIT_BRANCH=dev”
	@echo "export GIT_ORG=automation-paas-cd-pipeline"
	@echo "export PULL_REQUEST_ASSIGNEE=autopaas"
	@echo "export PROMOTION_ENV=development"
	@echo "export ENABLE_DEV_HEAD_USE=true"
	@echo "export GIT_TOKEN=$(GIT_TOKEN)"
	@echo "export PROMOTION_ENV_APP_SET=application-sets/aws-dev/us-east-1/application-set.yaml"
	@echo "export DEVELOPMENT_ENV_APP_SET=application-sets/aws-dev/us-east-1/application-set.yaml"	
	@echo "export REPLACEMENTS=\"resources/values.yaml config.imageTag.app,$(REGISTRY_IMAGE_TAG_SHORT);resources/values.yaml config.imageTag.client,$(REGISTRY_IMAGE_TAG_SHORT);resources/values.yaml config.imageTag.root,$(REGISTRY_IMAGE_TAG_SHORT)\""


help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

vars: 
	@$(foreach V, $(.VARIABLES), echo "$(V) = $($(V))";)

