# JWT Authentication Comprehensive Setup Guide

Complete guide for setting up JWT authentication in MCP Composer with dynamic environment variable prefixes.

## Table of Contents

1. [Overview](#overview)
2. [Dynamic Prefix System](#dynamic-prefix-system)
3. [Configuration Methods](#configuration-methods)
4. [Environment Variables](#environment-variables)
5. [Code Examples](#code-examples)
6. [Security Best Practices](#security-best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Topics](#advanced-topics)

## Overview

The JWT authentication module provides secure, stateless authentication for MCP Composer applications. It supports:

- **Dynamic environment variable prefixes** for multi-application deployments
- Multiple JWT algorithms (HS256, RS256, ES256, etc.)
- Token validation (signature, expiration, issuer, audience)
- JWKS endpoint support for automatic key rotation
- Comprehensive error handling

## Dynamic Prefix System

### Why Dynamic Prefixes?

Dynamic prefixes allow you to:
- Run multiple applications with different JWT configurations
- Separate development, staging, and production environments
- Avoid environment variable conflicts
- Maintain clean, organized configuration

### How It Works

Instead of hardcoding environment variable names like `SOLIS_JWT_SECRET`, you specify a prefix:

```python
# Load with default "JWT_" prefix
config = JWTConfig.from_env(prefix="JWT_")

# Load with custom "MYAPP_JWT_" prefix
config = JWTConfig.from_env(prefix="MYAPP_JWT_")

# Load with environment-specific "PROD_JWT_" prefix
config = JWTConfig.from_env(prefix="PROD_JWT_")
```

The module automatically looks for variables like:
- `{PREFIX}SECRET`
- `{PREFIX}ALGORITHM`
- `{PREFIX}ISSUER`
- etc.

## Configuration Methods

### Method 1: Direct Secret/Key (Simplest)

Use `{PREFIX}SECRET` for direct PEM content or secret key:

```bash
# For default prefix
export JWT_SECRET="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

# For custom prefix
export MYAPP_JWT_SECRET="your-public-key-here"
```

```python
from mcp_composer.core.auth.jwt import JWTAuthProvider, JWTConfig

# Load with default prefix
jwt_provider = JWTAuthProvider.from_env()

# Load with custom prefix
config = JWTConfig.from_env(prefix="MYAPP_JWT_")
jwt_provider = JWTAuthProvider(config=config)
```

### Method 2: Full Environment Configuration

Set all JWT parameters with your chosen prefix:

```bash
# Using "MYAPP_JWT_" prefix
export MYAPP_JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----..."
export MYAPP_JWT_ALGORITHM="RS256"
export MYAPP_JWT_ISSUER="https://auth.myapp.com"
export MYAPP_JWT_AUDIENCE="myapp-api"
export MYAPP_JWT_VERIFY_EXP="true"
export MYAPP_JWT_VERIFY_ISS="true"
export MYAPP_JWT_VERIFY_AUD="true"
```

```python
config = JWTConfig.from_env(prefix="MYAPP_JWT_")
jwt_provider = JWTAuthProvider(config=config)
```

### Method 3: JWKS Endpoint

Use JWKS for automatic key rotation:

```bash
export MYAPP_JWT_JWKS_URI="https://auth.myapp.com/.well-known/jwks.json"
export MYAPP_JWT_ISSUER="https://auth.myapp.com"
export MYAPP_JWT_AUDIENCE="myapp-api"
export MYAPP_JWT_ALGORITHM="RS256"
```

### Method 4: Programmatic Configuration

Configure directly in code:

```python
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

config = JWTConfig(
    public_key=open("public_key.pem").read(),
    algorithm="RS256",
    issuer="https://auth.example.com",
    audience="my-api",
    verify_exp=True,
    verify_iss=True,
    verify_aud=True
)

jwt_provider = JWTAuthProvider(config=config)
```

## Environment Variables

### Complete Variable List

For any prefix `{PREFIX}`, these variables are supported:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `{PREFIX}SECRET` | string | None | Secret key or PEM public key content |
| `{PREFIX}PUBLIC_KEY` | string | None | Public key for RSA/ECDSA algorithms |
| `{PREFIX}ALGORITHM` | string | "HS256" | JWT signing algorithm |
| `{PREFIX}ISSUER` | string | None | Expected token issuer (iss claim) |
| `{PREFIX}AUDIENCE` | string | None | Expected token audience (aud claim) |
| `{PREFIX}VERIFY_EXP` | boolean | true | Verify token expiration |
| `{PREFIX}VERIFY_ISS` | boolean | false | Verify token issuer |
| `{PREFIX}VERIFY_AUD` | boolean | false | Verify token audience |
| `{PREFIX}VERIFY_SIGNATURE` | boolean | true | Verify token signature |
| `{PREFIX}JWKS_URI` | string | None | JWKS endpoint URL |
| `{PREFIX}REQUIRED_SCOPES` | string | "" | Comma-separated required scopes |
| `{PREFIX}LEEWAY` | integer | 0 | Clock skew tolerance (seconds) |

### Example Configurations

#### Development Environment

```bash
# Using "DEV_JWT_" prefix
export DEV_JWT_SECRET="dev-secret-key-change-in-production"
export DEV_JWT_ALGORITHM="HS256"
export DEV_JWT_VERIFY_EXP="false"  # Relaxed for development
```

#### Staging Environment

```bash
# Using "STG_JWT_" prefix
export STG_JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----..."
export STG_JWT_ALGORITHM="RS256"
export STG_JWT_ISSUER="https://auth-stg.example.com"
export STG_JWT_AUDIENCE="staging-api"
export STG_JWT_VERIFY_EXP="true"
export STG_JWT_VERIFY_ISS="true"
```

#### Production Environment

```bash
# Using "PROD_JWT_" prefix
export PROD_JWT_JWKS_URI="https://auth.example.com/.well-known/jwks.json"
export PROD_JWT_ISSUER="https://auth.example.com"
export PROD_JWT_AUDIENCE="production-api"
export PROD_JWT_ALGORITHM="RS256"
export PROD_JWT_VERIFY_EXP="true"
export PROD_JWT_VERIFY_ISS="true"
export PROD_JWT_VERIFY_AUD="true"
export PROD_JWT_REQUIRED_SCOPES="read,write,admin"
```

## Code Examples

### Example 1: Single Application with Default Prefix

```python
from mcp_composer import MCPComposer
from mcp_composer.core.auth.jwt import JWTAuthProvider

# Environment: JWT_SECRET, JWT_ALGORITHM, etc.
jwt_provider = JWTAuthProvider.from_env()

composer = MCPComposer(
    name="my-app",
    auth=jwt_provider.verifier
)

await composer.run_http_async(host="0.0.0.0", port=9000)
```

### Example 2: Multiple Applications with Different Prefixes

```python
from mcp_composer import MCPComposer
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

# App 1: Using "APP1_JWT_" prefix
app1_config = JWTConfig.from_env(prefix="APP1_JWT_")
app1_jwt = JWTAuthProvider(config=app1_config)
app1_composer = MCPComposer("app1", auth=app1_jwt.verifier)

# App 2: Using "APP2_JWT_" prefix
app2_config = JWTConfig.from_env(prefix="APP2_JWT_")
app2_jwt = JWTAuthProvider(config=app2_config)
app2_composer = MCPComposer("app2", auth=app2_jwt.verifier)

# Run on different ports
await app1_composer.run_http_async(port=9001)
await app2_composer.run_http_async(port=9002)
```

### Example 3: Environment-Specific Configuration

```python
import os
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

# Determine environment
env = os.getenv("ENVIRONMENT", "development")

# Load appropriate configuration
if env == "development":
    prefix = "DEV_JWT_"
elif env == "staging":
    prefix = "STG_JWT_"
elif env == "production":
    prefix = "PROD_JWT_"
else:
    raise ValueError(f"Unknown environment: {env}")

# Load JWT config with environment-specific prefix
config = JWTConfig.from_env(prefix=prefix)
jwt_provider = JWTAuthProvider(config=config)

composer = MCPComposer(f"{env}-app", auth=jwt_provider.verifier)
```

### Example 4: Custom Composer with Configurable Prefix

```python
def create_secure_composer(name: str, jwt_prefix: str = "JWT_"):
    """
    Create a composer with JWT authentication using custom prefix.
    
    Args:
        name: Composer name
        jwt_prefix: Environment variable prefix (default: "JWT_")
    
    Returns:
        Configured MCPComposer instance
    """
    from mcp_composer import MCPComposer
    from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider
    
    # Load JWT configuration with specified prefix
    jwt_config = JWTConfig.from_env(prefix=jwt_prefix)
    jwt_provider = JWTAuthProvider(config=jwt_config)
    
    # Create and return composer
    return MCPComposer(name=name, auth=jwt_provider.verifier)

# Usage
solis_composer = create_secure_composer("solis", jwt_prefix="SOLIS_JWT_")
custom_composer = create_secure_composer("custom", jwt_prefix="CUSTOM_JWT_")
```

## Security Best Practices

### 1. Use Strong Algorithms

```bash
# ✅ DO: Use RS256 or ES256 for production
export PROD_JWT_ALGORITHM="RS256"

# ❌ DON'T: Use HS256 for public APIs (symmetric key)
```

### 2. Always Validate Tokens

```bash
# ✅ DO: Enable all validations in production
export PROD_JWT_VERIFY_EXP="true"
export PROD_JWT_VERIFY_ISS="true"
export PROD_JWT_VERIFY_AUD="true"
export PROD_JWT_VERIFY_SIGNATURE="true"

# ❌ DON'T: Disable validations in production
```

### 3. Use Environment-Specific Prefixes

```bash
# ✅ DO: Separate environments with prefixes
export DEV_JWT_SECRET="dev-key"
export PROD_JWT_SECRET="prod-key"

# ❌ DON'T: Mix environments without prefixes
export JWT_SECRET="shared-key"  # Dangerous!
```

### 4. Rotate Keys Regularly

```bash
# ✅ DO: Use JWKS for automatic rotation
export PROD_JWT_JWKS_URI="https://auth.example.com/.well-known/jwks.json"

# ❌ DON'T: Use static keys indefinitely
```

### 5. Require Specific Scopes

```bash
# ✅ DO: Limit access with scopes
export PROD_JWT_REQUIRED_SCOPES="read,write,admin"

# ❌ DON'T: Allow any token without scope validation
```

### 6. Use HTTPS Only

```bash
# ✅ DO: Ensure HTTPS for token transmission
# ❌ DON'T: Send tokens over HTTP
```

## Troubleshooting

### Common Issues

#### 1. Token Validation Fails

**Symptom:** "Invalid signature" or "Token verification failed"

**Solutions:**
- Verify public key matches the token's signing key
- Check algorithm matches (RS256, HS256, etc.)
- Ensure issuer and audience match token claims

```bash
# Debug: Check your token claims
python -c "
import jwt
token = 'your-token-here'
print(jwt.decode(token, options={'verify_signature': False}))
"
```

#### 2. Environment Variables Not Loading

**Symptom:** "Either secret or public_key must be provided"

**Solutions:**
- Check prefix matches exactly (case-sensitive)
- Verify underscore at end of prefix
- Use quotes for multi-line PEM keys

```bash
# ✅ Correct
export MYAPP_JWT_SECRET="key"

# ❌ Wrong (missing underscore)
export MYAPPJWT_SECRET="key"

# ❌ Wrong (case mismatch)
export myapp_jwt_secret="key"
```

#### 3. JWKS Endpoint Issues

**Symptom:** "Failed to fetch JWKS" or "Key not found"

**Solutions:**
- Verify JWKS URL is accessible
- Check network connectivity
- Ensure correct key ID (kid) in token header

```bash
# Test JWKS endpoint
curl https://auth.example.com/.well-known/jwks.json
```

#### 4. Clock Skew Issues

**Symptom:** "Token expired" but token should be valid

**Solution:** Add leeway for clock skew

```bash
export PROD_JWT_LEEWAY="30"  # 30 seconds tolerance
```

### Diagnostic Tools

#### Check Token Contents

```python
from mcp_composer.core.auth.jwt import decode_jwt_token

token = "your-jwt-token"
payload = decode_jwt_token(token, verify=False)
print(f"Issuer: {payload.get('iss')}")
print(f"Audience: {payload.get('aud')}")
print(f"Expiration: {payload.get('exp')}")
print(f"Scopes: {payload.get('scope')}")
```

#### Validate Configuration

```python
from mcp_composer.core.auth.jwt import JWTConfig

try:
    config = JWTConfig.from_env(prefix="MYAPP_JWT_")
    print("✅ Configuration loaded successfully")
    print(f"Algorithm: {config.algorithm}")
    print(f"Issuer: {config.issuer}")
    print(f"Audience: {config.audience}")
except Exception as e:
    print(f"❌ Configuration error: {e}")
```

## Advanced Topics

### Custom Token Extraction

```python
from mcp_composer.core.auth.jwt import JWTConfig

config = JWTConfig(
    secret="your-secret",
    header_name="X-Custom-Auth",  # Custom header
    header_prefix="Token"  # Custom prefix
)
```

### Multi-Tenant Support

```python
def get_jwt_provider_for_tenant(tenant_id: str):
    """Get JWT provider for specific tenant."""
    prefix = f"{tenant_id.upper()}_JWT_"
    config = JWTConfig.from_env(prefix=prefix)
    return JWTAuthProvider(config=config)

# Usage
tenant1_jwt = get_jwt_provider_for_tenant("tenant1")
tenant2_jwt = get_jwt_provider_for_tenant("tenant2")
```

### Dynamic Key Loading

```python
import os
from mcp_composer.core.auth.jwt import JWTAuthProvider

# Load key from file or environment
public_key = os.getenv("JWT_PUBLIC_KEY")
if not public_key and os.path.exists("public_key.pem"):
    with open("public_key.pem") as f:
        public_key = f.read()

jwt_provider = JWTAuthProvider.from_public_key(
    public_key=public_key,
    algorithm="RS256"
)
```

## Next Steps

- **[Quick Start Guide](QUICK_START_JWT.md)** - Get started in 2 minutes
- **[JWT Module README](../src/mcp_composer/core/auth/jwt/README.md)** - Technical API documentation
- **[Authentication Guide](../../docs/guide/authentication.md)** - All authentication methods
- **[Security Best Practices](../../docs/guide/authentication.md#security-best-practices)** - Production security

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the JWT module README
3. Check application logs for detailed error messages
4. Consult the main authentication guide