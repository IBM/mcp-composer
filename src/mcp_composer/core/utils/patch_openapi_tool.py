"""override FastMCP FastMCPOpenAPI._create_openapi_tool
for disable the output schema generation based on the OpenAPI specification
"""

from fastmcp.server.openapi import OpenAPITool, FastMCPOpenAPI
from fastmcp.utilities import openapi
from fastmcp.utilities.openapi import (
    _combine_schemas,
    format_description_with_responses,
)
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def _patched_create_openapi_tool(
    self,
    route: openapi.HTTPRoute,
    name: str,
    tags: set[str],
):
    """Creates and registers an OpenAPITool with enhanced description."""
    combined_schema = _combine_schemas(route)

    # Extract output schema from OpenAPI responses
    output_schema = None

    # Get a unique tool name
    tool_name = self._get_unique_name(name, "tool")

    base_description = (
        route.description or route.summary or f"Executes {route.method} {route.path}"
    )

    # Format enhanced description with parameters and request body
    enhanced_description = format_description_with_responses(
        base_description=base_description,
        responses=route.responses,
        parameters=route.parameters,
        request_body=route.request_body,
    )

    tool = OpenAPITool(
        client=self._client,
        route=route,
        name=tool_name,
        description=enhanced_description,
        parameters=combined_schema,
        output_schema=output_schema,
        tags=set(route.tags or []) | tags,
        timeout=self._timeout,
    )

    # Call component_fn if provided
    if self._mcp_component_fn is not None:
        try:
            self._mcp_component_fn(route, tool)
            logger.debug("Tool %s customized by component_fn", tool_name)
        except Exception as e:
            logger.warning(
                "Error in component_fn for tool %s : %s. Using component as-is.",
                tool_name,
                e,
            )

    # Use the potentially modified tool name as the registration key
    final_tool_name = tool.name

    # Register the tool by directly assigning to the tools dictionary
    self._tool_manager._tools[final_tool_name] = tool
    logger.debug(
        "Registered TOOL:'%s' - %s:%s with tags: %s",
        final_tool_name,
        route.method,
        route.path,
        route.tags,
    )


FastMCPOpenAPI._create_openapi_tool = _patched_create_openapi_tool
