from planning_agent.core.state import State
from beeai_framework.tools.mcp import MCPTool 
from beeai_framework.agents.react import ReActAgent
from beeai_framework.backend.chat import ChatModel

async def create_executor_control_agent(state: State, tools: list[MCPTool], llm: ChatModel) -> ReActAgent: 
    sys = f"""
                You are a tool calling agent. Answer the user query with your provided tools.\n_back

                Here is the full list of your tools:\n\n
                {state.filtered_tool_list_as_str()}
        """ 
    prompt = f"User Query: {state.task}"
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