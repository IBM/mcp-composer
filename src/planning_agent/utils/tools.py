import json 
import re
from random import randint

from planning_agent.core.state import State

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from mcp.types import Tool
from typing import Iterable
from textwrap import shorten

def clip(text: str, limit: int = 60) -> str: 
    return shorten(text.replace("\n", " "), width=limit, placeholder="...")

def randomToolSelection(entry: object) -> bool: 
    control_group_tools = {"mcp-instana_getApplications", "mcp-instana_getCallGroup", "mcp-instana_getTraceGroups", "mcp-instana_getTrace", 
                "mcp-instana_getTraces", "mcp-instana_getApplicationServices", "mcp-instana_getApplicationConfigs", 
                "mcp-instana_getCallDetails", "mcp-instana_getEndpointsMetrics", "mcp-instana_getServicesMetrics", 
                "mcp-instana_getApplicationTagCatalog", "mcp-instana_getApplicationEndpoints"}
    if entry["name"] in control_group_tools:
        return True
    random = randint(0, 100)
    if random < 8: 
        return True 
    return False

def update_tool_state(state: State, tools: Iterable[Tool]) -> None: 

    '''
    Convert tool list into a single string that can embed into the planner object
    '''
    tools_formatted = [
            {
                "name": t.name, 
                "description": t.description, 
                "args": t.inputSchema
            }
            for t in tools
        ]
    
    
    '''EXPERIMENT 1 TOGGLE BELOW'''
    #tools_formatted = list(filter(randomToolSelection, tools_formatted))
    
    state.tools = tools_formatted
    

    print(f"TOOL LENGTH: {len(tools_formatted)}")

    state.tool_schemas = {t.name: t.inputSchema for t in tools}

