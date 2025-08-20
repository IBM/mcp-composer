import pytest
from mcp_composer_client import llm
from unittest.mock import patch, MagicMock


def test_parse_llm_name_openai():
    provider, model = llm.parse_llm_name("openai(gpt-3.5)")
    assert provider == "openai"
    assert model.startswith("gpt-")


def test_parse_llm_name_none():
    provider, model = llm.parse_llm_name("")
    assert provider == ""
    assert model == ""


@patch("mcp_composer_client.llm.ChatModel")
def test_get_llm(mock_ChatModel):
    mock_ChatModel.from_name.return_value = MagicMock()
    result = llm.get_llm("openai(gpt-3.5)")
    assert result is not None
