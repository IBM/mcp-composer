# rate_limit_middleware.py
from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Optional

from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.exceptions import ToolError

try:
    from mcp_composer.core.utils.logger import LoggerFactory

    _LOGGER = LoggerFactory.get_logger()
except Exception:
    import logging

    _LOGGER = logging.getLogger("mcp_composer.ratelimit")


@dataclass
class Bucket:
    capacity: float
    refill_per_sec: float
    tokens: float
    last: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def refill(self):
        now = time.monotonic()
        dt = max(0.0, now - self.last)
        if dt > 0:
            self.tokens = min(self.capacity, self.tokens + dt * self.refill_per_sec)
            self.last = now


class RateLimitingMiddleware(Middleware):
    """
    Simple token-bucket rate limiter.

    Config:
      requests_per_minute: int = 100          # average rate
      burst_limit: int = 10                   # bucket capacity
      scope: "per_client"|"global"|"per_tool" = "per_client"
      enforce: bool = True                    # True=raise ToolError, False=log only
      client_id_field: str = "client_id"      # context attribute to read
    """

    def __init__(
        self,
        *,
        requests_per_minute: int = 100,
        burst_limit: int = 10,
        scope: str = "per_client",
        enforce: bool = True,
        client_id_field: str = "client_id",
        **_: Dict[str, Any],
    ):
        self.rps = max(1, int(requests_per_minute)) / 60.0
        self.capacity = max(1, int(burst_limit))
        self.scope = scope
        self.enforce = bool(enforce)
        self.client_id_field = client_id_field

        # buckets keyed by scope
        self._buckets: Dict[Tuple[str, str], Bucket] = {}
        self._lock = asyncio.Lock()

    def _key(self, ctx: MiddlewareContext) -> Tuple[str, str]:
        tool = getattr(getattr(ctx, "message", None), "name", "<unknown>")
        if self.scope == "per_tool":
            return ("tool", tool)
        if self.scope == "global":
            return ("global", "global")
        client = (
            getattr(ctx, self.client_id_field, None)
            or getattr(ctx, "tenant_id", None)
            or "default"
        )
        return (str(client), tool)

    async def _bucket(self, key: Tuple[str, str]) -> Bucket:
        b = self._buckets.get(key)
        if b:
            return b
        async with self._lock:
            return self._buckets.setdefault(
                key, Bucket(self.capacity, self.rps, self.capacity)
            )

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        key = await self._bucket(self._key(context))
        async with key.lock:
            key.refill()
            if key.tokens < 1.0:
                msg = f"rate limited: scope={self.scope} key={self._key(context)}"
                if self.enforce:
                    raise ToolError(msg)
                _LOGGER.warning("⚠️ " + msg)
                # soft-mode: continue without consuming
                return await call_next(context)
            key.tokens -= 1.0

        return await call_next(context)
