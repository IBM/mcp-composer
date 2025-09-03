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
    return s[:max_len] + f"... (+{len(s)-max_len} chars)"


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

    def _decorate_common_attrs(
        self, span, context: MiddlewareContext, op: str, name: str
    ):
        _attr(span, "mcp.operation", op)
        _attr(span, "mcp.name", name)
        server_name, stripped = _split_tool_fullname(name)

        # Prefer FastMCP-provided values if present
        composer_name = _ctx_get(
            context, "fastmcp_context.fastmcp.name", "composer_name"
        )
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
        if tool_calls:
            tool_calls.add(1, {"tool": tool})
        if in_bytes:
            try:
                in_bytes.record(
                    len(json.dumps(args, default=str).encode("utf-8")), {"tool": tool}
                )
            except Exception:
                pass

        if self.log_tools:
            if self.log_args:
                self._log(
                    context, f"🛠️  call {tool} args={_truncate(args, self.max_len)}"
                )
            else:
                self._log(context, f"🛠️  call {tool}")

        start = time.time()
        span_cm = (
            _TRACER.start_as_current_span(self._span_name("agent.tool", tool))
            if self.enable_tracing
            else nullcontext()
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
                                {"size_bytes": len(json.dumps(result, default=str))}
                                if self.trace_payload_sizes
                                else {}
                            ),
                        },
                    )
                    span.set_status(Status(StatusCode.OK))

                if self.log_tools:
                    if self.log_results:
                        self._log(
                            context,
                            f"✅ {tool} result={_truncate(result, self.max_len)}",
                        )
                    else:
                        self._log(context, f"✅ {tool} ok")

                # Duration
                if tool_duration:
                    tool_duration.record(
                        int((time.time() - start) * 1000), {"tool": tool}
                    )

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
            self._log(context, "listing tools")

        span_cm = (
            _TRACER.start_as_current_span(self._span_name("mcp.list.tools"))
            if self.enable_tracing
            else nullcontext()
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
            _TRACER.start_as_current_span(self._span_name("mcp.prompts.list"))
            if self.enable_tracing
            else nullcontext()
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
