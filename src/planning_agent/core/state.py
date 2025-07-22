import os
import re

from pydantic import BaseModel, Field
from typing import Any, Dict, Iterable
from mcp.types import Tool
from beeai_framework.backend.chat import SystemMessage
from planning_agent.utils.compact_schemalizer import compact_signature

from textwrap import shorten


def parseDescriptions(desc: str) -> str: 
    pattern = r'- \*\*Example:\*\*[\s]*```json(?:(?!```).)*```'
    cleaned_text = re.sub(pattern, '', desc, flags=re.DOTALL)
    return cleaned_text

def clip(text: str, limit: int = 500) -> str: 
        return shorten(text.replace("\n", " "), width=limit, placeholder="...")
class State(BaseModel, arbitrary_types_allowed=True):
    task: str
    plan: Dict[str, Any] | None = None 
    mcp_base_url: str = None

    tools: Iterable[Tool] | None = None
    filtered_tools: Iterable[Tool] | None = None
    tool_schemas: Dict | None = None
    tool_names: Iterable[str] | None = None

    user_feedback: str | None = None
    validation_error: str | None = None

    plan_msg: SystemMessage | None = None
    filter_msg: SystemMessage | None = None

    def filter_tools(self, subset: set[str]):
        self.tool_names = set()
        self.filtered_tools = []
        for tool in self.tools: 
            if(tool["name"] in subset): 
                print(tool["name"])
                self.tool_names.add(tool["name"])
                self.filtered_tools.append(tool)


    def tool_list_as_str_clipped(self, limit: int = 100) -> str: 
        signature_lines = []
        for i in range(len(self.tools)):
            t = self.tools[i]
            sig = f"{i+1}. {t["name"]} # {clip(t["description"], limit)}"
            signature_lines.append(sig)
        return "\n\n".join(signature_lines)
    
    def tool_list_as_str_full_desc(self) -> str: 
        signature_lines = []
        for i in range(len(self.tools)):
            t = self.tools[i]
            sig = f"{i+1}. {t["name"]}#{t["description"][:2000]}"
            signature_lines.append(sig)
        return "\n\n".join(signature_lines)

    def tool_list_as_str_full_info(self) -> str: 
        signature_lines = []
        for t in self.tools: 
            #sig = f"- {t["name"]}({compact_signature(t["args"])}) # {clip(t["description"], limit = limit)}"

            '''EXPERIMENT 1 TOGGLE ABOVE & BELOW'''
            sig = f"- {t["name"]}; \nDescription # {t["description"]} \n  Schema: {t["args"]});"
            signature_lines.append(sig)
        return "\n\n".join(signature_lines)

    def tool_list_as_str(self) -> str: 
        signature_lines = []
        for i in range(len(self.tools)):
            t = self.tools[i]
            sig = f"{i+1}. {t["name"]}#{parseDescriptions(t["description"])[:2000]}"
            signature_lines.append(sig)
        return "\n\n".join(signature_lines)

    def filtered_tool_list_as_str(self) -> str: 
        signature_lines = []
        for t in self.filtered_tools: 
            #sig = f"- {t["name"]}({compact_signature(t["args"])}) # {clip(t["description"], limit = limit)}"

            '''EXPERIMENT 1 TOGGLE ABOVE & BELOW'''
            sig = f"- {t["name"]}; \nDescription # {t["description"]} \n  Schema: {t["args"]});"
            signature_lines.append(sig)
        return "\n\n".join(signature_lines) 

    def filtered_tool_list_desc(self) -> str: 
        signature_lines = []
        for i in range(len(self.filtered_tools)):
            t = self.tools[i]
            sig = f"{i+1}. {t["name"]}#{t["description"][:2000]}"
            signature_lines.append(sig)
        return "\n\n".join(signature_lines)