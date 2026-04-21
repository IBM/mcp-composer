"""
Solis Composer with ISV Token Authentication.

This composer integrates IBM Document Search tools with ISV token-based authentication
for secure access to Solis resources. It validates platform session cookies and exchanges
them for ISV tokens via IBM's authentication service.

Catalog MCPs (skill / agent / workflow) and the startup skill poller live in
``catalog_composer.py`` — run that process when you need catalog management without
Solis doc search and ISV middleware.

Environment variables:
- MCP_COMPOSER_ENV: local | test | dev | prod (drives ISV endpoint and cookie; local and test use same ISV config)
- ISV_AUTH_COOKIE_NAME: override cookie name (optional)
- ISV_FORWARD_COOKIES: comma-separated cookie names to forward (optional)
- MCP_COMPOSER_LOG_LEVEL: DEBUG | INFO (optional)
"""

import asyncio
import os

from mcp_composer import MCPComposer
from mcp_composer.core.auth.jwt.isv_token_validator import ISVTokenValidator
from mcp_composer.core.tools import IBMDocSearchDirectTool
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.middleware import PromptInjectionMiddleware, TracingMiddleware, SecretsAndPIIMiddleware
from mcp_composer.middleware.auth_context_middleware import (
    AuthContextMiddleware,
    REQUEST_CONTEXT_KEY,
)
from mcp_composer.middleware.auth_utils import tool_name_to_server_id
from mcp_composer.middleware.error_sanitization_middleware import ErrorSanitizationMiddleware
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer.middleware.tool_auth_middleware import ToolAuthenticationMiddleware


# -----------------------------------------------------------------------------
# Configuration (from env)
# -----------------------------------------------------------------------------

_log_level = (os.getenv("MCP_COMPOSER_LOG_LEVEL") or "DEBUG").strip().upper()
logger = LoggerFactory.get_logger(level=_log_level)

_env_raw = (os.getenv("MCP_COMPOSER_ENV") or "test").strip().lower()
environment = "test" if _env_raw == "local" else _env_raw

auth_cookie_name = os.getenv("ISV_AUTH_COOKIE_NAME", "mcsp-glb-iam-test").strip()
_forward_cookies_env = os.getenv("ISV_FORWARD_COOKIES", "").strip()
FORWARD_COOKIES = (
    [c.strip() for c in _forward_cookies_env.split(",") if c.strip()]
    if _forward_cookies_env
    else [auth_cookie_name, REQUEST_CONTEXT_KEY]
)

cache_enabled = os.getenv("ISV_CACHE_ENABLED", "true").lower() == "true"
cache_ttl = int(os.getenv("ISV_CACHE_TTL", "7200"))
timeout = float(os.getenv("ISV_REQUEST_TIMEOUT", "30"))

logger.info(
    "Solis Composer ready | env=%s | auth_cookie=%s | forward_cookies=%s | cache=%s | timeout=%ss | log_level=%s",
    environment,
    auth_cookie_name,
    FORWARD_COOKIES,
    cache_enabled,
    timeout,
    _log_level,
)


# -----------------------------------------------------------------------------
# Composer and ISV validator
# -----------------------------------------------------------------------------

isv_validator = ISVTokenValidator(
    environment=os.getenv("ISV_ENVIRONMENT", "test"),
    cache_enabled=cache_enabled,
    cache_ttl=cache_ttl,
    timeout=timeout,
)

gw = MCPComposer(name="solis-composer", auth=None)



# -----------------------------------------------------------------------------
# Middleware setup
# -----------------------------------------------------------------------------


def setup_middleware(composer: MCPComposer) -> None:
    """Register middleware: auth (tool + context), optional tracing, filter, error sanitization."""
    server_manager = composer._server_manager

    def is_iam_enabled_for_tool(tool_name: str) -> bool:
        server_id = tool_name_to_server_id(tool_name)
        return server_manager.is_iam_enabled_for_server(server_id) if server_id else False

    composer.add_middleware(
        ToolAuthenticationMiddleware(
            validator=isv_validator,
            is_iam_enabled_for_tool=is_iam_enabled_for_tool,
        )
    )
    logger.info("✓ Added ToolAuthenticationMiddleware (IAM gate from solis_config)")

    composer.add_middleware(
        AuthContextMiddleware(
            forward_cookies=FORWARD_COOKIES,
            add_isv_token=True,
            add_cookie_header=True,
            use_cookie_as_auth=True,
            auth_cookie_name=auth_cookie_name,
            enabled_tool_patterns=None,
            is_iam_enabled_for_tool=is_iam_enabled_for_tool,
        )
    )
    logger.info("✓ Added AuthContextMiddleware (IAM gate from solis_config only)")

    if environment != "prod":
        tracing_log_level = (os.getenv("MCP_COMPOSER_LOG_LEVEL") or "DEBUG").strip().upper()
        composer.add_middleware(
            TracingMiddleware(
                log_tools=True,
                log_resources=False,
                log_prompts=False,
                log_args=True,
                log_results=True,
                log_level=tracing_log_level,
                max_payload_length=2000,
            )
        )
        logger.info("Added TracingMiddleware (log_level=%s)", tracing_log_level)
    else:
        logger.info("Skipped TracingMiddleware (prod)")

    composer.add_middleware(middleware=ListFilteredTool(composer, isv_validator=isv_validator))
    composer.add_middleware(ErrorSanitizationMiddleware())
    logger.info("Added middleware: ListFilteredTool (with ISV auth), ErrorSanitizationMiddleware")

    composer.add_middleware(PromptInjectionMiddleware())
    logger.info("Added PromptInjectionMiddleware")

    composer.add_middleware(middleware=SecretsAndPIIMiddleware())
    logger.info("Added PIIMiddleware")


# -----------------------------------------------------------------------------
# Tools and run modes
# -----------------------------------------------------------------------------


def setup_tools(composer: MCPComposer) -> None:
    """Register composer tools."""
    composer.add_tool(IBMDocSearchDirectTool())
    logger.info("Added IBM Doc Search Direct Tool")

async def run_http_mode(composer: MCPComposer) -> None:
    await composer.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")


async def run_stdio_mode(composer: MCPComposer) -> None:
    """Run composer in STDIO mode."""
    logger.info("Starting STDIO server")
    await composer.run_stdio_async()


async def run_sse_mode(composer: MCPComposer) -> None:
    """Run composer in SSE mode."""
    await composer.run_async(transport="sse", host="0.0.0.0", port=9000, log_level="debug")


MODE_HANDLERS = {
    "http": run_http_mode,
    "stdio": run_stdio_mode,
    "sse": run_sse_mode,
}


async def run_composer_mode(composer: MCPComposer, mode: str) -> None:
    handler = MODE_HANDLERS.get(mode)
    if not handler:
        raise ValueError(f"Unsupported MCP_MODE: {mode}. Use 'http', 'sse', or 'stdio'")
    await handler(composer)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


async def main() -> None:
    mode = os.getenv("MCP_MODE", "sse").lower()
    logger.info("Starting Solis Composer in %s mode", mode)
    logger.info("ISV Token Authentication is ACTIVE")

    try:
        setup_middleware(gw)
        setup_tools(gw)
        await gw.setup_member_servers()
        logger.info("Member servers setup complete")
        await run_composer_mode(gw, mode)
    except Exception as e:
        logger.error("Solis Composer failed: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Solis Composer stopped by user")
    except Exception as e:
        logger.error("Solis Composer failed: %s", e, exc_info=True)
        raise
