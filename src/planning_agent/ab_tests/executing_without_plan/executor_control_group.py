import asyncio
import json
import os 

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from beeai_framework.workflows import Workflow
from beeai_framework.agents import AgentExecutionConfig
from beeai_framework.agents.react import ReActAgent
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.backend.chat import ChatModel
from beeai_framework.tools.mcp import MCPTool 
from beeai_framework.emitter import EventMeta

from ab_tests.executing_without_plan.bee_agent_without_plan import create_executor_control_agent
from core.state import State

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logging 


def make_execute_step(llm: ChatModel, bee_tools = list[MCPTool], n_back: int = 3, max_retries: int = 1): 
    async def execute(state: State): 

        agent, prompt = await create_executor_control_agent(state, bee_tools, llm)
        print(prompt)
        # Run agent with the prompt
        try: 
            response = await agent.run(
                prompt= prompt,
                execution=AgentExecutionConfig(max_retries_per_step=5, total_max_retries=50, max_iterations=50),
            ).on("*", print_events)
            print("Agent 🤖 : ", response.result.text)
        
        except Exception as e: 
            print(repr(e.get_cause()))
        
        return Workflow.END  

    return execute

#Set Logging
#logging.basicConfig(level = os.getenv('LOG_LEVEL', 'ERROR'))
#logger = logging.getLogger(__name__)

def print_events(data: any, event: EventMeta) -> None:
    """Print agent events"""
    if event.name in ["retry", "update", "success"]:
        print(f"\n** Event ({event.name}): {event.path} **\n{data}")


if __name__ == "__main__":
    asyncio.run(main())