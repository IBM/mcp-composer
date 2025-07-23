import argparse 
import asyncio 

from beeai_framework.workflows import Workflow
from planning_agent.utils.tools import update_tool_state
from planning_agent.utils.planmsg import build_plan_msg
from planning_agent.utils.filtermsg import build_filter_msg

from planning_agent.core.state import State
from planning_agent.core.MCPClient import MCPClient
from beeai_framework.tools.mcp import MCPTool 


from planning_agent.agent import planner, executor, revisor, validator, filtrator
from planning_agent.ab_tests.executing_without_plan import executor_control_group
from planning_agent.utils.buildllm import build_llm

import os
from dotenv import load_dotenv
load_dotenv()


async def build_workflow(client: MCPClient, bee_tools: [MCPTool]):
    llm = build_llm()

    async def init(state: State) -> str:
        response = await client.list_mcp_tools()
        tools = response.tools
        update_tool_state(state, tools)
        build_filter_msg(state)

        return Workflow.END
        #return "filter"
       

    flow = Workflow(State, name="MCP-Planner-Only")
    flow.add_step("init", init)
    flow.add_step("filter", filtrator.make_filter_step(llm))
    flow.add_step("plan", planner.make_plan_step(llm))
    flow.add_step("revision", revisor.make_revision_step(llm, validate_step_id="validate", cancel_step_id="cleanup"))
    flow.add_step("validate", validator.make_validate_step())
    flow.add_step("execute", executor.make_execute_step(llm, bee_tools))
    #flow.add_step("execute_two", executor_control_group.make_execute_step(llm, bee_tools))

    return flow

async def main(task_input: str): 
    client = MCPClient()
    
    apiToken = os.getenv('INSTANA_API_KEY')
    
    #headers={"Authorization": f"apiToken {apiToken}"}

    headers = {}

    url = os.getenv('MCP_BASE_URL')
    
    try: 
        await client.connect_to_streamable_http_server(url)
        
        bee_tools = await client.list_bee_tools()
        init_state = State(task=task_input, mcp_base_url=url)
        
        flow = await build_workflow(client, bee_tools)
        await flow.run(init_state)
    finally: 
        await client.cleanup()

if __name__ == "__main__": 
    parser = argparse.ArgumentParser(
        description="Plan-only MCP workflow powered by Watson x"
    )
    parser.add_argument(
        "prompt", 
        nargs="+", 
        help="What the agent should plan (enclose in quotes in needed)"
    )

    args = parser.parse_args()
    user_prompt = " ".join(args.prompt)

    asyncio.run(main(user_prompt))



