from fastmcp.server.openapi import RouteMap, MCPType
import httpx
import json
from mcp_gateway.utils.logger import LoggerFactory
from enum import Enum
logger = LoggerFactory.get_logger()

class MemberServerType(str, Enum):
    OpenAPI="openapi"
    Client="client"


async def load_custom_mappings_from_json(json_data: str | list[dict]) -> list[RouteMap]:
    """
    Convert JSON-formatted route mappings into a list of RouteMap objects.

    Args:
        json_data: JSON string or already-parsed list of dicts

    Returns:
        List[RouteMap]
    """
    if isinstance(json_data, str):
        mappings = json.loads(json_data)
    else:
        mappings = json_data

    route_maps = []
    for mapping in mappings:
        methods = mapping.get("methods", "*")
        pattern = mapping["pattern"]
        mcp_type_str = mapping["mcp_type"].upper()

        try:
            mcp_type = MCPType[mcp_type_str]
        except KeyError:
            raise ValueError(f"Invalid MCP type: {mcp_type_str}")

        route_maps.append(RouteMap(methods=methods, pattern=pattern, mcp_type=mcp_type))

    return route_maps


async def load_spec_from_url(base_url,openapi_spec_url):
   logger.info("Downloading the json spec for the open api")
   async with httpx.AsyncClient(base_url=base_url) as client:
            response = await client.get(openapi_spec_url)
            response.raise_for_status()
            spec = response.json()
            return spec
   
async def load_json(filepath):
    
    with open(filepath, 'r', encoding='utf-8-sig') as file:
        data = json.load(file)        
        return data
