from planning_agent.core.state import State
from typing import Dict


from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

from planning_agent.utils.planmsg import build_plan_msg
from planning_agent.utils.build_embedding_model import create_chroma, suggest_tools

import json

def make_filter_step(embedding_model: int, approach: int): 

    async def filter(state: State) -> str: 

        try: 
            client, col = create_chroma(state, embedding_model, approach)

            suggested_tools = suggest_tools(state.task, col)
            
            suggested_tools = set(map(lambda entry: entry[0], suggested_tools))

            state.filter_tools(suggested_tools)
        
            return Workflow.NEXT
        
        except Exception as e: 
            print(e)
            return Workflow.NEXT


    return filter 