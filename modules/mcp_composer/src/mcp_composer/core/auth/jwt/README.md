# JWT Authentication Module

This module provides JWT (JSON Web Token) authentication support for MCP Composer using FastMCP's built-in `JWTVerifier`.

## Overview

The JWT authentication module offers a clean, configurable interface for securing your MCP Composer applications with JWT tokens. It wraps FastMCP's `JWTVerifier` with additional configuration management and utility functions.

## Features

- ✅ **Multiple Algorithms**: Support for HS256, RS256, ES256, and more
- ✅ **Flexible Configuration**: Environment variables or code-based setup
- ✅ **Comprehensive Validation**: Signature, expiration, issuer, audience
- ✅ **Easy Integration**: Simple API for MCP Composer
- ✅ **Utility Functions**: Token extraction, decoding, generation
- ✅ **Production Ready**: Security best practices built-in

## Quick Start

### 1. Basic Usage with Secret Key

```python
from mcp_composer import MCPComposer
from mcp_composer.core.auth.jwt import JWTAuthProvider

# Create JWT provider with secret
jwt_provider = JWTAuthProvider.from_secret(
    secret="your-secret-key",
    algorithm="HS256",
    verify_exp=True
)

# Initialize composer with JWT auth
composer = MCPComposer("my-app", auth=jwt_provider.get_verifier())
```

### 2. Load from Environment Variables (with Dynamic Prefix)

```python
from mcp_composer.core.auth.jwt import JWTAuthProvider, JWTConfig

# Set environment variables with default "JWT_" prefix
# JWT_SECRET=your-secret-key
# JWT_ALGORITHM=HS256
# JWT_VERIFY_EXP=true

# Load configuration from environment with default prefix
jwt_provider = JWTAuthProvider.from_env()
composer = MCPComposer("my-app", auth=jwt_provider.get_verifier())

# OR use custom prefix for different applications
# MYAPP_JWT_SECRET=myapp-secret
# MYAPP_JWT_ALGORITHM=RS256

config = JWTConfig.from_env(prefix="MYAPP_JWT_")
jwt_provider = JWTAuthProvider(config=config)
composer = MCPComposer("my-app", auth=jwt_provider.get_verifier())
```

### 3. Advanced Configuration

```python
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

# Create detailed configuration
config = JWTConfig(
    secret="your-secret-key",
    algorithm="HS256",
    issuer="https://auth.example.com",
    audience="my-api",
    verify_exp=True,
    verify_iss=True,
    verify_aud=True,
    required_claims=["sub", "role", "tenant"],
    leeway=30  # 30 seconds clock skew tolerance
)

jwt_provider = JWTAuthProvider(config=config)
composer = MCPComposer("my-app", auth=jwt_provider.get_verifier())
```

## Configuration

### JWTConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `secret` | `str` | `None` | Secret key for HMAC algorithms (HS256, HS384, HS512) |
| `public_key` | `str` | `None` | Public key for RSA/ECDSA algorithms (RS256, ES256, PS256) |
| `algorithm` | `str` | `"HS256"` | JWT signing algorithm |
| `issuer` | `str` | `None` | Expected token issuer (iss claim) |
| `audience` | `str` | `None` | Expected token audience (aud claim) |
| `verify_exp` | `bool` | `True` | Verify token expiration |
| `verify_iss` | `bool` | `False` | Verify token issuer |
| `verify_aud` | `bool` | `False` | Verify token audience |
| `verify_signature` | `bool` | `True` | Verify token signature |
| `header_name` | `str` | `"Authorization"` | HTTP header containing JWT |
| `header_prefix` | `str` | `"Bearer"` | Token prefix in header |
| `required_claims` | `List[str]` | `[]` | List of required claims |
| `leeway` | `int` | `0` | Leeway in seconds for time validation |

### Environment Variables with Dynamic Prefixes

The JWT module supports **dynamic environment variable prefixes**, allowing you to configure different JWT settings for different applications or environments.

When using `JWTConfig.from_env(prefix="YOUR_PREFIX_")`, the following environment variables are supported:

```bash
# Example 1: Default "JWT_" prefix
JWT_SECRET=your-secret-key
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...
JWT_ALGORITHM=HS256
JWT_ISSUER=https://auth.example.com
JWT_AUDIENCE=my-api
JWT_VERIFY_EXP=true
JWT_VERIFY_ISS=true
JWT_VERIFY_AUD=true
JWT_VERIFY_SIGNATURE=true
JWT_HEADER_NAME=Authorization
JWT_HEADER_PREFIX=Bearer
JWT_REQUIRED_CLAIMS=sub,role,tenant
JWT_LEEWAY=30

# Example 2: Custom "MYAPP_JWT_" prefix
MYAPP_JWT_SECRET=myapp-secret-key
MYAPP_JWT_ALGORITHM=RS256
MYAPP_JWT_ISSUER=https://myapp.example.com
MYAPP_JWT_AUDIENCE=myapp-api

# Example 3: Environment-specific "PROD_JWT_" prefix
PROD_JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...
PROD_JWT_ALGORITHM=RS256
PROD_JWT_ISSUER=https://auth.production.com
PROD_JWT_AUDIENCE=prod-api
```

**Usage with Custom Prefixes:**

```python
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

# Load with default prefix
default_config = JWTConfig.from_env(prefix="JWT_")

# Load with custom prefix
myapp_config = JWTConfig.from_env(prefix="MYAPP_JWT_")

# Load with environment-specific prefix
prod_config = JWTConfig.from_env(prefix="PROD_JWT_")

# Create providers
default_provider = JWTAuthProvider(config=default_config)
myapp_provider = JWTAuthProvider(config=myapp_config)
prod_provider = JWTAuthProvider(config=prod_config)
```

## Supported Algorithms

### HMAC (Symmetric)
- **HS256**: HMAC with SHA-256 (recommended for development)
- **HS384**: HMAC with SHA-384
- **HS512**: HMAC with SHA-512

### RSA (Asymmetric)
- **RS256**: RSA with SHA-256 (recommended for production)
- **RS384**: RSA with SHA-384
- **RS512**: RSA with SHA-512

### ECDSA (Asymmetric)
- **ES256**: ECDSA with SHA-256
- **ES384**: ECDSA with SHA-384
- **ES512**: ECDSA with SHA-512

### RSA-PSS (Asymmetric)
- **PS256**: RSA-PSS with SHA-256
- **PS384**: RSA-PSS with SHA-384
- **PS512**: RSA-PSS with SHA-512

## Usage Examples

### Example 1: Development Setup (HS256)

```python
from mcp_composer import MCPComposer
from mcp_composer.core.auth.jwt import JWTAuthProvider

# Simple setup for development
jwt_provider = JWTAuthProvider.from_secret(
    secret="dev-secret-change-in-production",
    algorithm="HS256",
    verify_exp=False  # Relaxed for development
)

composer = MCPComposer("dev-app", auth=jwt_provider.get_verifier())
```

### Example 2: Production Setup (RS256)

```python
import os
from mcp_composer.core.auth.jwt import JWTAuthProvider

# Load public key from file or environment
public_key = os.getenv("JWT_PUBLIC_KEY") or open("public_key.pem").read()

jwt_provider = JWTAuthProvider.from_public_key(
    public_key=public_key,
    algorithm="RS256",
    issuer="https://auth.production.com",
    audience="production-api",
    verify_exp=True,
    verify_iss=True,
    verify_aud=True
)

composer = MCPComposer("prod-app", auth=jwt_provider.get_verifier())
```

### Example 3: Multi-Tenant Setup

```python
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

config = JWTConfig(
    secret=os.getenv("JWT_SECRET"),
    algorithm="HS256",
    issuer="https://auth.example.com",
    verify_exp=True,
    verify_iss=True,
    required_claims=["sub", "role", "tenant", "permissions"]
)

jwt_provider = JWTAuthProvider(config=config)
composer = MCPComposer("multi-tenant-app", auth=jwt_provider.get_verifier())
```

## Utility Functions

### Token Extraction

```python
from mcp_composer.core.auth.jwt import extract_jwt_from_header

# Extract token from Authorization header
header = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
token = extract_jwt_from_header(header)
```

### Token Decoding

```python
from mcp_composer.core.auth.jwt import decode_jwt_token

# Decode and verify token
claims = decode_jwt_token(
    token=token,
    secret="your-secret",
    algorithm="HS256",
    verify=True,
    issuer="https://auth.example.com"
)

print(claims["sub"])  # user@example.com
print(claims["role"])  # admin
```

### Token Generation

```python
from mcp_composer.core.auth.jwt import generate_jwt_token

# Generate a new token
payload = {
    "sub": "user@example.com",
    "name": "John Doe",
    "role": "admin"
}

token = generate_jwt_token(
    payload=payload,
    secret="your-secret",
    algorithm="HS256",
    expires_in=3600,  # 1 hour
    issuer="https://auth.example.com"
)
```

### Claims Validation

```python
from mcp_composer.core.auth.jwt import validate_jwt_claims

claims = {"sub": "user@example.com", "role": "admin"}
required = ["sub", "role", "tenant"]

is_valid = validate_jwt_claims(claims, required)
# False - missing 'tenant' claim
```

## Security Best Practices

### 1. Use Strong Secrets

```python
# Generate a strong secret
import secrets
secret = secrets.token_urlsafe(32)
```

### 2. Use Asymmetric Algorithms in Production

```python
# Use RS256 instead of HS256 for production
jwt_provider = JWTAuthProvider.from_public_key(
    public_key=public_key,
    algorithm="RS256"
)
```

### 3. Always Verify Expiration

```python
config = JWTConfig(
    secret=secret,
    verify_exp=True,  # Always verify expiration
    leeway=30  # Allow 30 seconds clock skew
)
```

### 4. Validate Issuer and Audience

```python
config = JWTConfig(
    secret=secret,
    issuer="https://auth.example.com",
    audience="my-api",
    verify_iss=True,
    verify_aud=True
)
```

### 5. Require Critical Claims

```python
config = JWTConfig(
    secret=secret,
    required_claims=["sub", "role", "tenant"]
)
```

### 6. Use Short-Lived Tokens

```python
# Generate tokens with short expiration
token = generate_jwt_token(
    payload=payload,
    secret=secret,
    expires_in=900  # 15 minutes
)
```

## Error Handling

```python
import jwt
from mcp_composer.core.auth.jwt import decode_jwt_token

try:
    claims = decode_jwt_token(token, secret=secret, verify=True)
except jwt.ExpiredSignatureError:
    print("Token has expired")
except jwt.InvalidIssuerError:
    print("Invalid token issuer")
except jwt.InvalidAudienceError:
    print("Invalid token audience")
except jwt.InvalidTokenError as e:
    print(f"Invalid token: {e}")
```

## Testing

### Unit Tests

```python
import pytest
from mcp_composer.core.auth.jwt import JWTConfig, JWTAuthProvider

def test_jwt_config_from_env():
    config = JWTConfig.from_env(prefix="TEST_JWT_")
    assert config.algorithm == "HS256"

def test_jwt_provider_creation():
    provider = JWTAuthProvider.from_secret("test-secret")
    verifier = provider.get_verifier()
    assert verifier is not None
```

## Troubleshooting

### Issue: "Either secret or public_key must be provided"

**Solution**: Ensure you provide either a secret (for HMAC) or public_key (for RSA/ECDSA):

```python
# For HMAC
config = JWTConfig(secret="your-secret", algorithm="HS256")

# For RSA
config = JWTConfig(public_key=public_key, algorithm="RS256")
```

### Issue: "Invalid algorithm"

**Solution**: Use a supported algorithm:

```python
# Valid algorithms
config = JWTConfig(secret="secret", algorithm="HS256")  # ✅
config = JWTConfig(secret="secret", algorithm="INVALID")  # ❌
```

### Issue: Token verification fails

**Solution**: Check your configuration matches the token:

```python
# Ensure algorithm matches
# Ensure secret/public_key is correct
# Check issuer and audience if verifying them
config = JWTConfig(
    secret="correct-secret",
    algorithm="HS256",  # Must match token
    issuer="https://auth.example.com",  # Must match token
    verify_iss=True
)
```

## API Reference

See the module docstrings for detailed API documentation:

- `JWTConfig`: Configuration model
- `JWTAuthProvider`: Provider wrapper
- `extract_jwt_from_header()`: Extract token from header
- `decode_jwt_token()`: Decode and verify token
- `generate_jwt_token()`: Generate new token
- `validate_jwt_claims()`: Validate required claims

## License

This module is part of MCP Composer and follows the same license.