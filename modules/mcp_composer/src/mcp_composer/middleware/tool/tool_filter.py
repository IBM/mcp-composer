"""Tools filter middleware"""

import os
from typing import TYPE_CHECKING, Any
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from starlette.exceptions import HTTPException

from mcp_composer.core.auth.jwt.isv_token_validator import ISVUser
from mcp_composer.core.utils.context_request import ctx_get
from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory

if TYPE_CHECKING:
    from mcp_composer.core.auth.jwt.isv_token_validator import ISVTokenValidator

logger = LoggerFactory.get_logger()

CONTEXT_REQUEST_KEY = "fastmcp_context.request_context.request"
ENV_LOCAL = "local"


class ListFilteredTool(Middleware):
    """Filter tools of member server before sending to clients.
    1. Remove tools
    2. Update description of tools if exist
    3. Non-local: user_instances start empty; only ISV validation (when a session
       cookie is present) may populate them for product-based filtering.
    """

    def __init__(self, gw, isv_validator: "ISVTokenValidator | None" = None) -> None:
        """
        Initialize ListFilteredTool middleware.

        Args:
            gw: MCPComposer gateway instance
            isv_validator: Optional ISVTokenValidator for authentication during list_tools
        """
        self.gw = gw
        self.isv_validator = isv_validator

    async def on_list_tools(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        try:
            tools = await call_next(context)
            env = (os.getenv("MCP_COMPOSER_ENV") or "").strip().lower()

            # Local: no ISV validation, no user-instance-based filtering
            if env == ENV_LOCAL:
                logger.info("Local mode - returning all tools without filtering")
                return tools

            request = ctx_get(context, CONTEXT_REQUEST_KEY)

            user_instances: list[dict[str, Any]] = []

            if self.isv_validator and request:
                cookie_name = self.isv_validator.config.cookie_name
                if self._check_authentication_cookie(request, cookie_name):
                    user_instances = await self._authenticate_and_get_instances(request)
                else:
                    logger.info(
                        "Non-local, ISV enabled, missing session %r — user_instances empty",
                        cookie_name,
                    )
            elif self.isv_validator and not request:
                logger.info(
                    "Non-local, ISV enabled, no HTTP request in context — user_instances empty"
                )

            logger.info(
                "list_tools filter: MCP_COMPOSER_ENV=%r, user_instances=%d",
                env,
                len(user_instances),
            )
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

            tool_names = list(tools.keys()) if isinstance(tools, dict) else [tool.name for tool in tools]
            logger.info("all the tools without any filter: %s\n", tool_names)
            filtered_tools = self.gw._tool_manager.filter_tools(
                tools, user_instances=user_instances
            )
            tool_names_after = list(tools.keys()) if isinstance(tools, dict) else [tool.name for tool in tools]
            logger.info("all the tools without any filter but after filtered_tools: %s\n", tool_names_after)
            logger.info(
                "Filtered tools: %d total, %d after filtering",
                len(tools),
                len(filtered_tools),
            )

            return filtered_tools
        except ToolFilterError as e:
            logger.exception("Tools filtering failed in middleware: %s", e)
            raise ToolFilterError("Tools filtering failed in middleware") from e

    def _check_authentication_cookie(self, request: Any, cookie_name: str) -> bool:
        """Return True if the ISV session cookie is present on the request."""
        headers = getattr(request, "headers", {})
        cookie_header = headers.get("cookie", "")
        return cookie_name in cookie_header or cookie_name in headers

    async def _authenticate_and_get_instances(
        self, request: Any
    ) -> list[dict[str, Any]]:
        """
        Validate the request with ISV and return user_instances for tool filtering.

        On failure or empty user_instances, returns [] so list_tools yields an empty
        tool list (after filtering) instead of raising.
        """
        if not self.isv_validator:
            return []

        try:
            logger.debug(
                "Authenticating request to fetch user instances for tool filtering"
            )
            token_data = await self.isv_validator.validate_request(request)
            logger.debug("Token data in ListFilteredTool: %s", token_data)

            if not hasattr(request, "state"):
                from starlette.datastructures import State

                request.state = State()

            request.state.user = ISVUser(token_data)

            user_instances = (
                token_data.get("user_instances")
                or token_data.get("userInstances")
                or []
            )
            if isinstance(user_instances, dict):
                user_instances = [user_instances]
            logger.debug("User instances in ListFilteredTool: %s", user_instances)
            if not user_instances:
                logger.info(
                    "ISV token had no user_instances / userInstances; returning empty"
                )
                return []

            logger.info(
                "✓ Authentication successful for list_tools (found %d instances)",
                len(user_instances),
            )
            return user_instances

        except HTTPException as e:
            logger.warning(
                "ISV validation failed (HTTP %s); returning empty user_instances: %s",
                e.status_code,
                e.detail,
            )
            return []
        except Exception as e:
            logger.warning(
                "ISV authentication failed; returning empty user_instances: %s", str(e)
            )
            return []
