"""Error sanitization middleware for user-friendly error messages.

This middleware intercepts tool errors, logs detailed information internally,
and returns sanitized, user-friendly error messages that don't expose
platform or configuration details.
"""

import re
import traceback
from collections import defaultdict
from typing import Any, Dict, Optional, Tuple
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent, CallToolResult

from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class _ErrorToolResult(ToolResult):
    """ToolResult subclass for sanitized error responses.

    Provides `.to_mcp_result()` (required by the FastMCP middleware pipeline)
    and exposes `.isError` / `.structuredContent` for direct attribute access.
    """

    isError: bool = True
    structuredContent: dict[str, Any] | None = None

    def __init__(self, content: list, structured_content: dict, **kwargs):
        super().__init__(
            content=content, structured_content=structured_content, **kwargs
        )
        self.structuredContent = structured_content

    def to_mcp_result(self):
        return CallToolResult(
            content=self.content,
            structuredContent=self.structured_content,
            isError=True,
        )


class ErrorSanitizationMiddleware(Middleware):
    """Middleware that sanitizes tool errors for end users.

    Features:
    - Logs full error details internally
    - Returns user-friendly error messages
    - Hides platform/configuration details
    - Provides alternative suggestions
    """

    def __init__(
        self,
        enable_sanitization: bool = True,
        exempt_tools: Optional[set[str]] = None,
        log_full_traceback: bool = True,
        track_statistics: bool = True,
    ):
        """Initialize error sanitization middleware.

        Args:
            enable_sanitization: If False, errors pass through unchanged
            exempt_tools: Set of tool names to skip sanitization
            log_full_traceback: Whether to log full traceback (default: True)
            track_statistics: Whether to track error statistics (default: True)
        """
        super().__init__()
        self.enable_sanitization = enable_sanitization
        self.exempt_tools = exempt_tools or set()
        self.log_full_traceback = log_full_traceback
        self.track_statistics = track_statistics
        self.error_counts: Dict[str, int] = defaultdict(int)

    def _categorize_error(self, error: Exception) -> Tuple[str, str, Optional[str]]:
        """Categorize error and generate user-friendly message.

        Returns:
            Tuple of (category, user_message, suggestion)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Network/Connection errors
        if any(
            term in error_str
            for term in [
                "connection",
                "timeout",
                "network",
                "unreachable",
                "refused",
                "dns",
                "socket",
                "connectionerror",
                "timeouterror",
                "max retries",
                "max retries exceeded",
                "max retries reached",
                "max iterations",
                "max iterations exceeded",
                "max iterations reached",
            ]
        ):
            return (
                "connection",
                "Unable to connect to the service. Please check your network connection and try again.",
                "Try again in a few moments. If the issue persists, verify your network connection or contact support.",
            )

        # Authentication errors
        if any(
            term in error_str
            for term in [
                "401",
                "unauthorized",
                "authentication",
                "auth",
                "credential",
                "token",
                "apikey",
                "forbidden",
                "403",
                "permission",
            ]
        ):
            return (
                "authentication",
                "Authentication failed. Please verify your credentials.",
                "Check your API keys or authentication settings. You may need to refresh your credentials.",
            )

        # Not found errors
        if any(
            term in error_str
            for term in [
                "404",
                "not found",
                "does not exist",
                "notfound",
                "missing",
            ]
        ):
            return (
                "not_found",
                "The requested resource could not be found.",
                "Verify the resource name or identifier. Try searching for similar resources or check if the resource was moved.",
            )

        # Rate limiting
        if any(
            term in error_str
            for term in [
                "429",
                "rate limit",
                "too many requests",
                "quota",
                "throttle",
            ]
        ):
            return (
                "rate_limit",
                "Too many requests. Please wait a moment before trying again.",
                "Wait a few seconds and retry. Consider reducing the frequency of your requests.",
            )

        # Server errors (5xx)
        if any(
            term in error_str
            for term in [
                "500",
                "502",
                "503",
                "504",
                "internal server",
                "bad gateway",
                "service unavailable",
                "gateway timeout",
            ]
        ):
            return (
                "server_error",
                "The service is temporarily unavailable. Please try again later.",
                "Wait a few moments and retry. If the issue persists, the service may be undergoing maintenance.",
            )

        # Validation errors
        if (
            any(
                term in error_str
                for term in [
                    "validation",
                    "invalid",
                    "malformed",
                    "parse",
                    "json",
                    "schema",
                    "validationerror",
                ]
            )
            or "ValidationError" in error_type
        ):
            return (
                "validation",
                "The request contains invalid data. Please check your input and try again.",
                "Review the required fields and formats. Ensure all required parameters are provided correctly.",
            )

        # Configuration errors (hide details)
        if any(
            term in error_str
            for term in [
                "config",
                "endpoint",
                "url",
                "environment",
                "variable",
                "setting",
                "configuration",
            ]
        ):
            return (
                "configuration",
                "A configuration issue prevented the operation from completing.",
                "Contact your administrator or support team to verify system configuration.",
            )

        # Circuit breaker
        if "circuit" in error_str or "CircuitBreaker" in error_type:
            return (
                "circuit_breaker",
                "The service is temporarily unavailable due to repeated failures.",
                "Wait a moment and try again. The service will automatically recover once stable.",
            )

        # Generic error
        return (
            "generic",
            "An unexpected error occurred while processing your request.",
            "Please try again. If the problem persists, contact support with the request details.",
        )

    def _sanitize_error_message(self, error: Exception) -> str:
        """Remove sensitive information from error messages."""
        error_msg = str(error)

        # Remove file paths
        error_msg = re.sub(r"/[^\s]+", "[path]", error_msg)

        # Remove IP addresses
        error_msg = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[ip]", error_msg)

        # Remove API keys/tokens (common patterns)
        error_msg = re.sub(
            r"(?i)(api[_-]?key|token|secret|password|credential)\s*[:=]\s*[\w-]+",
            r"\1=[hidden]",
            error_msg,
        )

        # Remove URLs with credentials
        error_msg = re.sub(
            r"https?://[^:]+:[^@]+@[^\s]+",
            "[url]",
            error_msg,
        )

        # Remove stack trace indicators
        error_msg = re.sub(r"File\s+.*?line\s+\d+", "[source]", error_msg)
        error_msg = re.sub(r"Traceback.*", "", error_msg, flags=re.DOTALL)

        return error_msg.strip()

    def _get_alternative_suggestions(self, tool_name: str, category: str) -> list[str]:
        """Generate alternative suggestions based on tool and error category."""
        suggestions = []

        if category == "connection":
            suggestions.extend(
                [
                    "Check your internet connection",
                    "Verify the service endpoint is accessible",
                    "Try again in a few moments",
                ]
            )
        elif category == "authentication":
            suggestions.extend(
                [
                    "Verify your API credentials",
                    "Check if your authentication token has expired",
                    "Contact your administrator for credential assistance",
                ]
            )
        elif category == "not_found":
            suggestions.extend(
                [
                    "Double-check the resource identifier",
                    "Search for similar resources",
                    "Verify the resource hasn't been deleted or moved",
                ]
            )
        elif category == "rate_limit":
            suggestions.extend(
                [
                    "Wait 30-60 seconds before retrying",
                    "Reduce the frequency of requests",
                    "Consider batching multiple operations",
                ]
            )
        elif category == "server_error":
            suggestions.extend(
                [
                    "Wait a few minutes and retry",
                    "Check service status page if available",
                    "Contact support if the issue persists",
                ]
            )
        elif category == "validation":
            suggestions.extend(
                [
                    "Review the tool's required parameters",
                    "Check the format of your input data",
                    "Refer to the tool's documentation for correct usage",
                ]
            )

        # Tool-specific suggestions
        if "search" in tool_name.lower():
            suggestions.append("Try rephrasing your search query")
        elif "model" in tool_name.lower() or "mesh" in tool_name.lower():
            suggestions.append("Try a different model or provider")
        elif "document" in tool_name.lower():
            suggestions.append("Verify the document exists and is accessible")

        return suggestions[:3]  # Limit to 3 suggestions

    ERROR_STATUS_CODES = (401, 403, 404, 429, 500, 502, 503, 504)

    def _is_error_result(self, result: Dict[str, Any]) -> bool:
        """True if the tool result represents an error (should be sanitized and isError=True)."""
        if result.get("error"):
            return True
        status = result.get("status_code")
        if status is not None and status in self.ERROR_STATUS_CODES:
            return True
        data = result.get("data")
        if isinstance(data, dict) and (data.get("error") or data.get("message")):
            return True
        return False

    def _extract_raw_message(self, result: Dict[str, Any]) -> str:
        """Get the raw error message from various result shapes (top-level or data.*)."""
        msg = result.get("message") or result.get("error")
        if msg:
            return str(msg)
        data = result.get("data")
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error")
            if msg:
                return str(msg)
        return str(result.get("error", ""))

    def _sanitize_error_result(
        self, result: Dict[str, Any], tool_name: str
    ) -> _ErrorToolResult:
        """Sanitize a tool result that is an error; return _ErrorToolResult."""
        status_code = result.get("status_code")
        raw_message = self._extract_raw_message(result)
        category, user_msg, suggestion = self._categorize_error(Exception(raw_message))

        # Log raw details internally (do not expose to client)
        logger.debug(
            "Sanitizing tool error result (tool=%s, status_code=%s): %s",
            tool_name,
            status_code,
            raw_message[:200] + "..." if len(raw_message) > 200 else raw_message,
        )

        # Short text for the agent (no long JWT/backend message)
        error_text = user_msg
        if suggestion:
            error_text += f"\n\nSuggestion: {suggestion}"

        structured = {
            "success": False,
            "service": result.get("service"),
            "status_code": status_code,
            "error": user_msg,
            "message": user_msg,
        }
        if suggestion:
            structured["suggestion"] = suggestion

        return _ErrorToolResult(
            content=[TextContent(type="text", text=error_text)],
            structured_content=structured,
        )

    def _get_method_name(self, context: MiddlewareContext) -> str:
        """Extract method name from context."""
        # Try to get method from message
        if hasattr(context, "message"):
            msg = context.message
            # Check for tool name
            if hasattr(msg, "name") and msg.name:
                return f"call_tool:{msg.name}"
            # Check for prompt name
            if hasattr(msg, "prompt_name") and msg.prompt_name:
                return f"call_prompt:{msg.prompt_name}"
            # Check for resource URI
            if hasattr(msg, "uri") and msg.uri:
                return f"read_resource:{msg.uri}"

        # Try to get from context attributes
        method = getattr(context, "method", None)
        if method:
            return str(method)

        return "unknown"

    def _track_error(self, error: Exception, method: str) -> None:
        """Track error statistics."""
        if not self.track_statistics:
            return

        error_key = f"{type(error).__name__}:{method}"
        self.error_counts[error_key] += 1

    def _log_error(
        self,
        error: Exception,
        method: str,
        category: str,
        tool_name: Optional[str] = None,
    ) -> None:
        """Log error with context."""
        context_info = f"Error in {method}"
        if tool_name and tool_name != "<unknown>":
            context_info += f" (tool: {tool_name})"
        context_info += f": {type(error).__name__}: {error}"

        if self.log_full_traceback:
            logger.error(f"{context_info}\n{traceback.format_exc()}")
        else:
            logger.error(context_info)

    async def on_message(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        """Intercept all messages and handle errors at message level."""
        method = self._get_method_name(context)

        try:
            return await call_next(context)
        except Exception as error:
            # Track error statistics
            self._track_error(error, method)

            # Log the error
            tool_name = (
                getattr(context.message, "name", None)
                if hasattr(context, "message")
                else None
            )
            category, _, _ = self._categorize_error(error)
            self._log_error(error, method, category, tool_name)

            # Re-raise to let specific hooks handle sanitization
            raise

    async def on_call_tool(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Intercept tool calls and sanitize errors."""
        tool_name = getattr(context.message, "name", "<unknown>") or "<unknown>"

        # Skip sanitization for exempt tools
        if tool_name in self.exempt_tools or not self.enable_sanitization:
            return await call_next(context)

        try:
            result = await call_next(context)
            # Sanitize tool results that are errors (top-level error, status_code 4xx/5xx, or data.error)
            if (
                self.enable_sanitization
                and isinstance(result, dict)
                and self._is_error_result(result)
            ):
                result = self._sanitize_error_result(result, tool_name)
            return result

        except ToolError as e:
            # ToolError is already user-facing, but we can still sanitize it
            category, user_msg, suggestion = self._categorize_error(e)
            method = self._get_method_name(context)

            # Track error statistics
            self._track_error(e, method)

            # Log error with context
            self._log_error(e, method, category, tool_name)

            # Generate sanitized message
            sanitized_msg = self._sanitize_error_message(e)
            alternatives = self._get_alternative_suggestions(tool_name, category)

            # Create user-friendly error message
            error_details = {
                "error": user_msg,
                "suggestion": suggestion,
                "alternatives": alternatives,
                "tool": tool_name,
            }

            error_text = f"{user_msg}\n\n"
            if suggestion:
                error_text += f"Suggestion: {suggestion}\n\n"
            if alternatives:
                error_text += "Alternatives:\n"
                for alt in alternatives:
                    error_text += f"  • {alt}\n"

            return _ErrorToolResult(
                content=[TextContent(type="text", text=error_text)],
                structured_content=error_details,
            )

        except Exception as e:
            # Catch all other exceptions
            category, user_msg, suggestion = self._categorize_error(e)
            method = self._get_method_name(context)

            # Track error statistics
            self._track_error(e, method)

            # Log error with context
            self._log_error(e, method, category, tool_name)

            # Generate sanitized message
            sanitized_msg = self._sanitize_error_message(e)
            alternatives = self._get_alternative_suggestions(tool_name, category)

            # Create user-friendly error message
            error_details = {
                "error": user_msg,
                "suggestion": suggestion,
                "alternatives": alternatives,
                "tool": tool_name,
            }

            error_text = f"{user_msg}\n\n"
            if suggestion:
                error_text += f"Suggestion: {suggestion}\n\n"
            if alternatives:
                error_text += "Alternatives:\n"
                for alt in alternatives:
                    error_text += f"  • {alt}\n"

            return _ErrorToolResult(
                content=[TextContent(type="text", text=error_text)],
                structured_content=error_details,
            )

    def get_error_statistics(self) -> Dict[str, int]:
        """Get error statistics.

        Returns:
            Dictionary mapping error keys (error_type:method) to counts
        """
        return dict(self.error_counts)

    def reset_statistics(self) -> None:
        """Reset error statistics."""
        self.error_counts.clear()
