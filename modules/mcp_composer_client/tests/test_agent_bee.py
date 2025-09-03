import pytest
from mcp_composer_client import agent_bee
from unittest.mock import patch, MagicMock, AsyncMock
from beeai_framework.backend import Message
from beeai_framework.tools.tool import AnyTool


def test_to_framework_message_user():
    msg = agent_bee.to_framework_message("user", "hello")
    # The content is a list of MessageTextContent objects, so we need to access the text property
    assert msg.content[0].text == "hello"
    assert msg.__class__.__name__ == "UserMessage"


def test_to_framework_message_agent():
    msg = agent_bee.to_framework_message("agent", "hi")
    # The content is a list of MessageTextContent objects, so we need to access the text property
    assert msg.content[0].text == "hi"
    assert msg.__class__.__name__ == "AssistantMessage"


def test_to_framework_message_invalid():
    with pytest.raises(ValueError):
        agent_bee.to_framework_message("invalid", "fail")


@patch("mcp_composer_client.agent_bee.TokenMemory")
@patch("mcp_composer_client.agent_bee.ReActAgent")
@patch("mcp_composer_client.agent_bee.get_llm")
@pytest.mark.asyncio
async def test_create_agent_from_tools(mock_get_llm, mock_ReActAgent, mock_TokenMemory):
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    
    # Mock the memory
    mock_memory = MagicMock()
    mock_memory.add_many = AsyncMock()
    mock_TokenMemory.return_value = mock_memory
    
    mock_agent = MagicMock()
    mock_agent.memory = mock_memory
    mock_ReActAgent.return_value = mock_agent
    
    # Create properly typed mock objects
    tools: list[AnyTool] = [MagicMock(spec=AnyTool)]
    messages: list[Message] = [MagicMock(spec=Message)]
    
    # Properly await the async function
    agent = await agent_bee.create_agent_from_tools(tools, messages)
    assert agent is not None


# More advanced async tests for run_agent_multimcp can be added with pytest-asyncio
