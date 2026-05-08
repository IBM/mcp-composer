"""Tools filter middleware"""

import logging
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

            # PHASE 1.4: Context-based early exit
            # Check if user is already authenticated and has user_instances in request.state
            if request and hasattr(request, "state") and hasattr(request.state, "user"):
                user = request.state.user
                # Check if user has user_instances from previous authentication
                if hasattr(user, "token_data") and isinstance(user.token_data, dict):
                    cached_user_instances = (
                        user.token_data.get("user_instances")
                        or user.token_data.get("userInstances")
                    )
                    if cached_user_instances:
                        user_instances = cached_user_instances if isinstance(cached_user_instances, list) else [cached_user_instances]
                        logger.debug(
                            "Using user_instances from authenticated request.state.user (context early exit)"
                        )
                        # Skip all authentication - user already validated
                        if logger.isEnabledFor(logging.INFO):
                            logger.info(
                                "list_tools filter: user already authenticated, %d instances",
                                len(user_instances),
                            )
                        
                        # Skip to filtering
                        filtered_tools = self.gw._tool_manager.filter_tools(
                            tools, user_instances=user_instances
                        )
                        
                        if logger.isEnabledFor(logging.INFO):
                            logger.info(
                                "Filtered to %d tools (%d removed)",
                                len(filtered_tools),
                                len(tools) - len(filtered_tools),
                            )
                        
                        return filtered_tools

            # PHASE 1.2: Early-exit caching optimization
            # Check cache BEFORE calling validate_request to avoid expensive API calls
            if self.isv_validator and request:
                cookie_name = self.isv_validator.config.cookie_name
                if self._check_authentication_cookie(request, cookie_name):
                    # Try to get cached instances first (early exit)
                    session_id = None
                    if self.isv_validator.cache:
                        cookie_header = request.headers.get("cookie", "")
                        if cookie_header:
                            session_id = self.isv_validator.extract_session_cookie(cookie_header)
                        
                        if session_id:
                            cached_instances = self.isv_validator.cache.get_instances(session_id)
                            if cached_instances is not None:
                                user_instances = cached_instances
                                logger.debug("Using cached instances for tool filtering (early exit)")
                            else:
                                # Cache miss - do full validation
                                user_instances = await self._authenticate_and_get_instances(request)
                        else:
                            # No session ID - do full validation
                            user_instances = await self._authenticate_and_get_instances(request)
                    else:
                        # No cache - do full validation
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

            # PHASE 1.3: Reduce logging overhead
            # Move expensive operations inside debug check
            if logger.isEnabledFor(logging.INFO):
                logger.info(
                    "list_tools filter: MCP_COMPOSER_ENV=%r, user_instances=%d",
                    env,
                    len(user_instances),
                )
            
            # Only compute product IDs if debug logging is enabled
            if logger.isEnabledFor(logging.DEBUG) and user_instances:
                product_ids = {
                    inst.get("subscription", {}).get("productId")
                    for inst in user_instances
                    if inst.get("subscription")
                }
                logger.debug("User has access to products: %s", product_ids)

            # Only extract tool names if info logging is enabled
            if logger.isEnabledFor(logging.INFO):
                tool_count = len(tools)
                logger.info("Filtering %d tools for user", tool_count)
            
            filtered_tools = self.gw._tool_manager.filter_tools(
                tools, user_instances=user_instances
            )
            
            if logger.isEnabledFor(logging.INFO):
                logger.info(
                    "Filtered to %d tools (%d removed)",
                    len(filtered_tools),
                    len(tools) - len(filtered_tools),
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
