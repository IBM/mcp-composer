from mcp_composer.composer import MCPComposer
from .utils import (
    LoggerFactory,
    ValidationError,
    AllServersValidator,
    ServerConfigValidator,
)
from .member_servers import MCPServerBuilder, ServerManager


try:
    from importlib.metadata import version

    __version__ = version("mcp_composer")
except Exception:
    __version__ = "0.0.0-dev"
