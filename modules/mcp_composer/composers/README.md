# Solis Composer - ISV Token Authentication

Complete guide for setting up and running the Solis Composer with ISV Token Authentication.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Environment Variables](#environment-variables)
5. [Running the Composer](#running-the-composer)
6. [Authentication Flow](#authentication-flow)
7. [Troubleshooting](#troubleshooting)
8. [Security Best Practices](#security-best-practices)

## Overview

The Solis Composer uses **ISV Token Authentication**, a cookie-based authentication system for the IBM Solis platform. This authentication method:

- Validates session cookies from IBM Solis platform
- Exchanges cookies for ISV tokens via IBM's authentication endpoint
- Supports multiple environments (test, dev, prod)
- Includes token caching for performance
- Provides automatic token refresh

## Quick Start

### 1. Set Up Environment Variables (2 minutes)

Copy the example environment file:

```bash
cd modules/mcp_composer/composers
cp .env.isv.example .env
```

Edit `.env` and configure your ISV settings:

```bash
# Required: ISV Environment
ISV_ENVIRONMENT=test  # Options: test, dev, prod

# Optional: Override defaults
# ISV_COOKIE_NAME=mcsp-glb-iam-test
# ISV_ENDPOINT_URL=https://aws.login.test.saas.ibm.com/security/auth/isv/token

# Optional: Cache and timeout settings
ISV_CACHE_ENABLED=true
ISV_CACHE_TTL=7200
ISV_REQUEST_TIMEOUT=30.0
```

### 2. Run the Composer

```bash
# From the mcp-composer root directory
uv run composers/solis_composer.py
```

The composer will start on `http://0.0.0.0:9000/sse`

### 3. Test Authentication

```bash
# Get your session cookie from IBM Solis platform
COOKIE="your-session-cookie-value"

# Test the endpoint
curl -H "Cookie: mcsp-glb-iam-test=$COOKIE" \
     http://localhost:9000/sse/tools/list
```

## Configuration

### Environment-Based Configuration

The ISV Token Authentication system automatically configures itself based on the `ISV_ENVIRONMENT` setting:

| Environment | Cookie Name | Endpoint URL |
|------------|-------------|--------------|
| `test` | `mcsp-glb-iam-test` | `https://aws.login.test.saas.ibm.com/security/auth/isv/token` |
| `dev` | `mcsp-glb-iam-dev` | `https://aws.login.dev.saas.ibm.com/security/auth/isv/token` |
| `prod` | `mcsp-glb-iam-prod` | `https://aws.login.prod.saas.ibm.com/security/auth/isv/token` |

### Custom Configuration

You can override the auto-determined values:

```bash
# Override cookie name
ISV_COOKIE_NAME=my-custom-cookie

# Override endpoint URL
ISV_ENDPOINT_URL=https://custom.auth.endpoint.com/token
```

### Configuration Priority

The system uses this priority order:
1. **Direct parameters** (passed to ISVTokenVerifier constructor)
2. **Environment variables** (ISV_COOKIE_NAME, ISV_ENDPOINT_URL)
3. **Auto-determined** (based on ISV_ENVIRONMENT)

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ISV_ENVIRONMENT` | Target environment | `test`, `dev`, or `prod` |

### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ISV_COOKIE_NAME` | string | Auto-determined | Session cookie name |
| `ISV_ENDPOINT_URL` | string | Auto-determined | ISV token endpoint URL |
| `ISV_CACHE_ENABLED` | boolean | `true` | Enable token caching |
| `ISV_CACHE_TTL` | integer | `7200` | Cache TTL in seconds (2 hours) |
| `ISV_REQUEST_TIMEOUT` | float | `30.0` | Request timeout in seconds |

### Example Configurations

#### Test Environment (Default)

```bash
ISV_ENVIRONMENT=test
ISV_CACHE_ENABLED=true
ISV_CACHE_TTL=7200
ISV_REQUEST_TIMEOUT=30.0
```

#### Development Environment

```bash
ISV_ENVIRONMENT=dev
ISV_CACHE_ENABLED=true
ISV_CACHE_TTL=3600
ISV_REQUEST_TIMEOUT=30.0
```

#### Production Environment

```bash
ISV_ENVIRONMENT=prod
ISV_CACHE_ENABLED=true
ISV_CACHE_TTL=7200
ISV_REQUEST_TIMEOUT=60.0
```

## Running the Composer

### Standard Mode (SSE)

```bash
# From mcp-composer root directory
uv run composers/solis_composer.py
```

### With Custom Port

```bash
# Edit solis_composer.py and change the port in run_sse_mode()
# Default: port=9000
```

### With Debug Logging

```bash
# Set log level in solis_composer.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Authentication Flow

### 1. Client Request

Client sends request with session cookie:

```http
GET /sse/tools/list HTTP/1.1
Host: localhost:9000
Cookie: mcsp-glb-iam-test=your-session-cookie-value
```

### 2. Cookie Extraction

The ISV Token Validator extracts the cookie from:
- Standard `Cookie` header
- Custom header (e.g., `mcsp-glb-iam-test`)

### 3. Token Exchange

If not cached, the validator:
1. Sends cookie to ISV endpoint
2. Receives ISV token
3. Caches token (if caching enabled)

### 4. Token Validation

The validator:
1. Checks token expiration
2. Validates token structure
3. Creates authenticated user context

### 5. Request Processing

The composer processes the request with authenticated context.

## Troubleshooting

### Common Issues

#### 1. "ISVTokenVerifier object has no attribute 'get_routes'"

**Cause:** Using an older version of the ISV Token Validator

**Solution:** Ensure you're using the latest version with FastMCP integration:
```python
from mcp_composer.core.auth.jwt import ISVTokenVerifier
```

#### 2. "Cookie not found in request"

**Cause:** Cookie not sent or wrong cookie name

**Solutions:**
- Verify cookie name matches `ISV_COOKIE_NAME`
- Check cookie is sent in request headers
- Try sending cookie in custom header: `-H "mcsp-glb-iam-test: value"`

```bash
# Debug: Check what cookies are being sent
curl -v -H "Cookie: mcsp-glb-iam-test=$COOKIE" http://localhost:9000/sse/tools/list
```

#### 3. "Failed to exchange cookie for ISV token"

**Cause:** Invalid cookie or endpoint unreachable

**Solutions:**
- Verify cookie is valid and not expired
- Check endpoint URL is correct
- Ensure network connectivity to ISV endpoint
- Verify `ISV_ENVIRONMENT` matches your cookie's environment

```bash
# Test endpoint connectivity
curl -X POST https://aws.login.test.saas.ibm.com/security/auth/isv/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type": "urn:ibm:params:oauth:grant-type:isv-cookie", "session_cookie": "test"}'
```

#### 4. "Token expired"

**Cause:** Cached token expired

**Solutions:**
- Token will auto-refresh on next request
- Reduce `ISV_CACHE_TTL` if tokens expire frequently
- Disable caching: `ISV_CACHE_ENABLED=false`

#### 5. Environment Variables Not Loading

**Cause:** `.env` file not in correct location or not loaded

**Solutions:**
- Ensure `.env` is in `modules/mcp_composer/composers/` directory
- Check file permissions
- Verify variable names are correct (case-sensitive)

```bash
# Debug: Check if variables are loaded
python -c "import os; print(os.getenv('ISV_ENVIRONMENT'))"
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Verify Configuration

```python
from mcp_composer.core.auth.jwt import ISVTokenVerifier

verifier = ISVTokenVerifier(environment="test")
print(f"Cookie name: {verifier.validator.cookie_name}")
print(f"Endpoint: {verifier.validator.endpoint_url}")
print(f"Cache enabled: {verifier.validator.cache_enabled}")
```

## Security Best Practices

### 1. Use HTTPS in Production

```bash
# ✅ DO: Use HTTPS for production
ISV_ENVIRONMENT=prod
# Deploy behind HTTPS proxy/load balancer

# ❌ DON'T: Use HTTP for sensitive data
```

### 2. Secure Cookie Transmission

```bash
# ✅ DO: Ensure cookies are transmitted securely
# - Use Secure flag on cookies
# - Use HttpOnly flag
# - Use SameSite attribute

# ❌ DON'T: Send cookies over unencrypted connections
```

### 3. Enable Token Caching

```bash
# ✅ DO: Enable caching to reduce API calls
ISV_CACHE_ENABLED=true
ISV_CACHE_TTL=7200

# ❌ DON'T: Disable caching in production (performance impact)
```

### 4. Set Appropriate Timeouts

```bash
# ✅ DO: Set reasonable timeouts
ISV_REQUEST_TIMEOUT=30.0  # 30 seconds

# ❌ DON'T: Use very long timeouts (can cause resource exhaustion)
```

### 5. Environment Separation

```bash
# ✅ DO: Use separate environments
# Test: ISV_ENVIRONMENT=test
# Dev: ISV_ENVIRONMENT=dev
# Prod: ISV_ENVIRONMENT=prod

# ❌ DON'T: Mix environments or use test credentials in production
```

### 6. Monitor and Log

```bash
# ✅ DO: Monitor authentication failures
# - Track failed authentication attempts
# - Alert on unusual patterns
# - Log security events

# ❌ DON'T: Ignore authentication errors
```

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Solis Composer                          │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              ISVTokenVerifier                         │ │
│  │  (FastMCP Authentication Interface)                   │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │         ISVTokenValidator                       │ │ │
│  │  │  - Cookie extraction                            │ │ │
│  │  │  - Token exchange                               │ │ │
│  │  │  - Token caching                                │ │ │
│  │  │  - Token validation                             │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │         ISVAuthBackend                          │ │ │
│  │  │  - Request authentication                       │ │ │
│  │  │  - User context creation                        │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              MCPComposer                              │ │
│  │  - Tool management                                    │ │
│  │  - Resource management                                │ │
│  │  - Request routing                                    │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Authentication Middleware Stack

```
Request → AuthenticationMiddleware → AuthContextMiddleware → MCPComposer
          (validates token)          (sets user context)     (processes request)
```

## Related Documentation

- **[ISV Authentication Guide](../../docs/guide/isv_authentication.md)** - Detailed ISV authentication documentation
- **[Authentication Guide](../../docs/guide/authentication.md)** - All authentication methods
- **[Configuration Guide](../../docs/guide/configuration.md)** - General configuration options
- **[Environment File](.env.isv.example)** - ISV configuration template

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the ISV authentication guide
3. Check application logs for detailed error messages
4. Verify environment configuration