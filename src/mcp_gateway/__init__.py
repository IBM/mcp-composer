from importlib.metadata import version

from mcp_gateway.gateway import MCPGateway
from mcp_gateway.member_servers import MCPServerBuilder
from mcp_gateway.member_servers import ServerManager

from mcp_gateway.utils import LoggerFactory



try:
    from importlib.metadata import version
    __version__ = version("mcp_gateway")
except Exception:
    __version__ = "0.0.0-dev"
