import os
from pydantic import BaseModel, ValidationError
import json
from typing import Type

from beeai_framework.tools.tool import AnyTool
from mcp_composer_client.llm import run_llm
from packages.mcp_composer_client.src.mcp_composer_client.vector_store import build_index, query_tools
from dotenv import load_dotenv

load_dotenv()


async def select_tool_by_vector_search(
    user_input: str, tools_all: list[AnyTool]
) -> list[str]:
    # Select tools by asking an LLM what kinds of tools it needs and then vector searching the embeddings of the tool list
    prompt_llm_thoughts_for_vec_search_sys_msg = """
        You are a tool selection reasoning agent. You will be given a user query, 
        and then you will respond with an elaborate paragraph (~300-500 words)
        of how you would approach answering the query. 

        Mention: 
        1. what types of tools you would be looking to call to solve the query.
        2. what the end data/response might look like.
        3. intermediate steps/logic that might be required before getting to the final answer . 

        RULES: 
        1. In the 300-500 word range
        2. Formatted as one paragraph ONLY! 
        """
    prompt_llm_thoughts_for_vec_search_user_msg = "User Query: {user_input}"
    vec_search_prompt = await run_llm(
        user_input=prompt_llm_thoughts_for_vec_search_user_msg.format(
            user_input=user_input
        ),
        sys_input=prompt_llm_thoughts_for_vec_search_sys_msg,
    )

    # Create the tool vector store if it doesn't already exist
    VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_DATABASE")
    if not os.path.exists(VECTOR_STORE_PATH):
        build_index(tool_docs=tools_all, index_path=VECTOR_STORE_PATH)

    # Query the paragraph against the database
    hits = query_tools(paragraph=vec_search_prompt, k=10)
    selected_tool_names = [h["name"] for h in hits]
    return selected_tool_names


async def select_tool_by_LLM(user_input: str, tools_all: list[AnyTool]) -> list[str]:
    """Select tools by using all tools descriptions and call LLM to output what tools are relevant"""
    tools_descriptions = {t.name: t.description for t in tools_all}
    tool_description_str = "\n".join(
        [f"{k}: {v}\n" for k, v in tools_descriptions.items()]
    )

    # prompt
    prompt_filter_tools = """Based on the tools descriptions list and user query, select which tools are relevant to user query, list only relevant tools line by line without number, without any explanation, output in plain text format.
\nTool list: {tool_descriptions}\n\nUser query:\n {user_input}"""

    # call LLM
    result = await run_llm(
        user_input=prompt_filter_tools.format(
            tool_descriptions=tool_description_str, user_input=user_input
        )
    )

    # parse output from LLM, assuming each line for each tool
    selected_tool_names = [
        line for line in result.strip().split("\n") if " " not in line and len(line) > 0
    ]
    return selected_tool_names


def validate_beeai_tool_schema(tool_input_schema: Type[BaseModel]) -> bool:
    try:
        if not issubclass(tool_input_schema, BaseModel):
            print(
                "Schema Validation Error: Provided input_schema is not a Pydantic BaseModel subclass."
            )
            return False
        try:
            json_schema_dict = tool_input_schema.model_json_schema(mode="validation")
        except Exception as e:
            print(
                f"Schema Validation Error: Failed to generate JSON schema from {tool_input_schema.__name__}: {e}"
            )
            return False
        try:
            json_schema_string = json.dumps(json_schema_dict)
        except TypeError as e:
            print(
                f"Schema Validation Error: Generated JSON schema from {tool_input_schema.__name__} could not be serialized: {e}"
            )
            return False

        return True

    except Exception:
        return False


async def auto_filter_tools(
    user_input: str, tools_all: list[AnyTool], select_method: str = "llm"
) -> list[str]:
    """Get list of tools what are relevant to user input from LLM calling"""
    sel_tools: list[str] = []

    # select specific select_tool_xxx function based on "select_method"
    if select_method in ["auto", "llm"]:
        sel_tools = await select_tool_by_LLM(user_input=user_input, tools_all=tools_all)
    elif select_method in ["vec_search"]:
        sel_tools = await select_tool_by_vector_search(
            user_input=user_input, tools_all=tools_all
        )

    return sel_tools
