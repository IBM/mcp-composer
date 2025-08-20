from typing import Any

# FastMCP interfaces
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.exceptions import ToolError

from mcp_composer.core.middleware.middleware_config import MiddlewareEntry
from mcp_composer.core.middleware.hook_policy import HookPolicy


def _hook_name(h: Any) -> str:
    """Normalize Enum-like hook to string."""
    return getattr(h, "value", h)


class HookFilter(Middleware):
    """
    Wraps a middleware to enforce:
      - applied_hooks (which hooks this middleware participates in)
      - HookPolicy (include/exclude conditions)
    """

    def __init__(self, inner: Middleware, entry: MiddlewareEntry):
        self.inner = inner
        self.entry = entry
        self.hooks = {_hook_name(h) for h in entry.applied_hooks}
        c = entry.conditions
        self.policy = HookPolicy(
            include_tools=c.include_tools,
            exclude_tools=c.exclude_tools,
            include_prompts=c.include_prompts,
            exclude_prompts=c.exclude_prompts,
            include_server_ids=c.include_server_ids,
            exclude_server_ids=c.exclude_server_ids,
        )

    async def on_request(self, context: MiddlewareContext, call_next: CallNext):
        if "on_request" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_request"):
            return await self.inner.on_request(context, call_next)
        return await call_next(context)

    async def on_message(self, context: MiddlewareContext, call_next: CallNext):
        if "on_message" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_message"):
            return await self.inner.on_message(context, call_next)
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        if "on_list_tools" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_list_tools"):
            return await self.inner.on_list_tools(context, call_next)
        return await call_next(context)

    async def on_list_resources(self, context: MiddlewareContext, call_next: CallNext):
        if "on_list_resources" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_list_resources"):
            return await self.inner.on_list_resources(context, call_next)
        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next: CallNext):
        if "on_read_resource" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_read_resource"):
            return await self.inner.on_read_resource(context, call_next)
        return await call_next(context)

    async def on_list_prompts(self, context: MiddlewareContext, call_next: CallNext):
        if "on_list_prompts" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        # Legacy compatibility
        if hasattr(self.inner, "on_list_prompts"):
            return await self.inner.on_list_prompts(context, call_next)
        if hasattr(self.inner, "on_get_prompt"):
            return await self.inner.on_get_prompt(context, call_next)
        return await call_next(context)

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        if "on_call_tool" not in self.hooks or not self.policy.allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_call_tool"):
            return await self.inner.on_call_tool(context, call_next)
        return await call_next(context)
