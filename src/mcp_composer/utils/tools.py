"""Tools util functions"""

from typing import Optional
from fastmcp.tools.tool import Tool
from fastmcp.exceptions import NotFoundError


def format_tool(tool: Tool) -> dict:
    """return tool in dict"""
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
    }


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
