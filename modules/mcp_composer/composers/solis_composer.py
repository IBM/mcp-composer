"""
Solis Composer with JWT Authentication.

This composer integrates IBM Document Search tools with JWT-based authentication
for secure access to Solis resources.
"""
import os
import asyncio
import json as json_module
from mcp_composer.core.auth.jwt.jwt_config import JWTConfig
from mcp_composer.core.auth.jwt.jwt_provider import JWTAuthProvider
from mcp_composer.core.tools.ibm_document_search_tool import IBMDocumentSearchTool
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer import MCPComposer
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


# Configure JWT authentication for Solis
def load_jwt_provider(prefix: str = "SOLIS_JWT_") -> JWTAuthProvider | None:
    """
    Load JWT provider with configurable environment variable prefix.

    Args:
        prefix: Environment variable prefix (default: "SOLIS_JWT_")
                For example, "MYAPP_JWT_" would look for MYAPP_JWT_SECRET, etc.

    Priority order:
    1. {PREFIX}SECRET - Direct PEM/key content in environment variable
    2. Full environment configuration ({PREFIX}PUBLIC_KEY, {PREFIX}ALGORITHM, etc.)

    Example:
        # Use default SOLIS prefix
        jwt_provider = load_jwt_provider()

        # Use custom prefix for different app
        jwt_provider = load_jwt_provider(prefix="MYAPP_JWT_")
    """

    # Normalize prefix to ensure it ends with underscore
    if prefix and not prefix.endswith("_"):
        prefix = f"{prefix}_"

    secret_var = f"{prefix}SECRET"

    # Priority 1: Direct secret/key content from {PREFIX}SECRET
    jwt_secret = os.getenv(secret_var)
    if jwt_secret:
        try:
            logger.info("Loading JWT public key from %s environment variable", secret_var)

            # Detect format: PEM, JSON, or raw key
            jwt_secret = jwt_secret.strip()

            if jwt_secret.startswith("{") or jwt_secret.startswith("["):
                # JSON format - parse and extract key
                try:
                    key_data = json_module.loads(jwt_secret)
                    if isinstance(key_data, dict):
                        public_key = (
                            key_data.get("public_key")
                            or key_data.get("publicKey")
                            or key_data.get("key")
                            or key_data.get("jwk", {}).get("n")
                        )
                        if not public_key:
                            logger.warning("JSON doesn't contain 'public_key' field. Using raw content.")
                            public_key = jwt_secret
                    else:
                        public_key = str(key_data)
                    logger.info("Parsed public key from JSON format")
                except json_module.JSONDecodeError:
                    # Not valid JSON, treat as raw key
                    public_key = jwt_secret
                    logger.info("Using raw key content")
            else:
                # PEM format or raw key string
                public_key = jwt_secret
                logger.info("Using PEM/raw key format")

            # Create JWT provider with dynamic prefix
            provider = JWTAuthProvider.from_public_key(
                public_key=public_key,
                algorithm=os.getenv(f"{prefix}ALGORITHM", "RS256"),
                issuer=os.getenv(f"{prefix}ISSUER"),
                audience=os.getenv(f"{prefix}AUDIENCE"),
            )
            logger.info("JWT authentication configured from %s", secret_var)
            return provider

        except Exception as e:
            logger.error("Failed to load JWT from %s: %s", secret_var, e, exc_info=True)
            raise

    # Priority 2: Load from full environment configuration
    try:
        jwt_config: JWTConfig = JWTConfig.from_env(prefix=prefix)
        provider: JWTAuthProvider = JWTAuthProvider(config=jwt_config)
        logger.info("JWT authentication configured from environment with prefix: %s", prefix)
        return provider
    except Exception as e:
        logger.warning("Failed to load JWT config from environment: %s", e)
        logger.info("JWT authentication disabled - running without auth")
        return None


# Load JWT provider
jwt_provider = load_jwt_provider()

# Option 3: Explicit configuration (uncomment to use)
# jwt_provider = JWTAuthProvider.from_secret(
#     secret=os.getenv("SOLIS_JWT_SECRET", "dev-secret-change-in-production"),
#     algorithm="HS256",
#     issuer="https://solis.ibm.com",
#     audience="solis-api",
#     verify_exp=True,
#     verify_iss=True,
#     verify_aud=True,
#     required_claims=["sub", "role", "tenant"]
# )

# Initialize composer with JWT authentication
gw = MCPComposer(name="solis-composer", auth=jwt_provider.get_verifier() if jwt_provider else None)


async def main():
    """
    Initialize and run the Solis composer with JWT authentication.

    Environment Variables:
        MCP_MODE: Server mode (http, sse, stdio) - default: sse

        JWT Configuration (prefix: SOLIS_JWT_):
        - SOLIS_JWT_SECRET: Secret key for HS256 algorithm
        - SOLIS_JWT_PUBLIC_KEY: Public key for RS256 algorithm
        - SOLIS_JWT_ALGORITHM: JWT algorithm (default: HS256)
        - SOLIS_JWT_ISSUER: Expected token issuer
        - SOLIS_JWT_AUDIENCE: Expected token audience
        - SOLIS_JWT_VERIFY_EXP: Verify expiration (default: true)
        - SOLIS_JWT_VERIFY_ISS: Verify issuer (default: false)
        - SOLIS_JWT_VERIFY_AUD: Verify audience (default: false)

    Example:
        # Set environment variables
        export SOLIS_JWT_SECRET="your-secret-key"
        export SOLIS_JWT_ALGORITHM="HS256"
        export SOLIS_JWT_ISSUER="https://solis.ibm.com"
        export SOLIS_JWT_VERIFY_EXP="true"
        export MCP_MODE="sse"

        # Run composer
        python solis_composer.py
    """
    mode = os.getenv("MCP_MODE", "sse").lower()

    logger.info("Starting Solis Composer in %s mode", mode)
    if jwt_provider:
        logger.info("JWT authentication: ENABLED")
        logger.info("JWT algorithm: %s", jwt_provider.config.algorithm)
        logger.info("JWT verify expiration: %s", jwt_provider.config.verify_exp)
    else:
        logger.warning("JWT authentication: DISABLED")

    gw.add_middleware(middleware=ListFilteredTool(gw))
    logger.info("Added ListFilteredTool middleware")

    # Add IBM Document Search tool
    deep_research_tool = IBMDocumentSearchTool(
        {
            "name": "ibm_document_search",
            "resource_manager": gw.resource_manager,
        }
    )
    gw.add_tool(deep_research_tool)
    logger.info("Added IBM Document Search tool")

    # Setup member servers (if configured)
    await gw.setup_member_servers()
    logger.info("Member servers setup complete")

    # Run composer based on mode
    if mode == "http":
        await gw.run_http_async(
            host="0.0.0.0", port=9000, log_level="debug", path="/mcp"
        )
    elif mode == "stdio":
        logger.info("Starting STDIO server")
        await gw.run_stdio_async()
    elif mode == "sse":
        await gw.run_async(
            transport="sse", host="0.0.0.0", port=9000, log_level="debug"
        )
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}. Use 'http', 'sse', or 'stdio'")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Solis Composer stopped by user")
    except Exception as e:
        logger.error("Solis Composer failed: %s", e, exc_info=True)
        raise
