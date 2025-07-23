import json
from random import randint

from core.state import State

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from mcp.types import Tool
from typing import Iterable
from textwrap import shorten

def clip(text: str, limit: int = 60) -> str: 
    return shorten(text.replace("\n", " "), width=limit, placeholder="...")

def randomToolSelection(entry: object) -> bool: 
    if entry["name"] == "getCallGroup":
        return True
    random = randint(0, 100)
    if random < 1: 
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
    
    '''
    for t in tools_formatted: 
        if t["name"] == "getCallGroup": 
            print(t["description"])
            print(t["args"])
    '''
    
    '''EXPERIMENT 1 TOGGLE BELOW'''
    #tools_formatted = list(filter(randomToolSelection, tools_formatted))
    
    state.tools = tools_formatted
    

    print(f"TOOL LENGTH: {len(tools_formatted)}")

    state.tool_schemas = {t.name: t.inputSchema for t in tools}
    return json.dumps(state.tools, indent = 2)

