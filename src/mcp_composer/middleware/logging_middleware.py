# logging_middleware.py
from __future__ import annotations

from typing import Any, Dict, Optional
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

# Prefer your LoggerFactory if available; fall back to stdlib logging
try:
    from mcp_composer.core.utils.logger import LoggerFactory

    _BASE_LOGGER = LoggerFactory.get_logger()
except Exception:
    import logging

    _BASE_LOGGER = logging.getLogger("mcp_composer.logging")


def _get_logger(ctx: MiddlewareContext):
    # If FastMCP provides a context logger, prefer it
    return getattr(ctx, "logger", _BASE_LOGGER)


def _truncate(val: Any, max_len: int) -> Any:
    try:
        s = str(val)
    except Exception:
        return "<unprintable>"
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"... (+{len(s)-max_len} chars)"


class LoggingMiddleware(Middleware):
    """
    Config:
      log_tools: bool = True
      log_resources: bool = False
      log_prompts: bool = False
      log_args: bool = False
      log_results: bool = False
      max_payload_length: int = 1000
      log_level: "DEBUG"|"INFO"|"WARNING"|"ERROR" = "INFO"
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
        **_: Dict[str, Any],
    ):
        self.log_tools = bool(log_tools)
        self.log_resources = bool(log_resources)
        self.log_prompts = bool(log_prompts)
        self.log_args = bool(log_args)
        self.log_results = bool(log_results)
        self.max_len = int(max_payload_length)
        self.level = (log_level or "INFO").upper()

    # ---- helpers ----

    def _log(self, ctx: MiddlewareContext, msg: str, level: Optional[str] = None):
        logger = _get_logger(ctx)
        lvl = (level or self.level).upper()
        fn = getattr(logger, lvl.lower(), logger.info)
        fn(msg)

    # ---- hooks ----

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        if not self.log_tools:
            return await call_next(context)

        tool = getattr(context.message, "name", "unknown")
        args = getattr(context.message, "arguments", {})
        if self.log_args:
            self._log(context, f"🛠️  call {tool} args={_truncate(args, self.max_len)}")
        else:
            self._log(context, f"🛠️  call {tool}")

        try:
            result = await call_next(context)
            if self.log_results:
                self._log(
                    context, f"✅ {tool} result={_truncate(result, self.max_len)}"
                )
            else:
                self._log(context, f"✅ {tool} ok")
            return result
        except Exception as e:
            self._log(context, f"❌ {tool} error: {e}", level="ERROR")
            raise

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        if not self.log_tools:
            return await call_next(context)
        self._log(context, "📋 listing tools")
        result = await call_next(context)
        try:
            n = len(getattr(result, "tools", result))
        except Exception:
            n = 0
        self._log(context, f"📋 listed {n} tools")
        return result

    async def on_read_resource(self, context: MiddlewareContext, call_next: CallNext):
        if not self.log_resources:
            return await call_next(context)
        uri = getattr(context.message, "uri", "unknown")
        self._log(context, f"📖 read {uri}")
        result = await call_next(context)
        self._log(context, f"📖 read ok: {uri}")
        return result

    async def on_list_prompts(self, context: MiddlewareContext, call_next: CallNext):
        if not self.log_prompts:
            return await call_next(context)
        self._log(context, "💬 list prompts")
        result = await call_next(context)
        self._log(context, "💬 list prompts ok")
        return result
