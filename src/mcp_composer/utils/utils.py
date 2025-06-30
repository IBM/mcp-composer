import subprocess
import re
import importlib.util
import httpx
import aiohttp
import asyncio
import json
from typing import Tuple
from enum import Enum
from aiohttp import ClientConnectorError
from fastmcp.server.openapi import RouteMap, MCPType
from fastmcp.tools.tool import Tool

from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.exceptions import MemberServerError


logger = LoggerFactory.get_logger()


class MemberServerType(str, Enum):
    OpenAPI = "openapi"
    Client = "client"


async def _get_status(session, server: MemberMCPServer) -> Tuple[int, MemberMCPServer]:
    async with session.get(server.config.get("endpoint")) as resp:
        return resp.status, server


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


async def load_spec_from_url(base_url, openapi_spec_url):
    logger.info("Downloading the json spec for the open api")
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.get(openapi_spec_url)
        response.raise_for_status()
        spec = response.json()
        return spec


async def load_json(filepath):
    with open(filepath, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
        return data


async def get_member_health(
    server_config: list[MemberMCPServer],
) -> list[dict]:
    try:
        async with aiohttp.ClientSession(trust_env=True) as session:
            tasks = {
                server.id: asyncio.create_task(_get_status(session, server))
                for server in server_config
                if "endpoint" in server.config
            }

            results = await asyncio.gather(*tasks.values())

            status = []
            for (status_code, server), server_id in zip(results, tasks.keys()):
                server_status = {}
                health = (
                    HealthStatus.healthy
                    if status_code in {200, 406, 401}
                    else HealthStatus.unhealthy
                )
                server.health_status = health
                server_status["status"] = health
                server_status["server_name"] = server_id
                status.append(server_status)
            return status

    except ClientConnectorError as e:
        logger.exception("Connection Error: Failed to connect to MCP server. %s", e)
        raise MemberServerError(f"Failed to fetch the status of member servers: {e}")

    except Exception as e:
        logger.exception("Failed to fetch the status of member servers: %s", e)
        raise MemberServerError(f"Failed to fetch the status of member servers: {e}")


def check_duplicate_tool(existing_tools: list[str], tools: list[str]) -> set:
    tools_exists = set(existing_tools)
    new_tools = set(tools)
    return tools_exists.intersection(new_tools)


def get_server_doc_info(doc: dict) -> tuple[list[str], dict[str, str]]:
    remove_tools = []
    tools_description = {}
    if doc:
        remove_tools = doc.get("remove_tools", [])
        tools_description = doc.get("tools_description", {})
    return remove_tools, tools_description


def format_tool(tool: Tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
    }


def extract_imported_modules(script: str):
    # Naive regex for finding `import` and `from ... import`
    pattern = r"^\s*(?:import|from)\s+([\w_]+)"
    return list(set(re.findall(pattern, script, re.MULTILINE)))


def ensure_dependencies_installed(dependencies):
    for package in dependencies:
        if importlib.util.find_spec(package) is None:
            print(f"Installing missing package: {package}")
            subprocess.check_call(["uv", "pip", "install", package])


def create_api_request(tool):
    logger.info(f"Generate tool from API request on the fly:{tool}")

    async def api_tool():
        data = tool.get("data")
        headers = tool["headers"]
        method = tool["method"]
        body = data if data else None
        url = tool["url"]

        async with httpx.AsyncClient() as client:
            req = client.build_request(method.upper(), url, headers=headers, json=body)
            res = await client.send(req)
            return {"status_code": res.status_code, "body": res.text}

    api_tool.__name__ = tool["id"]
    api_tool.__doc__ = tool["description"]
    return api_tool
