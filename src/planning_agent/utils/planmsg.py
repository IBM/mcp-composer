from beeai_framework.backend.chat import SystemMessage
from planning_agent.core.state import State


def build_plan_msg(state: State) : 
    '''Return ONE SYSTEM MESSAGE that lists the tools + LLM_LOGIC RULE'''

    tool_list_as_str = state.filtered_tool_list_as_str()
    schema_str = "{\"steps\": [{\"tool\": \"...\", \"description\": \"...\" , \"args\": {...}}]}"
    
    plan_instructions = f"""
            You are a planning agent that makes PRECISE TOOL-CALLING PLANS to answer user queries.
            Your main goal is accuracy in terms of tool choice and paramater suggestions. 
            You will use the provided tools (below) to make this plan.\n\n
            
            The plan you make will be in JSON format
            ADHERE TO THE FOLLOWING OUTPUT JSON SCHEMA: {schema_str}\n\n

            TIPS\n
            USE DESCRIPTIONS to decide which tools to call and help decide on some of the parameters.\n
            Pay particular attention to EXPECTED units, values, enums, and types in the DESCRIPTIONS OF THE SCHEMA\n
            PAY ATTENTION TO DEPRECATED SCHEMA FIELDS explained in the Description \n
            LOOK AT DESCRIPTION FOR EXAMPLES \n
            The SCHEMA will help explain required fields and descriptions of more confusing ones\n\n

            RULES
            \n
            The plan should only be in granularity of tool calling.
            Use the output schema above\n
            Do not invent or rename tools. Each TOOL NAME SHOULD MATCH an exact entry in the list below\n
            Do not include intermediate logic like \"parse\", \"loop\", \"decide\", or \"store result\"\n"

            Tool List:\n
            {tool_list_as_str}
            """

    print(f"LENGTH OF PLANNING PROMPT: {len(plan_instructions)}")

    state.plan_msg = SystemMessage(
        content=(
            plan_instructions
        )
    )
