import asyncio
import logging
import os
import re
import sys
import traceback
from typing import Any
from dotenv import load_dotenv, find_dotenv
from collections.abc import AsyncGenerator
from beeai_framework.agents.react.agent import ReActAgent
from beeai_framework.agents.react.events import ReActAgentUpdateEvent
from beeai_framework.agents.tool_calling import ToolCallingAgent
from beeai_framework.agents.types import AgentExecutionConfig
from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.types import ChatModelParameters
from beeai_framework.emitter.emitter import Emitter, EventMeta
from beeai_framework.errors import FrameworkError
from beeai_framework.logger import Logger
from beeai_framework.backend.message import UserMessage
from beeai_framework.memory.token_memory import TokenMemory
from beeai_framework.memory.unconstrained_memory import UnconstrainedMemory
from beeai_framework.tools.mcp  import MCPTool
from beeai_framework.tools.tool import AnyTool
from mcp_composer_client.mcptools import Tools
import yaml


# Load environment variables
load_dotenv(find_dotenv(".env"))

# Configure logging - using DEBUG instead of trace
logger = Logger("app", level=logging.DEBUG)

prompt_system = """You are an AI Agent equipped with a set of tools. 
For user query, select and call the most relevant tools by providing accurate arguments based on the tool schemas. 
Return the result or answer to the user using the tool outputs, outputs in markdown format for readability, but remove ```markdown tag and don't use "#" for heading.
If the query cannot be fulfilled using available tools, clearly explain the limitation.
User query: {}"""

agent_tools = Tools()


llm = ChatModel.from_name(
    os.getenv('CHAT_MODEL_NAME', 'watsonx'), 
    ChatModelParameters(
        temperature=0.01, 
        max_tokens=1000
    )
)

# memory = TokenMemory(llm)
memory = UnconstrainedMemory()


def clear_memory():
    memory.reset()


def parse_llm_name(llm_name: str) -> tuple[str, str]:
	"""LLM name mapping to provider and chat model name"""
	if not llm_name:
		return "", ""
	
	pattern = r'(\w+)\(([^)]+)\)'
	matches = re.findall(pattern, llm_name)
	if len(matches)>=1:
		provider, chat_model = matches[0]
		provider = provider.lower()
		match provider:
			case "openai":
				chat_model = 'gpt-' + chat_model
				os.environ["OPENAI_CHAT_MODEL"] = chat_model
			case "watsonx":
				if "llama-4" in chat_model:
					chat_model = "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
				elif "llama-3" in chat_model:
					chat_model =  "meta-llama/llama-3-3-70b-instruct"
				elif "granite-3" in chat_model:
					chat_model =  "ibm/granite-3-3-8b-instruct"
				elif "mistral-large" in chat_model:
					chat_model =  "mistralai/mistral-large"
				elif "mistral-medium-2505" in chat_model:
					chat_model =  "mistralai/mistral-medium-2505"

				if chat_model != "":
					os.environ["WATSONX_CHAT_MODEL"] = chat_model
			case "ollama":        
				os.environ["OLLAMA_CHAT_MODE"] = chat_model

		print("select model:", provider, chat_model)
		return provider, chat_model
	else:
		return llm_name, ""


async def create_agent_from_tools(tools: list[AnyTool], llm_name: str | None = None) -> ReActAgent:
    """Create and configure the agent with tools and LLM"""
    llm_use = llm

    if llm_name:
        provider, chat_model = parse_llm_name(llm_name)
        if chat_model != "":
            llm_use = ChatModel.from_name(
                provider, ChatModelParameters(temperature=0.01, max_tokens=1000)
            )
        
    # Create agent with memory and tools
    agent = ReActAgent(llm=llm_use, tools=tools, memory=memory)
    # agent = ToolCallingAgent(llm=llm_use, tools=tools, memory=memory)
    return agent


async def auto_filter_tools(user_input: str) -> list[str]:
    """Get list of tools what are relevant to user input from LLM calling"""

    tools_all = agent_tools.tools
    tools_descriptions = {t.name:t.description for t in tools_all}
    
    tool_description_str = "\n".join([f"{k}: {v}\n" for k, v in tools_descriptions.items()])
    prompt_filter_tools = """Based on the tools descriptions list and user query, select which tools are relevant to user query, list only relevant tools line by line without number, without any explanation, output in plain text format.
\nTool list: {tool_descriptions}\n\nUser query:\n {user_input}"""
    
    result = await run_llm(user_input=prompt_filter_tools.format(tool_descriptions=tool_description_str,user_input=user_input))
    
    lines = result.strip().split("\n")

    return lines


async def run_agent_multimcp(
        user_input: str, 
        llm_name: str | None = None, 
        streaming: bool = False,
        auto_filter_tools: list[str] | None = None
    ) -> AsyncGenerator[str]:

    if len(agent_tools.tools) == 0:
        await agent_tools.create_mcp_tools()

    logger.info(f"Call Agent: \nuser-input={user_input}\nllm={llm_name}\nstream={streaming}\nfilter-tools={auto_filter_tools}")

    sel_tools = []

    if auto_filter_tools:
        for t in agent_tools.tools:
            if t.name in auto_filter_tools:
                sel_tools.append(t)
        logger.info(f"auto selected tools:  {len(sel_tools)}")

    # Create agent
    agent = await create_agent_from_tools(agent_tools.tools if len(sel_tools)==0 else sel_tools, llm_name)

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
            logger.info("calling agent ...")
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


async def run_llm(user_input: str) -> str:
    response = await llm.create(messages=[UserMessage(content=user_input)])
    return response.get_text_content()


async def call_agent(prompt):
    if prompt.lower() in ['q', "q"]: 
        if len(agent_tools.tools) > 0:
            await agent_tools.clean_exits()

    text = ""
    async for message in run_agent_multimcp(user_input=prompt):
        text += message
    
    await agent_tools.clean_exits()
    
    return text


def test():
    try:
        prompt = "what tools you have?"
        response = asyncio.run(call_agent(prompt))
        print(response)

    except FrameworkError as e:
        traceback.print_exc()
        sys.exit(e.explain())


if __name__ == "__main__":
    test()