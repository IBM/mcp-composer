# JWT Authentication Quick Start (2 Minutes)

Get JWT authentication running in your MCP Composer in under 2 minutes!

## Prerequisites

- MCP Composer installed
- A JWT public key or secret

## Step 1: Set Environment Variables (30 seconds)

Choose your prefix and set your JWT configuration:

```bash
# Option A: Using default "JWT_" prefix
export JWT_SECRET="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"
export JWT_ALGORITHM="RS256"
export JWT_ISSUER="https://auth.example.com"
export JWT_AUDIENCE="your-api"

# Option B: Using custom prefix (e.g., "MYAPP_JWT_")
export MYAPP_JWT_SECRET="your-public-key-here"
export MYAPP_JWT_ALGORITHM="RS256"
export MYAPP_JWT_ISSUER="https://myapp.example.com"
export MYAPP_JWT_AUDIENCE="myapp-api"
```

## Step 2: Create Your Composer (1 minute)

```python
from mcp_composer import MCPComposer
from mcp_composer.core.auth.jwt import JWTAuthProvider, JWTConfig

# Option A: Load with default "JWT_" prefix
jwt_provider = JWTAuthProvider.from_env()

# Option B: Load with custom prefix
jwt_config = JWTConfig.from_env(prefix="MYAPP_JWT_")
jwt_provider = JWTAuthProvider(config=jwt_config)

# Create composer with JWT auth
composer = MCPComposer(
    name="my-secure-app",
    auth=jwt_provider.verifier
)

# Add your tools and run
await composer.run_http_async(host="0.0.0.0", port=9000)
```

## Step 3: Test It (30 seconds)

```bash
# Get a JWT token from your auth provider
TOKEN="your-jwt-token-here"

# Test the endpoint
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:9000/mcp/tools/list
```

## Done! 🎉

Your MCP Composer is now secured with JWT authentication!

## Common Prefixes

Different applications can use different prefixes:

| Application | Prefix | Example Variable |
|------------|--------|------------------|
| Default | `JWT_` | `JWT_SECRET` |
| Solis | `SOLIS_JWT_` | `SOLIS_JWT_SECRET` |
| Custom App | `MYAPP_JWT_` | `MYAPP_JWT_SECRET` |
| Development | `DEV_JWT_` | `DEV_JWT_SECRET` |
| Production | `PROD_JWT_` | `PROD_JWT_SECRET` |

## Next Steps

- **[Comprehensive Setup Guide](SOLIS_JWT_SETUP.md)** - Detailed configuration options
- **[JWT Module README](../src/mcp_composer/core/auth/jwt/README.md)** - Technical documentation
- **[Authentication Guide](../../docs/guide/authentication.md)** - All authentication methods

## Troubleshooting

**Token validation fails?**
- Verify your public key matches the token's signing key
- Check issuer and audience match your token claims
- Ensure algorithm matches (RS256, HS256, etc.)

**Environment variables not loading?**
- Check prefix matches exactly (case-sensitive)
- Verify underscore at end of prefix
- Use quotes for multi-line PEM keys

**Need help?**
- Check logs for detailed error messages
- Use the diagnostic tools in the comprehensive guide
- Review the JWT module README for examples