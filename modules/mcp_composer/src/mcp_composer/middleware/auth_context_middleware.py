"""
Authentication Context Middleware

Extracts authentication information from incoming requests and makes it available
to member server tools via context variables. This allows automatic forwarding of
ISV tokens and platform cookies to downstream API calls without modifying tool arguments.
"""

import contextvars
import json
import logging
from typing import Any, Dict, List, Optional
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

AUTHORIZATION_PREFIX = "ibm-platform"

# Auth context dict keys
AUTH_KEY_ISV_TOKEN = "isv_token"
AUTH_KEY_COOKIES = "cookies"
AUTH_KEY_AUTHENTICATED = "authenticated"
AUTH_KEY_USER_IDENTITY = "user_identity"
AUTH_KEY_USER_INSTANCES = "user_instances"  # Simplified instance data (backward compatibility)
AUTH_KEY_USER_INSTANCES_FULL = "user_instances_full"  # Full instance data for authorization
AUTH_KEY_AUTH_TOKEN = "auth_token"  # Cookie value to use as Authorization header

# HTTP header names for auth forwarding
AUTH_HEADER_ISV_TOKEN = "X-ISV-Token"
AUTH_HEADER_PLATFORM_COOKIE = "X-Platform-Cookie"
AUTH_HEADER_USER_INSTANCES = "X-User-Instances"

# Request header names we read from
HEADER_COOKIE = "cookie"
HEADER_AUTHORIZATION = "authorization"
HEADER_USER_INSTANCES = "x-user-instances"

# Cookie key for request context (derived from dashboard URL when not provided)
REQUEST_CONTEXT_KEY = "x-request-context"

# Module-level context variable to store authentication context
# This is thread-safe and async-safe via contextvars
auth_context_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "auth_context", default=None
)


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
        use_cookie_as_auth: bool = False,
        auth_cookie_name: str = "mcsp-glb-iam-test",
        **kwargs,
    ):
        super().__init__(**kwargs)
        # No default cookies - only forward what's explicitly configured
        self.forward_cookies = forward_cookies if forward_cookies is not None else []
        self.add_isv_token = add_isv_token
        self.add_cookie_header = add_cookie_header
        self.use_cookie_as_auth = use_cookie_as_auth
        self.auth_cookie_name = auth_cookie_name

        logger.info(
            "AuthContextMiddleware initialized (forward_cookies=%s, add_isv_token=%s, add_cookie_header=%s, use_cookie_as_auth=%s, auth_cookie_name=%s)",
            self.forward_cookies or "none",
            self.add_isv_token,
            self.add_cookie_header,
            self.use_cookie_as_auth,
            self.auth_cookie_name,
        )

    def _get_request(self, context: MiddlewareContext) -> Any:
        """Get the HTTP request from context, or None if unavailable."""
        fastmcp_ctx = getattr(context, "fastmcp_context", None)
        if fastmcp_ctx is None:
            return None
        request_context = getattr(fastmcp_ctx, "request_context", None)
        return getattr(request_context, "request", None) if request_context else None

    def _extract_from_user(self, request: Any, auth_context: Dict[str, Any]) -> None:
        """Extract ISV token and identity from request.state.user."""
        request_state = getattr(request, "state", None)
        if request_state is None or not hasattr(request_state, "user"):
            return
        user = request_state.user
        if hasattr(user, "access_token") and user.access_token:
            auth_context[AUTH_KEY_ISV_TOKEN] = user.access_token
            auth_context[AUTH_KEY_AUTHENTICATED] = True
            logger.debug("Extracted ISV token from authenticated user")
        if hasattr(user, "identity"):
            auth_context[AUTH_KEY_USER_IDENTITY] = user.identity

    def _extract_user_instances(
        self, request: Any, auth_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract user instances from user.identity or X-User-Instances header."""
        instances: List[Dict[str, Any]] = []

        request_state = getattr(request, "state", None)
        if request_state and hasattr(request_state, "user"):
            user = request_state.user
            if hasattr(user, "identity") and user.identity:
                identity = user.identity
                if isinstance(identity, dict):
                    raw = identity.get("userInstances", identity.get("user_instances"))
                elif hasattr(identity, "userInstances"):
                    raw = identity.userInstances
                elif hasattr(identity, "user_instances"):
                    raw = identity.user_instances
                else:
                    raw = None
                if isinstance(raw, list):
                    instances = raw

        if not instances:
            request_headers = getattr(request, "headers", None)
            if request_headers and (raw_header := request_headers.get(HEADER_USER_INSTANCES, "")):
                try:
                    raw = json.loads(raw_header)
                    if isinstance(raw, list):
                        instances = raw
                except json.JSONDecodeError:
                    pass

        return instances

    def _update_x_request_context_from_instances(
        self,
        auth_context: Dict[str, Any],
        instances: List[Dict[str, Any]],
    ) -> None:
        """
        Update x-request-context from dashboard URL (host part before ?) when
        not already provided by the client and x-request-context is in forward_cookies.
        """
        if REQUEST_CONTEXT_KEY not in self.forward_cookies:
            return
        if auth_context[AUTH_KEY_COOKIES].get(REQUEST_CONTEXT_KEY):
            return
        if not instances:
            return

        first = instances[0]
        dashboard_url = first.get("dashboardURL") or ""
        if dashboard_url:
            host = dashboard_url.split("?")[0].rstrip("/")
            if host:
                auth_context[AUTH_KEY_COOKIES][REQUEST_CONTEXT_KEY] = host
                logger.debug("Set x-request-context from dashboard URL: %s", host[:60])

    def _extract_cookies_and_auth_header(
        self, request: Any, auth_context: Dict[str, Any]
    ) -> None:
        """Extract cookies and fallback ISV token from request headers."""
        request_headers = getattr(request, "headers", None)
        if request_headers is None:
            return

        if self.forward_cookies:
            # Parse standard Cookie header
            cookie_header = request_headers.get(HEADER_COOKIE, "")
            if cookie_header:
                for cookie in cookie_header.split(";"):
                    cookie = cookie.strip()
                    if "=" in cookie:
                        name, value = cookie.split("=", 1)
                        if any(fn in name for fn in self.forward_cookies):
                            auth_context[AUTH_KEY_COOKIES][name] = value
                            logger.debug("Extracted cookie from Cookie header: %s", name)

            # Extract from custom headers
            for cookie_name in self.forward_cookies:
                if header_value := request_headers.get(cookie_name, ""):
                    auth_context[AUTH_KEY_COOKIES][cookie_name] = header_value
                    logger.debug("Extracted cookie from custom header: %s", cookie_name)

        # Fallback: ISV token from Authorization header
        if auth_context.get(AUTH_KEY_ISV_TOKEN):
            return
        auth_header = request_headers.get(HEADER_AUTHORIZATION, "")
        if auth_header.startswith(AUTHORIZATION_PREFIX):
            potential_token = auth_header[len(AUTHORIZATION_PREFIX) :].strip()
            if len(potential_token) > 20:
                auth_context[AUTH_KEY_ISV_TOKEN] = potential_token
                auth_context[AUTH_KEY_AUTHENTICATED] = True
                logger.debug("Extracted ISV token from Authorization header")

    def _extract_auth_context(self, context: MiddlewareContext) -> Dict[str, Any]:
        """
        Extract authentication context from the incoming request.

        Returns:
            Dict containing:
            - isv_token: ISV access token from authenticated user
            - cookies: Dict of cookie name -> value for forwarding
            - authenticated: Boolean indicating if user is authenticated
        """
        auth_context: Dict[str, Any] = {
            AUTH_KEY_ISV_TOKEN: None,
            AUTH_KEY_COOKIES: {},
            AUTH_KEY_AUTHENTICATED: False,
            AUTH_KEY_USER_INSTANCES: [],  # Simplified format (backward compatibility)
            AUTH_KEY_USER_INSTANCES_FULL: [],  # Full instance data for authorization
            AUTH_KEY_AUTH_TOKEN: None,  # Cookie value for Authorization header
        }

        try:
            request = self._get_request(context)
            if request is None:
                return auth_context

            self._extract_from_user(request, auth_context)
            self._extract_cookies_and_auth_header(request, auth_context)
            
            # If use_cookie_as_auth is enabled, extract the auth cookie value
            if self.use_cookie_as_auth:
                logger.debug("use_cookie_as_auth is enabled, auth_cookie_name: %s", self.auth_cookie_name)
                logger.debug("Available cookies: %s", list(auth_context[AUTH_KEY_COOKIES].keys()))
                if self.auth_cookie_name in auth_context[AUTH_KEY_COOKIES]:
                    cookie_value = auth_context[AUTH_KEY_COOKIES][self.auth_cookie_name]
                    auth_context[AUTH_KEY_AUTH_TOKEN] = cookie_value
                    logger.info("✓ Extracted auth token from cookie '%s': %s",
                               self.auth_cookie_name,
                               cookie_value[:20] + "..." if len(cookie_value) > 20 else cookie_value)
                else:
                    logger.warning("✗ Cookie '%s' not found in request cookies", self.auth_cookie_name)
            else:
                logger.debug("use_cookie_as_auth is disabled")

            instances = self._extract_user_instances(request, auth_context)
            if instances:
                # Store full instance data for authorization and routing
                auth_context[AUTH_KEY_USER_INSTANCES_FULL] = instances
                logger.debug("Stored %d full user instances for authorization", len(instances))
                
                # Keep simplified format for backward compatibility
                auth_context[AUTH_KEY_USER_INSTANCES] = [
                    {
                        "instance_id": i.get("id", ""),
                        "subscriptionName": (i.get("subscription") or {}).get("subscriptionName", ""),
                        "productId": (i.get("subscription") or {}).get("productId", ""),
                        "host": (i.get("dashboardURL") or "").split("?")[0].rstrip("/"),
                    }
                    for i in instances
                ]
                self._update_x_request_context_from_instances(auth_context, instances)

        except Exception as e:
            logger.warning("Failed to extract authentication context: %s", e)

        return auth_context

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        """
        Extract authentication context and store in context variable before tool execution.
        Only runs when the tool name contains "gurdium init".
        """
        tool_name = getattr(context.message, "name", "unknown")
        logger.info("Tool name: %s", tool_name)
        if "gurdium" not in tool_name.lower():
            return await call_next(context)

        auth_context = self._extract_auth_context(context)
        auth_context_var.set(auth_context)

        # Log at appropriate level: info when authenticated, debug otherwise
        cookies = auth_context.get(AUTH_KEY_COOKIES, {})
        if auth_context[AUTH_KEY_AUTHENTICATED]:
            token_status = "present" if auth_context.get(AUTH_KEY_ISV_TOKEN) else "absent"
            logger.info(
                "Tool '%s' executing with auth (token=%s, cookies=%d)",
                tool_name,
                token_status,
                len(cookies),
            )
        else:
            logger.debug("Tool '%s' executing without authentication context", tool_name)

        if logger.isEnabledFor(logging.DEBUG):
            token = auth_context.get(AUTH_KEY_ISV_TOKEN)
            token_preview = f"{token[:20]}..." if token and len(token) > 20 else token
            cookie_preview = ", ".join(
                f"{k}={v[:20]}..." if len(v) > 20 else f"{k}={v}"
                for k, v in cookies.items()
            )
            logger.debug(
                "Auth context: tool=%s, token=%s, cookies=[%s]",
                tool_name,
                token_preview,
                cookie_preview,
            )

        try:
            return await call_next(context)
        finally:
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
    auth_context = get_auth_context()
    if not auth_context:
        return {}

    headers: Dict[str, str] = {}
    if token := auth_context.get(AUTH_KEY_ISV_TOKEN):
        headers[AUTH_HEADER_ISV_TOKEN] = token
    if cookies := auth_context.get(AUTH_KEY_COOKIES):
        if cookie_str := "; ".join(f"{k}={v}" for k, v in cookies.items()):
            headers[AUTH_HEADER_PLATFORM_COOKIE] = cookie_str
    if instances := auth_context.get(AUTH_KEY_USER_INSTANCES):
        headers[AUTH_HEADER_USER_INSTANCES] = json.dumps(instances)
    return headers
