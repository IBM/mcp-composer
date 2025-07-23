from beeai_framework.backend.chat import SystemMessage
from planning_agent.core.state import State


def build_filter_msg(state: State) : 

    
    plan_instructions = f"""
            You are a tool filtering agent that outputs a list of ONLY 3-10 tool names in JSON FORMAT.
            You will be provided a numbered tool list and a user query. Select the tool names that are MOST RELEVANT to answering the user query. 
            Consdier keeping tools that are important for intermediate logic (id retrieval, bool checks, etc.) \n

            RULES
            \n\n
            OUTPUT A JSON with a "tools" key and your list as the value\n
            THE LIST MUST HAVE AT LEAST THREE TOOL NAMES and NO MORE THAN TEN\n 
            Do not invent or rename tools. Use names only from the list provided\n
            Do not include any tool names more than once\n
            No reasoning, comments, descriptions, JUST THE TOOL NAMES\n\n
            """

    state.filter_msg = SystemMessage(
        content=(
            plan_instructions
        )
    )