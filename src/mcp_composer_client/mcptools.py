import os
import logging
import yaml
from typing import Any, Literal
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
from contextlib import AsyncExitStack
from beeai_framework.tools.mcp import MCPTool
from beeai_framework.tools.tool import AnyTool
from beeai_framework.logger import Logger


# Configure logging - using DEBUG instead of trace
logger = Logger("app", level=logging.DEBUG)


# Base Config model for all types of MCP server
class MCPBaseConfig(BaseModel):
    description: str
    enabled: bool = True
    filters: list[str] | None
    excludes: list[str] | None


# Config for remote server (SSE, Streamable_HTTP)
class MCPRemoteConfig(MCPBaseConfig):
    mcp_composer_url: str
    type: Literal["sse", "streamable_http"]


# Config for Stdio server
class MCPSTDIOConfig(MCPBaseConfig):
    description: str
    command: str
    args: list[str]
    env: dict[str, str] | None


# Config for OAS-to-MCP server
class MCPOASConfig(MCPBaseConfig):
    base_url: str
    auth_header: str
    token_env: str
    spec_path: str
    tags: list[str] | None


# Config containing all, structure of config/mcp_composer_client.yaml
class MCPServersConfig(BaseModel):
    remote_servers: dict[str, MCPRemoteConfig]
    stdio_servers: dict[str, MCPSTDIOConfig] | None
    oas_servers: dict[str, MCPOASConfig] | None


def remove_disenabled_mcp_servers(config: dict[str, Any]):
    """Remove mcp servers with 'enabled' as false"""
    disenabled: list[str] = [k for k, v in config.items() if not v.enabled]
    logger.info(f"Disenabled MCP: {disenabled}")
    for name in disenabled:
        config.pop(name)


class Tools:
    def __init__(self, config_path: str = "config/mcp_composer_client.yaml"):
        self._config: dict[str, Any] = {}
        USER_CONFIG_FILE = os.getenv("USER_CONFIG_FILE", "no")

        # read config file if env USER_CONFIG_FILE is missing or False
        logger.info(f"USER_CONFIG_FILE={USER_CONFIG_FILE}")
        if USER_CONFIG_FILE == "yes":
            logger.info(f"Load tools from config file '{config_path}'.")
            try:
                with open(config_path, "r") as file:
                    config_dict = yaml.safe_load(file)
                # Parse and validate the configuration using Pydantic
                configs: MCPServersConfig = MCPServersConfig.model_validate(config_dict)

                if configs.remote_servers:
                    self._config.update(configs.remote_servers)
                if configs.stdio_servers is not None:
                    self._config.update(configs.stdio_servers)
                if configs.oas_servers is not None:
                    self._config.update(configs.oas_servers)
            except FileNotFoundError:
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in configuration file: {e}")
            except Exception as e:
                raise ValueError(f"Error parsing configuration: {e}")
        else:
            base_url = str(os.getenv("MCP_BASE_URL"))
            logger.info(f"Load tools from MCP Compsoser Base URL '{base_url}'.")
            self._config["MCP_composer"] = MCPRemoteConfig(
                description="MCP Composer",
                enabled=True,
                mcp_composer_url=base_url,
                type="streamable_http",
                filters=None,
                excludes=None,
            )

        remove_disenabled_mcp_servers(self._config)

        self._products: list[str] = list(self._config.keys())
        logger.info(f"Enabled MCP: {self._products}")

        # async context exits for MCP sessions
        self._list_exits: list[AsyncExitStack] = []
        self._client_sessions: list[Any] = []
        self._tools: list[AnyTool] = []
        self._tools_details: dict[str, dict[str, str]] = {}

    def init_cmp_mcp(self, cfg: MCPRemoteConfig) -> str:
        return cfg.mcp_composer_url

    def init_std_mcp(self, cfg: MCPSTDIOConfig) -> StdioServerParameters:
        return StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env)

    def init_oas_mcp(self, cfg: MCPOASConfig) -> StdioServerParameters:
        args = ["@ivotoby/openapi-mcp-server", "--disable-abbreviation", "true"]

        env = {
            "API_BASE_URL": cfg.base_url,
            "OPENAPI_SPEC_PATH": cfg.spec_path,
            "API_HEADERS": cfg.auth_header.format(os.getenv(cfg.token_env)),
            # "API_HEADERS": cfg.auth_header.format(os.getenv(cfg.token_env))+","+"InstanceId:"+os.getenv("CONCERT_INSTANCE_ID")
        }

        # if product == "Concert":
        #       args.append("--headers")
        #       args.append("InstanceId: "+os.getenv("CONCERT_INSTANCE_ID"))

        if cfg.tags:
            for tag in cfg.tags:
                args.append("--tag")
                args.append(tag)

        # Create server parameters for stdio connection
        server_params = StdioServerParameters(command="npx", args=args, env=env)

        return server_params

    async def create_mcp_tools(self, close_context: bool = False) -> None:
        if len(self.tools) > 0:
            await self.clean_exits()

        tool_count = {}

        products = []

        for product, cfg in self._config.items():
            products.append(product)

            # create async context mgr
            exit_stack = AsyncExitStack()
            self._list_exits.append(exit_stack)

            logger.info(f"Loading tools from MCP server '{product}' ... ")
            # create transport based on each MCP server config's type
            if isinstance(cfg, MCPRemoteConfig):
                server_params = self.init_cmp_mcp(cfg)
                if cfg.type == "streamable_http":
                    transport = await exit_stack.enter_async_context(
                        streamablehttp_client(url=server_params)
                    )
                elif cfg.type == "sse":
                    transport = await exit_stack.enter_async_context(
                        sse_client(url=server_params)
                    )
                else:
                    transport = None
                    continue
            else:
                if isinstance(cfg, MCPOASConfig):
                    server_params = self.init_oas_mcp(cfg)
                elif isinstance(cfg, MCPSTDIOConfig):
                    server_params = self.init_std_mcp(cfg)
                else:
                    raise ValueError
                transport = await exit_stack.enter_async_context(
                    stdio_client(server=server_params)
                )

            # create MCP client session
            session = await exit_stack.enter_async_context(
                ClientSession(transport[0], transport[1])
            )
            await session.initialize()
            self._client_sessions.append(session)

            # get tools from MCP server
            mcp_tools = await MCPTool.from_client(session)

            # filtering tools based on config
            logger.info(
                f"filter [{product}] tools: original tools = {len(mcp_tools)}, filters={cfg.filters}, excludes={cfg.excludes}"
            )
            filtered_tools = self.filter_oas_tools(mcp_tools, cfg.filters, cfg.excludes)
            logger.info(f"filtered tools = {len(filtered_tools)}")
            self._tools += filtered_tools
            tool_count[product] = len(filtered_tools)
            # fill tools details (description, schema)
            self._tools_details[product] = {}
            for t in filtered_tools:
                tool_schema = ""
                try:
                    tool_schema = ""
                    for k, v in t.input_schema().model_fields.items():
                        tool_schema += f"- {k}: {str(v)}\n\n"
                except:
                    # print(f"error in reading schema of tool '{t.name}'")
                    pass

                self._tools_details[product][t.name] = (
                    t.description + "\n\n**Schema**\n\n" + tool_schema
                )

        for product in products:
            logger.info(f"Product[{product}] \tenabeld tools: {tool_count[product]}")
        logger.info(f"Products[All] \t\tenabled tools:  {len(self._tools)}")

        if close_context:
            await self.clean_exits()

        return

    @property
    def tools(self) -> list[AnyTool]:
        return self._tools

    @property
    def products(self) -> list[str]:
        return self._products

    async def clean_exits(self) -> None:
        for exit_stack, client_session in zip(self._list_exits, self._client_sessions):
            try:
                await exit_stack.aclose()
                await client_session.aclose()
            finally:
                continue

        self._list_exits.clear()
        self._client_sessions.clear()
        self._tools.clear()

    def get_product_tools_desc(self, product: str) -> dict[str, str]:
        """Get tools descriptions"""
        return self._tools_details[product]

    def get_product_tags(self, product: str) -> list[str] | None:
        """Get tags of product from config"""
        if isinstance(self._config[product], MCPOASConfig):
            return self._config[product].tags
        else:
            return None

    def filter_oas_tools(
        self,
        tools: list[MCPTool],
        filters: list[str] | None = None,
        excludes: list[str] | None = None,
    ) -> list[MCPTool]:
        """Filter OAS tools based on filters, excludes"""
        if filters:
            if len(filters) > 0:
                tools = list(filter(lambda tool: tool.name in filters, tools))

        if excludes:
            exclude_list = []
            if len(excludes) > 0:
                for ex in excludes:
                    for t in tools:
                        if ex.lower() in t.name.lower():
                            exclude_list.append(t.name)

            if len(exclude_list) > 0:
                tools = list(filter(lambda tool: tool.name not in exclude_list, tools))
        return tools
