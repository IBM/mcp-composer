# fastmcp_middleware_enhanced.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import yaml
import json
from pathlib import Path

# Import FastMCP middleware classes
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

from mcp_composer.core.middleware.middleware_config import MiddlewareEntry
from mcp_composer.core.middleware.middleware_manager import _hook_name, _match_glob


class ComposerMiddleware(Middleware):
    """
    Wrap a middleware instance to enforce:
      - applied_hooks
      - include/exclude conditions for tools/prompts/server_ids
    """

    def __init__(self, inner: Middleware, entry: MiddlewareEntry):
        self.inner = inner
        self.entry = entry
        # Normalize Enum hooks to strings if your config uses Enums
        self.hooks = {_hook_name(h) for h in entry.applied_hooks}

        c = entry.conditions
        self.inc_tools = c.include_tools or ["*"]
        self.exc_tools = c.exclude_tools or []
        self.inc_prompts = c.include_prompts or []
        self.exc_prompts = c.exclude_prompts or []
        self.inc_servers = c.include_server_ids or []
        self.exc_servers = c.exclude_server_ids or []

    def _allowed(self, ctx: MiddlewareContext) -> bool:
        # Tool name (from message)
        tool = getattr(getattr(ctx, "message", None), "name", "") or ""
        if self.inc_tools and not any(_match_glob(p, tool) for p in self.inc_tools):
            return False
        if self.exc_tools and any(_match_glob(p, tool) for p in self.exc_tools):
            return False

        # Prompt name (if present)
        prompt = getattr(getattr(ctx, "message", None), "prompt_name", "") or ""
        if self.inc_prompts and not any(
            _match_glob(p, prompt) for p in self.inc_prompts
        ):
            return False
        if self.exc_prompts and any(_match_glob(p, prompt) for p in self.exc_prompts):
            return False

        # Server id (if present on context)
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

    # ---- Hook shims (only call inner if hook is enabled+allowed and method exists) ----

    async def on_request(self, context: MiddlewareContext, call_next: CallNext):
        if "on_request" not in self.hooks or not self._allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_request"):
            return await self.inner.on_request(context, call_next)
        return await call_next(context)

    async def on_message(self, context: MiddlewareContext, call_next: CallNext):
        if "on_message" not in self.hooks or not self._allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_message"):
            return await self.inner.on_message(context, call_next)
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        if "on_list_tools" not in self.hooks or not self._allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_list_tools"):
            return await self.inner.on_list_tools(context, call_next)
        return await call_next(context)

    async def on_list_resources(self, context: MiddlewareContext, call_next: CallNext):
        if "on_list_resources" not in self.hooks or not self._allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_list_resources"):
            return await self.inner.on_list_resources(context, call_next)
        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next: CallNext):
        if "on_read_resource" not in self.hooks or not self._allowed(context):
            return await call_next(context)
        if hasattr(self.inner, "on_read_resource"):
            return await self.inner.on_read_resource(context, call_next)
        return await call_next(context)

    async def on_list_prompts(self, context: MiddlewareContext, call_next: CallNext):
        if "on_list_prompts" not in self.hooks or not self._allowed(context):
            return await call_next(context)
        # Some legacy middlewares may implement on_get_prompt; call if present.
        if hasattr(self.inner, "on_list_prompts"):
            return await self.inner.on_list_prompts(context, call_next)
        if hasattr(self.inner, "on_get_prompt"):
            return await self.inner.on_get_prompt(context, call_next)
        return await call_next(context)
