import pytest
from mcp_composer_client import agent_bee
from unittest.mock import patch, MagicMock


def test_to_framework_message_user():
    msg = agent_bee.to_framework_message("user", "hello")
    assert msg.content == "hello"
    assert msg.__class__.__name__ == "UserMessage"


def test_to_framework_message_agent():
    msg = agent_bee.to_framework_message("agent", "hi")
    assert msg.content == "hi"
    assert msg.__class__.__name__ == "AssistantMessage"


def test_to_framework_message_invalid():
    with pytest.raises(ValueError):
        agent_bee.to_framework_message("invalid", "fail")


@patch("mcp_composer_client.agent_bee.ReActAgent")
@patch("mcp_composer_client.agent_bee.get_llm")
def test_create_agent_from_tools(mock_get_llm, mock_ReActAgent):
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    mock_agent = MagicMock()
    mock_ReActAgent.return_value = mock_agent
    tools = [MagicMock()]
    messages = [MagicMock()]
    agent = pytest.run(agent_bee.create_agent_from_tools(tools, messages))
    assert agent is not None


# More advanced async tests for run_agent_multimcp can be added with pytest-asyncio
