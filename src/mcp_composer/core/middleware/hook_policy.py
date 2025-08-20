import re
from typing import Any, Dict, List

# FastMCP interfaces
from fastmcp.server.middleware import MiddlewareContext


# =========================
# Utilities
# =========================


def _match_glob(pat: str, s: str) -> bool:
    """Full-string '*' glob match."""
    rx = "^" + re.escape(pat).replace("\\*", ".*") + "$"
    return re.match(rx, s or "") is not None


def _hook_name(h: Any) -> str:
    """Normalize Enum-like hook to string."""
    return getattr(h, "value", h)


class HookPolicy:
    """Evaluates include/exclude conditions for tools/prompts/server_ids."""

    def __init__(
        self,
        include_tools: List[str] | None = None,
        exclude_tools: List[str] | None = None,
        include_prompts: List[str] | None = None,
        exclude_prompts: List[str] | None = None,
        include_server_ids: List[str] | None = None,
        exclude_server_ids: List[str] | None = None,
    ) -> None:
        self.inc_tools = include_tools or ["*"]
        self.exc_tools = exclude_tools or []
        self.inc_prompts = include_prompts or []
        self.exc_prompts = exclude_prompts or []
        self.inc_servers = include_server_ids or []
        self.exc_servers = exclude_server_ids or []

    def allowed(self, ctx: MiddlewareContext) -> bool:
        # tool
        tool = getattr(getattr(ctx, "message", None), "name", "") or ""
        if self.inc_tools and not any(_match_glob(p, tool) for p in self.inc_tools):
            return False
        if self.exc_tools and any(_match_glob(p, tool) for p in self.exc_tools):
            return False
        # prompt
        prompt = getattr(getattr(ctx, "message", None), "prompt_name", "") or ""
        if self.inc_prompts and not any(
            _match_glob(p, prompt) for p in self.inc_prompts
        ):
            return False
        if self.exc_prompts and any(_match_glob(p, prompt) for p in self.exc_prompts):
            return False
        # server id (if present)
        server_id = getattr(ctx, "server_id", "") or ""
        if self.inc_servers and not any(
            _match_glob(p, server_id) for p in self.inc_servers
        ):
            return False
        if self.exc_servers and any(
            _match_glob(p, server_id) for p in self.exc_servers
        ):
            return False
        return True
