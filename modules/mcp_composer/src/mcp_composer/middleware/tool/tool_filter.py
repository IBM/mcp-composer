"""Tools filter middleware"""

from fastmcp.server.middleware import Middleware, MiddlewareContext

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class ListFilteredTool(Middleware):
    """Filter tools of member server before sending to clients
    1. Remove tools
    2. Update description of tools if exist
    """

    def __init__(self, gw):
        self.gw = gw

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        try:
            tools = await self.gw.get_tools()
            filtered_tools = self.gw._tool_manager.filter_tools(tools)
            await call_next(context)
            return [tool for _, tool in filtered_tools.items()]
        except ToolFilterError as e:
            logger.exception("Tools filtering failed in middleware: %s", e)
            raise ToolFilterError("Tools filtering failed in middleware") from e
