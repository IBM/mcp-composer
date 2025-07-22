from planning_agent.core.state import State
from typing import Dict

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

from planning_agent.ab_tests.constants import FilterApproaches


from planning_agent.utils.planmsg import build_plan_msg

import json

def make_filter_step(llm: ChatModel, option: int): 

    async def filter(state: State) -> str: 

        try: 

            tool_list_as_str = None

            if option == FilterApproaches.DESCRIPTIONS: 
                tool_list_as_str = state.tool_list_as_str()
            elif option == FilterApproaches.FULL_DESCRIPTIONS:
                tool_list_as_str = state.tool_list_as_str_full_desc()
            else: 
                tool_list_as_str = state.tool_list_as_str_full_info()
            print("hello")
            print(tool_list_as_str)
            messages = [
                        state.filter_msg, 
                        UserMessage(content=(
                            f"User Query: {state.task}\n"
                            f"Tool List: \n {tool_list_as_str}"
                        )), 
                    ]

            chat_input = ChatModelInput(
                    messages = messages, 
                    response_format = {"type": "json_object"}
                )

            response = await llm.create(messages = chat_input.messages, response_format= chat_input.response_format, temperature = 0.3, max_tokens = 1000)
            json_str = response.messages[0].content[0].text
            obj = json.loads(json_str)

            filtered_tools = set(obj["tools"])
            state.filter_tools(filtered_tools)        

            return Workflow.NEXT
        
        except Exception as e: 
            print(e)
            print("Error in Completing Filter Step")
            return Workflow.NEXT
        

    return filter 