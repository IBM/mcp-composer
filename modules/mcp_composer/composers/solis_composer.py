"""
Solis Composer with JWT Authentication.

This composer integrates IBM Document Search tools with JWT-based authentication
for secure access to Solis resources.
"""
import os
import asyncio
from mcp_composer.core.auth.jwt.jwt_utils import load_jwt_provider, log_jwt_configuration
from mcp_composer.core.tools.ibm_document_search_tool import IBMDocumentSearchTool
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer import MCPComposer
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Load JWT provider from utility function with SOLIS-specific prefix
jwt_provider = load_jwt_provider(prefix="SOLIS_JWT_")

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

def setup_middleware(composer: MCPComposer) -> None:
    """Configure and register middleware components."""
    composer.add_middleware(middleware=ListFilteredTool(composer))
    logger.info("Added ListFilteredTool middleware")


def setup_tools(composer: MCPComposer) -> None:
    """Configure and register tools."""
    deep_research_tool = IBMDocumentSearchTool(
        {
            "name": "ibm_document_search",
            "resource_manager": composer.resource_manager,
        }
    )
    composer.add_tool(deep_research_tool)
    logger.info("Added IBM Document Search tool")


async def run_http_mode(composer: MCPComposer) -> None:
    """Run composer in HTTP mode."""
    await composer.run_http_async(
        host="0.0.0.0", port=9000, log_level="debug", path="/mcp"
    )


async def run_stdio_mode(composer: MCPComposer) -> None:
    """Run composer in STDIO mode."""
    logger.info("Starting STDIO server")
    await composer.run_stdio_async()


async def run_sse_mode(composer: MCPComposer) -> None:
    """Run composer in SSE mode."""
    await composer.run_async(
        transport="sse", host="0.0.0.0", port=9000, log_level="debug"
    )


# Mode dispatch table
MODE_HANDLERS = {
    "http": run_http_mode,
    "stdio": run_stdio_mode,
    "sse": run_sse_mode,
}


async def run_composer_mode(composer: MCPComposer, mode: str) -> None:
    """Execute composer in specified mode."""
    handler = MODE_HANDLERS.get(mode)
    if not handler:
        raise ValueError(
            f"Unsupported MCP_MODE: {mode}. Use 'http', 'sse', or 'stdio'"
        )
    await handler(composer)


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
    log_jwt_configuration(jwt_provider)

    setup_middleware(gw)
    setup_tools(gw)

    # Setup member servers (if configured)
    await gw.setup_member_servers()
    logger.info("Member servers setup complete")

    # Run composer based on mode
    await run_composer_mode(gw, mode)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Solis Composer stopped by user")
    except Exception as e:
        logger.error("Solis Composer failed: %s", e, exc_info=True)
        raise
