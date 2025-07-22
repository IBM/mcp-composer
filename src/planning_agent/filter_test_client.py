import argparse 
import asyncio 

from beeai_framework.workflows import Workflow
from planning_agent.utils.tools import update_tool_state
from planning_agent.utils.planmsg import build_plan_msg
from planning_agent.utils.filtermsg import build_filter_msg

from planning_agent.core.state import State
from planning_agent.core.MCPClient import MCPClient
from beeai_framework.tools.mcp import MCPTool 


from planning_agent.utils.create_bee_agent import create_agent

from planning_agent.ab_tests.filter_tests import llm_only as filter_llm_only
from planning_agent.ab_tests.filter_tests import vec_search_only as filter_vec_search
from planning_agent.ab_tests.filter_tests import vec_search_and_llm as filter_vec_search_and_llm
from planning_agent.ab_tests.filter_tests import coarse_llm_fine_llm as filter_llm_coarse_to_fine
from planning_agent.ab_tests.filter_tests import llm_prompt_vec_search as filter_llm_reasoning_to_vec_search
from planning_agent.ab_tests.filter_tests import llm_vec_llm as filter_three_step

from planning_agent.ab_tests.filter_tests import write
from planning_agent.ab_tests.constants import Constants


from planning_agent.ab_tests.executing_without_plan import executor_control_group
from planning_agent.utils.buildllm import build_llm

from enum import Enum

import os
from dotenv import load_dotenv
load_dotenv()


async def build_workflow(client: MCPClient, bee_tools: [MCPTool], option: int):

    llm = None
    embedding_model = None

    if option in Constants.LLM_OPTIONS and Constants.LLM_OPTIONS[option] is not None: 
        llm = build_llm(Constants.LLM_OPTIONS[option])
    if option in Constants.EMBEDDING_OPTIONS: 
        embedding_model = Constants.EMBEDDING_OPTIONS[option]

    async def init(state: State) -> str:
        response = await client.list_mcp_tools()
        tools = response.tools
        update_tool_state(state, tools)

        build_filter_msg(state)

        return Workflow.NEXT


    flow = Workflow(State, name="MCP-Planner-Only")
    flow.add_step("init", init)

    approach = Constants.OptionFilterMap[option]

    match approach: 
        case 1 | 2 | 9: 
            flow.add_step("filter", filter_llm_only.make_filter_step(llm, approach))
        case 3 | 4 | 5 | 6: 
            flow.add_step("filter", filter_vec_search.make_filter_step(embedding_model, approach))
        case 7: 
            flow.add_step("filter", filter_vec_search_and_llm.make_filter_step(llm, embedding_model))
        case 8: 
            flow.add_step("filter", filter_llm_coarse_to_fine.make_filter_step(llm))
        case 10: 
            flow.add_step("filter", filter_llm_reasoning_to_vec_search.make_filter_step(llm, embedding_model))
        case 11: 
            flow.add_step("filter", filter_three_step.make_filter_step(llm, embedding_model))


    flow.add_step("write", write.make_write_step(option))

    return flow

async def main(task_input: str, option: int): 
    client = MCPClient()
    url = os.getenv('MCP_BASE_URL')
    
    try: 
        await client.connect_to_streamable_http_server(url)
        
        bee_tools = await client.list_bee_tools()
        init_state = State(task=task_input, mcp_base_url=url)
        flow = await build_workflow(client, bee_tools, option)
        response = await flow.run(init_state)
    finally: 
        await client.cleanup()

if __name__ == "__main__": 
    parser = argparse.ArgumentParser(
        description="Composer Client Agent"
    )
    parser.add_argument("all_args", nargs=argparse.REMAINDER, help="All remaining arguments as a list")
    args = parser.parse_args()
    option = int(args.all_args[0])
    user_prompt = " ".join(args.all_args[1:]) 

    asyncio.run(main(user_prompt, option))



