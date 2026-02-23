"""Tools filter middleware"""

import json
from typing import Any, List, Optional

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp.types import CallToolResult, TextContent

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.middleware.auth_context_middleware import (
    AUTH_KEY_USER_INSTANCES_FULL,
    HEADER_USER_INSTANCES,
    get_auth_context,
)
from mcp_composer.middleware.auth_utils import tool_name_to_server_id

logger = LoggerFactory.get_logger()


def _normalize_to_instance_list(raw: Any) -> List[dict]:
    """Turn header value into a list of instance dicts. Handles list, wrapper dict, single instance."""
    if raw is None:
        return []
    if isinstance(raw, list):
        if len(raw) == 1 and isinstance(raw[0], dict):
            inner = raw[0].get("userInstances") or raw[0].get("user_instances")
            if isinstance(inner, list):
                return inner
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("userInstances"), list):
            return raw["userInstances"]
        if isinstance(raw.get("user_instances"), list):
            return raw["user_instances"]
        return [raw]
    return []


def _get_instance_product_id(instance: dict) -> Optional[str]:
    """Get productId from an instance (subscription.productId or product_id)."""
    sub = instance.get("subscription")
    if isinstance(sub, dict):
        val = sub.get("productId") or sub.get("product_id")
        if val:
            return val
    return instance.get("productId") or instance.get("product_id") or None


class ListFilteredTool(Middleware):
    """Filter tools of member server before sending to clients
    1. Remove tools
    2. Update description of tools if exist
    3. When x-user-instances header is present, remove tools whose server's
       solis_config.product_id is not in the user's instances.
    On call_tool, reject with error if the tool's product is not in user instances.
    """

    def __init__(self, gw):
        self.gw = gw

    def _get_request(self, context: MiddlewareContext) -> Any:
        """Get the HTTP request from context, or None if unavailable."""
        fastmcp_ctx = getattr(context, "fastmcp_context", None)
        if fastmcp_ctx is None:
            return None
        request_context = getattr(fastmcp_ctx, "request_context", None)
        return getattr(request_context, "request", None) if request_context else None

    def _extract_user_instances_from_request(self, request: Any) -> Optional[List[dict]]:
        """Extract and normalize x-user-instances from request headers. Returns None if absent/invalid."""
        if request is None:
            return None
        headers = getattr(request, "headers", None) or {}
        raw_header = (
            headers.get(HEADER_USER_INSTANCES)
            or headers.get("X-User-Instances")
            or headers.get("x-User-Instances")
            or ""
        )
        if not raw_header or not isinstance(raw_header, str):
            return None
        try:
            raw = json.loads(raw_header)
        except json.JSONDecodeError as e:
            logger.warning("%s header JSON invalid: %s", HEADER_USER_INSTANCES, e)
            return None
        instances = _normalize_to_instance_list(raw)
        return instances if instances else None

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        try:
            request = self._get_request(context)
            user_instances = self._extract_user_instances_from_request(request)

            tools = await self.gw.get_tools()
            filtered_tools = self.gw._tool_manager.filter_tools(
                tools, user_instances=user_instances
            )
            await call_next(context)
            return [tool for _, tool in filtered_tools.items()]
        except ToolFilterError as e:
            logger.exception("Tools filtering failed in middleware: %s", e)
            raise ToolFilterError("Tools filtering failed in middleware") from e

    async def on_call_tool(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Gate tool calls: reject if tool's server has product_id and user has no matching instance."""
        tool_name = getattr(context.message, "name", "") or ""

        server_id = tool_name_to_server_id(tool_name)
        if server_id is None:
            return await call_next(context)

        product_id = None
        try:
            member = self.gw._server_manager.get(server_id)
            if member and member.config:
                solis = member.config.get("solis_config") or {}
                product_id = solis.get("product_id")
        except Exception:  # noqa: S110 - broad catch for get() raising or missing config
            pass

        if not product_id:
            return await call_next(context)

        auth_context = get_auth_context()
        instances = (auth_context or {}).get(AUTH_KEY_USER_INSTANCES_FULL) or []
        if not instances:
            return await call_next(context)

        has_match = any(
            _get_instance_product_id(inst) == product_id for inst in instances
        )
        if has_match:
            return await call_next(context)

        available = list(
            set(_get_instance_product_id(i) or "unknown" for i in instances)
        )
        message = (
            f"Access denied: No instance with productId '{product_id}'. "
            f"User instances have productIds: {', '.join(available)}"
        )
        logger.warning(
            "Tool '%s' blocked: product_id '%s' not in user instances %s",
            tool_name,
            product_id,
            available,
        )
        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            structuredContent={
                "error": "Forbidden",
                "message": message,
                "product_id": product_id,
                "available_product_ids": available,
            },
            isError=True,
        )
