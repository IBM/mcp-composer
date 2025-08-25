"""
MCP Composer Client module.

This module provides client-side functionality for MCP Composer including:
- Agent implementations (BeeAI framework integration)
- MCP tool management and selection
- LLM integration
- Vector store operations
- ACP server functionality
"""

from .agent_bee import (
    create_agent_from_tools,
    run_agent_multimcp,
    to_framework_message,
)
from .mcptools import Tools, MCPBaseConfig, MCPRemoteConfig, MCPSTDIOConfig, MCPOASConfig, MCPServersConfig
from .llm import get_llm
from .tool_select import auto_filter_tools, validate_beeai_tool_schema
from .vector_store import VectorStore
from .acp_server import ACPServer

__all__ = [
    # Agent functions
    "create_agent_from_tools",
    "run_agent_multimcp", 
    "to_framework_message",
    
    # Tool management
    "Tools",
    "MCPBaseConfig",
    "MCPRemoteConfig",
    "MCPSTDIOConfig", 
    "MCPOASConfig",
    "MCPServersConfig",
    
    # LLM and tool selection
    "get_llm",
    "auto_filter_tools",
    "validate_beeai_tool_schema",
    
    # Storage and server
    "VectorStore",
    "ACPServer",
]
