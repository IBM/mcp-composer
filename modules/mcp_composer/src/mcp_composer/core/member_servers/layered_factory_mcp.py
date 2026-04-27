"""
Layered MCP Factory for native MCP protocol servers.
Provides a discovery layer on top of MCP protocol servers that don't have OpenAPI specs.
"""

from typing import Any
from fastmcp import FastMCP, Client  # type: ignore
from fastmcp.exceptions import ToolError  # type: ignore
from fastmcp.server import create_proxy  # type: ignore
from fastmcp.tools import Tool  # type: ignore
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Import auth context helper to get authentication headers
AUTH_CONTEXT_AVAILABLE = False
try:
    from mcp_composer.middleware.auth_context_middleware import (
        AUTH_KEY_USER_INSTANCES_FULL,
        get_auth_context,
    )

    AUTH_CONTEXT_AVAILABLE = True
except ImportError:
    AUTH_KEY_USER_INSTANCES_FULL = "user_instances_full"
    get_auth_context = lambda: None  # type: ignore[assignment]
    logger.debug(
        "AuthContextMiddleware not available - auth context forwarding disabled"
    )


class LayeredMCPFactory(FastMCP):
    """
    A layered wrapper for MCP protocol servers that provides discovery and introspection tools.
    Unlike LayeredOpenAPIFactory which requires an OpenAPI spec, this works with native MCP servers.

    This extends FastMCP and uses a proxy to forward tools from the underlying MCP server.
    """

    def __init__(
        self,
        client: Client,
        server_id: str = "unknown",
        product_id: str | None = None,
        tool_descriptions: dict[str, str] | None = None,
    ):
        """
        Initialize the layered MCP factory.

        Args:
            client: The MCP client connected to the remote server
            server_id: Server ID for authorization (legacy)
            product_id: Product ID for authorization matching
            tool_descriptions: Optional custom descriptions for the layered tools
        """
        # Store configuration before calling super().__init__
        self.client = client
        self.server_id = server_id
        self.product_id = product_id
        self._tool_descriptions = tool_descriptions or {}
        self._cached_tools: list[dict[str, Any]] | None = None

        # Initialize the parent FastMCP class
        super().__init__(
            name="Layered MCP FastMCP",
            instructions="""This MCP server provides a discovery layer on top of a native MCP protocol server with three main capabilities:

1. **get_service_info** - Discover and list all available tools from the underlying MCP server
2. **get_type_info** - Get detailed information about a specific tool including its schema and usage
3. **make_tool_call** - Execute a tool call on the underlying MCP server with the provided arguments

Usage workflow:
1. First use get_service_info() to see what's available
2. Then use get_type_info(tool_name) to understand the specific tool
3. Finally use make_tool_call(tool_name, arguments) to execute the tool

All tools are proxied from the underlying MCP server.""",
        )

        # Create the underlying proxy that forwards all tools from the client
        self._proxy = create_proxy(client, name=f"proxy_{server_id}")

        logger.info(
            "LayeredMCPFactory initialized with server_id: %s, product_id: %s",
            self.server_id,
            self.product_id,
        )

        # Add our custom discovery tools
        self.add_tool(
            Tool.from_function(
                self.get_service_info,
                description=self._safe_tool_description(
                    "get_service_info",
                    "Discover and list all available tools from the underlying MCP server.",
                ),
            )
        )
        self.add_tool(
            Tool.from_function(
                self.get_type_info,
                description=self._safe_tool_description(
                    "get_type_info",
                    "Get detailed information about a specific tool including its schema and usage.",
                ),
            )
        )
        self.add_tool(
            Tool.from_function(
                self.make_tool_call,
                description=self._safe_tool_description(
                    "make_tool_call",
                    "Execute a tool call on the underlying MCP server with the provided arguments.",
                ),
            )
        )

        logger.debug("LayeredMCPFactory initialization complete")

    def _safe_tool_description(self, key: str, fallback: str) -> str:
        """Get custom tool description or fallback to default."""
        value = self._tool_descriptions.get(key, "")
        if not isinstance(value, str):
            value = ""
        return value.strip() or fallback

    def _get_input_schema(self, tool_dict: dict[str, Any], tool: Any) -> Any:
        """Resolve a tool's input schema from normalized dict or tool object."""
        if "inputSchema" in tool_dict:
            return tool_dict["inputSchema"]
        if "input_schema" in tool_dict:
            return tool_dict["input_schema"]
        if "parameters" in tool_dict:
            return tool_dict["parameters"]
        if hasattr(tool, "inputSchema"):
            return getattr(tool, "inputSchema")
        if hasattr(tool, "input_schema"):
            return getattr(tool, "input_schema")
        if hasattr(tool, "parameters"):
            return getattr(tool, "parameters")
        return None

    def _normalize_tool_dict(self, tool: Any) -> dict[str, Any]:
        """Convert a proxied or native tool object into a normalized dict."""
        tool_dict: dict[str, Any] = {}

        # Try dict conversion first if tool is already a dict
        if isinstance(tool, dict):
            tool_dict = tool.copy()
        # Try model_dump if available and callable
        elif hasattr(tool, "model_dump") and callable(getattr(tool, "model_dump")):
            try:
                result = tool.model_dump()
                # Verify it's actually a dict (not a MagicMock or other object)
                if isinstance(result, dict):
                    tool_dict = result
                    logger.debug(
                        "Converted tool using model_dump(): %s", tool_dict.get("name")
                    )
                else:
                    logger.debug(
                        "model_dump() did not return a dict, will build manually"
                    )
            except Exception as e:
                logger.debug("Failed to use model_dump(): %s", e)
        # Try dict() method if available and callable
        elif hasattr(tool, "dict") and callable(getattr(tool, "dict")):
            try:
                result = tool.dict()
                # Verify it's actually a dict
                if isinstance(result, dict):
                    tool_dict = result
                    logger.debug(
                        "Converted tool using dict(): %s", tool_dict.get("name")
                    )
                else:
                    logger.debug("dict() did not return a dict, will build manually")
            except Exception as e:
                logger.debug("Failed to use dict(): %s", e)

        # Ensure we have name and description
        if "name" not in tool_dict:
            tool_dict["name"] = getattr(tool, "name", str(tool))

        if "description" not in tool_dict:
            tool_dict["description"] = getattr(tool, "description", "") or ""

        # Get input schema
        input_schema = self._get_input_schema(tool_dict, tool)
        if input_schema is not None:
            tool_dict["inputSchema"] = input_schema
        else:
            logger.warning(
                "Tool '%s' has no inputSchema. Available attributes: %s",
                tool_dict.get("name"),
                dir(tool) if hasattr(tool, "__dir__") else type(tool),
            )

        return tool_dict

    def _extract_instances_from_context(
        self, auth_context: Any
    ) -> list[dict[str, Any]]:
        """
        Extract user instances from auth context, handling different context formats.

        Args:
            auth_context: The authentication context (dict or object)

        Returns:
            List of user instances, or empty list if not found
        """
        if isinstance(auth_context, dict):
            instances = auth_context.get(AUTH_KEY_USER_INSTANCES_FULL, [])
        elif hasattr(auth_context, AUTH_KEY_USER_INSTANCES_FULL):
            instances = getattr(auth_context, AUTH_KEY_USER_INSTANCES_FULL)
        elif hasattr(auth_context, "get"):
            instances = auth_context.get(AUTH_KEY_USER_INSTANCES_FULL, [])
        else:
            instances = []

        # Ensure we return a list
        if instances is None:
            return []
        if not isinstance(instances, list):
            logger.warning(
                "Expected list of instances, got %s", type(instances).__name__
            )
            return []

        return instances

    def _get_instance_product_id(self, instance: dict[str, Any]) -> str | None:
        """
        Get productId from an instance. Supports full shape (subscription.productId/product_id),
        normalized shape (top-level productId/product_id), and snake_case keys.
        """
        sub = instance.get("subscription")
        if isinstance(sub, dict):
            val = sub.get("productId") or sub.get("product_id")
            if val:
                return val
        val = instance.get("productId") or instance.get("product_id")
        return val if val else None

    def _authorize_and_select_instance(
        self,
        instances: list[dict[str, Any]],
        server_id: str,
    ) -> dict[str, Any] | None:
        """
        Authorize user access by matching productId with instance productId.
        Returns the first matching active instance or None if unauthorized.

        Supports both full instance shape (subscription.productId) and normalized shape (top-level productId).
        """
        if not instances:
            logger.warning("No user instances available for authorization")
            return None

        if not self.product_id:
            logger.error(
                "productId not configured in server config. Authorization cannot proceed."
            )
            return None

        logger.info(
            "Using productId-based authorization: productId='%s'", self.product_id
        )

        matching_instances = [
            inst
            for inst in instances
            if self._get_instance_product_id(inst) == self.product_id
            and inst.get("state") == "active"
        ]

        if matching_instances:
            selected = matching_instances[0]
            subscription_name = (selected.get("subscription") or {}).get(
                "subscriptionName", "unknown"
            )
            logger.info(
                "✓ Authorization successful: productId '%s' matched instance subscription '%s'",
                self.product_id,
                subscription_name,
            )
            logger.info(
                "  Instance: id='%s', name='%s'",
                selected.get("id"),
                selected.get("name"),
            )
            return selected

        # No match found with productId
        available_products = list(
            set(self._get_instance_product_id(inst) or "unknown" for inst in instances)
        )
        logger.warning(
            "Authorization failed: productId '%s' not found in user instances. Available productIds: %s",
            self.product_id,
            available_products,
        )
        return None

    async def _fetch_tools(self) -> list[dict[str, Any]]:
        """Fetch tools from the underlying MCP server and cache them."""
        if self._cached_tools is not None:
            logger.debug("Returning cached tools (%d tools)", len(self._cached_tools))
            return self._cached_tools

        tools = []

        # Try method 1: Get tools from the proxy's list_tools
        try:
            logger.info("Attempting to fetch tools from proxy.list_tools()")
            proxy_tools = await self._proxy.list_tools()
            logger.info(
                "Proxy returned %d tools", len(proxy_tools) if proxy_tools else 0
            )

            if proxy_tools:
                for tool in proxy_tools:
                    tool_dict = self._normalize_tool_dict(tool)

                    tools.append(tool_dict)
                    logger.debug(
                        "Found tool from proxy: %s (has inputSchema: %s)",
                        tool_dict.get("name"),
                        "inputSchema" in tool_dict,
                    )

                if tools:
                    self._cached_tools = tools
                    logger.info("Successfully fetched %d tools from proxy", len(tools))
                    return tools
        except Exception as e:
            logger.warning("Failed to fetch tools from proxy: %s", e)
            logger.exception("Proxy fetch full traceback:")

        # Try method 2: Get tools directly from client
        try:
            logger.info("Attempting to fetch tools from client.list_tools()")
            
            # Log client configuration details
            logger.info("Client configuration details:")
            logger.info("  - Client type: %s", type(self.client).__name__)
            logger.info("  - Client attributes: %s", dir(self.client))
            
            # Try to extract connection details if available
            if hasattr(self.client, 'read_url'):
                logger.info("  - Read URL: %s", getattr(self.client, 'read_url', 'N/A'))
            if hasattr(self.client, 'write_url'):
                logger.info("  - Write URL: %s", getattr(self.client, 'write_url', 'N/A'))
            if hasattr(self.client, '_transport'):
                logger.info("  - Transport type: %s", type(getattr(self.client, '_transport', None)).__name__)
            if hasattr(self.client, 'timeout'):
                logger.info("  - Timeout: %s", getattr(self.client, 'timeout', 'N/A'))
            
            logger.info("Attempting to connect to client...")
            async with self.client:
                result = await self.client.list_tools()
                logger.info("Client.list_tools() returned: %s", type(result))
                logger.debug("Result attributes: %s", dir(result) if result else "None")

            if hasattr(result, "tools"):
                logger.info(
                    "Result has 'tools' attribute with %d items", len(result.tools)
                )
                for tool in result.tools:
                    tool_dict = self._normalize_tool_dict(tool)

                    tools.append(tool_dict)
                    logger.debug(
                        "Found tool from client: %s (has inputSchema: %s)",
                        tool_dict.get("name"),
                        "inputSchema" in tool_dict,
                    )
            else:
                logger.warning(
                    "Result does not have 'tools' attribute. Result type: %s",
                    type(result),
                )

            if tools:
                self._cached_tools = tools
                logger.info("Successfully fetched %d tools from client", len(tools))
                return tools
        except Exception as e:
            logger.error("Failed to fetch tools from client: %s", e)
            logger.error("Exception type: %s", type(e).__name__)
            logger.error("Exception args: %s", e.args)
            
            # Log additional network-related error details
            import sys
            import traceback
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error("Full exception details:")
            logger.error("  - Type: %s", exc_type)
            logger.error("  - Value: %s", exc_value)
            logger.error("  - Traceback:")
            for line in traceback.format_tb(exc_traceback):
                logger.error("    %s", line.strip())
            
            # Check for specific network errors
            if "timeout" in str(e).lower():
                logger.error("⚠️  TIMEOUT ERROR: Connection timed out - check network latency or increase timeout")
            elif "connection" in str(e).lower():
                logger.error("⚠️  CONNECTION ERROR: Cannot establish connection - check network policies, DNS, and firewall")
            elif "ssl" in str(e).lower() or "certificate" in str(e).lower():
                logger.error("⚠️  SSL/TLS ERROR: Certificate validation failed - check SSL configuration")
            elif "refused" in str(e).lower():
                logger.error("⚠️  CONNECTION REFUSED: Target server is not accepting connections")
            
            logger.exception("Full traceback:")

        # If we got here, no tools were found
        logger.warning("No tools found from either proxy or client")
        self._cached_tools = []
        return []

    async def get_service_info(self) -> str:
        """
        Discover and list all available tools from the underlying MCP server.

        Returns:
            JSON string with tool information
        """
        import json

        tools = await self._fetch_tools()

        if not tools:
            return json.dumps(
                {
                    "message": "No tools available from the underlying MCP server",
                    "tools": [],
                },
                indent=2,
            )

        # Format tools for display
        formatted_tools = []
        for tool in tools:
            formatted_tool = {
                "name": tool["name"],
                "description": tool["description"],
            }
            if tool.get("inputSchema") is not None:
                formatted_tool["inputSchema"] = tool["inputSchema"]
            formatted_tools.append(formatted_tool)

        return json.dumps(
            {
                "message": f"Found {len(formatted_tools)} tools",
                "tools": formatted_tools,
            },
            indent=2,
        )

    async def get_type_info(self, tool_name: str) -> str:
        """
        Get detailed information about a specific tool.

        Args:
            tool_name: The name of the tool to inspect

        Returns:
            JSON string with detailed tool information including extracted parameters
        """
        import json

        tools = await self._fetch_tools()

        # Find the requested tool
        tool = next((t for t in tools if t["name"] == tool_name), None)

        if not tool:
            available_tools = [t["name"] for t in tools]
            return json.dumps(
                {
                    "error": f"Tool '{tool_name}' not found",
                    "available_tools": available_tools,
                },
                indent=2,
            )

        result = {
            "name": tool["name"],
            "description": tool["description"],
        }

        input_schema = tool.get("inputSchema")
        if input_schema is not None:
            result["inputSchema"] = input_schema

            # Extract parameters from JSON Schema
            if isinstance(input_schema, dict):
                parameters = self._extract_parameters_from_schema(input_schema)
                if parameters:
                    result["parameters"] = parameters

                # Try to generate example from schema
                try:
                    from fastmcp.utilities.openapi import generate_example_from_schema

                    example = generate_example_from_schema(input_schema)
                    if example:
                        result["example"] = example
                except Exception as e:
                    logger.debug(
                        "Could not generate example for tool %s: %s", tool_name, e
                    )

        return json.dumps(result, indent=2)

    def _extract_parameters_from_schema(
        self, schema: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Extract parameter information from a JSON Schema.

        Args:
            schema: The JSON Schema (typically from inputSchema)

        Returns:
            List of parameter dictionaries with name, type, description, required, etc.
        """
        parameters: list[dict[str, Any]] = []

        if not isinstance(schema, dict):
            return parameters

        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        for param_name, param_schema in properties.items():
            if not isinstance(param_schema, dict):
                continue

            param_info = {
                "name": param_name,
                "type": param_schema.get("type", "unknown"),
                "description": param_schema.get("description", ""),
                "required": param_name in required_fields,
            }

            # Add additional schema properties if present
            if "default" in param_schema:
                param_info["default"] = param_schema["default"]

            if "enum" in param_schema:
                param_info["enum"] = param_schema["enum"]

            if "format" in param_schema:
                param_info["format"] = param_schema["format"]

            if "pattern" in param_schema:
                param_info["pattern"] = param_schema["pattern"]

            if "minimum" in param_schema:
                param_info["minimum"] = param_schema["minimum"]

            if "maximum" in param_schema:
                param_info["maximum"] = param_schema["maximum"]

            if "minLength" in param_schema:
                param_info["minLength"] = param_schema["minLength"]

            if "maxLength" in param_schema:
                param_info["maxLength"] = param_schema["maxLength"]

            # Handle array types
            if param_schema.get("type") == "array" and "items" in param_schema:
                param_info["items"] = param_schema["items"]

            # Handle object types with nested properties
            if param_schema.get("type") == "object" and "properties" in param_schema:
                param_info["properties"] = param_schema["properties"]

            parameters.append(param_info)

        return parameters

    async def make_tool_call(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> str:
        """
        Execute a tool call on the underlying MCP server.

        Args:
            tool_name: The name of the tool to execute
            arguments: The arguments to pass to the tool (optional)

        Returns:
            JSON string with the result from the tool execution
        """
        import json

        if arguments is None:
            arguments = {}

        logger.info("Calling tool '%s' with arguments: %s", tool_name, arguments)

        try:
            # Verify the tool exists
            tools = await self._fetch_tools()
            tool = next((t for t in tools if t["name"] == tool_name), None)

            if not tool:
                available_tools = [t["name"] for t in tools]
                return json.dumps(
                    {
                        "error": f"Tool '{tool_name}' not found",
                        "available_tools": available_tools,
                    },
                    indent=2,
                )

            # AUTHORIZATION CHECK: Only run if product_id is configured
            if AUTH_CONTEXT_AVAILABLE and self.product_id:
                try:
                    auth_context = get_auth_context()
                    logger.debug(
                        "Auth context retrieved: %s", type(auth_context).__name__
                    )

                    if not auth_context:
                        logger.warning(
                            "Auth context not available for tool: %s", tool_name
                        )
                        # Continue without authorization if no context
                    else:
                        # Get full instance data
                        instances_full = self._extract_instances_from_context(
                            auth_context
                        )

                        safe_length = (
                            len(instances_full)
                            if hasattr(instances_full, "__len__")
                            else "unknown"
                        )
                        logger.debug(
                            "Instances retrieved: type=%s, length=%s",
                            type(instances_full).__name__,
                            safe_length,
                        )

                        if not instances_full:
                            logger.warning(
                                "No user instances found in auth context for tool: %s",
                                tool_name,
                            )
                            return json.dumps(
                                {
                                    "error": "Unauthorized",
                                    "message": "No user instances available for authorization",
                                    "status_code": 401,
                                    "tool": tool_name,
                                    "server_id": self.server_id,
                                },
                                indent=2,
                            )

                        # AUTHORIZATION: Match product_id with instance.subscription.productId
                        logger.debug(
                            "Authorizing with product_id='%s'", self.product_id
                        )
                        selected_instance = self._authorize_and_select_instance(
                            instances_full,
                            self.server_id,
                        )

                        if not selected_instance:
                            # No user instance had productId matching server's product_id
                            available_product_ids = list(
                                set(
                                    self._get_instance_product_id(i) or "unknown"
                                    for i in instances_full
                                )
                            )
                            logger.error(
                                "Authorization failed for tool '%s': product_id '%s' not in user instances' productIds %s",
                                tool_name,
                                self.product_id,
                                available_product_ids,
                            )
                            return json.dumps(
                                {
                                    "error": "Unauthorized",
                                    "message": f"Access denied: No instance with productId '{self.product_id}'. "
                                    f"User instances have productIds: {', '.join(available_product_ids)}",
                                    "status_code": 401,
                                    "tool": tool_name,
                                    "server_id": self.server_id,
                                    "product_id": self.product_id,
                                    "available_product_ids": available_product_ids,
                                },
                                indent=2,
                            )

                        # Authorization successful
                        resolved_instance_id = selected_instance.get(
                            "id"
                        ) or selected_instance.get("instance_id", "")
                        resolved_product_id = (
                            self._get_instance_product_id(selected_instance) or ""
                        )
                        logger.info(
                            "✓ Authorized tool '%s': instance_id=%s, productId=%s",
                            tool_name,
                            resolved_instance_id,
                            resolved_product_id,
                        )
                except Exception as e:
                    logger.error("Error during authorization check: %s", e)
                    logger.exception("Full traceback:")
                    return json.dumps(
                        {
                            "error": "Authorization check failed",
                            "details": str(e),
                            "tool": tool_name,
                        },
                        indent=2,
                    )

            # Call the tool using the proxy which handles tool forwarding
            logger.debug("Calling tool '%s' via proxy", tool_name)
            result = await self._proxy.call_tool(tool_name, arguments)
            logger.debug("Tool call completed, processing result")

            # Extract content from result
            if hasattr(result, "content"):
                content_list = []
                for item in result.content:
                    # Use getattr with default to avoid Pylance errors
                    content = getattr(item, "text", None)
                    if content is None:
                        content = getattr(item, "data", None)
                    if content is None:
                        content = item
                    content_list.append(content)

                if len(content_list) == 1:
                    single = content_list[0]
                    if isinstance(single, str):
                        return single
                    return json.dumps(single, indent=2)
                return json.dumps(content_list, indent=2)

            if isinstance(result, str):
                return result
            return json.dumps(result, indent=2)

        except ToolError as e:
            logger.error("Proxied tool '%s' failed with ToolError: %s", tool_name, e)
            logger.exception("Full ToolError traceback:")

            def _resolve_tool_error_message(exc: BaseException) -> str:
                cause = getattr(exc, "__cause__", None)
                if cause is not None:
                    return _resolve_tool_error_message(cause)
                context = getattr(exc, "__context__", None)
                if context is not None:
                    return _resolve_tool_error_message(context)
                return str(exc)

            error_message = _resolve_tool_error_message(e) or "Tool execution failed"
            prefix = f"Error calling tool {tool_name!r}: "
            if error_message.startswith(prefix):
                error_message = error_message[len(prefix) :]

            error_details = {
                "error": "Tool execution failed",
                "tool": tool_name,
                "message": error_message,
            }

            # Use getattr with default to avoid Pylance errors
            error_code = getattr(e, "code", None)
            if error_code is not None:
                error_details["error_code"] = error_code

            details = getattr(e, "details", None)
            if details is not None:
                error_details["details"] = details

            content = getattr(e, "content", None)
            if content is not None:
                error_details["content"] = str(content)

            return json.dumps(error_details, indent=2)
        except Exception as e:
            logger.error("Error calling tool '%s': %s", tool_name, e)
            logger.exception("Full traceback:")
            return json.dumps(
                {"error": f"Failed to call tool '{tool_name}'", "details": str(e)},
                indent=2,
            )
