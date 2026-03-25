"""Tool Manager"""

from __future__ import annotations
import inspect
from typing import TYPE_CHECKING, Optional, Sequence, Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


from fastmcp.tools.tool import Tool
from fastmcp.server.providers import LocalProvider

from mcp_composer.core.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.middleware.auth_utils import tool_name_to_server_id
from mcp_composer.core.models import tool
from mcp_composer.core.utils.exceptions import ToolDisableError, ToolDuplicateError
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils import LoggerFactory, get_server_doc_info
from mcp_composer.core.member_servers import ServerManager
from mcp_composer.core.utils.tools import (
    generate_tool_from_curl,
    generate_tool_from_open_api,
    tool_exist,
    tool_config,
    check_duplicate_tool,
)

if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer

try:
    from mcp_composer.core.custom_tool import tools as custom_tools
except ImportError:
    custom_tools = None


logger = LoggerFactory.get_logger()


class MCPToolManager:
    """Manages member servers tools."""

    def __init__(
        self,
        composer: MCPComposer,
        server_manager: ServerManager,
        database: Optional[DatabaseInterface] = None,
    ):
        # Note: ToolManager doesn't exist in FastMCP 3.0, so we don't inherit from it
        self._composer = composer
        self._server_manager = server_manager
        self._database = database
        self._disabled_tools: list[str] = []
        self._tools: list[str] = []

    def _get_mounted_servers(self):
        """Safely access mounted servers, returning empty list if not initialized."""
        mounted_servers = getattr(self._composer, "_mounted_servers", None)
        if isinstance(mounted_servers, list):
            return mounted_servers
        return []

    def unmount(self, server_id):
        """Unmount a member server"""
        try:
            # Find the matching mounted server
            parent_mounted = self._get_mounted_servers()
            # Access the parent class's _mounted_servers directly for deletion
            for idx, mounted_server in enumerate(parent_mounted):
                if (
                    hasattr(mounted_server, "prefix")
                    and mounted_server.prefix == server_id
                ):
                    del parent_mounted[idx]
                    break
            # unmount the server from the composer(FastMCP instance) providers
            # Note: FastMCP 3.0 doesn't have a built-in tool manager or a standard way to unmount providers,
            providers = getattr(self._composer, "providers", [])
            for idx, provider in enumerate(list(providers)):
                if not isinstance(provider, LocalProvider):
                    transforms = getattr(provider, "transforms", None) or []
                    if transforms:
                        namespace = transforms[0]
                        namespace_prefix = getattr(namespace, "_prefix", None)
                        if namespace_prefix == server_id:
                            del providers[idx]
                            break
        except Exception as e:
            logger.exception("Error unmounting server '%s': %s", server_id, e)
            raise RuntimeError(f"Error unmounting server '{server_id}'") from e

    async def has_tool(self, key: str | list[str]) -> bool:
        """Check if one or more tools exist by name."""
        tools = await self._composer.list_tools()

        if isinstance(key, str):
            # Single key: short-circuit search
            return any(tool.name == key for tool in tools)

        # Multiple keys: build set once, then check
        tool_names = {tool.name for tool in tools}
        return any(k in tool_names for k in key)

    def _get_instance_product_id(self, instance: dict[str, Any]) -> Optional[str]:
        """Get productId from an instance (subscription.productId or product_id)."""
        sub = instance.get("subscription")
        if isinstance(sub, dict):
            val = sub.get("productId") or sub.get("product_id")
            if val:
                return val
        return instance.get("productId") or instance.get("product_id") or None

    def filter_tools(
        self,
        tools: Sequence[Tool],
        user_instances: Optional[list[dict[str, Any]]] = None,
    ) -> Sequence[Tool]:
        """
        Filters and updates a dictionary of tools based on server configuration and
        locally disabled tools, performing the following actions for all member servers:
        1. Removes disabled tools.
        2. Updates tool descriptions.
        3. When user_instances is provided, removes tools whose server's solis_config.product_id
           is not present in any of the user's instances.
        """
        try:
            # 1. Special case: If all tools are disabled locally
            if self._disabled_tools == ["all"]:
                tool = self._composer.add_tool(
                    Tool.from_function(self.enable_all_tools)
                )
                return [tool]

            # 2. Gather all disabled tools and description updates
            # Start with locally disabled tools
            remove_set = set(self._disabled_tools)
            description_updates: dict[str, str] = {}

            server_config = self._server_manager.list()

            for member in server_config:
                # Skip unhealthy servers
                if member.health_status != HealthStatus.healthy:
                    continue

                # Accumulate disabled tools from healthy members
                if member.disabled_tools:
                    remove_set.update(member.disabled_tools)

                # Accumulate description updates from healthy members
                if member.tools_description:
                    for name, desc in member.tools_description.items():
                        description_updates[f"{member.id}_{name}"] = desc

            self._composer.disable(names=remove_set)

            # 3. Filter and update the tools dictionary
            # filtered_tools = [tool for tool in tools if tool.name not in remove_set]

            # Update descriptions for the remaining tools
            for name, description in description_updates.items():
                for tool in tools:
                    if tool.name == name:
                        tool.description = description

            # 4. Product-based filter: when user_instances is provided, keep only tools
            # whose server's product_id is in the user's instances (or server has no product_id)
            server_to_product: dict[str, Optional[str]] = {
                member.id: (member.config.get("solis_config") or {}).get("product_id")
                for member in server_config
            }

            allowed_product_ids: set[str] = set()
            if user_instances:
                logger.debug(
                    "TOOL FILTER :user_instances in filter tools: %s", user_instances
                )
                for inst in user_instances:
                    pid = self._get_instance_product_id(inst)
                    if pid:
                        allowed_product_ids.add(pid)
                logger.debug(
                    "TOOL FILTER :allowed_product_ids in filter tools: %s",
                    allowed_product_ids,
                )

            result = []
            for tool in tools:
                server_id = tool_name_to_server_id(tool.name)
                logger.debug("TOOL FILTER :server_id in filter tools: %s", server_id)

                # Always keep tools that are not mapped to a product-bearing server
                if server_id is None or server_id not in server_to_product:
                    result.append(tool)
                    continue

                # If we have user instances, enforce product-based filtering
                if allowed_product_ids:
                    product_id = server_to_product.get(server_id)
                    if product_id and product_id in allowed_product_ids:
                        result.append(tool)

            logger.debug("TOOL FILTER : result in filter tools: %s", result)
            return result

        except Exception as e:
            logger.exception("Tools filtering failed: %s", e)
            raise

    async def load_custom_tools(self):
        """Load tools using saved OpenAPI, Curl, and Python script."""
        try:
            if custom_tools:
                for name, func in inspect.getmembers(custom_tools, inspect.isfunction):
                    logger.info("Adding tool from custom tool folder: %s", name)
                    self._composer.add_tool(Tool.from_function(func))
            # Load tools from curl commands
            for tool_fn in await generate_tool_from_curl():
                self._composer.add_tool(Tool.from_function(tool_fn))

            # Load tools from OpenAPI Specifications
            server_data = await generate_tool_from_open_api()
            return server_data
        except Exception as e:
            raise e

    async def fetch_server_tools(
        self,
        server: MemberMCPServer,
        remove: Optional[list[str]] = None,
        description: Optional[dict[str, str]] = None,
    ) -> Sequence[Tool]:
        """Fetch member server tools"""
        result = []
        # Find the matching mounted server and get its tools
        mounted_servers = self._server_manager._member_servers
        if not mounted_servers:
            return result

        for name, mounted_server in mounted_servers.items():
            if name == server.id:
                if mounted_server.server is not None:
                    tools = await mounted_server.server.list_tools()

                    server_tools = {tool.name: tool for tool in tools}
                    result = [
                        v
                        for k, v in server_tools.items()
                        if not remove or k not in remove
                    ]
                break  # Stop after finding the matching server

        # Update tool descriptions if provided
        if description:
            for name, desc in description.items():
                for tool in result:
                    if tool.name == name:
                        tool.description = desc
        return result

    async def get_all_tools(
        self,
        server_id: Optional[str] = None,
    ) -> Sequence[Tool]:
        """Get all tools by key."""
        tools: Sequence[Tool] = []
        remove = []
        composer_doc = self._server_manager.get_document(self._composer.name)
        if composer_doc:
            remove, description = get_server_doc_info(composer_doc)
            logger.info("Found disabled tools in composer: %s", remove)

        # Case 1: Specific server
        if server_id:
            server = self._server_manager.get(server_id)
            doc = self._server_manager.get_document(server_id)
            _, description = get_server_doc_info(doc)
            logger.info(
                """Case 2: Fetch tools for server '%s'.
                Removed: '%s'. Descriptions: '%s'""",
                server_id,
                remove,
                description,
            )
            return await self.fetch_server_tools(server, remove, description)

        # Default Case: All tools
        tools.extend(await self._composer.list_tools())
        logger.info("Default Case: Fetch all tools from member servers and composer")
        return tools

    async def get_tool_config_by_name(self, name: str) -> list[dict]:
        """
        Get a tool configuration details
        """
        tools = self.filter_tools(await self._composer.list_tools())
        tool_configs = tool_config(tools, name)
        logger.info("Tool configuration details by tool name:%s", tool_configs)
        return tool_configs

    async def get_tool_config_by_server(self, server_id: str) -> list[dict]:
        """
        Get all tool configuration details of a specific member server
        """
        self._server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        tool_configs = tool_config(server_tools)
        logger.info("Tool configuration details by server name: %s", tool_configs)
        return tool_configs

    async def disable_tools_by_server(self, tools: list[str], server_id: str) -> str:
        """
        disable a tool or multiple tools from the member server
        """
        self._server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        await tool_exist(tools, server_tools)
        self._server_manager.disable_tools(tools, server_id)
        logger.info("Disabled %s tools from server", tools)
        return f"Disabled {tools} tools from server {server_id}"

    async def enable_tools_by_server(self, tools: list[str], server_id: str) -> str:
        """
        enable a tool or multiple tools from the member server
        """
        self._server_manager.check_server_exist(server_id)
        self._server_manager.enable_tools(tools, server_id)
        logger.info("Enabled %s tools from server", tools)
        return f"Enabled {tools} tools from server {server_id}"

    async def disable_tools(self, tools: list[str]) -> str:
        """
        disable a tool or multiple tools
        """
        if tools[0].lower() == "all":
            self._disabled_tools = ["all"]
            logger.info("Disabled all tools")
        else:
            for tool in tools:
                if not await self.has_tool(tool):
                    raise ToolDisableError(f"Tool {tool} does not exist")
            existing_tools = self._disabled_tools
            duplicate_tool = check_duplicate_tool(existing_tools, tools)

            if duplicate_tool:
                raise ToolDuplicateError(f"Tool {duplicate_tool} is already disabled")

            existing_tools.extend(tools)
            logger.info("Added new disabled tool list %s in composer.", tools)
        if self._database:
            self._database.disable_tools(tools, server_id=self._composer.name)
        return f"Successfully disabled tools: {tools}"

    async def enable_tools(self, tools: list[str]) -> str:
        """
        enable a tool or multiple tools
        """
        disabled_tools = self._disabled_tools
        tools_to_remove = [tl for tl in tools if tl in disabled_tools]
        if not tools_to_remove:
            raise ValueError("Tool is not disabled")
        # Remove matching tools from disabled_tools
        self._disabled_tools = [
            tl for tl in disabled_tools if tl not in tools_to_remove
        ]
        self._composer.enable(names=set(tools_to_remove))

        if self._database:
            self._database.enable_tools(
                self._disabled_tools, server_id=self._composer.name
            )

        logger.info("Enabled %s tools from composer", tools)
        return f"Enabled {tools} tools from composer"

    async def enable_all_tools(self) -> str:
        """
        enable all tools
        """
        if len(self._disabled_tools) == 1 and self._disabled_tools[0].lower() == "all":
            self._disabled_tools = []

        if self._database:
            self._database.enable_tools(
                self._disabled_tools, server_id=self._composer.name
            )

        logger.info("Enabled all tools from composer")
        return "Enabled all tools from composer"

    async def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> str:
        """
        Update tool description of member servers
        """
        self._server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)

        # Extract tool name if it's prefixed with server_id
        tool_name = tool
        prefix = f"{server_id}_"
        if tool.startswith(prefix):
            tool_name = tool[len(prefix) :]

        await tool_exist(tool_name, server_tools)
        self._server_manager.update_tool_description(tool_name, description, server_id)
        logger.info(
            "Updated tool '%s' with description '%s' for server '%s'",
            tool,
            description,
            server_id,
        )
        return f"Updated {tool} with description: {description}"

    async def filter_tool_by_keyword(self, keyword: str):
        """
        Filter tools by keyword using cosine similarity (based on TF-IDF vectorization).
        Returns tools sorted by similarity score (highest first).
        """
        logger.info("Filter tools by using keyword: %s", keyword)
        tools = self.filter_tools(
            await self._composer.list_tools()
        )  # Get dict of tools: {name: tool}
        tools = {t.name: t for t in tools}  # Ensure valid names
        tool_names = [t.name for t in tools.values()]  # Extract tool names

        # Create corpus: keyword + all tool names
        corpus = [keyword] + tool_names

        # TF-IDF vectorization
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)).fit(corpus)
        vectors = vectorizer.transform(corpus)

        # Compute cosine similarity between keyword and all tool names
        keyword_vector = vectors[0]
        tool_vectors = vectors[1:]
        similarities = cosine_similarity(keyword_vector, tool_vectors).flatten()

        # Pair tool names with similarity scores
        scored_tools = sorted(
            zip(tool_names, similarities), key=lambda x: x[1], reverse=True
        )
        # You can apply a threshold to filter out very dissimilar tools if needed
        # Lower threshold for better matching of prefixed tool names
        similarity_threshold = 0.01
        filtered_tools = {
            name: tools[name]
            for name, score in scored_tools
            if score >= similarity_threshold
        }
        logger.info(
            "Filtered tools list by using keyword '%s': %s", keyword, filtered_tools
        )
        return filtered_tools

    async def disable_composer_tool(self, tools: Optional[list[str]] = None) -> str:
        """
        Disable specified composer tools, or all composer tools if none are specified.
        """
        # 1. Determine the set of tools to disable
        if tools is None:
            # If no tools are specified, disable all available tools
            composer_tools = await self._composer.list_tools()
            tools_to_disable = [tool.name for tool in composer_tools]
        else:
            # Check if all specified tools actually exist
            if not self._tools:
                composer_tools = await self._composer.list_tools()
                self._tools = [tool.name for tool in composer_tools]
            non_existent_tools = [tool for tool in tools if tool not in self._tools]
            if non_existent_tools:
                # Raise an error if any specified tool doesn't exist
                raise ToolDisableError(
                    f"One or more tools do not exist: {', '.join(non_existent_tools)}"
                )
            tools_to_disable = tools

        # 2. Update the local set of disabled tools
        existing_disabled_tools = set(self._disabled_tools)
        newly_disabled_tools = [
            tool for tool in tools_to_disable if tool not in existing_disabled_tools
        ]
        self._disabled_tools.extend(newly_disabled_tools)

        # 4. Logging and return value
        # Log the full list of tools processed, even if some were already disabled
        logger.info("Disabled composer tools: %s", tools_to_disable)
        return f"Disabled composer tools: {tools_to_disable}"
