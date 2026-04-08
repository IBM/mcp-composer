# Docker Guide for Optional Dependencies

## Overview
The optional dependency implementation is fully compatible with Docker. This guide explains how to build Docker images with the dependencies you need.

## Current Dockerfile Behavior

The current [`Dockerfile`](Dockerfile) at line 43 uses:
```dockerfile
RUN uv sync --locked --no-install-project --no-dev
```

With the new optional dependency structure:
- **Default**: Only core dependencies are installed (smaller image ~20MB)
- **To add features**: Specify extras during build

## Installation Options

### Option 1: Install All Optional Dependencies (Safest)
**Use case**: Existing deployments, want all features

**Modify line 43 in Dockerfile:**
```dockerfile
RUN uv sync --locked --no-install-project --no-dev --all-extras
```

**Pros**: 
- ✅ All features available
- ✅ No runtime surprises
- ✅ Simple change

**Cons**:
- ❌ Larger image size (~50MB)
- ❌ More dependencies to maintain

---

### Option 2: Install Specific Extras (Recommended)
**Use case**: Production deployments, know which features you need

**Modify line 43 in Dockerfile:**
```dockerfile
# For IBM Cloud + Databases + AI features
RUN uv sync --locked --no-install-project --no-dev \
    --extra ibm-cloud \
    --extra databases \
    --extra ai

# Or for minimal + specific features
RUN uv sync --locked --no-install-project --no-dev \
    --extra ibm-cloud \
    --extra databases
```

**Available extras:**
- `ibm-cloud` - IBM Cloud services (Cloudant, Secrets Manager)
- `databases` - PostgreSQL support
- `secrets` - HashiCorp Vault
- `ai` - AI/ML features (Google GenAI, LiteLLM, Ollama, scikit-learn)
- `a2a` - Agent-to-Agent SDK
- `search` - DuckDuckGo search
- `tracing` - OpenTelemetry tracing

**Pros**:
- ✅ Smaller image size
- ✅ Only install what you need
- ✅ Better security posture
- ✅ Explicit dependencies

**Cons**:
- ⚠️ Need to know which features you use

---

### Option 3: Use Build Args (Most Flexible)
**Use case**: Multiple deployment scenarios, CI/CD pipelines

**Add to Dockerfile (after line 7):**
```dockerfile
ARG INSTALL_EXTRAS="all"
```

**Replace line 43 with:**
```dockerfile
RUN if [ "$INSTALL_EXTRAS" = "all" ]; then \
      uv sync --locked --no-install-project --no-dev --all-extras; \
    elif [ "$INSTALL_EXTRAS" = "none" ]; then \
      uv sync --locked --no-install-project --no-dev; \
    else \
      EXTRAS_ARGS=""; \
      IFS=',' read -ra EXTRAS <<< "$INSTALL_EXTRAS"; \
      for extra in "${EXTRAS[@]}"; do \
        EXTRAS_ARGS="$EXTRAS_ARGS --extra $extra"; \
      done; \
      uv sync --locked --no-install-project --no-dev $EXTRAS_ARGS; \
    fi
```

**Build commands:**
```bash
# Install all extras
docker build --build-arg INSTALL_EXTRAS=all -t mcp-composer:full .

# Install only core (minimal)
docker build --build-arg INSTALL_EXTRAS=none -t mcp-composer:minimal .

# Install specific extras
docker build --build-arg INSTALL_EXTRAS="ibm-cloud,databases,ai" -t mcp-composer:custom .
```

**Pros**:
- ✅ Maximum flexibility
- ✅ Single Dockerfile for all scenarios
- ✅ Easy CI/CD integration
- ✅ Can build different images for different environments

**Cons**:
- ⚠️ More complex Dockerfile
- ⚠️ Need to remember build args

---

## Recommendations by Use Case

### For Solis Composer (Current Setup)
Since `solis_composer.py` likely uses IBM Cloud and AI features:

```dockerfile
RUN uv sync --locked --no-install-project --no-dev \
    --extra ibm-cloud \
    --extra databases \
    --extra ai
```

### For Development
```dockerfile
RUN uv sync --locked --no-install-project --no-dev --all-extras
```

### For Production (Minimal)
```dockerfile
# Only install what you actually use
RUN uv sync --locked --no-install-project --no-dev \
    --extra ibm-cloud \
    --extra databases
```

### For CI/CD
Use Option 3 with build args to create different images for different environments.

---

## Verifying Installed Dependencies

After building, you can verify which extras are installed:

```bash
# Run the container
docker run -it mcp-composer:latest bash

# Check installed packages
uv pip list

# Or use the new CLI command
uv run mcp-composer config check-dependencies
```

---

## Environment-Based Detection

The implementation includes automatic detection of required extras based on environment variables. Set these in your Docker environment:

```dockerfile
# In Dockerfile or docker-compose.yml
ENV CLOUDANT_URL=https://...
ENV POSTGRES_URL=postgresql://...
ENV GOOGLE_API_KEY=...
```

Then check what's needed:
```bash
docker run mcp-composer:latest uv run mcp-composer config check-dependencies
```

---

## Migration Path

### Existing Deployments
1. **No immediate action required** - Current Dockerfile will work
2. **To optimize**: Update to Option 2 with specific extras
3. **Test thoroughly** before deploying to production

### New Deployments
1. Start with Option 2 (specific extras)
2. Use environment detection to verify requirements
3. Adjust extras as needed

---

## Image Size Comparison

| Configuration | Estimated Size | Use Case |
|--------------|----------------|----------|
| Core only | ~20MB | Minimal, testing |
| Core + ibm-cloud + databases | ~35MB | Production (typical) |
| All extras | ~50MB | Development, full features |

---

## Troubleshooting

### Error: "Install with: pip install mcp-composer[xxx]"
**Cause**: Missing optional dependency
**Solution**: Add the required extra to your Dockerfile build

### Build fails with dependency conflicts
**Cause**: Lock file out of sync
**Solution**: Run `uv lock` locally and commit the updated lock file

### Runtime import errors
**Cause**: Feature used but extra not installed
**Solution**: Add the required extra to Dockerfile and rebuild

---

## Example Dockerfiles

### Minimal Production
```dockerfile
FROM ${BUILDER_IMAGE}:${TAG} AS builder
# ... (existing setup)
RUN uv sync --locked --no-install-project --no-dev \
    --extra ibm-cloud \
    --extra databases
```

### Full Development
```dockerfile
FROM ${BUILDER_IMAGE}:${TAG} AS builder
# ... (existing setup)
RUN uv sync --locked --no-install-project --no-dev --all-extras
```

### Flexible CI/CD
```dockerfile
ARG INSTALL_EXTRAS="ibm-cloud,databases,ai"
FROM ${BUILDER_IMAGE}:${TAG} AS builder
# ... (existing setup)
RUN EXTRAS_ARGS=""; \
    IFS=',' read -ra EXTRAS <<< "$INSTALL_EXTRAS"; \
    for extra in "${EXTRAS[@]}"; do \
      EXTRAS_ARGS="$EXTRAS_ARGS --extra $extra"; \
    done; \
    uv sync --locked --no-install-project --no-dev $EXTRAS_ARGS
```
