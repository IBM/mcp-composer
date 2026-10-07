"""Unit tests for the A2A MCP bridge service."""

import uuid
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_composer.a2a_service.a2a_mcp import (
    _sanitize_agent_card_data,
    _create_client_factory,
    build_agent_card_embeddings,
    cancel_task,
    fetch_agent_card,
    find_agent,
    get_embedding_adapter,
    get_task_result,
    invalidate_embeddings_cache,
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

    # Reset embeddings cache
    module_under_test._embeddings_cache = None
    module_under_test._embeddings_cache_timestamp = None

    # Reset embedding adapter
    module_under_test._embedding_adapter = None

    # Stub persistence to avoid disk IO
    monkeypatch.setattr(module_under_test, "save_to_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(module_under_test, "load_from_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        module_under_test,
        "get_auth_context",
        lambda: {
            "authenticated": True,
            "token": "test-token",
            "auth_token": None,
        },
    )


def build_agent_card(
    name: str = "Test Agent", url: str = "http://agent:10000"
) -> AgentCard:
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
            task_event = Message(**send_params)  # type: ignore[arg-type]
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
async def test_list_agents_not_blocked_by_auth_context(monkeypatch):
    """Non-runtime A2A tools should remain unaffected by runtime auth checks."""
    monkeypatch.setattr(module_under_test, "get_auth_context", lambda: None)
    agents = await list_agents()
    assert isinstance(agents, list)


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

    saved: dict[str, Any] = {}

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
async def test_send_message_allows_missing_auth_context(monkeypatch):
    """Missing auth context is allowed; process-level auth remains the gate."""
    monkeypatch.setattr(module_under_test, "get_auth_context", lambda: None)

    async def _fetch(url, auth_headers=None):
        raise RuntimeError("unreachable")

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    res = await send_message("http://nope", "hi")
    assert res["status"] == "error"
    assert res.get("error") != "Unauthorized"


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
    assert "envelope" in res
    assert res["envelope"]["message_id"]


@pytest.mark.asyncio
async def test_send_message_includes_session_context_and_metadata(monkeypatch):
    """send_message sets A2A context_id, metadata, and response envelope for multi-turn."""
    url = "http://agent:10000"
    module_under_test.registered_agents[url] = build_agent_card(url=url)
    captured: dict[str, Any] = {}

    class CaptureClient(DummyA2AClient):
        def send_message(self, req: Any) -> Any:
            captured["req"] = req
            return super().send_message(req)

    async def _fetch(u: str) -> Any:
        return build_agent_card(url=u)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)
    monkeypatch.setattr(
        module_under_test,
        "_create_client_factory",
        lambda _c: DummyFactory(CaptureClient()),
    )

    res = await send_message(
        url,
        "ping",
        session_id="sess-1",
        message_id="mid-1",
        parent_message_id="p0",
        thread_id="th-1",
        transaction_id="tx-1",
        idempotency_key="idem-1",
    )
    assert res["status"] == "success"
    assert captured.get("req") is not None
    assert captured["req"].context_id == "sess-1"
    assert captured["req"].message_id == "mid-1"
    assert captured["req"].metadata.get("parent_message_id") == "p0"
    assert captured["req"].metadata.get("thread_id") == "th-1"
    assert captured["req"].metadata.get("transaction_id") == "tx-1"
    assert captured["req"].metadata.get("idempotency_key") == "idem-1"
    assert res["envelope"]["session_id"] == "sess-1"
    assert res["message_id"] == "mid-1"
    assert module_under_test.task_agent_mapping["task-123"]["session_id"] == "sess-1"


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
async def test_get_task_result_unauthorized_when_not_authenticated(monkeypatch):
    """Runtime A2A tools should fail when auth context is not authenticated."""
    monkeypatch.setattr(
        module_under_test,
        "get_auth_context",
        lambda: {"authenticated": False, "token": "test-token"},
    )

    res = await get_task_result("missing")
    assert res["status"] == "error"
    assert res["error"] == "Unauthorized"
    assert "Authenticated context is required" in res["message"]


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
async def test_cancel_task_allows_authenticated_context_without_token(monkeypatch):
    """Authenticated context without a token falls through to task lookup."""
    monkeypatch.setattr(
        module_under_test,
        "get_auth_context",
        lambda: {"authenticated": True},
    )

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
                non_task_event = SimpleNamespace(
                    type="message", content="response without task"
                )
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
    calls: list[dict[str, Any]] = [saved_agents, saved_tasks]

    def _load(_path):
        return calls.pop(0)

    monkeypatch.setattr(module_under_test, "load_from_json", _load)

    load_registered_agents()
    assert "http://agent:10000" in module_under_test.registered_agents
    assert module_under_test.task_agent_mapping == {
        "task-1": {"agent_url": "http://agent:10000"}
    }


def test_load_registered_agents_with_invalid_data(monkeypatch):
    """Test loading agents with invalid data falls back to sanitization."""
    saved_agents = {
        "http://agent:10000": {"invalid": "data"},
    }
    saved_tasks: dict[str, Any] = {}

    calls: list[dict[str, Any]] = [saved_agents, saved_tasks]

    def _load(_path):
        return calls.pop(0)

    monkeypatch.setattr(module_under_test, "load_from_json", _load)

    load_registered_agents()
    assert "http://agent:10000" in module_under_test.registered_agents
    # Should have sanitized the invalid data
    agent = module_under_test.registered_agents["http://agent:10000"]
    assert agent.name == "Unknown Agent"


# ============================================================================
# Embeddings Cache Tests
# ============================================================================


def test_invalidate_embeddings_cache():
    """Test that invalidate_embeddings_cache clears the cache."""
    import pandas as pd

    # Set up a fake cache
    module_under_test._embeddings_cache = pd.DataFrame({"test": [1, 2, 3]})
    module_under_test._embeddings_cache_timestamp = 123456.789

    # Invalidate the cache
    invalidate_embeddings_cache()

    # Verify cache is cleared
    assert module_under_test._embeddings_cache is None
    assert module_under_test._embeddings_cache_timestamp is None


def test_build_agent_card_embeddings_no_agents(monkeypatch):
    """Test build_agent_card_embeddings with no agents returns empty DataFrame."""
    monkeypatch.setattr(module_under_test, "load_agent_cards", lambda: ([], []))

    df = build_agent_card_embeddings(use_cache=False)
    assert df.empty


def test_build_agent_card_embeddings_caching(monkeypatch):
    """Test that build_agent_card_embeddings caches results."""
    import pandas as pd
    import numpy as np

    # Mock load_agent_cards to return test data
    test_cards = [
        {"name": "Agent1", "description": "Test agent 1"},
        {"name": "Agent2", "description": "Test agent 2"},
    ]
    test_uris = ["resource://agent_cards/agent1", "resource://agent_cards/agent2"]

    call_count = {"count": 0}

    def mock_load_agent_cards():
        call_count["count"] += 1
        return test_uris, test_cards

    # Mock generate_embeddings to return dummy embeddings
    def mock_generate_embeddings(text):
        return np.random.rand(384).tolist()  # Typical embedding size

    monkeypatch.setattr(module_under_test, "load_agent_cards", mock_load_agent_cards)
    monkeypatch.setattr(
        module_under_test, "generate_embeddings", mock_generate_embeddings
    )

    # First call should generate embeddings
    df1 = build_agent_card_embeddings(use_cache=True)
    assert len(df1) == 2
    assert call_count["count"] == 1
    assert module_under_test._embeddings_cache is not None

    # Second call should use cache (load_agent_cards should not be called again)
    df2 = build_agent_card_embeddings(use_cache=True)
    assert len(df2) == 2
    assert call_count["count"] == 1  # Should still be 1, not 2

    # Verify both DataFrames are the same object (cached)
    assert df1 is df2


def test_build_agent_card_embeddings_force_regenerate(monkeypatch):
    """Test that use_cache=False forces regeneration."""
    import numpy as np

    test_cards = [{"name": "Agent1", "description": "Test agent 1"}]
    test_uris = ["resource://agent_cards/agent1"]

    call_count = {"count": 0}

    def mock_load_agent_cards():
        call_count["count"] += 1
        return test_uris, test_cards

    def mock_generate_embeddings(text):
        return np.random.rand(384).tolist()

    monkeypatch.setattr(module_under_test, "load_agent_cards", mock_load_agent_cards)
    monkeypatch.setattr(
        module_under_test, "generate_embeddings", mock_generate_embeddings
    )

    # First call with cache
    df1 = build_agent_card_embeddings(use_cache=True)
    assert call_count["count"] == 1

    # Second call with use_cache=False should regenerate
    df2 = build_agent_card_embeddings(use_cache=False)
    assert call_count["count"] == 2  # Should be called again

    # DataFrames should be different objects
    assert df1 is not df2


@pytest.mark.asyncio
async def test_register_agent_invalidates_cache(monkeypatch):
    """Test that registering an agent invalidates the embeddings cache."""
    import pandas as pd

    # Set up a fake cache
    module_under_test._embeddings_cache = pd.DataFrame({"test": [1, 2, 3]})
    module_under_test._embeddings_cache_timestamp = 123456.789

    agent_url = "http://agent:10000"

    async def _fetch(url):
        return build_agent_card(url=url)

    monkeypatch.setattr(module_under_test, "fetch_agent_card", _fetch)

    # Register agent
    result = await register_agent(agent_url, ctx=AsyncMock())
    assert result["status"] == "success"

    # Verify cache was invalidated
    assert module_under_test._embeddings_cache is None
    assert module_under_test._embeddings_cache_timestamp is None


@pytest.mark.asyncio
async def test_unregister_agent_invalidates_cache(monkeypatch):
    """Test that unregistering an agent invalidates the embeddings cache."""
    import pandas as pd

    # Set up agent and cache
    url = "http://agent:10000"
    agent = build_agent_card(url=url)
    module_under_test.registered_agents[url] = agent
    module_under_test._embeddings_cache = pd.DataFrame({"test": [1, 2, 3]})
    module_under_test._embeddings_cache_timestamp = 123456.789

    # Unregister agent
    result = await unregister_agent(url)
    assert result["status"] == "success"

    # Verify cache was invalidated
    assert module_under_test._embeddings_cache is None
    assert module_under_test._embeddings_cache_timestamp is None


def test_build_agent_card_embeddings_filters_failed_embeddings(monkeypatch):
    """Test that rows with failed embeddings are filtered out."""
    import numpy as np

    test_cards = [
        {"name": "Agent1", "description": "Test agent 1"},
        {"name": "Agent2", "description": "Test agent 2"},
        {"name": "Agent3", "description": "Test agent 3"},
    ]
    test_uris = [
        "resource://agent_cards/agent1",
        "resource://agent_cards/agent2",
        "resource://agent_cards/agent3",
    ]

    # Mock generate_embeddings to fail for second agent
    def mock_generate_embeddings(text):
        if "Agent2" in text:
            return []  # Empty embedding indicates failure
        return np.random.rand(384).tolist()

    monkeypatch.setattr(
        module_under_test, "load_agent_cards", lambda: (test_uris, test_cards)
    )
    monkeypatch.setattr(
        module_under_test, "generate_embeddings", mock_generate_embeddings
    )

    df = build_agent_card_embeddings(use_cache=False)

    # Should only have 2 agents (Agent2 filtered out)
    assert len(df) == 2
    assert all(df["card_embeddings"].apply(len) > 0)


def test_build_agent_card_embeddings_exception_handling(monkeypatch):
    """Test that exceptions during embedding generation are handled gracefully."""
    test_cards = [{"name": "Agent1", "description": "Test agent 1"}]
    test_uris = ["resource://agent_cards/agent1"]

    def mock_generate_embeddings(text):
        raise RuntimeError("Embedding generation failed")

    monkeypatch.setattr(
        module_under_test, "load_agent_cards", lambda: (test_uris, test_cards)
    )
    monkeypatch.setattr(
        module_under_test, "generate_embeddings", mock_generate_embeddings
    )

    # Should return the current fallback value on exception
    df = build_agent_card_embeddings(use_cache=False)
    assert df is None


def test_find_agent_uses_cached_embeddings(monkeypatch):
    """Test that find_agent uses cached embeddings."""
    import pandas as pd
    import numpy as np

    # Create mock cached embeddings
    test_cards = [
        {"name": "Agent1", "description": "Test agent 1", "url": "http://agent1:10000"},
        {"name": "Agent2", "description": "Test agent 2", "url": "http://agent2:10000"},
    ]
    test_uris = ["resource://agent_cards/agent1", "resource://agent_cards/agent2"]
    embeddings = [np.random.rand(384).tolist() for _ in range(2)]

    cached_df = pd.DataFrame(
        {"card_uri": test_uris, "agent_card": test_cards, "card_embeddings": embeddings}
    )

    module_under_test._embeddings_cache = cached_df
    module_under_test._embeddings_cache_timestamp = 123456.789

    # Mock get_embedding_adapter
    class MockAdapter:
        def encode(self, text):
            return np.random.rand(384)

    monkeypatch.setattr(
        module_under_test, "get_embedding_adapter", lambda: MockAdapter()
    )

    # Call find_agent
    result = find_agent("test query")

    # Should return a dict (agent card)
    assert isinstance(result, dict)
    assert "name" in result
    assert result["name"] in ["Agent1", "Agent2"]


def test_find_agent_empty_dataframe(monkeypatch):
    """Test find_agent with empty DataFrame."""
    import pandas as pd

    monkeypatch.setattr(
        module_under_test, "build_agent_card_embeddings", lambda: pd.DataFrame()
    )

    result = find_agent("test query")
    assert result == "{}"


def test_find_agent_empty_query_embedding(monkeypatch):
    """Test find_agent when query embedding generation returns empty result."""
    import pandas as pd
    import numpy as np

    # Create mock cached embeddings
    test_cards = [{"name": "Agent1", "description": "Test agent 1"}]
    test_uris = ["resource://agent_cards/agent1"]
    embeddings = [np.random.rand(384).tolist()]

    cached_df = pd.DataFrame(
        {"card_uri": test_uris, "agent_card": test_cards, "card_embeddings": embeddings}
    )

    module_under_test._embeddings_cache = cached_df

    # Mock adapter that returns empty embedding
    class MockAdapter:
        def encode(self, text):
            return []  # Empty embedding

    monkeypatch.setattr(
        module_under_test, "get_embedding_adapter", lambda: MockAdapter()
    )

    result = find_agent("test query")
    assert result == "{}"


def test_find_agent_none_query_embedding(monkeypatch):
    """Test find_agent when query embedding generation returns None."""
    import pandas as pd
    import numpy as np

    # Create mock cached embeddings
    test_cards = [{"name": "Agent1", "description": "Test agent 1"}]
    test_uris = ["resource://agent_cards/agent1"]
    embeddings = [np.random.rand(384).tolist()]

    cached_df = pd.DataFrame(
        {"card_uri": test_uris, "agent_card": test_cards, "card_embeddings": embeddings}
    )

    module_under_test._embeddings_cache = cached_df

    # Mock adapter that returns None
    class MockAdapter:
        def encode(self, text):
            return None

    monkeypatch.setattr(
        module_under_test, "get_embedding_adapter", lambda: MockAdapter()
    )

    result = find_agent("test query")
    assert result == "{}"


def test_find_agent_empty_numpy_array_embedding(monkeypatch):
    """Test find_agent when query embedding is an empty numpy array."""
    import pandas as pd
    import numpy as np

    # Create mock cached embeddings
    test_cards = [{"name": "Agent1", "description": "Test agent 1"}]
    test_uris = ["resource://agent_cards/agent1"]
    embeddings = [np.random.rand(384).tolist()]

    cached_df = pd.DataFrame(
        {"card_uri": test_uris, "agent_card": test_cards, "card_embeddings": embeddings}
    )

    module_under_test._embeddings_cache = cached_df

    # Mock adapter that returns empty numpy array
    class MockAdapter:
        def encode(self, text):
            return np.array([])  # Empty numpy array

    monkeypatch.setattr(
        module_under_test, "get_embedding_adapter", lambda: MockAdapter()
    )

    result = find_agent("test query")
    assert result == "{}"


# ============================================================================
# Embedding Provider Fallback Tests
# ============================================================================


def test_get_embedding_adapter_success(monkeypatch):
    """Test successful embedding adapter initialization."""
    from unittest.mock import Mock, patch

    mock_adapter = Mock()

    with patch(
        "mcp_composer.core.tools.model_providers.factory.ModelProviderFactory"
    ) as mock_factory:
        mock_factory.create_embedding_provider.return_value = mock_adapter

        adapter = get_embedding_adapter()
        assert adapter == mock_adapter
        mock_factory.create_embedding_provider.assert_called_once()


def test_get_embedding_adapter_fallback_enabled(monkeypatch):
    """Test fallback to sentence-transformers when primary provider fails and fallback is enabled."""
    from unittest.mock import Mock, patch

    # Set fallback to enabled
    monkeypatch.setattr(module_under_test, "EMBEDDING_ALLOW_FALLBACK", True)

    fallback_adapter = Mock()

    with patch(
        "mcp_composer.core.tools.model_providers.factory.ModelProviderFactory"
    ) as mock_factory:
        # First call fails, second call (fallback) succeeds
        mock_factory.create_embedding_provider.side_effect = [
            RuntimeError("Primary provider failed"),
            fallback_adapter,
        ]

        adapter = get_embedding_adapter()
        assert adapter == fallback_adapter
        assert mock_factory.create_embedding_provider.call_count == 2


def test_get_embedding_adapter_fallback_disabled(monkeypatch):
    """Test that initialization fails when primary provider fails and fallback is disabled."""
    from unittest.mock import Mock, patch

    # Set fallback to disabled
    monkeypatch.setattr(module_under_test, "EMBEDDING_ALLOW_FALLBACK", False)

    with patch(
        "mcp_composer.core.tools.model_providers.factory.ModelProviderFactory"
    ) as mock_factory:
        mock_factory.create_embedding_provider.side_effect = RuntimeError(
            "Primary provider failed"
        )

        # Should raise the original exception
        with pytest.raises(RuntimeError, match="Primary provider failed"):
            get_embedding_adapter()


def test_get_embedding_adapter_both_providers_fail(monkeypatch):
    """Test that initialization fails when both primary and fallback providers fail."""
    from unittest.mock import Mock, patch

    # Set fallback to enabled
    monkeypatch.setattr(module_under_test, "EMBEDDING_ALLOW_FALLBACK", True)

    with patch(
        "mcp_composer.core.tools.model_providers.factory.ModelProviderFactory"
    ) as mock_factory:
        # Both calls fail
        mock_factory.create_embedding_provider.side_effect = [
            RuntimeError("Primary provider failed"),
            RuntimeError("Fallback provider failed"),
        ]

        # Should raise RuntimeError about both providers failing
        with pytest.raises(
            RuntimeError,
            match="Both primary .* and fallback .* embedding providers failed",
        ):
            get_embedding_adapter()


def test_get_embedding_adapter_caches_result(monkeypatch):
    """Test that embedding adapter is cached after first initialization."""
    from unittest.mock import Mock, patch

    mock_adapter = Mock()

    with patch(
        "mcp_composer.core.tools.model_providers.factory.ModelProviderFactory"
    ) as mock_factory:
        mock_factory.create_embedding_provider.return_value = mock_adapter

        # First call
        adapter1 = get_embedding_adapter()
        # Second call should return cached adapter
        adapter2 = get_embedding_adapter()

        assert adapter1 == adapter2
        # Factory should only be called once
        mock_factory.create_embedding_provider.assert_called_once()


def test_get_embedding_adapter_fallback_logs_warning(monkeypatch):
    """Test that fallback works and logs warning messages (verified via stderr in test output)."""
    from unittest.mock import Mock, patch

    # Set fallback to enabled
    monkeypatch.setattr(module_under_test, "EMBEDDING_ALLOW_FALLBACK", True)

    fallback_adapter = Mock()

    with patch(
        "mcp_composer.core.tools.model_providers.factory.ModelProviderFactory"
    ) as mock_factory:
        # First call fails, second call (fallback) succeeds
        mock_factory.create_embedding_provider.side_effect = [
            RuntimeError("API key invalid"),
            fallback_adapter,
        ]

        adapter = get_embedding_adapter()

        assert adapter == fallback_adapter
        # Verify both providers were called (primary failed, fallback succeeded)
        assert mock_factory.create_embedding_provider.call_count == 2
