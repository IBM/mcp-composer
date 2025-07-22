from planning_agent.core.state import State
from typing import Dict

from planning_agent.utils.build_embedding_model import create_chroma, suggest_tools

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

from planning_agent.utils.planmsg import build_plan_msg

import json

def make_filter_step(llm: ChatModel, embedding_model: int): 
    async def filter_step(state: State) -> str: 

        try: 
            
            client, col = create_chroma(state, embedding_model)
        
            suggested_tools = suggest_tools(state.task, col, n_results = 50)
            
            suggested_tools = set(map(lambda entry: entry[0], suggested_tools))

            shortened_tool_list = list(filter(lambda e: e["name"] in suggested_tools, state.tools))
            state.tools = shortened_tool_list

            tool_list_as_str = state.tool_list_as_str_full_desc()

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


            return Workflow.NEXT
    
        except Exception as e: 
                print(e)
                return Workflow.NEXT
        

    return filter_step 