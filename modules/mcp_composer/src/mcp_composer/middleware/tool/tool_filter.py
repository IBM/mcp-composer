"""Tools filter middleware"""

import os
from typing import TYPE_CHECKING, Any, List, Dict, Optional
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp_composer.core.utils.context_request import ctx_get, extract_user_instances
from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory

if TYPE_CHECKING:
    from mcp_composer.core.auth.jwt.isv_token_validator import ISVTokenValidator

logger = LoggerFactory.get_logger()

CONTEXT_REQUEST_KEY = "fastmcp_context.request_context.request"


class ListFilteredTool(Middleware):
    """Filter tools of member server before sending to clients.
    1. Remove tools
    2. Update description of tools if exist
    3. Perform ISV authentication to fetch user instances (non-local mode)
    """

    def __init__(self, gw, isv_validator: Optional["ISVTokenValidator"] = None):
        """
        Initialize ListFilteredTool middleware.

        Args:
            gw: MCPComposer gateway instance
            isv_validator: Optional ISVTokenValidator for authentication during list_tools
        """
        self.gw = gw
        self.isv_validator = isv_validator

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        try:
            tools = await self.gw.get_tools()
            env = os.getenv("MCP_COMPOSER_ENV", "").lower()

            # Skip filtering in local mode
            if env == "local":
                logger.info("Local mode - returning all tools without filtering")
                await call_next(context)
                return [tool for _, tool in tools.items()]

            request = ctx_get(context, CONTEXT_REQUEST_KEY)

            # Try to authenticate and fetch user instances if validator is provided
            if self.isv_validator and request:
                user_instances = await self._authenticate_and_get_instances(request)
            else:
                # Fallback: extract from existing context or header
                user_instances = extract_user_instances(request)

            logger.info("Filtering tools based on %d user instances", len(user_instances))
            if user_instances:
                logger.debug(
                    "User has access to products: %s",
                    list(
                        set(
                            inst.get("subscription", {}).get("productId")
                            for inst in user_instances
                            if inst.get("subscription")
                        )
                    ),
                )

            filtered_tools = self.gw._tool_manager.filter_tools(tools, user_instances=user_instances)

            logger.info("Filtered tools: %d total, %d after filtering", len(tools), len(filtered_tools))

            await call_next(context)
            return [tool for _, tool in filtered_tools.items()]
        except ToolFilterError as e:
            logger.exception("Tools filtering failed in middleware: %s", e)
            raise ToolFilterError("Tools filtering failed in middleware") from e

    async def _authenticate_and_get_instances(self, request: Any) -> List[Dict[str, Any]]:
        """
        Authenticate request and fetch user instances.

        Args:
            request: HTTP request object

        Returns:
            List of user instances, or empty list if authentication fails
        """
        try:
            logger.debug("Authenticating request to fetch user instances for tool filtering")

            # Validate token and fetch instances
            token_data = await self.isv_validator.validate_request(request)

            # Store user in request.state for downstream use
            if not hasattr(request, "state"):
                from starlette.datastructures import State

                request.state = State()

            from mcp_composer.core.auth.jwt.isv_token_validator import ISVUser

            request.state.user = ISVUser(token_data)

            user_instances = token_data.get("user_instances", [])
            logger.info("✓ Authentication successful for list_tools (found %d instances)", len(user_instances))

            return user_instances

        except Exception as e:
            # Authentication failed - log and return empty list (backward compatible)
            logger.warning("Authentication failed for list_tools, returning unfiltered tools: %s", str(e))
            return []
