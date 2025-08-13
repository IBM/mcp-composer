import time
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple, Deque, Any, List
from collections import deque
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
import mcp.types as mt

"""app.add_middleware(
    RateLimiterMiddleware(
        per_tool={
            # tool: (capacity, refill_per_sec, default_cost)
            "search_docs": (20.0, 0.5, 1.0),     # burst 20, 0.5/s (~30/min)
            "ask_llm":     (60.0, 1.0, 10.0),    # burst 60, 1/s, cost ~10 per call
        },
        per_tenant_global=(100.0, 2.0),          # burst 100, 2/s across all tools
        per_tenant_daily_budget=20000.0,         # 20k “cost units” per rolling 24h
        estimate_cost=lambda tool, args: (
            len((args.get("query") or "")) / 8 if tool == "ask_llm" else 1.0
        ),
        get_tenant=lambda ctx: getattr(ctx, "tenant_id", "unknown"),
        get_user=lambda ctx: getattr(ctx, "user_id", "unknown"),
    )
)
"""


@dataclass
class Bucket:
    capacity: float
    refill_rate_per_sec: float
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def refill(self, now: float):
        dt = max(0.0, now - self.last_refill)
        if dt > 0:
            self.tokens = min(
                self.capacity, self.tokens + dt * self.refill_rate_per_sec
            )
            self.last_refill = now


@dataclass
class BudgetWindow:
    # Rolling 24h window of costs
    events: Deque[Tuple[float, float]] = field(default_factory=deque)
    total: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RateLimiterMiddleware(Middleware):
    """
    Per-tenant & per-tool token buckets + 24h budgets.

    Config:
      per_tool: { tool_name: (capacity, refill_per_sec, default_cost) }
      per_tenant_global: (capacity, refill_per_sec)  # optional
      per_tenant_daily_budget: max cost over rolling 24h window (optional)
      estimate_cost: async or sync callable(tool, args)-> float
      key_funcs: functions to extract tenant and user from context
    """

    def __init__(
        self,
        *,
        per_tool: Optional[Dict[str, Tuple[float, float, float]]] = None,
        per_tenant_global: Optional[Tuple[float, float]] = None,
        per_tenant_daily_budget: Optional[float] = None,
        estimate_cost: Optional[Callable[[str, Dict[str, Any]], float]] = None,
        get_tenant: Optional[Callable[[Any], str]] = None,
        get_user: Optional[Callable[[Any], str]] = None,
    ):
        self.per_tool_cfg = per_tool or {}
        self.global_cfg = per_tenant_global
        self.daily_budget_limit = per_tenant_daily_budget
        self.estimate_cost = estimate_cost
        self.get_tenant = get_tenant or (
            lambda ctx: getattr(ctx, "tenant_id", "unknown")
        )
        self.get_user = get_user or (lambda ctx: getattr(ctx, "user_id", "unknown"))

        self._tool_buckets: Dict[Tuple[str, str], Bucket] = {}
        self._tenant_global_buckets: Dict[str, Bucket] = {}
        self._budgets: Dict[str, BudgetWindow] = {}
        self._lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _now_wall(self) -> float:
        return time.time()

    async def _get_tool_bucket(self, tenant: str, tool: str) -> Optional[Bucket]:
        cfg = self.per_tool_cfg.get(tool)
        if not cfg:
            return None
        cap, refill, _default_cost = cfg
        key = (tenant, tool)
        b = self._tool_buckets.get(key)
        if b:
            return b
        async with self._lock:
            return self._tool_buckets.setdefault(
                key, Bucket(capacity=cap, refill_rate_per_sec=refill, tokens=cap)
            )

    async def _get_global_bucket(self, tenant: str) -> Optional[Bucket]:
        if not self.global_cfg:
            return None
        cap, refill = self.global_cfg
        b = self._tenant_global_buckets.get(tenant)
        if b:
            return b
        async with self._lock:
            return self._tenant_global_buckets.setdefault(
                tenant, Bucket(capacity=cap, refill_rate_per_sec=refill, tokens=cap)
            )

    async def _get_budget(self, tenant: str) -> Optional[BudgetWindow]:
        if self.daily_budget_limit is None:
            return None
        bw = self._budgets.get(tenant)
        if bw:
            return bw
        async with self._lock:
            return self._budgets.setdefault(tenant, BudgetWindow())

    def _purge_old_budget(self, bw: BudgetWindow, now_wall: float):
        # Remove items older than 24h
        cutoff = now_wall - 24 * 3600
        while bw.events and bw.events[0][0] < cutoff:
            ts, cost = bw.events.popleft()
            bw.total -= cost
            if bw.total < 0:  # guard rounding
                bw.total = 0.0

    def _default_cost(self, tool: str) -> float:
        cfg = self.per_tool_cfg.get(tool)
        return cfg[2] if cfg else 1.0  # unit cost by default

    async def on_call_tool(self, context, call_next):
        tool = getattr(context.message, "name", "<unknown>")
        args = getattr(context.message, "arguments", {}) or {}
        tenant = self.get_tenant(context)
        # 1) Estimate cost upfront (best-effort)
        try:
            est = (
                self.estimate_cost(tool, args)
                if self.estimate_cost
                else self._default_cost(tool)
            )
            est = float(est) if est and est > 0 else self._default_cost(tool)
        except Exception:
            est = self._default_cost(tool)

        # 2) Enforce daily budget
        bw = await self._get_budget(tenant)
        if bw:
            async with bw.lock:
                self._purge_old_budget(bw, self._now_wall())
                if bw.total + est > float(self.daily_budget_limit):
                    raise ToolError(
                        f"Daily budget exceeded for tenant '{tenant}'. Limit={self.daily_budget_limit}, used~={bw.total:.2f}, req={est:.2f}"
                    )

        # 3) Deduct from global tenant bucket (burst control)
        gb = await self._get_global_bucket(tenant)
        now = self._now()
        if gb:
            async with gb.lock:
                gb.refill(now)
                if gb.tokens < est:
                    raise ToolError(
                        f"Rate limited (tenant global). Need {est:.2f} tokens, have {gb.tokens:.2f}"
                    )
                gb.tokens -= est

        # 4) Deduct from per-tool bucket
        tb = await self._get_tool_bucket(tenant, tool)
        if tb:
            async with tb.lock:
                tb.refill(now)
                if tb.tokens < est:
                    # Refund global if we took it
                    if gb:
                        async with gb.lock:
                            gb.tokens = min(gb.capacity, gb.tokens + est)
                    raise ToolError(
                        f"Rate limited (tool '{tool}'). Need {est:.2f}, have {tb.tokens:.2f}"
                    )
                tb.tokens -= est

        # 5) Run the call, then record actual cost if available; else use est
        actual_cost = est
        try:
            result = await call_next(context)
            # If your framework exposes token usage post-call, adjust here:
            # actual_cost = getattr(result, "token_usage", est)
            return result
        finally:
            if bw:
                async with bw.lock:
                    self._purge_old_budget(bw, self._now_wall())
                    bw.events.append((self._now_wall(), actual_cost))
                    bw.total += actual_cost
