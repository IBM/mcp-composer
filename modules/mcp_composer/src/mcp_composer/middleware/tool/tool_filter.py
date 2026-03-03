"""Tools filter middleware"""

import os
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp_composer.core.utils.context_request import ctx_get, extract_user_instances
from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory
logger = LoggerFactory.get_logger()

CONTEXT_REQUEST_KEY = "fastmcp_context.request_context.request"


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
            env = os.getenv("MCP_COMPOSER_ENV", "").lower()

            # Skip filtering in local mode
            if env == "local":
                logger.info("Local mode - returning all tools without filtering")
                await call_next(context)
                return [tool for _, tool in tools.items()]

            # Apply product-based filtering in dev/prod
            ##self.gw.disable_composer_tool()
            await self.gw._tool_manager.disable_tools(["register_mcp_server", "delete_mcp_server", "member_health", "activate_mcp_server", "deactivate_mcp_server", "get_tool_config_by_name", "get_tool_config_by_server", "disable_tools", "enable_tools", "update_tool_description", "add_prompts",   "disable_prompts", "enable_prompts", "delete_prompts", "create_resource", "create_resource_template",  "disable_resources", "enable_resources", "delete_resources"])
            await self.gw._tool_manager.enable_tools(["ibm_doc_search_direct"])

            request = ctx_get(context, CONTEXT_REQUEST_KEY)
           
            user_instances = extract_user_instances(request)

            filtered_tools = self.gw._tool_manager.filter_tools(tools, user_instances=user_instances)
            await call_next(context)
            return [tool for _, tool in filtered_tools.items()]
        except ToolFilterError as e:
            logger.exception("Tools filtering failed in middleware: %s", e)
            raise ToolFilterError("Tools filtering failed in middleware") from e
