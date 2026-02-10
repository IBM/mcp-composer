"""Session-aware middleware for accessing session and request context.

This middleware provides access to session information, request IDs, and
other context data from FastMCP's request context.
"""

from typing import Any, Dict, Optional
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def _get_nested(obj: Any, dotted: str) -> Any:
    """Get nested attr or dict key via dotted path, e.g. 'fastmcp_context.fastmcp.name'."""
    cur = obj
    for part in dotted.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _ctx_get(context: MiddlewareContext, *names: str, default: Any = None) -> Any:
    """Try dotted names on context, then on context.message."""
    for name in names:
        val = _get_nested(context, name)
        if val is not None:
            return val
        msg = getattr(context, "message", None)
        if msg is not None:
            val = _get_nested(msg, name)
            if val is not None:
                return val
    return default


def _get_headers(context: MiddlewareContext) -> Dict[str, str]:
    """Extract headers from context using multiple strategies."""
    headers: Dict[str, str] = {}

    # Strategy 1: Direct headers attribute
    if hasattr(context, "headers"):
        headers = context.headers or {}
        if headers:
            return headers

    # Strategy 2: FastMCP context -> request_context -> request -> headers
    if hasattr(context, "fastmcp_context"):
        fastmcp_ctx = context.fastmcp_context
        if hasattr(fastmcp_ctx, "request_context") and fastmcp_ctx.request_context:
            req_ctx = fastmcp_ctx.request_context
            if hasattr(req_ctx, "request"):
                req = req_ctx.request
                if hasattr(req, "headers"):
                    headers = req.headers or {}
                    if headers:
                        return headers

    # Strategy 3: Try to get from message
    if hasattr(context, "message"):
        msg = context.message
        if hasattr(msg, "headers"):
            headers = msg.headers or {}
            if headers:
                return headers

    return headers


class SessionAwareMiddleware(Middleware):
    """Middleware that provides access to session and request context.

    This middleware extracts session information, request IDs, and other
    context data from FastMCP's request context. It can be used by other
    middleware or tools to access session-specific information.

    Features:
    - Extracts session_id from FastMCP context
    - Extracts request_id from headers or context
    - Provides access to HTTP headers when available
    - Stores session info in context for downstream use
    """

    def __init__(
        self,
        log_session_info: bool = False,
        session_id_header: str = "x-session-id",
        request_id_header: str = "x-request-id",
    ):
        """Initialize session-aware middleware.

        Args:
            log_session_info: Whether to log session information (default: False)
            session_id_header: HTTP header name for session ID (default: "x-session-id")
            request_id_header: HTTP header name for request ID (default: "x-request-id")
        """
        super().__init__()
        self.log_session_info = log_session_info
        self.session_id_header = session_id_header.lower()
        self.request_id_header = request_id_header.lower()

    def _extract_session_info(self, context: MiddlewareContext) -> Dict[str, Any]:
        """Extract session and request information from context.

        Returns:
            Dictionary containing session_id, request_id, headers, and other context info
        """
        session_info: Dict[str, Any] = {
            "session_id": None,
            "request_id": None,
            "headers": {},
            "has_mcp_session": False,
            "transport": None,
        }

        # Try to get FastMCP context
        fastmcp_ctx = _ctx_get(context, "fastmcp_context", default=None)

        if fastmcp_ctx:
            # MCP session available - can access session-specific attributes
            session_info["has_mcp_session"] = True

            # Extract session_id from FastMCP context
            session_id = _ctx_get(
                context,
                "fastmcp_context.session_id",
                "session_id",
                default=None,
            )
            if session_id:
                session_info["session_id"] = str(session_id)

            # Extract request_id from FastMCP context
            request_id = _ctx_get(
                context,
                "fastmcp_context.request_id",
                "request_id",
                default=None,
            )
            if request_id:
                session_info["request_id"] = str(request_id)

            # Extract transport type
            transport = _ctx_get(
                context,
                "fastmcp_context.transport",
                "transport",
                default=None,
            )
            if transport:
                session_info["transport"] = str(transport)

            # Extract FastMCP server name
            composer_name = _ctx_get(
                context,
                "fastmcp_context.fastmcp.name",
                default=None,
            )
            if composer_name:
                session_info["composer_name"] = str(composer_name)

        # Get headers (works for HTTP transport)
        headers = _get_headers(context)
        if headers:
            session_info["headers"] = dict(headers)

            # Extract session_id from headers if not already found
            if not session_info["session_id"]:
                session_id = headers.get(self.session_id_header) or headers.get(
                    self.session_id_header.upper()
                )
                if session_id:
                    session_info["session_id"] = str(session_id)

            # Extract request_id from headers if not already found
            if not session_info["request_id"]:
                request_id = headers.get(self.request_id_header) or headers.get(
                    self.request_id_header.upper()
                )
                if request_id:
                    session_info["request_id"] = str(request_id)

        # Store session info in context for downstream middleware/tools
        if not hasattr(context, "session_info"):
            context.session_info = session_info
        else:
            # Merge with existing session_info if present
            existing = getattr(context, "session_info", {})
            if isinstance(existing, dict):
                existing.update(session_info)
                context.session_info = existing

        return session_info

    async def on_request(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Intercept requests and extract session information."""
        session_info = self._extract_session_info(context)

        if self.log_session_info:
            logger.debug(
                "Session info - session_id: %s, request_id: %s, transport: %s",
                session_info.get("session_id", "N/A"),
                session_info.get("request_id", "N/A"),
                session_info.get("transport", "N/A"),
            )

        return await call_next(context)

    async def on_call_tool(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Extract session info before tool calls."""
        # Ensure session info is available
        if not hasattr(context, "session_info"):
            self._extract_session_info(context)

        return await call_next(context)

    async def on_list_tools(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Extract session info before listing tools."""
        if not hasattr(context, "session_info"):
            self._extract_session_info(context)

        return await call_next(context)

    async def on_list_resources(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Extract session info before listing resources."""
        if not hasattr(context, "session_info"):
            self._extract_session_info(context)

        return await call_next(context)

    async def on_list_prompts(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Extract session info before listing prompts."""
        if not hasattr(context, "session_info"):
            self._extract_session_info(context)

        return await call_next(context)

    @staticmethod
    def get_session_id(context: MiddlewareContext) -> Optional[str]:
        """Get session ID from context (helper method for other middleware/tools)."""
        if hasattr(context, "session_info"):
            return context.session_info.get("session_id")
        return None

    @staticmethod
    def get_request_id(context: MiddlewareContext) -> Optional[str]:
        """Get request ID from context (helper method for other middleware/tools)."""
        if hasattr(context, "session_info"):
            return context.session_info.get("request_id")
        return None

    @staticmethod
    def get_headers(context: MiddlewareContext) -> Dict[str, str]:
        """Get headers from context (helper method for other middleware/tools)."""
        if hasattr(context, "session_info"):
            return context.session_info.get("headers", {})
        return {}
