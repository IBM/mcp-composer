# graphql_tool.py

import ast
from typing import Dict, Any

import requests
from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import PrivateAttr
from starlette.exceptions import HTTPException

from mcp_composer.core.utils import ConfigKey, LoggerFactory, AuthStrategy


logger = LoggerFactory.get_logger()


class GraphQLTool(Tool):
    _endpoint: str = PrivateAttr()
    _headers: Dict[str, str] = PrivateAttr(default_factory=dict)

    def __init__(self, config: dict):
        self._endpoint = config[ConfigKey.GRAPHQL][ConfigKey.ENDPOINT]
        self._headers = {}

        auth_strategy = config.get(ConfigKey.AUTH_STRATEGY, "none")
        auth = config.get(ConfigKey.AUTH, {})

        if auth_strategy == AuthStrategy.BEARER:
            self._headers = {
                "Authorization": f"{auth.get(ConfigKey.AUTH_PREFIX, '')} {auth.get(ConfigKey.TOKEN, '')}"
            }
        elif ConfigKey.HEADERS in config.get(ConfigKey.AUTH, ""):
            self._headers = {
                auth.get(ConfigKey.AUTH_PREFIX, ""): auth.get(ConfigKey.TOKEN, "")
            }

        parameters = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GraphQL query string"},
                "variables": {
                    "type": "object",
                    "description": "Optional GraphQL variables",
                },
            },
            "required": ["query"],
        }

        super().__init__(
            name=config["id"],
            description=f"GraphQL query tool for {self._endpoint}",
            parameters=parameters,
        )
        # Set non-model fields
        self._endpoint = config[ConfigKey.GRAPHQL][ConfigKey.ENDPOINT]
        auth_strategy = config.get(ConfigKey.AUTH_STRATEGY, "none")
        auth = config.get(ConfigKey.AUTH, {})

        if auth_strategy == "bearer":
            self._headers = {
                "Authorization": f"{auth.get(ConfigKey.AUTH_PREFIX, '')} {auth.get(ConfigKey.TOKEN, '')}"
            }
        elif auth_strategy == "header":
            self._headers = {
                auth.get(ConfigKey.AUTH_PREFIX, ""): auth.get(ConfigKey.TOKEN, "")
            }

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        raw_query = arguments["query"]

        # 🔧 Unescape if it came in escaped (Claude-style)
        if isinstance(raw_query, str) and '\\"' in raw_query:
            try:
                raw_query = ast.literal_eval(f'"{raw_query}"')
            except (ValueError, SyntaxError):
                pass  # fallback — let the request fail if invalid

        variables = arguments.get("variables", {})

        payload = {"query": raw_query, "variables": variables}
        logger.info("Payload: %s", payload)
        logger.info("Endpoint: %s", self._endpoint)
        try:
            response = requests.post(
                self._endpoint, json=payload, headers=self._headers, timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return ToolResult(content=[TextContent(type="text", text=str(result))])
        except HTTPException as e:
            logger.error("error  %s", e)
            raise
