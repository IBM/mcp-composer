"""Enforce disabled tools on the composed ``tools/list`` and ``tools/call`` paths."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from mcp_composer.core.utils.logger import LoggerFactory

if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer

logger = LoggerFactory.get_logger()


# With ``disable_tools(["all"])`` only this tool stays available.
_ENABLE_ALL_TOOL = "enable_all_tools"


class DisabledToolsMiddleware(Middleware):
    """Hide and reject tools that the operator or a client has disabled.

    The deny list is read on every request, so ``disable_tools`` and
    ``enable_tools`` take effect immediately. It combines:

    * the composer-level list (``MCPToolManager._disabled_tools``), which holds
      composed names such as ``m_wipe_records``, and
    * each member's ``disabled_tools``, which are stored unprefixed in the
      configuration and are matched as ``f"{member.id}_{name}"``.
    """

    def __init__(self, composer: MCPComposer) -> None:
        self._composer = composer

    def _is_denied(self, name: str) -> bool:
        # pylint: disable=protected-access
        composer_disabled = self._composer._tool_manager._disabled_tools
        if composer_disabled == ["all"]:
            return name != _ENABLE_ALL_TOOL
        if name in composer_disabled:
            return True
        return any(
            name == f"{member.id}_{tool}"
            for member in self._composer._server_manager.list()
            for tool in member.disabled_tools
        )

    async def on_list_tools(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        tools = await call_next(context)
        return [tool for tool in tools if not self._is_denied(tool.name)]

    async def on_call_tool(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        name = context.message.name
        if self._is_denied(name):
            logger.warning("Rejected call to disabled tool '%s'", name)
            raise ToolError(f"Tool '{name}' is disabled")
        return await call_next(context)
