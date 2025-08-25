"""Utility functions"""

import asyncio
import importlib.util
import json
import os
import re
import subprocess
from typing import Any, Callable, Dict, Optional, Tuple

import aiohttp
import httpx
from aiohttp import ClientConnectorError
from fastmcp.prompts.prompt import Prompt, PromptArgument
from fastmcp.server.openapi import MCPType, RouteMap

from mcp_composer.core.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.core.settings.adapters import ADAPTER_REGISTRY
from mcp_composer.core.settings.base_adapter import SecretAdapter
from mcp_composer.core.utils.exceptions import MemberServerError
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


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
        except KeyError as e:
            raise ValueError(f"Invalid MCP type: {mcp_type_str}") from e

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
        raise MemberServerError(
            f"Failed to fetch the status of member servers: {e}"
        ) from e

    except Exception as e:
        logger.exception("Failed to fetch the status of member servers: %s", e)
        raise MemberServerError(
            f"Failed to fetch the status of member servers: {e}"
        ) from e


def get_server_doc_info(doc: dict) -> tuple[list[str], dict[str, str]]:
    disabled_tools = []
    tools_description = {}
    if doc:
        disabled_tools = doc.get("disabled_tools", [])
        tools_description = doc.get("tools_description", {})
    return disabled_tools, tools_description


def extract_imported_modules(script: str):
    # Naive regex for finding `import` and `from ... import`
    pattern = r"^\s*(?:import|from)\s+([\w_]+)"
    return list(set(re.findall(pattern, script, re.MULTILINE)))


def ensure_dependencies_installed(dependencies):
    for package in dependencies:
        if importlib.util.find_spec(package) is None:
            logger.info("Installing missing package: %s", package)
            subprocess.check_call(["uv", "pip", "install", package])


def build_prompt_from_dict(entry: dict) -> Prompt:
    """
    Build a FastMCP Prompt from a dictionary configuration.

    Args:
        entry: Dictionary containing prompt configuration
            - name: Prompt name (required)
            - template: Prompt template (required)
            - description: Optional description
            - arguments: Optional list of argument configurations
            - tags: Optional set of tags

    Returns:
        Prompt: Configured FastMCP Prompt object
    """
    if not isinstance(entry, dict):
        raise ValueError("Entry must be a dictionary")

    name = entry.get("name")
    template = entry.get("template")
    if not name or not template:
        raise ValueError("Prompt must include both 'name' and 'template'")

    description = entry.get("description", "")
    tags = set(entry.get("tags", [])) if entry.get("tags") else None
    arguments = entry.get("arguments", [])

    fn = _create_prompt_function(template, arguments)
    prompt = Prompt.from_function(fn=fn, name=name, description=description, tags=tags)

    if arguments:
        prompt.arguments = _build_prompt_arguments(arguments)

    return prompt


def _create_prompt_function(template: str, arguments: list[Any]) -> Callable:
    """
    Dynamically build a function for the prompt using provided template and arguments.
    """
    if not arguments:
        return lambda: template

    arg_names = _extract_argument_names(arguments)
    param_list = ", ".join(arg_names)
    format_args = ", ".join([f"{name}={name}" for name in arg_names])

    func_code = f"""
def prompt_fn({param_list}):
    template = \"\"\"{template}\"\"\"
    try:
        return template.format({format_args})
    except KeyError as e:
        raise ValueError(f"Template references undefined argument: {{e}}")
    except Exception as e:
        raise ValueError(f"Error formatting template: {{e}}")
"""

    namespace = {}
    exec(func_code, namespace)
    return namespace["prompt_fn"]


def _extract_argument_names(arguments: list[Any]) -> list[str]:
    """
    Extract argument names from argument config.
    """
    arg_names = []
    for arg in arguments:
        if isinstance(arg, dict):
            if "name" not in arg:
                raise ValueError("Argument name is required")
            arg_names.append(arg["name"])
        elif isinstance(arg, str):
            arg_names.append(arg)
        else:
            raise ValueError(f"Invalid argument format: {arg}")
    return arg_names


def _build_prompt_arguments(arguments: list[Any]) -> list[Any]:
    """
    Create PromptArgument objects from argument definitions.
    """
    prompt_arguments = []

    for arg in arguments:
        if isinstance(arg, dict):
            prompt_arguments.append(
                PromptArgument(
                    name=arg.get("name", ""),
                    description=arg.get("description", ""),
                    required=arg.get("required", True),
                )
            )
        elif isinstance(arg, str):
            prompt_arguments.append(PromptArgument(name=arg))

    return prompt_arguments


def get_version_adapter(config: Optional[Dict[str, Any]] = None) -> SecretAdapter:
    if config:
        adapter_type = config.get("type", "file").lower()
        adapter_args = {k: v for k, v in config.items() if k != "type"}
    else:
        adapter_type = os.getenv("VERSION_ADAPTER_TYPE", "file").lower()
        adapter_args = (
            {
                "file_path": os.getenv(
                    "VERSION_CONFIG_FILE_PATH", "versioned_config.json"
                )
            }
            if adapter_type == "file"
            else {}
        )

    adapter_factory = ADAPTER_REGISTRY.get(adapter_type)
    if not adapter_factory:
        raise ValueError(f"Unsupported version adapter type: {adapter_type}")

    return adapter_factory(**adapter_args)
