from beeai_framework.backend.chat import SystemMessage
from core.state import State


def build_filter_msg(state: State) : 

    
    plan_instructions = f"""
            You are a tool filtering agent that outputs a list of 1-3 tool names.
            You will be provided a tool list and a user query. Select the tool names that are MOST RELEVANT to answering the user query. 
            Keep tools that are important for intermediate logic (id retrieval, bool checks, etc.) \n

            RULES
            \n\n
            OUTPUT A JSON with a "tools" key and your list as the value\n
            THE LIST MUST HAVE AT LEAST ONE TOOL NAME and can have up to 3\n 
            Do not invent or rename tools. Use names only from the list provided\n
            No reasoning, comments, descriptions, JUST THE LIST OF NAMES\n\n
            """

    state.filter_msg = SystemMessage(
        content=(
            plan_instructions
        )
    )