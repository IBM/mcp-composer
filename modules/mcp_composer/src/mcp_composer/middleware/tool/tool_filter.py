"""Tools filter middleware"""

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp_composer.core.utils.context_request import get_http_request, extract_user_instances
from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class ListFilteredTool(Middleware):
    """Filter tools of member server before sending to clients.
    1. Remove tools
    2. Update description of tools if exist
    """

    def __init__(self, gw):
        self.gw = gw

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        try:
            tools = await self.gw.get_tools()
            self.gw.disable_composer_tool()
            self.gw.enable_tools(["ibm_doc_search_direct"])
            request = get_http_request(context)
            logger.debug("TOOL FILTER :request in list tools: %s", context)
            user_instances = extract_user_instances(request)
            logger.debug("TOOL FILTER :user_instances in list tools: %s", user_instances)
            filtered_tools = self.gw._tool_manager.filter_tools(
                tools, user_instances=user_instances
            )
            await call_next(context)
            return [tool for _, tool in filtered_tools.items()]
        except ToolFilterError as e:
            logger.exception("Tools filtering failed in middleware: %s", e)
            raise ToolFilterError("Tools filtering failed in middleware") from e
