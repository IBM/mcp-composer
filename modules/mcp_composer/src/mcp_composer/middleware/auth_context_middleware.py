"""
Authentication Context Middleware

Extracts authentication information from incoming requests and makes it available
to member server tools via context variables. This allows automatic forwarding of
ISV tokens and platform cookies to downstream API calls without modifying tool arguments.
"""

import contextvars
from typing import Any, Dict, Optional
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Module-level context variable to store authentication context
# This is thread-safe and async-safe via contextvars
auth_context_var = contextvars.ContextVar("auth_context", default=None)


class AuthContextMiddleware(Middleware):
    """
    Middleware that extracts authentication context from incoming requests
    and stores it in a context variable for use by member server tools.

    This middleware:
    1. Extracts ISV token from authenticated user (request.state.user)
    2. Extracts platform session cookies from request headers
    3. Stores them in a context variable
    4. Makes them available to tools without modifying tool arguments

    Configuration:
        forward_cookies: List of cookie names to forward (default: empty list - no cookies forwarded unless explicitly specified)
        add_isv_token: Whether to add ISV token as X-ISV-Token header (default: True)
        add_cookie_header: Whether to add cookies as X-Platform-Cookie header (default: True)
    """

    def __init__(
        self,
        forward_cookies: Optional[list[str]] = None,
        add_isv_token: bool = True,
        add_cookie_header: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        # No default cookies - only forward what's explicitly configured
        self.forward_cookies = forward_cookies if forward_cookies is not None else []
        self.add_isv_token = add_isv_token
        self.add_cookie_header = add_cookie_header

        if self.forward_cookies:
            logger.info(
                "AuthContextMiddleware initialized (forward_cookies=%s, add_isv_token=%s, add_cookie_header=%s)",
                self.forward_cookies,
                self.add_isv_token,
                self.add_cookie_header,
            )
        else:
            logger.info(
                "AuthContextMiddleware initialized with NO cookie forwarding (add_isv_token=%s, add_cookie_header=%s)",
                self.add_isv_token,
                self.add_cookie_header,
            )

    def _extract_auth_context(self, context: MiddlewareContext) -> Dict[str, Any]:
        """
        Extract authentication context from the incoming request.

        Returns:
            Dict containing:
            - isv_token: ISV access token from authenticated user
            - cookies: Dict of cookie name -> value for forwarding
            - authenticated: Boolean indicating if user is authenticated
        """
        auth_context = {"isv_token": None, "cookies": {}, "authenticated": False}

        try:
            # Navigate to request object
            if hasattr(context, "fastmcp_context"):
                fastmcp_ctx = context.fastmcp_context
                if hasattr(fastmcp_ctx, "request_context"):
                    request = fastmcp_ctx.request_context.request

                    # Extract ISV token from authenticated user
                    if hasattr(request, "state") and hasattr(request.state, "user"):
                        user = request.state.user

                        # ISVUser has access_token attribute
                        if hasattr(user, "access_token") and user.access_token:
                            auth_context["isv_token"] = user.access_token
                            auth_context["authenticated"] = True
                            logger.debug("Extracted ISV token from authenticated user")

                        # Also check for user identity
                        if hasattr(user, "identity"):
                            auth_context["user_identity"] = user.identity

                    # Extract cookies from request headers
                    if hasattr(request, "headers"):
                        # Method 1: Extract from standard Cookie header
                        cookie_header = request.headers.get("cookie", "")
                        if cookie_header:
                            # Parse cookies
                            for cookie in cookie_header.split(";"):
                                cookie = cookie.strip()
                                if "=" in cookie:
                                    name, value = cookie.split("=", 1)
                                    # Check if this is a cookie we want to forward
                                    if any(forward_name in name for forward_name in self.forward_cookies):
                                        auth_context["cookies"][name] = value
                                        logger.debug("Extracted cookie from Cookie header: %s", name)

                        # Method 2: Extract from custom headers (e.g., mcsp-glb-iam-test: value)
                        # Some clients send cookies as individual headers instead of Cookie header
                        for cookie_name in self.forward_cookies:
                            header_value = request.headers.get(cookie_name, "")
                            if header_value:
                                auth_context["cookies"][cookie_name] = header_value
                                logger.debug("Extracted cookie from custom header: %s", cookie_name)

                        # Method 3: Extract ISV token from Authorization header if present
                        # This handles cases where ISV token is sent directly
                        auth_header = request.headers.get("authorization", "")
                        if auth_header.startswith("Bearer ") and not auth_context.get("isv_token"):
                            # Only use if we don't already have ISV token from user object
                            potential_token = auth_header[7:]  # Remove "Bearer " prefix
                            # ISV tokens typically start with specific patterns
                            if potential_token and len(potential_token) > 20:
                                auth_context["isv_token"] = potential_token
                                auth_context["authenticated"] = True
                                logger.debug("Extracted ISV token from Authorization header")

        except Exception as e:
            logger.warning("Failed to extract authentication context: %s", e)

        return auth_context

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        """
        Extract authentication context and store in context variable before tool execution.
        """
        tool_name = getattr(context.message, "name", "unknown")

        # Extract authentication context
        auth_context = self._extract_auth_context(context)

        # Store in context variable for access by tools
        auth_context_var.set(auth_context)

        # Log detailed authentication context for debugging
        logger.info("=" * 80)
        logger.info("AUTH CONTEXT MIDDLEWARE - EXTRACTED CONTEXT")
        logger.info("=" * 80)
        logger.info("Tool: %s", tool_name)
        logger.info("Authenticated: %s", auth_context["authenticated"])
        logger.info("ISV Token Present: %s", "isv_token" in auth_context and auth_context["isv_token"] is not None)
        if "isv_token" in auth_context and auth_context["isv_token"]:
            token_preview = (
                auth_context["isv_token"][:20] + "..."
                if len(auth_context["isv_token"]) > 20
                else auth_context["isv_token"]
            )
            logger.info("ISV Token Preview: %s", token_preview)
        logger.info("Cookies Count: %d", len(auth_context.get("cookies", {})))
        for cookie_name, cookie_value in auth_context.get("cookies", {}).items():
            value_preview = cookie_value[:20] + "..." if len(cookie_value) > 20 else cookie_value
            logger.info("  Cookie: %s = %s", cookie_name, value_preview)
        logger.info("=" * 80)

        if auth_context["authenticated"]:
            logger.info(
                "✓ Tool '%s' will execute with authentication context",
                tool_name,
                "present" if auth_context["isv_token"] else "absent",
                len(auth_context["cookies"]),
            )
        else:
            logger.debug("Tool '%s' executing without authentication context", tool_name)

        # Continue to next middleware/tool
        try:
            return await call_next(context)
        finally:
            # Clean up context variable after tool execution
            auth_context_var.set(None)


def get_auth_context() -> Optional[Dict[str, Any]]:
    """
    Helper function to get the current authentication context.

    This can be called from anywhere in the tool execution chain to access
    the authentication context set by AuthContextMiddleware.

    Returns:
        Dict with authentication context or None if not available
    """
    return auth_context_var.get()


def get_auth_headers() -> Dict[str, str]:
    """
    Helper function to build authentication headers from current context.

    Returns:
        Dict of headers to add to HTTP requests
    """
    headers = {}
    auth_context = get_auth_context()

    if auth_context:
        # Add ISV token as X-ISV-Token header
        if auth_context.get("isv_token"):
            headers["X-ISV-Token"] = auth_context["isv_token"]

        # Add cookies as X-Platform-Cookie header
        if auth_context.get("cookies"):
            cookie_str = "; ".join(f"{name}={value}" for name, value in auth_context["cookies"].items())
            if cookie_str:
                headers["X-Platform-Cookie"] = cookie_str

    return headers
