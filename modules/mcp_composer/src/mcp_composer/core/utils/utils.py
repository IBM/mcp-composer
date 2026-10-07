"""Utility functions"""

import asyncio
import importlib.util
import inspect
import json
import keyword
import os
import re
import string
import subprocess
from typing import Any, Callable

import aiohttp
import httpx
from aiohttp import ClientConnectorError
from fastmcp.prompts import Prompt, PromptArgument
from fastmcp.server.providers.openapi import MCPType, RouteMap
from pydantic import HttpUrl

from mcp_composer.core.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.core.settings.adapters import ADAPTER_REGISTRY
from mcp_composer.core.settings.base_adapter import SecretAdapter
from mcp_composer.core.utils.exceptions import MemberServerError
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.validator import MemberServerType, ConfigKey

logger = LoggerFactory.get_logger()


async def _get_status(
    session, server: MemberMCPServer, endpoint: str
) -> tuple[int, MemberMCPServer]:
    async with session.get(endpoint) as resp:
        return resp.status, server


async def load_custom_mappings_from_json(json_data: str | list[dict]) -> list[RouteMap]:
    """
    Convert JSON-formatted route mappings into a list of RouteMap objects.

    Args:
        json_data: JSON string or already-parsed list of dicts

    Returns:
        list[RouteMap]
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
    """
    Load JSON spec from URL or S3.
    Automatically detects S3 URLs and uses boto3 for authenticated access.

    Supports two S3 URL formats:
    1. Virtual-hosted style: https://bucket-name.s3.region.amazonaws.com/path/to/file.json
    2. Path-style: https://s3.region.amazonaws.com/bucket-name/path/to/file.json

    Args:
        base_url: Base URL for the API endpoint
        openapi_spec_url: URL to the OpenAPI spec (HTTP/HTTPS or S3)

    Returns:
        dict: Parsed JSON specification

    Raises:
        ValueError: If S3 access fails or JSON is invalid
        httpx.HTTPStatusError: If HTTP request fails
    """
    logger.info("Loading OpenAPI spec from: %s", openapi_spec_url)

    # Check if URL is an S3 URL (virtual-hosted style)
    s3_virtual_pattern = r"https://([^.]+)\.s3\.([^.]+)\.amazonaws\.com/(.+)"
    s3_virtual_match = re.match(s3_virtual_pattern, openapi_spec_url)

    # Check if URL is an S3 URL (path-style)
    s3_path_pattern = r"https://s3\.([^.]+)\.amazonaws\.com/([^/]+)/(.+)"
    s3_path_match = re.match(s3_path_pattern, openapi_spec_url)

    if s3_virtual_match or s3_path_match:
        # Import boto3 only when needed (optional dependency)
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as e:
            logger.error(
                "boto3 is required for S3 URL support. Install with: pip install mcp-composer[aws]"
            )
            raise ValueError(
                "boto3 is not installed. Install with: pip install mcp-composer[aws]"
            ) from e

        # Extract bucket, region, and key based on URL format
        if s3_virtual_match:
            bucket = s3_virtual_match.group(1)
            region = s3_virtual_match.group(2)
            key = s3_virtual_match.group(3)
            logger.info(
                "Detected S3 virtual-hosted style URL - bucket: %s, region: %s, key: %s",
                bucket,
                region,
                key,
            )
        elif s3_path_match:
            region = s3_path_match.group(1)
            bucket = s3_path_match.group(2)
            key = s3_path_match.group(3)
            logger.info(
                "Detected S3 path-style URL - bucket: %s, region: %s, key: %s",
                bucket,
                region,
                key,
            )
        else:
            # This should never happen due to the outer if condition, but added for type safety
            raise ValueError(f"Failed to parse S3 URL: {openapi_spec_url}")

        try:
            s3_client = boto3.client("s3", region_name=region)
            response = s3_client.get_object(Bucket=bucket, Key=key)
            spec_content = response["Body"].read().decode("utf-8")
            spec = json.loads(spec_content)
            logger.info(
                "Successfully loaded OpenAPI spec from S3: s3://%s/%s", bucket, key
            )
            return spec
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"].get("Message", "Unknown error")
            logger.error(
                "Failed to load spec from S3 (s3://%s/%s): %s - %s",
                bucket,
                key,
                error_code,
                error_message,
            )
            raise ValueError(
                f"Cannot load OpenAPI spec from S3 (s3://{bucket}/{key}): {error_code} - {error_message}"
            ) from e
        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON in S3 object (s3://%s/%s): %s", bucket, key, str(e)
            )
            raise ValueError(
                f"Invalid JSON in OpenAPI spec from S3 (s3://{bucket}/{key})"
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error loading spec from S3 (s3://%s/%s): %s",
                bucket,
                key,
                str(e),
            )
            raise ValueError(
                f"Unexpected error loading OpenAPI spec from S3 (s3://{bucket}/{key}): {str(e)}"
            ) from e
    else:
        # Standard HTTP/HTTPS URL - use existing logic
        logger.info("Using standard HTTP client for non-S3 URL")
        async with httpx.AsyncClient(base_url=base_url) as client:
            response = await client.get(openapi_spec_url)
            response.raise_for_status()
            spec = response.json()
            return spec


async def load_json(filepath):
    """Load json from local"""
    with open(filepath, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
        return data


async def get_member_health(
    server_config: list[MemberMCPServer],
) -> list[dict]:
    """Fetch server status"""
    try:
        async with aiohttp.ClientSession(trust_env=True) as session:
            task_items = []
            for server in server_config:
                endpoint = get_endpoint_from_config(server.config)
                if endpoint:
                    task_items.append(
                        (server.id, _get_status(session, server, str(endpoint)))
                    )

            if not task_items:
                return []

            results = await asyncio.gather(*(task for _, task in task_items))

            status = []
            for (status_code, server), (server_id, _) in zip(results, task_items):
                server_status = {}
                health = (
                    HealthStatus.healthy
                    if status_code in {200, 406, 401}
                    else HealthStatus.unhealthy
                )
                server.health_status = health
                server_status["status"] = health.value
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


def load_json_sync(filepath):
    """Synchronous version of load_json for use in __init__ methods"""
    with open(filepath, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
        return data


def get_server_doc_info(doc: dict) -> tuple[list[str], dict[str, str]]:
    """Get server tools details"""
    disabled_tools = []
    tools_description = {}
    if doc:
        disabled_tools = doc.get("disabled_tools", [])
        tools_description = doc.get("tools_description", {})
    return disabled_tools, tools_description


def extract_imported_modules(script: str):
    """Get import module names from the python script"""
    # Naive regex for finding `import` and `from ... import`
    pattern = r"^\s*(?:import|from)\s+([\w_]+)"
    return list(set(re.findall(pattern, script, re.MULTILINE)))


def ensure_dependencies_installed(dependencies):
    """Install the python packages mentioned in the python script"""
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


def get_version_adapter(config: dict[str, Any] | None = None) -> SecretAdapter:
    """Return adapter version"""
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


def get_endpoint_from_config(config: dict[str, Any]) -> HttpUrl | None:
    """Get the endpoint from config for different server types: HTTP, SSE, OpenAPI, etc."""

    server_type = config.get("type")

    if server_type in {
        MemberServerType.HTTP,
        MemberServerType.SSE,
        MemberServerType.STDIO,
        MemberServerType.CLIENT,
    }:
        endpoint = config.get("endpoint")

    elif server_type == MemberServerType.OPENAPI:
        endpoint = config.get(ConfigKey.OPEN_API, {}).get(ConfigKey.ENDPOINT)

    elif server_type == MemberServerType.GRAPHQL:
        endpoint = config.get(ConfigKey.GRAPHQL, {}).get(ConfigKey.ENDPOINT)

    else:
        endpoint = None

    return endpoint


def load_from_json(filename: str) -> dict[str, Any]:
    """
    Load dictionary data from a JSON file.

    Args:
        filename: The filename to load from

    Returns:
        The loaded dictionary, or an empty dictionary if the file doesn't exist
    """
    if not os.path.exists(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Error loading data to '%s' : '%s'", filename, str(e))
        return {}


def save_to_json(data: dict[str, Any], filename: str) -> bool:
    """
    Save dictionary data to a JSON file.

    Args:
        data: The dictionary to save
        filename: The filename to save to

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(filename, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error("Error saving data to '%s' : '%s'", filename, str(e))
        return False


_PROMPT_ARG_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _PromptFormatter(string.Formatter):
    """Substitute named arguments only. Reject attribute and index access."""

    def __init__(self, allowed: set[str]) -> None:
        self._allowed = allowed

    def get_field(self, field_name: str, args: Any, kwargs: Any) -> tuple[Any, str]:
        if field_name not in self._allowed:
            raise KeyError(field_name)
        return kwargs[field_name], field_name

    def convert_field(self, value: Any, conversion: str | None) -> Any:
        if conversion is not None:
            raise ValueError("Format conversions are not allowed in prompt templates")
        return value

    def format_field(self, value: Any, format_spec: str) -> str:
        if format_spec:
            raise ValueError(
                "Format specifications are not allowed in prompt templates"
            )
        return format(value, "")


def _render_prompt_template(template: str, values: dict[str, Any]) -> str:
    """Fill a prompt template. The template is data, never source."""
    try:
        return _PromptFormatter(set(values)).format(template, **values)
    except KeyError as exc:
        raise ValueError(f"Template references undefined argument: {exc}") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Error formatting template: {exc}") from exc


def _create_prompt_function(template: str, arguments: list[Any]) -> Callable:
    """
    Build a prompt callable that substitutes argument values into ``template``.

    The template is kept as a string. It is not interpolated into source and
    it is not passed to ``exec``.
    """
    if not isinstance(template, str):
        raise ValueError("Prompt template must be a string")
    if not arguments:
        return lambda: template

    arg_names = _extract_argument_names(arguments)

    def prompt_fn(*args: Any, **kwargs: Any) -> str:
        if args and kwargs:
            raise ValueError("Pass prompt arguments by name or by position")
        if args:
            if len(args) != len(arg_names):
                raise ValueError(
                    f"Expected {len(arg_names)} prompt arguments, got {len(args)}"
                )
            values = dict(zip(arg_names, args, strict=True))
        else:
            values = {name: kwargs[name] for name in arg_names}
        return _render_prompt_template(template, values)

    prompt_fn.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for name in arg_names
        ]
    )
    return prompt_fn


def _extract_argument_names(arguments: list[Any]) -> list[str]:
    """
    Extract argument names from argument config.
    """
    arg_names = []
    for arg in arguments:
        if isinstance(arg, dict):
            if "name" not in arg:
                raise ValueError("Argument name is required")
            name = arg["name"]
        elif isinstance(arg, str):
            name = arg
        else:
            raise ValueError(f"Invalid argument format: {arg}")
        if (
            not isinstance(name, str)
            or keyword.iskeyword(name)
            or not _PROMPT_ARG_NAME.fullmatch(name)
        ):
            raise ValueError(f"Invalid prompt argument name: {name}")
        if name in arg_names:
            raise ValueError(f"Duplicate prompt argument name: {name}")
        arg_names.append(name)
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
