from planning_agent.core.state import State
from typing import Dict

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

from planning_agent.utils.planmsg import build_plan_msg

import json

def make_filter_step(llm: ChatModel): 

    async def filter(state: State) -> str: 


        tool_list_as_str = state.tool_list_as_str()

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

        response = await llm.create(messages = chat_input.messages, response_format= chat_input.response_format, temperature = 0.3, top_p = 1.0)

       
        json_str = response.messages[0].content[0].text
        obj = json.loads(json_str)

        filtered_tools = set(obj["tools"])
        state.filter_tools(filtered_tools)
        build_plan_msg(state)

        return Workflow.NEXT
        

    return filter 