import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any, Callable

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
import mcp.types as mt


"""app.add_middleware(
    ConcurrencyLimiterMiddleware(
        per_tool_limits={
            "ask_llm": 8,            # max 8 concurrent across tenants
            "search_docs": 16
        },
        per_tenant_limits={
            # You can fill dynamically on tenant creation, or default in code
            # "tenantA": 10,
        },
        acquire_timeout=1.5,         # fail fast if queue exceeds 1.5s
        get_tenant=lambda ctx: getattr(ctx, "tenant_id", "unknown"),
    )
)
"""


class ConcurrencyError(ToolError):
    pass


@dataclass
class Gate:
    sem: asyncio.Semaphore
    # Track current holders for observability (optional)
    in_flight: int = 0


class ConcurrencyLimiterMiddleware(Middleware):
    """
    Bulkhead pattern via semaphores.

    Config:
      per_tool_limits: { tool_name: max_concurrency }
      per_tenant_limits: { tenant_id: max_concurrency }
      acquire_timeout: seconds to wait; 0 or None -> immediate fail if saturated
      get_tenant: context -> tenant_id
    """

    def __init__(
        self,
        *,
        per_tool_limits: Optional[Dict[str, int]] = None,
        per_tenant_limits: Optional[Dict[str, int]] = None,
        acquire_timeout: Optional[float] = 2.0,
        get_tenant: Optional[Callable[[Any], str]] = None,
    ):
        self.per_tool_limits = per_tool_limits or {}
        self.per_tenant_limits = per_tenant_limits or {}
        self.acquire_timeout = acquire_timeout
        self.get_tenant = get_tenant or (
            lambda ctx: getattr(ctx, "tenant_id", "unknown")
        )

        self._tool_gates: Dict[str, Gate] = {}
        self._tenant_gates: Dict[str, Gate] = {}
        self._lock = asyncio.Lock()

    async def _get_gate(self, table: Dict[str, Gate], key: str, limit: int) -> Gate:
        g = table.get(key)
        if g:
            return g
        async with self._lock:
            return table.setdefault(key, Gate(asyncio.Semaphore(limit)))

    async def _try_acquire(self, gate: Gate, timeout: Optional[float]) -> bool:
        if timeout is None or timeout <= 0:
            ok = gate.sem.locked() and gate.sem._value <= 0  # quick check
            if ok:
                return False
            acquired = (
                gate.sem.acquire_nowait()
                if hasattr(gate.sem, "acquire_nowait")
                else None
            )
            if acquired is None:  # py versions without acquire_nowait
                try:
                    await asyncio.wait_for(gate.sem.acquire(), timeout=0.0)
                    acquired = True
                except Exception:
                    acquired = False
            if acquired:
                gate.in_flight += 1
            return acquired
        else:
            try:
                await asyncio.wait_for(gate.sem.acquire(), timeout=timeout)
                gate.in_flight += 1
                return True
            except asyncio.TimeoutError:
                return False

    def _release(self, gate: Gate):
        gate.sem.release()
        gate.in_flight = max(0, gate.in_flight - 1)

    async def on_call_tool(self, context, call_next):
        tool = getattr(context.message, "name", "<unknown>")
        tenant = self.get_tenant(context)

        # Resolve gates if limits configured
        tool_gate = None
        tenant_gate = None

        if tool in self.per_tool_limits:
            tool_gate = await self._get_gate(
                self._tool_gates, tool, self.per_tool_limits[tool]
            )
        if tenant in self.per_tenant_limits:
            tenant_gate = await self._get_gate(
                self._tenant_gates, tenant, self.per_tenant_limits[tenant]
            )

        # Acquire (tenant first, then tool) to reduce head-of-line blocking across tools
        acquired_tenant = acquired_tool = False

        if tenant_gate:
            acquired_tenant = await self._try_acquire(tenant_gate, self.acquire_timeout)
            if not acquired_tenant:
                raise ConcurrencyError(f"Tenant '{tenant}' concurrency limit reached")

        try:
            if tool_gate:
                acquired_tool = await self._try_acquire(tool_gate, self.acquire_timeout)
                if not acquired_tool:
                    raise ConcurrencyError(f"Tool '{tool}' concurrency limit reached")

            # Proceed
            return await call_next(context)

        finally:
            if acquired_tool and tool_gate:
                self._release(tool_gate)
            if acquired_tenant and tenant_gate:
                self._release(tenant_gate)
