from beeai_framework.backend.chat import ChatModel
from beeai_framework.agents.react.agent import ReActAgent
from beeai_framework.agents.tool_calling import ToolCallingAgent

from planning_agent.core.state import State 

import json
from beeai_framework.tools.mcp  import MCPTool
from beeai_framework.memory.unconstrained_memory import UnconstrainedMemory

def get_system_prompt(state: State): 
        sys_prompt = f"""
                You are a tool calling agent. Answer the user query with your provided tools. 
                You are also provided an action plan that is a suggested way to solve the user query. 
                You should refer to this plan, as it is likely a decent starting point, but make adjustments as needed!  
                If the plan's suggested tool calls cause errors or returns unexpected/blank results, 
                use your reasoning capabilities TO MAKE ADJUSTMENTS, calling the same tools with different params, or other tools 
                if necessesary.\n\n 
                
                TIP: To make tool-calling adjustments, refer to the examples and explanations IN THE TOOL DESCRIPTIONS of the tool list below. 


                Here is the list of your tools:\n\n
                {state.filtered_tool_list_as_str()}

                """ 
        return sys_prompt
def get_prompt(state: State): 
        return f"User Query: {state.task}.\nSuggested Action Plan: {state.plan}"
  
async def create_agent(state: State, tools: list[MCPTool], llm: ChatModel) -> ReActAgent:
    """Create and configure the agent with tools and LLM"""
    sys = get_system_prompt(state)
    prompt = get_prompt(state) 
    # Create agent with memory and tools
    templates: dict[str, Any] = {
        "system": lambda template: template.update(
            defaults={"instructions": f"{sys}"}
        ),
    } 
    tools = list(filter(lambda tool: tool.name in state.tool_names, tools))
    print(f"LENGTH OF TOOLS: {len(tools)}")
    agent = ReActAgent(llm=llm, templates = templates, tools=tools, memory=UnconstrainedMemory())
    #agent = ToolCallingAgent(llm=llm, templates = templates, tools=tools, memory=UnconstrainedMemory())
    return agent, prompt
