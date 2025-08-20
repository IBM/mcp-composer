"""Tools util functions"""

from typing import Optional, List, Dict, Any, Callable, Tuple
from fastmcp.tools.tool import Tool
from fastmcp.exceptions import NotFoundError
from pydantic import ValidationError
import uncurl

from mcp_composer.core.utils.exceptions import ToolGenerateError
from mcp_composer.core.models.tool import OpenApiToolAuthConfig, ToolBuilderConfig
from mcp_composer.core.utils.auth_strategy import get_client
from mcp_composer.core.utils.custom_tool import DynamicToolGenerator, OpenApiTool
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def format_tool(tool: Tool) -> dict:
    """return tool in dict"""
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
    }


async def generate_tool_from_curl() -> List[Callable[[], Any]]:
    """Create tool from curl command"""
    try:
        return DynamicToolGenerator.read_curl_from_file()
    except ToolGenerateError as e:
        logger.exception(
            "Failed to generate tool from saved curl config details: %s", e
        )
        raise ToolGenerateError(
            "Failed to generate tool from saved curl config details"
        ) from e


async def generate_tool_from_open_api() -> Dict[str, Tuple[Dict[str, Any], Any]]:
    """Create tool from OpenAPI specification"""
    try:
        return await OpenApiTool.read_openapi_from_file()
    except Exception as e:
        logger.exception(
            "Failed to generate tool from saved OpenAPI specification: %s", e
        )
        raise ToolGenerateError(
            "Failed to generate tool from saved OpenAPI specification"
        ) from e


async def tool_from_script(config: dict) -> Callable[[], Any]:
    """Create Tool dynamically from the python config script"""
    try:
        # Validate and parse input
        script_model = ToolBuilderConfig(**config)
        if script_model.script_config:
            logger.info("Generate tool from python script")
            return DynamicToolGenerator().create_from_script(script_model)

        if script_model.curl_config:
            parsed = uncurl.parse_context(script_model.curl_config["value"])
            tool_data = {
                "_id": script_model.name,
                "id": script_model.name,
                "description": script_model.description,
                "headers": parsed.headers,
                "method": parsed.method,
                "body": parsed.data,
                "url": parsed.url,
            }
            logger.info("Generate tool from curl command, parsed details:%s", tool_data)
            DynamicToolGenerator.write_curl_to_file(tool_data)
            return DynamicToolGenerator.create_api_request(tool_data)

        # If neither script_config nor curl_config exists
        raise ValueError("Either script_config or curl_config must be provided")

    except ValidationError as e:
        logger.exception("Invalid input: %s", e.errors())
        raise ToolGenerateError(f"Invalid input: {e.errors()}") from e

    except Exception as e:
        logger.exception("Failed to generate tool from config:%s", e)
        raise ToolGenerateError(str(e)) from e


async def tool_from_open_api(
    open_api: dict, auth_config: dict | None = None
) -> Tuple[str, Any]:
    """Create tool from OpenAPI specification"""
    try:
        # for now, considering only one server
        server_url = open_api["servers"][0]["url"]
        server_name = open_api["info"]["title"].replace(" ", "_")
        if auth_config:
            OpenApiToolAuthConfig(**auth_config)
        OpenApiTool(server_name, open_api, auth_config).write_openapi()
        return server_name, await get_client(server_url, auth_config)

    except KeyError as e:
        logger.exception("Failed to generate tool from openapi:%s", e)
        raise ToolGenerateError(
            "Failed to generate tool from openapi: server url or title is missing"
        ) from e

    except Exception as e:
        logger.exception("Failed to generate tool from openapi:%s", e)
        raise ToolGenerateError(f"Failed to generate tool from openapi:{e}") from e


async def tool_exist(tools: list[str] | str, all_tools: dict[str, Tool]) -> None:
    """Check tool exist or not"""
    tools_to_check = [tools] if isinstance(tools, str) else tools
    unknown_tools = [tool for tool in tools_to_check if tool not in all_tools.keys()]
    if unknown_tools:
        raise NotFoundError(f"Unknown tool(s):{unknown_tools}")


def tool_config(server_tools: dict[str, Tool], key: Optional[str] = None) -> list[dict]:
    """
    Get tool configuration details by tool name or server
    """
    if key:
        tool = server_tools.get(key)
        if not tool:
            raise NotFoundError(f"Unknown tool: {key}")
        return [format_tool(tool)]

    return [format_tool(tool) for tool in server_tools.values()]


def check_duplicate_tool(existing_tools: list[str], tools: list[str]) -> set:
    """Check for duplicate tool"""
    tools_exists = set(existing_tools)
    new_tools = set(tools)
    return tools_exists.intersection(new_tools)
