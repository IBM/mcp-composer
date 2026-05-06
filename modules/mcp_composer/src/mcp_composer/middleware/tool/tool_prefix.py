"""Tool prefix middleware for multi-server routing"""

from typing import Any
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class ToolPrefixMiddleware(Middleware):
    """Add server ID prefix to tool names in multi-server routes.

    This middleware ensures that tools from different servers have unique names
    by prefixing them with their server ID (e.g., 'server1_tool_name').
    """

    def __init__(self, server_id: str) -> None:
        """
        Initialize ToolPrefixMiddleware.

        Args:
            server_id: The server ID to use as prefix for tool names
        """
        self.server_id = server_id
        logger.info("Initialized ToolPrefixMiddleware for server: %s", server_id)

    async def on_list_tools(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Add server ID prefix to all tool names when listing tools."""
        try:
            tools = await call_next(context)
            # Handle both list and dict formats
            if isinstance(tools, dict):
                prefixed_tools = {}
                for tool_name, tool in tools.items():
                    # Only add prefix if not already present
                    if not tool_name.startswith(f"{self.server_id}_"):
                        prefixed_name = f"{self.server_id}_{tool_name}"
                        tool.name = prefixed_name
                        prefixed_tools[prefixed_name] = tool
                    else:
                        prefixed_tools[tool_name] = tool

                logger.debug(
                    "Prefixed %d tools for server %s",
                    len(prefixed_tools),
                    self.server_id,
                )
                return prefixed_tools
            else:
                # Handle list/sequence format
                for tool in tools:
                    if hasattr(tool, "name") and not tool.name.startswith(
                        f"{self.server_id}_"
                    ):
                        tool.name = f"{self.server_id}_{tool.name}"

                logger.debug(
                    "Prefixed %d tools for server %s", len(tools), self.server_id
                )
                return tools

        except Exception as e:
            logger.exception(
                "Error adding tool prefix for server %s: %s", self.server_id, e
            )
            raise
