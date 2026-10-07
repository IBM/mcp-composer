"""catalog — Thin MCP tools for skill and agent catalogs."""

from .agent_catalog_mcp import get_agent_mcp
from .skill_catalog_mcp import get_skill_mcp
from .workflow_catalog_mcp import get_workflow_mcp

__all__ = ["get_agent_mcp", "get_skill_mcp", "get_workflow_mcp"]
