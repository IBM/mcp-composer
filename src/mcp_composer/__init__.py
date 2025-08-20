# pylint: disable=W0718
from mcp_composer.core.composer import MCPComposer
from .core.utils import (
    LoggerFactory,
    ValidationError,
    AllServersValidator,
    ServerConfigValidator,
)
from .core.member_servers import MCPServerBuilder, ServerManager

__all__ = [
    "MCPComposer",
    "LoggerFactory",
    "ValidationError",
    "AllServersValidator",
    "ServerConfigValidator",
    "MCPServerBuilder",
    "ServerManager",
]

try:
    from importlib.metadata import version

    __version__ = version("mcp_composer")
except Exception:
    __version__ = "0.0.0-dev"
