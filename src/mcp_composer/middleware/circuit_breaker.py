import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


@dataclass
class CircuitState:
    state: str = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
    failures: Deque[float] = field(default_factory=deque)  # timestamps of failures
    opened_at: Optional[float] = None
    half_open_probe_in_flight: bool = False
    last_error: Optional[str] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CircuitBreakerMiddleware(Middleware):
    """
    Circuit breaker for tool calls.
    - failure_threshold: number of failures to trip within 'window_seconds'
    - open_timeout: seconds to stay OPEN before permitting HALF_OPEN probe
    - window_seconds: rolling failure window
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        open_timeout: float = 30.0,
        window_seconds: float = 60.0,
        exempt_tools: Optional[set] = None,
    ):
        self.failure_threshold = failure_threshold
        self.open_timeout = open_timeout
        self.window_seconds = window_seconds
        self.exempt_tools = exempt_tools or set()
        self._circuits: Dict[str, CircuitState] = {}
        self._global_lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    async def _state_for(self, tool_name: str) -> CircuitState:
        # Double-checked creation to avoid unnecessary contention
        if tool_name in self._circuits:
            return self._circuits[tool_name]
        async with self._global_lock:
            return self._circuits.setdefault(tool_name, CircuitState())

    def _gc_old_failures(self, cs: CircuitState, now: float):
        # Keep failures only within the rolling time window
        ws = self.window_seconds
        while cs.failures and now - cs.failures[0] > ws:
            cs.failures.popleft()

    def _trip_if_needed(self, cs: CircuitState, now: float):
        if len(cs.failures) >= self.failure_threshold and cs.state == "CLOSED":
            cs.state = "OPEN"
            cs.opened_at = now
            cs.half_open_probe_in_flight = False

    async def on_list_tools(self, context, call_next):
        # Optionally decorate tool metadata with circuit status
        result = await call_next(context)
        try:
            # result.tools is expected; if structure differs, skip decoration
            for t in getattr(result, "tools", []):
                cs = self._circuits.get(t.name)
                if cs:
                    status = cs.state
                    # Append non-invasive hint tag
                    if hasattr(t, "tags") and isinstance(t.tags, list):
                        if f"circuit:{status.lower()}" not in t.tags:
                            t.tags.append(f"circuit:{status.lower()}")
        except Exception:
            # Avoid breaking listing on decoration failure
            pass
        return result

    async def on_call_tool(self, context, call_next):
        tool_name = getattr(context.message, "name", None) or "<unknown>"

        if tool_name in self.exempt_tools:
            return await call_next(context)

        cs = await self._state_for(tool_name)
        now = self._now()

        async with cs.lock:
            # Housekeeping
            self._gc_old_failures(cs, now)

            # Evaluate state
            if cs.state == "OPEN":
                if cs.opened_at is None or (now - cs.opened_at) < self.open_timeout:
                    # Still cooling off
                    raise ToolError(f"Circuit OPEN for '{tool_name}'. Try again later.")
                else:
                    # Move to HALF_OPEN; allow one probe
                    cs.state = "HALF_OPEN"
                    cs.half_open_probe_in_flight = False  # reset probe flag

            if cs.state == "HALF_OPEN":
                if cs.half_open_probe_in_flight:
                    # Only one probe at a time
                    raise ToolError(
                        f"Circuit HALF_OPEN for '{tool_name}'. Probe in flight."
                    )
                # Mark probe in flight and let exactly one call through
                cs.half_open_probe_in_flight = True

        # Outside the lock: perform the call
        try:
            result = await call_next(context)
        except Exception as exc:
            # On failure, update state
            async with cs.lock:
                cs.last_error = str(exc)
                cs.failures.append(self._now())
                self._gc_old_failures(cs, self._now())

                if cs.state == "HALF_OPEN":
                    # Probe failed → back to OPEN
                    cs.state = "OPEN"
                    cs.opened_at = self._now()
                    cs.half_open_probe_in_flight = False
                else:
                    # CLOSED: see if we should trip
                    self._trip_if_needed(cs, self._now())

            # Re-raise to preserve original error semantics
            raise

        # Success path
        async with cs.lock:
            if cs.state == "HALF_OPEN":
                # Probe succeeded → close circuit & reset
                cs.state = "CLOSED"
                cs.failures.clear()
                cs.half_open_probe_in_flight = False
                cs.opened_at = None
                cs.last_error = None
            elif cs.state == "CLOSED":
                # Optional: decay failures on success
                if cs.failures:
                    cs.failures.clear()
                    cs.last_error = None

        return result
