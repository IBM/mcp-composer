from beeai_framework.tools.tool import AnyTool
from mcp_composer_client.llm import run_llm



async def select_tool_by_LLM(user_input: str, tools_all: list[AnyTool]) -> list[str]:
    """Select tools by using all tools descriptions and call LLM to output what tools are relevant"""
    tools_descriptions = {t.name:t.description for t in tools_all}    
    tool_description_str = "\n".join([f"{k}: {v}\n" for k, v in tools_descriptions.items()])

    # prompt 
    prompt_filter_tools = """Based on the tools descriptions list and user query, select which tools are relevant to user query, list only relevant tools line by line without number, without any explanation, output in plain text format.
\nTool list: {tool_descriptions}\n\nUser query:\n {user_input}"""    

    # call LLM 
    result = await run_llm(user_input=prompt_filter_tools.format(tool_descriptions=tool_description_str,user_input=user_input))    

    # parse output from LLM, assuming each line for each tool
    selected_tool_names = [line for line in result.strip().split("\n") if " " not in line and len(line)>0]
    return selected_tool_names


async def auto_filter_tools(user_input: str, tools_all: list[AnyTool], select_method: str = "llm") -> list[str]:
    """Get list of tools what are relevant to user input from LLM calling"""
    sel_tools: list[str] = []

    # select specific select_tool_xxx function based on "select_method"
    if select_method in ["auto", "llm"]:
        sel_tools = await select_tool_by_LLM(user_input=user_input, tools_all=tools_all) 

    return sel_tools