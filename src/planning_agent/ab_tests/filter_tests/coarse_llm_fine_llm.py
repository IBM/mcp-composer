from core.state import State
from typing import Dict

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

from planning_agent.utils.planmsg import build_plan_msg

import json

def make_filter_step(llm: ChatModel): 

    async def filter(state: State) -> str: 
        
        tool_list_as_str = None
        tool_list_as_str = state.tool_list_as_str_clipped()
        

        coarse_msg = f"""
            You are a coarse tool filtering agent that outputs a list of 5-25 tool names from a larger list.
            You will be provided the tool list and a user query. Select tools (provide the name) that are relevant to the user query. 
            INCLUDE any tool that is LOOSELY RELATED to the user query to the list. 
            Also CONSIDER tools that are important for intermediate logic (id retrieval, bool checks, etc.) \n

            RULES
            \n\n
            OUTPUT A JSON with a "tools" key and your list as the value. The list should just have tool names.\n
            THE LIST MUST HAVE AT LEAST FIVE TOOL NAMES.\n 
            Do not invent or rename tools. Use names only from the list provided \n
            Remember that tools only need to loosely to the user query \n
            No reasoning, comments, descriptions, JUST THE LIST OF NAMES\n\n
            """

        try: 
            messages = [
                        SystemMessage(content = coarse_msg), 
                        UserMessage(content=(
                            f"User Query: {state.task}\n"
                            f"Tool List: \n {tool_list_as_str}"
                        )), 
                    ]

            chat_input = ChatModelInput(
                    messages = messages, 
                    response_format = {"type": "json_object"}
                )
            response = await llm.create(messages = chat_input.messages, response_format= chat_input.response_format, temperature = 0.1)
            print(response)
        
            json_str = response.messages[0].content[0].text
            obj = json.loads(json_str)

            filtered_tools = set(obj["tools"])
            state.filter_tools(filtered_tools)


            tool_list_as_str = state.filtered_tool_list_desc()
            fine_msg = state.filter_msg

            messages = [
                        fine_msg, 
                        UserMessage(content=(
                            f"User Query: {state.task}\n"
                            f"Tool List: \n {tool_list_as_str}"
                        )), 
                    ]

            chat_input = ChatModelInput(
                    messages = messages, 
                    response_format = {"type": "json_object"}
                )

            response = await llm.create(messages = chat_input.messages, response_format= chat_input.response_format, temperature = 0.3, top_p = 1.0)

        
            json_str = response.messages[0].content[0].text
            obj = json.loads(json_str)

            filtered_tools = set(obj["tools"])
            state.filter_tools(filtered_tools)

            return Workflow.NEXT

        except Exception as e: 
            print(e.__cause__)
            return Workflow.NEXT

        
    return filter 