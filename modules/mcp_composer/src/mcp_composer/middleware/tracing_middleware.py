# logging_middleware.py
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.features.opentelemetry_metrics_registry import (
    tool_calls,
    tool_errors,
    tool_duration,
    in_bytes,
    out_bytes,
)

from mcp_composer.core.utils.logger import LoggerFactory

_BASE_LOGGER = LoggerFactory.get_logger()


# --- OpenTelemetry (optional, no-op if not installed) ---
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False

    class _NoTrace:  # minimal no-op shim
        def get_tracer(self, *_a, **_k):
            class _NoSpan:
                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

                def set_attribute(self, *_a, **_k):
                    pass

                def add_event(self, *_a, **_k):
                    pass

                def set_status(self, *_a, **_k):
                    pass

                def record_exception(self, *_a, **_k):
                    pass

            class _NoCtx:
                def start_as_current_span(self, *_a, **_k):
                    return _NoSpan()

            return _NoCtx()

    trace = _NoTrace()

    class Status:  # type: ignore
        def __init__(self, *_a, **_k):
            pass

    class StatusCode:  # type: ignore
        OK = "OK"
        ERROR = "ERROR"


_TRACER = trace.get_tracer("mcp_composer.tracing")
_ALLOWED = (bool, str, bytes, int, float)


def _get_logger(ctx: MiddlewareContext):
    return getattr(ctx, "logger", _BASE_LOGGER)


def _truncate(val: Any, max_len: int) -> Any:
    try:
        s = str(val)
    except Exception:
        return "<unprintable>"
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"... (+{len(s) - max_len} chars)"


def _json_sha256(obj: Any) -> str:
    try:
        b = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()
    except Exception:
        b = str(obj).encode(errors="ignore")
    return hashlib.sha256(b).hexdigest()


def _attr(span, key: str, value: Any):
    try:
        if value is None:
            return
        if isinstance(value, (list, tuple)):
            cleaned = [v for v in value if isinstance(v, _ALLOWED)]
            if cleaned:
                span.set_attribute(key, cleaned)
            return
        if isinstance(value, _ALLOWED):
            span.set_attribute(key, value)
            return
        span.set_attribute(key, str(value))
    except Exception:
        pass


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


def _ctx_get(context: MiddlewareContext, *names, default=None):
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


def _split_tool_fullname(tool_name: str) -> tuple[str | None, str]:
    """Return (server_prefix, stripped_tool_name).
    Rules: server_prefix = substring before first '_'.
    If no underscore, server_prefix=None, stripped_tool=full.
    """
    if not isinstance(tool_name, str) or not tool_name:
        return None, ""
    i = tool_name.find("_")
    if i <= 0:  # no '_' or starts with '_'
        return None, tool_name
    return tool_name[:i], tool_name[i + 1 :]


class TracingMiddleware(Middleware):
    """
    Config:
      log_tools: bool = True
      log_resources: bool = False
      log_prompts: bool = False
      log_args: bool = False
      log_results: bool = False
      max_payload_length: int = 1000
      log_level: "DEBUG"|"INFO"|"WARNING"|"ERROR" = "INFO"

      # Tracing options
      enable_tracing: bool = True
      trace_args_digest: bool = True
      trace_results_digest: bool = True
      trace_payload_sizes: bool = True
      trace_namespaced_spans: bool = True
    """

    def __init__(
        self,
        *,
        log_tools: bool = True,
        log_resources: bool = False,
        log_prompts: bool = False,
        log_args: bool = False,
        log_results: bool = False,
        max_payload_length: int = 1000,
        log_level: str = "INFO",
        # tracing
        enable_tracing: bool = True,
        trace_args_digest: bool = True,
        trace_results_digest: bool = True,
        trace_payload_sizes: bool = True,
        trace_namespaced_spans: bool = True,
        **_: Dict[str, Any],
    ):
        self.log_tools = bool(log_tools)
        self.log_resources = bool(log_resources)
        self.log_prompts = bool(log_prompts)
        self.log_args = bool(log_args)
        self.log_results = bool(log_results)
        self.max_len = int(max_payload_length)
        self.level = (log_level or "INFO").upper()

        # tracing
        self.enable_tracing = bool(enable_tracing and _OTEL_AVAILABLE)
        self.trace_args_digest = bool(trace_args_digest)
        self.trace_results_digest = bool(trace_results_digest)
        self.trace_payload_sizes = bool(trace_payload_sizes)
        self.trace_namespaced_spans = bool(trace_namespaced_spans)

    # ---- helpers ----

    def _log(self, ctx: MiddlewareContext, msg: str, level: Optional[str] = None):
        logger = _get_logger(ctx)
        lvl = (level or self.level).upper()
        fn = getattr(logger, lvl.lower(), logger.info)
        fn(msg)

    def _span_name(self, base: str, detail: Optional[str] = None) -> str:
        if not self.trace_namespaced_spans:
            return detail or base
        return f"{base}:{detail}" if detail else base

    def _decorate_common_attrs(self, span, context: MiddlewareContext, op: str, name: str):
        _attr(span, "mcp.operation", op)
        _attr(span, "mcp.name", name)
        server_name, stripped = _split_tool_fullname(name)

        # Prefer FastMCP-provided values if present
        composer_name = _ctx_get(context, "fastmcp_context.fastmcp.name", "composer_name")
        server_ver = _ctx_get(context, "server_version")
        session_id = _ctx_get(context, "fastmcp_context.session_id", "session_id")
        tenant_id = _ctx_get(context, "tenant_id")

        _attr(span, "mcp.composer.name", composer_name or "unknown")
        _attr(span, "mcp.servername", server_name or "unknown")
        _attr(span, "mcp.server.version", server_ver or "unknown")
        _attr(span, "gen_ai.session.id", session_id or "unknown")
        _attr(span, "mcp.tenant.id", tenant_id)

    # ---- hooks ----

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        tool = getattr(context.message, "name", "unknown")
        args = getattr(context.message, "arguments", {})
        start = time.time()
        logger = _get_logger(context)

        if tool_calls:
            tool_calls.add(1, {"tool": tool})
        if in_bytes:
            try:
                in_bytes.record(len(json.dumps(args, default=str).encode("utf-8")), {"tool": tool})
            except Exception:
                pass

        if self.log_tools:
            # Enhanced logging for tool calls
            logger.debug("=" * 80)
            logger.debug("TOOL CALL - FULL DETAILS")
            logger.debug("=" * 80)
            logger.debug("Tool Name: %s", tool)

            # Log session and context info
            session_id = _ctx_get(context, "fastmcp_context.session_id", "session_id")
            composer_name = _ctx_get(context, "fastmcp_context.fastmcp.name", "composer_name")
            tenant_id = _ctx_get(context, "tenant_id")

            logger.debug("Session ID: %s", session_id or "N/A")
            logger.debug("Composer: %s", composer_name or "N/A")
            logger.debug("Tenant ID: %s", tenant_id or "N/A")

            # Log authentication context
            logger.debug("-" * 80)
            logger.debug("AUTHENTICATION CONTEXT:")
            try:
                # Try to get request from fastmcp_context
                fastmcp_ctx = getattr(context, "fastmcp_context", None)
                if fastmcp_ctx:
                    request_ctx = getattr(fastmcp_ctx, "request_context", None)
                    if request_ctx:
                        request = getattr(request_ctx, "request", None)
                        if request:
                            # Log authentication headers
                            if hasattr(request, "headers"):
                                auth_header = request.headers.get("authorization")
                                if auth_header:
                                    logger.debug("  Authorization: ***REDACTED***")
                                else:
                                    logger.debug("  Authorization: Not present")

                                # Log cookie header (redacted)
                                cookie_header = request.headers.get("cookie")
                                if cookie_header:
                                    # Show cookie names but redact values
                                    cookies = cookie_header.split(";")
                                    cookie_names = [c.split("=")[0].strip() for c in cookies]
                                    logger.debug("  Cookies present: %s", cookie_names)
                                else:
                                    logger.debug("  Cookies: Not present")

                                # Log grant_type if present
                                grant_type = request.headers.get("grant_type")
                                if grant_type:
                                    logger.debug("  Grant Type: %s", grant_type)

                            # Log authenticated user info
                            if hasattr(request, "state") and hasattr(request.state, "user"):
                                user = request.state.user
                                logger.debug("  Authenticated User:")
                                if hasattr(user, "identity"):
                                    logger.debug("    Identity: %s", user.identity)
                                if hasattr(user, "is_authenticated"):
                                    logger.debug("    Is Authenticated: %s", user.is_authenticated)
                                if hasattr(user, "access_token"):
                                    token = user.access_token
                                    if len(token) > 20:
                                        redacted = f"{token[:10]}...{token[-10:]}"
                                    else:
                                        redacted = "***REDACTED***"
                                    logger.debug("    Access Token: %s", redacted)
                            else:
                                logger.debug("  No authenticated user in request.state")
                        else:
                            logger.debug("  No request object in request_context")
                    else:
                        logger.debug("  No request_context in fastmcp_context")
                else:
                    logger.debug("  No fastmcp_context available")
            except Exception as e:
                logger.debug("Could not extract authentication context: %s", e)

            # Log tool arguments
            logger.debug("-" * 80)
            logger.debug("TOOL ARGUMENTS:")
            if self.log_args:
                if args:
                    try:
                        args_json = json.dumps(args, indent=2, default=str)
                        logger.debug("%s", args_json)
                    except Exception:
                        logger.debug("%s", _truncate(args, self.max_len))
                else:
                    logger.debug("  No arguments")
            else:
                logger.debug("  (Argument logging disabled)")

            # Try to identify if this is a member server tool and log endpoint
            logger.debug("-" * 80)
            logger.debug("TOOL ROUTING INFO:")
            server_prefix, stripped_name = _split_tool_fullname(tool)
            if server_prefix:
                logger.debug("  Member Server Prefix: %s", server_prefix)
                logger.debug("  Stripped Tool Name: %s", stripped_name)
                logger.debug("  This appears to be a member server tool")

                # Try to get member server info from composer
                try:
                    if fastmcp_ctx:
                        fastmcp = getattr(fastmcp_ctx, "fastmcp", None)
                        if fastmcp and hasattr(fastmcp, "server_manager"):
                            server_manager = fastmcp.server_manager
                            if hasattr(server_manager, "servers"):
                                # Look for the server
                                for srv_name, srv_obj in server_manager.servers.items():
                                    if srv_name == server_prefix or srv_name.startswith(server_prefix):
                                        logger.debug("  Member Server Found: %s", srv_name)
                                        if hasattr(srv_obj, "config"):
                                            config = srv_obj.config
                                            if isinstance(config, dict):
                                                # Log endpoint/URL if available
                                                endpoint = (
                                                    config.get("url") or config.get("endpoint") or config.get("command")
                                                )
                                                if endpoint:
                                                    logger.debug("  Server Endpoint: %s", endpoint)
                                                transport = config.get("transport")
                                                if transport:
                                                    logger.debug("  Transport: %s", transport)
                                        break
                except Exception as e:
                    logger.debug("Could not extract member server info: %s", e)
            else:
                logger.debug("  This is a local/direct tool (no member server prefix)")

            logger.debug("-" * 80)

        start = time.time()
        span_cm = (
            _TRACER.start_as_current_span(self._span_name("agent.tool", tool)) if self.enable_tracing else nullcontext()
        )

        try:
            with span_cm as span:
                if self.enable_tracing:
                    _attr(span, "tool.name", tool)
                    _attr(
                        span,
                        "tool.version",
                        getattr(context.message, "version", "unknown"),
                    )
                    self._decorate_common_attrs(span, context, "tool.call", tool)

                    if self.trace_args_digest:
                        span.add_event(
                            "tool.input",
                            {
                                "sha256": _json_sha256(args),
                                **(
                                    {"size_bytes": len(json.dumps(args, default=str))}
                                    if self.trace_payload_sizes
                                    else {}
                                ),
                            },
                        )

                result = await call_next(context)

                if self.enable_tracing and self.trace_results_digest:
                    span.add_event(
                        "tool.output",
                        {
                            "sha256": _json_sha256(result),
                            **(
                                {"size_bytes": len(json.dumps(result, default=str))} if self.trace_payload_sizes else {}
                            ),
                        },
                    )
                    span.set_status(Status(StatusCode.OK))

                if self.log_tools:
                    # Enhanced result logging
                    logger.debug("-" * 80)
                    logger.debug("TOOL RESPONSE:")

                    if self.log_results:
                        try:
                            # Try to extract detailed response information
                            if hasattr(result, "content"):
                                # MCP ToolResult format
                                content = result.content
                                logger.debug("  Response Type: ToolResult")
                                if isinstance(content, list):
                                    logger.debug("  Content Items: %d", len(content))
                                    for idx, item in enumerate(content[:3]):  # First 3 items
                                        if hasattr(item, "type"):
                                            logger.debug("    Item %d Type: %s", idx, item.type)
                                        if hasattr(item, "text"):
                                            logger.debug("    Item %d Text: %s", idx, _truncate(item.text, 200))
                                    if len(content) > 3:
                                        logger.debug("    ... and %d more items", len(content) - 3)
                                else:
                                    logger.debug("  Content: %s", _truncate(content, self.max_len))

                                # Log if there's an error
                                if hasattr(result, "isError") and result.isError:
                                    logger.warning("  Tool returned an error!")
                            else:
                                # Raw result
                                logger.debug("  Response Type: Raw")
                                result_json = json.dumps(result, indent=2, default=str)
                                if len(result_json) > self.max_len:
                                    logger.debug("  Result (truncated):\n%s", result_json[: self.max_len])
                                    logger.debug("  ... (+%d chars)", len(result_json) - self.max_len)
                                else:
                                    logger.debug("  Result:\n%s", result_json)
                        except Exception as e:
                            logger.debug("Could not parse result details: %s", e)
                            logger.debug("  Result: %s", _truncate(result, self.max_len))

                        logger.debug("✅ Tool execution successful")
                    else:
                        logger.debug("  (Result logging disabled)")
                        logger.debug("✅ Tool execution successful")

                    logger.debug("=" * 80)

                # Duration
                if tool_duration:
                    tool_duration.record(int((time.time() - start) * 1000), {"tool": tool})

                # Output size
                if out_bytes:
                    try:
                        out_bytes.record(
                            len(json.dumps(result, default=str).encode("utf-8")),
                            {"tool": tool},
                        )
                    except Exception:
                        pass

                return result

        except Exception as e:
            if self.enable_tracing:
                try:
                    span.record_exception(e)  # type: ignore[attr-defined]
                    span.set_status(Status(StatusCode.ERROR, description=type(e).__name__))  # type: ignore[attr-defined]
                except Exception:
                    pass
                if tool_errors:
                    tool_errors.add(1, {"tool": tool})
                self._log(context, f" {tool} error: {e}", level="ERROR")
                raise
        finally:
            if self.enable_tracing:
                duration_ms = int((time.time() - start) * 1000)
                try:
                    _attr(span, "mcp.duration_ms", duration_ms)  # type: ignore[name-defined]
                except Exception:
                    pass

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        if self.log_tools:
            # Enhanced logging for list_tools
            logger = _get_logger(context)
            logger.debug("=" * 80)
            logger.debug("LIST_TOOLS REQUEST - FULL DETAILS")
            logger.debug("=" * 80)

            # Log context information
            session_id = _ctx_get(context, "fastmcp_context.session_id", "session_id")
            composer_name = _ctx_get(context, "fastmcp_context.fastmcp.name", "composer_name")
            tenant_id = _ctx_get(context, "tenant_id")

            logger.debug("Session ID: %s", session_id or "N/A")
            logger.debug("Composer: %s", composer_name or "N/A")
            logger.debug("Tenant ID: %s", tenant_id or "N/A")

            # Log full request message details
            if hasattr(context, "message"):
                msg = context.message
                logger.debug("-" * 80)
                logger.debug("REQUEST MESSAGE:")
                logger.debug("Type: %s", type(msg).__name__)

                # Log all message attributes
                try:
                    msg_dict = {}
                    for attr in dir(msg):
                        if not attr.startswith("_"):
                            try:
                                val = getattr(msg, attr)
                                if not callable(val):
                                    msg_dict[attr] = val
                            except Exception:
                                pass

                    logger.debug("Message attributes:")
                    for key, value in msg_dict.items():
                        logger.debug("  %s: %s", key, _truncate(value, 500))
                except Exception as e:
                    logger.debug("Could not extract message attributes: %s", e)

                # Try to serialize full message as JSON
                try:
                    import json

                    if hasattr(msg, "model_dump"):
                        msg_json = msg.model_dump()
                    elif hasattr(msg, "dict"):
                        msg_json = msg.dict()
                    else:
                        msg_json = str(msg)
                    logger.debug("-" * 80)
                    logger.debug("FULL REQUEST (JSON):")
                    logger.debug("%s", json.dumps(msg_json, indent=2, default=str))
                except Exception as e:
                    logger.debug("Could not serialize message to JSON: %s", e)

            # Try to access HTTP request headers if available
            logger.debug("-" * 80)
            logger.debug("HTTP REQUEST HEADERS:")
            try:
                # Try to get the underlying HTTP request from fastmcp_context
                fastmcp_ctx = getattr(context, "fastmcp_context", None)
                if fastmcp_ctx:
                    # Check for request object
                    request = getattr(fastmcp_ctx, "request", None)
                    if request and hasattr(request, "headers"):
                        for header_name, header_value in request.headers.items():
                            # Redact sensitive headers
                            if header_name.lower() in ["authorization", "cookie"]:
                                if len(header_value) > 20:
                                    redacted = f"{header_value[:10]}...{header_value[-10:]}"
                                else:
                                    redacted = "***REDACTED***"
                                logger.debug("  %s: %s", header_name, redacted)
                            else:
                                logger.debug("  %s: %s", header_name, header_value)
                    else:
                        logger.debug("  No HTTP request object found in context")
                else:
                    logger.debug("  No fastmcp_context available")
            except Exception as e:
                logger.debug("Could not extract HTTP headers: %s", e)

            # Log context attributes
            logger.debug("-" * 80)
            logger.debug("CONTEXT DETAILS:")
            try:
                ctx_attrs = {}
                for attr in dir(context):
                    if not attr.startswith("_") and attr != "message":
                        try:
                            val = getattr(context, attr)
                            if not callable(val):
                                ctx_attrs[attr] = val
                        except Exception:
                            pass

                for key, value in ctx_attrs.items():
                    logger.debug("  %s: %s", key, _truncate(value, 200))
            except Exception as e:
                logger.debug("Could not extract context attributes: %s", e)

            logger.debug("-" * 80)

        span_cm = (
            _TRACER.start_as_current_span(self._span_name("mcp.list.tools")) if self.enable_tracing else nullcontext()
        )

        with span_cm as span:
            if self.enable_tracing:
                self._decorate_common_attrs(span, context, "tools.list", "tools")
            result = await call_next(context)

            n = 0
            try:
                n = len(getattr(result, "tools", result))
            except Exception:
                pass

            if self.log_tools:
                logger = _get_logger(context)
                logger.debug("Tools returned: %d", n)

                # Log tool names if available
                try:
                    tools = getattr(result, "tools", result)
                    if tools and n > 0:
                        tool_names = [getattr(t, "name", str(t)) for t in tools[:10]]  # First 10
                        logger.debug("Tool names (first 10): %s", tool_names)
                        if n > 10:
                            logger.debug("... and %d more tools", n - 10)
                except Exception as e:
                    logger.debug("Could not extract tool names: %s", e)

                logger.debug("=" * 80)

            if self.enable_tracing:
                _attr(span, "mcp.tools.count", n)
                span.set_status(Status(StatusCode.OK))
            if self.log_tools:
                self._log(context, f"listed {n} tools")
            return result

    async def on_read_resource(self, context: MiddlewareContext, call_next: CallNext):
        uri = getattr(context.message, "uri", "unknown")
        if self.log_resources:
            self._log(context, f"read {uri}")

        span_cm = (
            _TRACER.start_as_current_span(self._span_name("mcp.resource.read", uri))
            if self.enable_tracing
            else nullcontext()
        )

        with span_cm as span:
            if self.enable_tracing:
                self._decorate_common_attrs(span, context, "resource.read", uri)
                _attr(span, "mcp.resource.uri", uri)

            result = await call_next(context)

            if self.enable_tracing:
                span.set_status(Status(StatusCode.OK))
            if self.log_resources:
                self._log(context, f"read ok: {uri}")
            return result

    async def on_list_prompts(self, context: MiddlewareContext, call_next: CallNext):
        if self.log_prompts:
            self._log(context, "list prompts")

        span_cm = (
            _TRACER.start_as_current_span(self._span_name("mcp.prompts.list")) if self.enable_tracing else nullcontext()
        )

        with span_cm as span:
            if self.enable_tracing:
                self._decorate_common_attrs(span, context, "prompts.list", "prompts")

            result = await call_next(context)

            if self.enable_tracing:
                span.set_status(Status(StatusCode.OK))
            if self.log_prompts:
                self._log(context, "list prompts ok")
            return result


# --- Small stdlib nullcontext for when tracing is disabled ---
try:
    from contextlib import nullcontext  # py3.7+
except Exception:  # pragma: no cover

    class nullcontext:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
