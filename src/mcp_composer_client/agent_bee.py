import asyncio
import logging
import os
import re
import sys
import traceback
from dotenv import load_dotenv, find_dotenv
from collections.abc import AsyncGenerator
from beeai_framework.agents.react.agent import ReActAgent
from beeai_framework.agents.react.events import ReActAgentUpdateEvent
from beeai_framework.agents.types import AgentExecutionConfig
from beeai_framework.backend import Message, AssistantMessage, UserMessage, SystemMessage
from beeai_framework.errors import FrameworkError
from beeai_framework.logger import Logger
from beeai_framework.backend.message import UserMessage
from beeai_framework.memory.token_memory import TokenMemory
from beeai_framework.memory.unconstrained_memory import UnconstrainedMemory
from beeai_framework.tools.mcp  import MCPTool
from beeai_framework.tools.tool import AnyTool
from acp_sdk.server import Context
from mcp_composer_client.mcptools import Tools
from mcp_composer_client.llm import get_llm
from mcp_composer_client.tool_select import auto_filter_tools, validate_beeai_tool_schema


# Load environment variables
load_dotenv(find_dotenv(".env"))

# Configure logging - using DEBUG instead of trace
logger = Logger("app", level=logging.DEBUG)

prompt_system = """You are an AI Agent equipped with a set of tools. 
For user query, select and call the most relevant tools by providing accurate arguments based on the tool schemas. 
Return the result or answer to the user using the tool outputs, outputs in markdown format for readability, but remove ```markdown tag and don't use "#" for heading.
If the query cannot be fulfilled using available tools, clearly explain the limitation. 

NOTE: In special cases, if you can answer the user questions without calling tools because of the given context you can feel free to do so. 
"""

prompt_user = "User query: {}"

agent_tools = Tools()

def to_framework_message(role: str, content: str) -> Message:
    match role:
        case "user":
            return UserMessage(content)
        case role if role == "agent" or (role.startswith("agent/")):
            return AssistantMessage(content)
        case _:
            raise ValueError(f"Unsupported role {role}")


async def create_agent_from_tools(tools: list[AnyTool], messages: list[Message], llm_name: str | None = None) -> ReActAgent:
    """Create and configure the agent with tools and LLM"""

    llm_use = get_llm(llm_name)
    # Create agent with memory and tools
    agent = ReActAgent(llm=llm_use, tools=tools, memory=TokenMemory(llm_use))
    await agent.memory.add_many(messages)
    logger.info(f"Chat history messages count: {len(messages)}")
    # agent = ToolCallingAgent(llm=llm_use, tools=tools, memory=memory)
    return agent


async def run_agent_multimcp(
        user_input: str, 
        llm_name: str | None = None,         
        tool_select_method: str | None = None,
        streaming: bool = False,
        context: Context | None = None
    ) -> AsyncGenerator[str]:

    if len(agent_tools.tools) == 0:
        await agent_tools.create_mcp_tools()

    logger.info(f"Call Agent: \nuser-input={user_input}\nllm={llm_name}\nstream={streaming}\ntool_select_method={tool_select_method}")

    sel_tools = []
    if tool_select_method:        
        selected_tools = await auto_filter_tools(user_input, tools_all=agent_tools.tools, select_method=tool_select_method)
        print("auto-selected tools:\n", selected_tools)
        if selected_tools:
            for t in agent_tools.tools:
                if t.name in selected_tools and validate_beeai_tool_schema(t.input_schema):
                    sel_tools.append(t)
            logger.info(f"auto selected tools:  {len(sel_tools)}")


    # get historical messages from context
    if context is not None:
        logger.info(f"session id = {context.session.id}")
        history = [message async for message in context.session.load_history()]
        chat_messages: list[Message] = [to_framework_message(message.role, str(message)) for message in history]
    else:
        chat_messages: list[Message]  = [SystemMessage(content=prompt_system)]
    chat_messages.append(UserMessage(content=prompt_user.format(user_input)))
    # Create agent
    agent = await create_agent_from_tools(
        tools=agent_tools.tools if len(sel_tools)==0 else sel_tools, 
        messages=chat_messages,
        llm_name=llm_name
    )

    try:  
        if streaming:
            logger.info("calling agent in streaming ...")
            # Run agent with the prompt
            async for response in agent.run(
                prompt=prompt_system.format(user_input),
                execution=AgentExecutionConfig(max_retries_per_step=3, total_max_retries=6, max_iterations=10),
            ):
                for event in response:
                    if isinstance(event, ReActAgentUpdateEvent):
                        if event.update.key == "final_answer":
                            yield event.update.parsed_value
            
            logger.info("calling agent is finished.")
        else:
            logger.info("calling agent in sync ...")
            response = await agent.run(
                    prompt=prompt_system.format(user_input),
                    execution=AgentExecutionConfig(max_retries_per_step=3, total_max_retries=6, max_iterations=10),
                )
            yield response.result.text
    except:
        logger.info("error occurred.")
        traceback.print_exc()
        yield "(error orrcurred)"

    await agent_tools.clean_exits()


async def call_agent(prompt):
    if prompt.lower() in ['q', "q"]: 
        if len(agent_tools.tools) > 0:
            await agent_tools.clean_exits()

    text = ""
    async for message in run_agent_multimcp(user_input=prompt, tool_select_method = "vec_search"):
        text += message
    
    await agent_tools.clean_exits()
    
    return text


def test():
    try:
        prompt = "list the first ten services on instana?"
        response = asyncio.run(call_agent(prompt))
        print(response)

    except FrameworkError as e:
        traceback.print_exc()
        sys.exit(e.explain())


if __name__ == "__main__":
    test()