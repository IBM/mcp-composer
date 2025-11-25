"""Unit tests for the A2A MCP bridge service."""

import uuid
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_composer.a2a_service.a2a_mcp import (
    _sanitize_agent_card_data,
    _create_client_factory,
    cancel_task,
    fetch_agent_card,
    get_task_result,
    list_agents,
    load_registered_agents,
    register_agent,
    send_message,
    unregister_agent,
)
from mcp_composer.a2a_service import a2a_mcp as module_under_test
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    TaskIdParams,
    Message,
    TaskQueryParams,
)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset in-memory stores before each test."""
    module_under_test.registered_agents.clear()
    module_under_test.task_agent_mapping.clear()

    # Stub persistence to avoid disk IO
    monkeypatch.setattr(module_under_test, "save_to_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(module_under_test, "load_from_json", lambda *args, **kwargs: {})


def build_agent_card(name: str = "Test Agent", url: str = "http://agent:10000") -> AgentCard:
    """Return agent card for testing."""
    return AgentCard(
        name=name,
        description="Test agent description",
        url=url,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="echo",
                name="Echo",
                description="Echo skill",
                tags=["test"],
                input_modes=["text"],
                output_modes=["text"],
            )
        ],
    )


class DummyA2AClient:
    """Mock A2A client for testing."""

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def send_message(self, _req):
        """Return async iterator for send_message."""

        async def gen() -> AsyncIterator[Any]:
            # Create a TaskStatus and Task using a2a.types
            send_params = {
                "role": "user",
                "parts": [{"type": "text", "text": "test message"}],
                "message_id": str(uuid.uuid4()),
                "task_id": "task-123",
            }
            task_event = Message(**send_params)
            yield task_event

        return gen()

    async def get_task(self, _req):
        # Return a Message with a task_id
        return TaskQueryParams(id="task-123")

    async def cancel_task(self, _req):
        return TaskIdParams(id="task-123")


class DummyFactory:
    """Mock client factory for testing."""

    def __init__(self, client: DummyA2AClient) -> None:
        self._client = client

    def create(self, _agent_card):
        return self._client


def test_sanitize_agent_card_data_defaults():
    """Ensure sanitizer fills defaults for missing/invalid agent card fields."""
    raw = {"name": "", "url": "", "capabilities": {}, "skills": []}
    card = _sanitize_agent_card_data(raw, "http://fallback")
    assert card.name == "Unknown Agent"
    assert card.url == "http://fallback"
    assert card.version == "0.1.0"
    assert card.capabilities.streaming is False
    assert len(card.skills) >= 1


def test_sanitize_agent_card_data_valid():
    """Ensure sanitizer preserves valid data."""
    raw = {
        "name": "Valid Agent",
        "url": "http://valid:8080",
        "version": "2.0.0",
        "description": "Valid description",
        "capabilities": {"streaming": True},
        "default_input_modes": ["text", "image"],
        "default_output_modes": ["text"],
        "skills": [
            {
                "id": "skill1",
                "name": "Skill One",
                "description": "First skill",
                "tags": ["tag1"],
                "input_modes": ["text"],
                "output_modes": ["text"],
            }
        ],
    }
    card = _sanitize_agent_card_data(raw, "http://fallback")
    assert card.name == "Valid Agent"
    assert card.url == "http://valid:8080"
    assert card.version == "2.0.0"
    assert card.capabilities.streaming is True
    assert len(card.skills) == 1
    assert card.skills[0].id == "skill1"


def test_create_client_factory():
    """Test client factory creation."""
    mock_httpx_client = MagicMock()
    factory = _create_client_factory(mock_httpx_client)
    assert factory is not None


@pytest.mark.asyncio
async def test_fetch_agent_card_success(monkeypatch):
    """Test successful agent card fetching."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Test Agent",
        "url": "http://test:8080",
        "version": "1.0.0",
        "description": "Test agent",
        "capabilities": {"streaming": True},
        "default_input_modes": ["text"],
        "default_output_modes": ["text"],
        "skills": [],
    }

    async def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    card = await fetch_agent_card("http://test:8080")
    assert card.name == "Test Agent"
    assert card.url == "http://test:8080"


@pytest.mark.asyncio
async def test_fetch_agent_card_well_known(monkeypatch):
    """Test agent card fetching from well-known location."""
    # Mock main endpoint failure
    mock_response_main = MagicMock()
    mock_response_main.status_code = 404

    # Mock well-known endpoint success
    mock_response_well_known = MagicMock()
    mock_response_well_known.status_code = 200
    mock_response_well_known.json.return_value = {
        "name": "Well Known Agent",
        "url": "http://wellknown:8080",
        "version": "1.0.0",
        "description": "Well known agent",
        "capabilities": {"streaming": False},
        "default_input_modes": ["text"],
        "default_output_modes": ["text"],
        "skills": [],
    }

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_response_main
        else:
            return mock_response_well_known

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    card = await fetch_agent_card("http://test:8080")
    assert card.name == "Well Known Agent"
    assert card.url == "http://wellknown:8080"


@pytest.mark.asyncio
async def test_fetch_agent_card_fallback(monkeypatch):
    """Test agent card fetching with fallback to default."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    async def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    card = await fetch_agent_card("http://test:8080")
    assert card.name == "Unknown Agent"
    assert card.url == "http://test:8080"


@pytest.mark.asyncio
async def test_register_agent_success(monkeypatch):
    """Test successful agent registration."""
    agent_url = "http://agent:10000"

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)

    result = await register_agent(agent_url, ctx=AsyncMock())
    assert result["status"] == "success"
    assert agent_url in module_under_test.registered_agents
    assert "agent" in result


@pytest.mark.asyncio
async def test_register_agent_failure(monkeypatch):
    """Test agent registration failure."""
    agent_url = "http://bad-agent"

    async def _raise(_):
        raise RuntimeError("boom")

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _raise)

    result = await register_agent(agent_url, ctx=AsyncMock())
    assert result["status"] == "error"
    assert "Failed to register agent" in result["message"]


@pytest.mark.asyncio
async def test_list_agents_returns_registered():
    """Test listing registered agents."""
    agent = build_agent_card()
    module_under_test.registered_agents[agent.url] = agent

    agents = await list_agents()
    assert isinstance(agents, list)
    assert len(agents) == 1
    assert agents[0]["url"] == agent.url


@pytest.mark.asyncio
async def test_unregister_agent_not_found():
    """Test unregistering non-existent agent."""
    result = await unregister_agent("http://missing")
    assert result["status"] == "error"
    assert "Agent not registered" in result["message"]


@pytest.mark.asyncio
async def test_unregister_agent_success(monkeypatch):
    """Test successful agent unregistration."""
    url = "http://agent:10000"
    agent = build_agent_card(url=url)
    module_under_test.registered_agents[url] = agent
    module_under_test.task_agent_mapping.update({"t1": url, "t2": "http://other"})

    saved: Dict[str, Any] = {}

    def _save(obj, path):
        saved[path] = obj

    monkeypatch.setattr(module_under_test, "save_to_json", _save)

    result = await unregister_agent(url)
    assert result["status"] == "success"
    assert url not in module_under_test.registered_agents
    assert "t1" not in module_under_test.task_agent_mapping
    assert result["removed_tasks"] == 1


@pytest.mark.asyncio
async def test_send_message_agent_not_registered():
    """Test sending message to unregistered agent."""
    res = await send_message("http://nope", "hi")
    assert res["status"] == "error"
    assert "Agent not registered" in res["message"]


@pytest.mark.asyncio
async def test_send_message_success(monkeypatch):
    """Test successful message sending."""
    url = "http://agent:10000"
    module_under_test.registered_agents[url] = build_agent_card(url=url)

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(DummyA2AClient()),
    )

    res = await send_message(url, "ping")
    assert res["status"] == "success"
    assert res["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_send_message_with_ctx(monkeypatch):
    """Test sending message with context."""
    url = "http://agent:10000"
    module_under_test.registered_agents[url] = build_agent_card(url=url)

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(DummyA2AClient()),
    )

    res = await send_message(url, "ping", ctx=AsyncMock())
    assert res["status"] == "success"
    assert res["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_send_message_error_handling(monkeypatch):
    """Test message sending error handling."""
    url = "http://agent:10000"
    module_under_test.registered_agents[url] = build_agent_card(url=url)

    class ErrorClient(DummyA2AClient):
        def send_message(self, _req):
            """Return async iterator that raises error."""

            async def gen() -> AsyncIterator[Any]:
                raise RuntimeError("client error")
                yield  # pragma: no cover

            return gen()

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(ErrorClient()),
    )

    res = await send_message(url, "ping")
    assert res["status"] == "error"
    assert "client error" in res["message"]


@pytest.mark.asyncio
async def test_get_task_result_task_missing():
    """Test getting result for unknown task."""
    res = await get_task_result("missing")
    assert res["status"] == "error"
    assert "Task ID not found" in res["message"]


@pytest.mark.asyncio
async def test_get_task_result_success(monkeypatch):
    """Test successful task result retrieval."""
    module_under_test.task_agent_mapping["task-123"] = "http://agent:10000"

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(DummyA2AClient()),
    )

    res = await get_task_result("task-123")
    assert res["status"] == "success"
    assert res["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_cancel_task_missing():
    """Test cancelling unknown task."""
    res = await cancel_task("missing")
    assert res["status"] == "error"
    assert "Task ID not found" in res["message"]


@pytest.mark.asyncio
async def test_cancel_task_success(monkeypatch):
    """Test successful task cancellation."""
    module_under_test.task_agent_mapping["task-123"] = "http://agent:10000"

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(DummyA2AClient()),
    )

    res = await cancel_task("task-123")
    assert res["status"] == "success"
    assert res["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_send_message_no_task_id(monkeypatch):
    """Test send_message when no task_id is returned."""
    url = "http://agent:10000"
    module_under_test.registered_agents[url] = build_agent_card(url=url)

    class NoTaskIdClient(DummyA2AClient):
        def send_message(self, _req):
            """Return async iterator with no task_id."""

            async def gen() -> AsyncIterator[Any]:
                # Mock a non-Task event (no task_id)
                non_task_event = SimpleNamespace(type="message", content="response without task")
                yield non_task_event

            return gen()

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(NoTaskIdClient()),
    )

    res = await send_message(url, "ping")
    assert res["status"] == "success"
    assert res["task_id"] is None


@pytest.mark.asyncio
async def test_send_message_with_different_agents(monkeypatch):
    """Test send_message with different registered agents."""
    url1 = "http://agent1:10000"
    url2 = "http://agent2:10000"
    module_under_test.registered_agents[url1] = build_agent_card(url=url1)
    module_under_test.registered_agents[url2] = build_agent_card(url=url2)

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(DummyA2AClient()),
    )

    # Test first agent
    res1 = await send_message(url1, "ping")
    assert res1["status"] == "success"
    assert res1["task_id"] == "task-123"

    # Test second agent
    res2 = await send_message(url2, "pong")
    assert res2["status"] == "success"
    assert res2["task_id"] == "task-123"


def test_load_registered_agents(monkeypatch):
    """Test loading registered agents from persistence."""
    saved_agents = {
        "http://agent:10000": build_agent_card(url="http://agent:10000").model_dump(),
    }
    saved_tasks = {"task-1": "http://agent:10000"}

    # First call returns agents, second call returns tasks
    calls: List[Dict[str, Any]] = [saved_agents, saved_tasks]

    def _load(_path):
        return calls.pop(0)

    monkeypatch.setattr(module_under_test, "load_from_json", _load)

    load_registered_agents()
    assert "http://agent:10000" in module_under_test.registered_agents
    assert module_under_test.task_agent_mapping == saved_tasks


def test_load_registered_agents_with_invalid_data(monkeypatch):
    """Test loading agents with invalid data falls back to sanitization."""
    saved_agents = {
        "http://agent:10000": {"invalid": "data"},
    }
    saved_tasks = {}

    calls: List[Dict[str, Any]] = [saved_agents, saved_tasks]

    def _load(_path):
        return calls.pop(0)

    monkeypatch.setattr(module_under_test, "load_from_json", _load)

    load_registered_agents()
    assert "http://agent:10000" in module_under_test.registered_agents
    # Should have sanitized the invalid data
    agent = module_under_test.registered_agents["http://agent:10000"]
    assert agent.name == "Unknown Agent"
