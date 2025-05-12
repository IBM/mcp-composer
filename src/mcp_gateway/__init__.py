# src/mcp_gateway/__init__.py

# Re-export public API from core components
from .mcp_gateway import MCPGateway

# Optional: expose these directly if commonly used
from .member_servers.builder import MCPServerBuilder
from .member_servers.member_server import MemberMCPServer
from .member_servers.server_manager import ServerManager

