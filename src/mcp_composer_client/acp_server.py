import os
import asyncio
from collections.abc import AsyncGenerator
from acp_sdk import Message, MessagePart
from acp_sdk.models import Metadata, Annotations
from acp_sdk.models.platform import PlatformUIAnnotation, PlatformUIType
from acp_sdk.server import Context, Server
from dotenv import load_dotenv
from mcp_composer_client.agent_bee import run_agent_multimcp, auto_filter_tools


# Load environment variables
load_dotenv()

server = Server( )

@server.agent(
   metadata=Metadata(
        annotations=Annotations(
            beeai_ui=PlatformUIAnnotation(
                ui_type=PlatformUIType.CHAT,
                user_greeting="Input your query",
                display_name="MCP Composer Chatbot",
            )
        )
    )
)
async def mcp_composer_chatbot(inputs: list[Message], context: Context) -> AsyncGenerator:
    """AI agent that calls Platform APIs to fulfill a user query"""

    response = ""
    async for message in run_agent_multimcp(user_input=str(inputs[-1])):
        response += message

    yield MessagePart(content=response)


@server.agent(
   metadata=Metadata(
        annotations=Annotations(
            beeai_ui=PlatformUIAnnotation(
                ui_type=PlatformUIType.CHAT,
                user_greeting="Input your query",
                display_name="MCP Composer Chatbot with Auto-selecting Tools",
            )
        )
    )
)
async def mcp_composer_chatbot_sel_tools(inputs: list[Message], context: Context) -> AsyncGenerator:
    """AI agent that calls Platform APIs to fulfill a user query"""

    selected_tools = await auto_filter_tools(str(inputs[-1]))
    print("auto-selected tools:\n", selected_tools)

    response = ""
    async for message in run_agent_multimcp(user_input=str(inputs[-1]), auto_filter_tools=selected_tools):
        response += message

    yield MessagePart(content=response)


def run():
    server.run(host=os.getenv("HOST", "localhost"), port=int(os.getenv("PORT", 8000)), configure_telemetry=False)
    
if __name__ == "__main__":
    try:
        run()
    except:
        exit(0)