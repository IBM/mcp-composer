"""
Solis Composer with ISV Token Authentication.

This composer integrates IBM Document Search tools with ISV token-based authentication
for secure access to Solis resources. It validates platform session cookies and exchanges
them for ISV tokens via IBM's authentication service.

Environment-based configuration automatically determines:
- Cookie name: mcsp-glb-iam-{env} (or mcsp-glb-iam for prod)
- ISV endpoint: https://aws.login.{env}.saas.ibm.com/security/auth/isv/token
"""

import os
import asyncio
from mcp_composer.core.tools import IBMDocSearchDirectTool
from mcp_composer.core.auth.jwt import ISVTokenVerifier
from mcp_composer.core.tools.ibm_document_search_tool import IBMDocumentSearchTool
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer.middleware import TracingMiddleware
from mcp_composer.middleware.auth_context_middleware import (
    AuthContextMiddleware,
    REQUEST_CONTEXT_KEY,
)
from mcp_composer import MCPComposer
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.middleware.error_sanitization_middleware import ErrorSanitizationMiddleware


logger = LoggerFactory.get_logger()

# Load ISV authentication configuration
environment = os.getenv("ISV_ENVIRONMENT", "test")

# Environment-specific cookie name for ISV authentication
_COOKIE_BY_ENV = {
    "test": "mcsp-glb-iam-test",
    "dev": "mcsp-glb-iam-dev",
    "prod": "mcsp-glb-iam",
}
FORWARD_COOKIES = [
    _COOKIE_BY_ENV.get(environment, "mcsp-glb-iam-test"),
    REQUEST_CONTEXT_KEY,
]
cache_enabled = os.getenv("ISV_CACHE_ENABLED", "true").lower() == "true"
cache_ttl = int(os.getenv("ISV_CACHE_TTL", "7200"))
timeout = float(os.getenv("ISV_REQUEST_TIMEOUT", "30"))

logger.info("=" * 70)
logger.info("Solis Composer - ISV Token Authentication")
logger.info("=" * 70)
logger.info("ISV Environment: %s", environment)
logger.info("Cache Enabled: %s", cache_enabled)
if cache_enabled:
    logger.info("Cache TTL: %d seconds", cache_ttl)
logger.info("Request Timeout: %.1f seconds", timeout)
logger.info("=" * 70)

# Initialize ISV token verifier
isv_verifier = ISVTokenVerifier(
    environment=environment, cache_enabled=cache_enabled, cache_ttl=cache_ttl, timeout=timeout
)

# Initialize composer with ISV authentication
# Note: ISVTokenVerifier is callable and compatible with FastMCP's auth interface
gw = MCPComposer(name="solis-composer", auth=isv_verifier)  # pyright: ignore[reportArgumentType]


def setup_middleware(composer: MCPComposer) -> None:
    """Configure and register middleware components."""
    # Add AuthContextMiddleware FIRST (highest priority)
    # This extracts ISV token and cookies from incoming requests
    # Cookie-based authorization: Uses platform session cookie value as Authorization header
    auth_cookie_name = _COOKIE_BY_ENV.get(environment, "mcsp-glb-iam-test")

    # Configure which tools should have auth context enabled
    # Add tool name patterns here (case-insensitive substring matching)
    enabled_tool_patterns = ["guardium"]  # Can add more patterns like ["gurdium", "watsonx", "lakehouse"]

    gw.add_middleware(
        AuthContextMiddleware(
            forward_cookies=FORWARD_COOKIES,
            add_isv_token=True,
            add_cookie_header=True,
            use_cookie_as_auth=True,
            auth_cookie_name=auth_cookie_name,
            enabled_tool_patterns=enabled_tool_patterns,
        )
    )
    logger.info("Added AuthContextMiddleware for automatic header forwarding")
    logger.info("Cookie-based authorization enabled using: %s", auth_cookie_name)
    logger.info("Auth context enabled for tool patterns: %s", enabled_tool_patterns)

    # Add TracingMiddleware for detailed logging
    gw.add_middleware(
        TracingMiddleware(
            log_tools=True,
            log_resources=False,
            log_prompts=False,
            log_args=True,
            log_results=True,  # Enable detailed result logging
            log_level="INFO",
            max_payload_length=2000,  # Increase max length for detailed logs
        )
    )
    logger.info("Added TracingMiddleware with enhanced logging")

    # Add tool filtering middleware
    composer.add_middleware(middleware=ListFilteredTool(composer))
    # Add error sanitization middleware last to catch all errors
    composer.add_middleware(ErrorSanitizationMiddleware())
    logger.info("Added middleware: ListFilteredTool, ErrorSanitizationMiddleware")


def setup_tools(composer: MCPComposer) -> None:
    """Configure and register tools."""
    ibm_doc_search_direct_tool = IBMDocSearchDirectTool()
    composer.add_tool(ibm_doc_search_direct_tool)
    logger.info("Added IBM Doc Search Direct Tool")


async def run_http_mode(composer: MCPComposer) -> None:
    """Run composer in HTTP mode."""
    await composer.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")


async def run_stdio_mode(composer: MCPComposer) -> None:
    """Run composer in STDIO mode."""
    logger.info("Starting STDIO server")
    await composer.run_stdio_async()


async def run_sse_mode(composer: MCPComposer) -> None:
    """Run composer in SSE mode."""
    await composer.run_async(transport="sse", host="0.0.0.0", port=9000, log_level="debug")


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
        raise ValueError(f"Unsupported MCP_MODE: {mode}. Use 'http', 'sse', or 'stdio'")
    await handler(composer)


async def main():
    mode = os.getenv("MCP_MODE", "sse").lower()

    logger.info("Starting Solis Composer in %s mode", mode)
    logger.info("ISV Token Authentication is ACTIVE")

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
