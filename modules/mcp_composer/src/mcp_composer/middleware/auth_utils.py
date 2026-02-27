"""
Shared auth helpers: tool name to server_id resolution.
"""


def tool_name_to_server_id(tool_name: str) -> str | None:
    """
    Return the member server id from a tool name (prefix before first '_').
    Same rule as tracing's _split_tool_fullname. Composer-owned tools have no prefix.
    """
    if not tool_name or not isinstance(tool_name, str):
        return None
    i = tool_name.find("_")
    if i <= 0:
        return None
    return tool_name[:i]
