import argparse 
import asyncio 
from typing import Optional 
from contextlib import AsyncExitStack

from pydantic import BaseModel
from beeai_framework.workflows import Workflow
from utils.tools import update_tool_state
from utils.planmsg import build_plan_msg
from utils.filtermsg import build_filter_msg

from beeai_framework.tools.mcp import MCPTool 


from core.state import State
from utils.create_bee_agent import create_agent
from agent import planner, executor, revisor, validator, filtrator
from ab_tests.executing_without_plan import executor_control_group
from ab_tests.vec_search_filtering import filtrator as filtrator_vec_search
from utils.buildllm import build_llm

from mcp import ClientSession 
from mcp.client.streamable_http import streamablehttp_client
import os
from dotenv import load_dotenv
load_dotenv()

class MCPClient: 

    def __init__(self): 
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
    async def connect_to_streamable_http_server(
        self, server_url: str, headers: Optional[dict] = None
    ): 
        self._streams_context = streamablehttp_client(
            url = server_url, 
            headers = headers or {},
        )
        read_stream, write_stream, _ = await self._streams_context.__aenter__()

        self._session_context = ClientSession(read_stream, write_stream)
        self.session: ClientSession = await self._session_context.__aenter__()

        await self.session.initialize()

        
    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:  # pylint: disable=W0125
            await self._streams_context.__aexit__(None, None, None)

    async def call_tool(self, tool, args): 
        result = await self.session.call_tool(tool, args)
        return result
    
    async def list_mcp_tools(self): 
        response = await self.session.list_tools()
        return response

    async def list_bee_tools(self): 
        tools = await MCPTool.from_client(self.session)
        return tools 

async def build_workflow(client: MCPClient, bee_tools: [MCPTool]):
    llm = build_llm()

    async def init(state: State) -> str:
        response = await client.list_mcp_tools()
        tools = response.tools
        update_tool_state(state, tools)
 
        #Comment lines below out if using filterer
        '''
        state.filtered_tools = state.tools
        state.tool_names = set()
        for tool in state.filtered_tools: 
            state.tool_names.add(tool["name"])
        build_plan_msg(state)
        '''

        build_filter_msg(state)
        return "filter"
        #return "plan"

    flow = Workflow(State, name="MCP-Planner-Only")
    flow.add_step("init", init)
    #flow.add_step("filter", filtrator.make_filter_step(llm))
    flow.add_step("filter", filtrator_vec_search.make_filter_step(llm))
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



