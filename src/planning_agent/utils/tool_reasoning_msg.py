from beeai_framework.backend.chat import SystemMessage
from planning_agent.core.state import State


def build_reasoning_message() -> SystemMessage: 
    plan_instructions = f"""
            You are a tool selection reasoning agent. You will be given a user query, 
            and then all you have to do is respond with an elaborate paragraph (~300-500 words)
            of how you would approach this problem and what types of tools you would be looking for 
            to solve the user query. 

            Mention: 
            1. what the end data/response might look like
            2. intermediate steps/logic that might be required before getting to the final answer  

            RULES: 
            1. In the 300-500 word range
            2. Formatted as one paragraph ONLY! 
            """

    toReturn = SystemMessage(
        content=(
            plan_instructions
        )
    )

    return toReturn 
