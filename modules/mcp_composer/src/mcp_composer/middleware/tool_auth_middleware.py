"""
Tool-Level Authentication Middleware

This middleware enforces ISV token authentication at tool execution time rather than
at connection time. This allows clients to establish SSE connections without authentication,
but requires valid tokens when invoking tools.

Key Features:
- Validates ISV tokens only during tool calls (not during connection)
- Integrates with existing ISVTokenValidator for token validation
- Stores validated token in auth context for downstream use
- Raises 401 errors for missing or invalid tokens
- Supports token caching via ISVTokenValidator
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from starlette.exceptions import HTTPException
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.middleware.auth_context_middleware import (
    auth_context_var,
    AUTH_KEY_ISV_TOKEN,
    AUTH_KEY_AUTHENTICATED,
    AUTH_KEY_COOKIES,
    AUTH_KEY_USER_IDENTITY,
    AUTH_KEY_USER_INSTANCES,
    AUTH_KEY_USER_INSTANCES_FULL,
    AUTH_KEY_AUTH_TOKEN,
)

logger = LoggerFactory.get_logger()

if TYPE_CHECKING:
    from mcp_composer.core.auth.jwt.isv_token_validator import ISVTokenValidator


class ToolAuthenticationMiddleware(Middleware):
    """
    Enforces ISV token authentication at tool execution time.

    This middleware runs during tool calls and validates the ISV token before
    allowing tool execution. It integrates with the existing ISVTokenValidator
    to maintain consistent token validation logic.

    Configuration:
        validator: ISVTokenValidator instance for token validation
        exempt_tools: Optional list of tool names that don't require authentication

    Example:
        >>> from mcp_composer.core.auth.jwt import ISVTokenValidator
        >>> validator = ISVTokenValidator(environment='test')
        >>> middleware = ToolAuthenticationMiddleware(validator=validator)
        >>> composer.add_middleware(middleware)
    """

    def __init__(
        self,
        validator: "ISVTokenValidator",
        exempt_tools: Optional[list[str]] = None,
        is_iam_enabled_for_tool: Optional[Callable[[str], bool]] = None,
        **kwargs,
    ):
        """
        Initialize tool authentication middleware.

        Args:
            validator: ISVTokenValidator instance for token validation
            exempt_tools: Optional list of tool names that don't require authentication
                         (e.g., ['health_check', 'list_tools'])
            is_iam_enabled_for_tool: Optional callable(tool_name) -> bool. If set, auth runs only
                         when it returns True (e.g. when the tool's server has solis_config.isIamEnabled).
                         If None, auth runs for all tools (backward compatible).
            **kwargs: Additional middleware configuration
        """
        super().__init__(**kwargs)
        self.validator = validator
        self.exempt_tools = set(exempt_tools or [])
        self.is_iam_enabled_for_tool = is_iam_enabled_for_tool

        logger.info("=" * 70)
        logger.info("ToolAuthenticationMiddleware Initialized")
        logger.info("=" * 70)
        logger.info("Authentication enforcement: Tool execution time")
        logger.info("Token validator: ISVTokenValidator")
        if self.is_iam_enabled_for_tool is not None:
            logger.info("IAM gate: enabled (auth only for tools whose server has solis_config.isIamEnabled)")
        if self.exempt_tools:
            logger.info("Exempt tools: %s", ", ".join(self.exempt_tools))
        else:
            logger.info("Exempt tools: None")
        logger.info("=" * 70)

    def _get_request(self, context: MiddlewareContext) -> Any:
        """
        Get the HTTP request from middleware context.

        Args:
            context: FastMCP middleware context

        Returns:
            HTTP request object or None if unavailable
        """
        fastmcp_ctx = getattr(context, "fastmcp_context", None)
        if fastmcp_ctx is None:
            return None
        request_context = getattr(fastmcp_ctx, "request_context", None)
        return getattr(request_context, "request", None) if request_context else None

    def _is_tool_exempt(self, tool_name: str) -> bool:
        """
        Check if a tool is exempt from authentication.

        Args:
            tool_name: Name of the tool being called

        Returns:
            True if tool is exempt, False otherwise
        """
        return tool_name in self.exempt_tools

    def _extract_user_identity(self, token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract user identity from token data if available.

        Args:
            token_data: Token response from ISVTokenValidator

        Returns:
            User identity dict or None
        """
        # ISV token response may contain user identity information
        # This can be extended based on actual token structure
        return token_data.get("identity") or token_data.get("user_identity")

    def _build_auth_context(self, token_data: Dict[str, Any], request: Any) -> Dict[str, Any]:
        """
        Build authentication context from validated token data.

        Args:
            token_data: Validated token response from ISVTokenValidator
            request: HTTP request object

        Returns:
            Authentication context dict
        """
        # Extract user instances from token_data
        user_instances = token_data.get("user_instances", [])

        auth_context: Dict[str, Any] = {
            AUTH_KEY_ISV_TOKEN: token_data.get("access_token"),
            AUTH_KEY_AUTHENTICATED: True,
            AUTH_KEY_COOKIES: {},
            AUTH_KEY_USER_INSTANCES: user_instances,  # Simplified format
            AUTH_KEY_USER_INSTANCES_FULL: user_instances,  # Full format (same for ISV)
            AUTH_KEY_AUTH_TOKEN: None,
        }

        # Extract user identity if available
        if user_identity := self._extract_user_identity(token_data):
            auth_context[AUTH_KEY_USER_IDENTITY] = user_identity

        # Extract cookies from request if available
        if request:
            request_headers = getattr(request, "headers", None)
            if request_headers:
                cookie_header = request_headers.get("cookie", "")
                if cookie_header:
                    cookies = {}
                    for cookie in cookie_header.split(";"):
                        cookie = cookie.strip()
                        if "=" in cookie:
                            name, value = cookie.split("=", 1)
                            cookies[name.strip()] = value.strip()
                    auth_context[AUTH_KEY_COOKIES] = cookies

        return auth_context

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        """
        Validate authentication before tool execution.

        This method is called by FastMCP before each tool invocation.
        It validates the ISV token and stores the authentication context
        for downstream use.

        Args:
            context: FastMCP middleware context
            call_next: Callback to continue middleware chain

        Returns:
            Result from next middleware or tool execution

        Raises:
            HTTPException: 401 if authentication fails
        """
        tool_name = getattr(context.message, "name", "unknown")

        # Skip auth when IAM is disabled for the tool's server or when tool is a discovery tool (no backend call)
        iam_disabled = self.is_iam_enabled_for_tool is not None and not self.is_iam_enabled_for_tool(tool_name)
        is_discovery_tool = tool_name.endswith("_get_service_info") or tool_name.endswith("_get_type_info")
        if iam_disabled or is_discovery_tool:
            logger.debug(
                "Tool '%s' skipping authentication (IAM disabled=%s, discovery tool=%s)",
                tool_name,
                iam_disabled,
                is_discovery_tool,
            )
            return await call_next(context)

        # Check if tool is exempt from authentication
        if self._is_tool_exempt(tool_name):
            logger.info("Tool '%s' is exempt from authentication, skipping validation", tool_name)
            return await call_next(context)

        # Get HTTP request
        request = self._get_request(context)
        if request is None:
            logger.warning("Unable to extract HTTP request from context for tool '%s'", tool_name)
            raise HTTPException(status_code=500, detail="Internal error: Unable to access request context")

        # Validate token
        logger.info("Validating authentication for tool '%s'", tool_name)
        try:
            # Use existing ISVTokenValidator to validate the request
            token_data = await self.validator.validate_request(request)

            # Build and store authentication context
            auth_context = self._build_auth_context(token_data, request)
            auth_context_var.set(auth_context)

            # Log success
            token_status = "cached" if token_data.get("cached") else "fresh"
            logger.info("✓ Tool '%s' authentication successful (token: %s)", tool_name, token_status)

            # Continue to next middleware/tool
            try:
                return await call_next(context)
            finally:
                # Clean up auth context after tool execution
                auth_context_var.set(None)

        except HTTPException as e:
            # Authentication failed - log and re-raise
            logger.warning("✗ Tool '%s' authentication failed: %s (status: %d)", tool_name, e.detail, e.status_code)
            raise
        except Exception as e:
            # Unexpected error during authentication
            logger.error("✗ Tool '%s' authentication error: %s", tool_name, str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")
