"""
Enhanced MCP A2A Bridge with improved task management and result retrieval.

This script implements a bridge between the MCP protocol and A2A protocol,
allowing MCP clients to interact with A2A agents.
"""

import os
import time
import uuid
from typing import Any, cast, TYPE_CHECKING
import json
from functools import wraps
from fastmcp import Context
import httpx
from starlette.exceptions import HTTPException

from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.utils import load_from_json, save_to_json

# Lazy import for optional AI dependencies
ai_available = True
genai: Any = None
np: Any = None
pd: Any = None
try:
    import importlib

    np = importlib.import_module("numpy")
    pd = importlib.import_module("pandas")
    try:
        genai = importlib.import_module("google.genai")
    except ImportError:
        genai = None
except ImportError:
    ai_available = False

# Lazy import for optional A2A dependency
a2a_available = True
AgentCard: Any = None
AgentCapabilities: Any = None
AgentSkill: Any = None
TaskQueryParams: Any = None
TaskIdParams: Any = None
Message: Any = None
Task: Any = None
TextPart: Any = None
ClientFactory: Any = None
ClientConfig: Any = None
try:
    import importlib

    a2a_types = importlib.import_module("a2a.types")
    a2a_client = importlib.import_module("a2a.client")

    AgentCard = a2a_types.AgentCard
    AgentCapabilities = a2a_types.AgentCapabilities
    AgentSkill = a2a_types.AgentSkill
    TaskQueryParams = a2a_types.TaskQueryParams
    TaskIdParams = a2a_types.TaskIdParams
    Message = a2a_types.Message
    Task = a2a_types.Task
    TextPart = a2a_types.TextPart
    ClientFactory = a2a_client.ClientFactory
    ClientConfig = a2a_client.ClientConfig
except ImportError:
    a2a_available = False


def get_auth_context() -> dict[str, Any] | None:
    """Auth context middleware is not part of the open-source build."""
    return None


logger = LoggerFactory.get_logger()

# File paths for persistent storage
REGISTERED_AGENTS_FILE = os.getenv("A2A_AGENT_CONFIG_FILE", "a2a_agent_config.json")
TASK_AGENT_MAPPING_FILE = os.getenv(
    "A2A_TASK_AGENT_MAPPING_FILE", "a2a_task_agent_mapping.json"
)

# Default embedding model constant
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"

# Embedding configuration from environment variables
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
EMBEDDING_MODEL_PROVIDER = os.getenv("EMBEDDING_MODEL_PROVIDER")
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME", DEFAULT_SENTENCE_TRANSFORMER_MODEL
)
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434")
# Control fallback behavior: "true" to allow fallback, "false" to fail on error
EMBEDDING_ALLOW_FALLBACK = (
    os.getenv("EMBEDDING_ALLOW_FALLBACK", "true").lower() == "true"
)

# Initialize in-memory dictionaries with stored data

registered_agents: dict[Any, Any] = {}
# task_id -> str (legacy) | {"agent_url", ...} (rich mapping for multi-turn)
task_agent_mapping: dict[str, Any] = {}


def _normalize_task_entry(val: Any) -> dict[str, Any]:
    """Support legacy file format (task_id -> URL string) and rich dict entries."""
    if isinstance(val, dict) and "agent_url" in val:
        return val
    if isinstance(val, str):
        return {"agent_url": val}
    return {"agent_url": str(val)}


def _task_entry_agent_url(val: Any) -> str:
    return str(_normalize_task_entry(val).get("agent_url", ""))


# Initialize embedding provider (lazy loading)
_embedding_adapter = None

# Cache for agent card embeddings
_embeddings_cache: Any = None
_embeddings_cache_timestamp: float | None = None


def _unauthorized_a2a_response(reason: str) -> dict[str, Any]:
    """Standard unauthorized payload for A2A runtime tools."""
    return {
        "status": "error",
        "error": "Unauthorized",
        "message": reason,
    }


def _require_authenticated_context_for_a2a_runtime() -> dict[str, Any] | None:
    """
    If an auth context middleware is present and has set context, require it to
    be authenticated. When no auth context is available, allow the call so that
    process-level OAuth / JWT (if configured) remains the gate.
    """
    auth_context = get_auth_context()
    if not auth_context:
        return None
    if not auth_context.get("authenticated"):
        return _unauthorized_a2a_response(
            "Authenticated context is required for A2A runtime tools"
        )
    return None


def _create_client_factory(httpx_client) -> Any:
    """
    Create a ClientFactory with default configuration.
    """
    if not a2a_available:
        raise ImportError(
            "A2A support requires 'a2a' extras. "
            "Install with: pip install mcp-composer[a2a]"
        )
    config = {"httpx_client": httpx_client}
    return ClientFactory(config=ClientConfig(**config))


def _sanitize_agent_card_data(raw: dict[str, Any], fallback_url: str) -> Any:
    name = raw.get("name") or "Unknown Agent"
    url = raw.get("url") or fallback_url
    version = raw.get("version") or "0.1.0"
    description = raw.get("description") or "No description provided"

    caps_raw = raw.get("capabilities") or {}
    streaming = bool(caps_raw.get("streaming", False))
    capabilities = AgentCapabilities(streaming=streaming)

    default_input_modes = raw.get("default_input_modes") or ["text"]
    default_output_modes = raw.get("default_output_modes") or ["text"]

    skills_raw = raw.get("skills") or []
    skills: list[Any] = []
    for s in skills_raw:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or "unknown"
        sname = s.get("name") or sid
        sk_desc = s.get("description") or ""
        tags = s.get("tags") or []
        input_modes = s.get("input_modes") or ["text"]
        output_modes = s.get("output_modes") or ["text"]
        skills.append(
            AgentSkill(
                id=sid,
                name=sname,
                description=sk_desc,
                tags=tags,
                input_modes=input_modes,
                output_modes=output_modes,
            )
        )

    return AgentCard(
        name=name,
        description=description,
        url=url,
        version=version,
        capabilities=capabilities,
        default_input_modes=default_input_modes,
        default_output_modes=default_output_modes,
        skills=skills
        or [
            AgentSkill(
                id="unknown",
                name="Unknown Skill",
                description="Unknown agent capabilities",
                tags=[],
                input_modes=["text"],
                output_modes=["text"],
            )
        ],
    )


def _build_message_metadata(
    session_id: str | None,
    parent_message_id: str | None,
    thread_id: str | None,
    transaction_id: str | None,
    idempotency_key: str | None,
) -> dict[str, Any] | None:
    """Optional A2A Message.metadata for multi-turn / correlation (see docs/guide/a2a.md)."""
    meta: dict[str, Any] = {}
    if parent_message_id:
        meta["parent_message_id"] = parent_message_id
    if thread_id:
        meta["thread_id"] = thread_id
    if transaction_id:
        meta["transaction_id"] = transaction_id
    if idempotency_key:
        meta["idempotency_key"] = idempotency_key
    if session_id:
        # Echo session in metadata for agents that read metadata (context_id is primary wire field).
        meta["session_id"] = session_id
    return meta or None


def _append_message_chunk(complete_response: list[dict[str, Any]], chunk: Any) -> None:
    """Serialize an incoming Message chunk for structured_content / raw output."""
    parts_text: list[str] = []
    for part in chunk.parts:
        if getattr(part.root, "kind", None) == "text":
            if isinstance(part.root, TextPart):
                parts_text.append(part.root.text)
    text = "".join(parts_text)
    entry: dict[str, Any] = {
        "text": text,
        "messages": text,
    }
    if getattr(chunk, "message_id", None):
        entry["message_id"] = chunk.message_id
    if getattr(chunk, "task_id", None):
        entry["task_id"] = chunk.task_id
    ctx_id = getattr(chunk, "context_id", None)
    if ctx_id:
        entry["session_id"] = ctx_id
    if getattr(chunk, "metadata", None):
        entry["metadata"] = chunk.metadata
    complete_response.append(entry)


def _persist_task_context(
    task_id: str,
    agent_url: str,
    session_id: str | None,
    message_id: str,
    parent_message_id: str | None,
    thread_id: str | None,
    transaction_id: str | None,
) -> None:
    task_agent_mapping[task_id] = {
        "agent_url": agent_url,
        "session_id": session_id,
        "message_id": message_id,
        "parent_message_id": parent_message_id,
        "thread_id": thread_id,
        "transaction_id": transaction_id,
    }
    save_to_json(task_agent_mapping, TASK_AGENT_MAPPING_FILE)


def require_a2a_auth(func):
    """
    Decorator to enforce authentication for A2A runtime tools.

    This decorator checks authentication context before executing the tool function.
    If authentication fails, it returns an error response instead of executing the tool.

    Usage:
        @require_a2a_auth
        async def my_runtime_tool(...) -> dict[str, Any]:
            ...
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> dict[str, Any]:
        try:
            auth_error = _require_authenticated_context_for_a2a_runtime()
            if auth_error:
                return auth_error
            return await func(*args, **kwargs)
        except HTTPException as e:
            # Convert HTTPException from middleware to our standard error format
            return _unauthorized_a2a_response(f"Authentication failed: {e.detail}")

    return wrapper


async def fetch_agent_card(url: str) -> Any:
    """
    Fetch the agent card from the agent's URL.
    First try the main URL, then the well-known location.
    """
    async with httpx.AsyncClient() as client:
        # First try the main endpoint
        try:
            response = await client.get(url)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and "name" in data and "url" in data:
                        try:
                            return AgentCard(**data)
                        except Exception:
                            return _sanitize_agent_card_data(data, url)
                except json.JSONDecodeError:
                    pass  # Not a valid JSON response, try the well-known URL
        except Exception:
            pass  # Connection error, try the well-known URL

        # Try the well-known location
        well_known_url = f"{url.rstrip('/')}/.well-known/agent.json"
        try:
            response = await client.get(well_known_url)
            if response.status_code == 200:
                try:
                    data = response.json()
                    try:
                        return AgentCard(**data)
                    except Exception:
                        return _sanitize_agent_card_data(data, well_known_url)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON in agent card from {well_known_url}"
                    ) from e
        except httpx.RequestError as e:
            raise ValueError(
                f"Failed to fetch agent card from {well_known_url}: {str(e)}"
            ) from e

    # If we can't get the agent card, create a minimal one with default values
    return AgentCard(
        name="Unknown Agent",
        description="Unknown agent",
        url=url,
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="unknown",
                name="Unknown Skill",
                description="Unknown agent capabilities",
                tags=[],
                input_modes=["text"],
                output_modes=["text"],
            )
        ],
    )


async def list_agents() -> list[dict[str, Any]]:
    """
    List all registered A2A agents.

    Returns:
        List of registered agents
    """
    return [agent.model_dump() for agent in registered_agents.values()]


@require_a2a_auth
async def register_agent(url: str, ctx: Context) -> dict[str, Any]:
    """
    Register an A2A agent with the bridge server.

    Args:
        url: URL of the A2A agent

    Returns:
        Dictionary with registration status
    """
    try:
        # Fetch the agent card directly
        agent_card = await fetch_agent_card(url)

        # Store the agent information
        if not agent_card.description:
            agent_card.description = "No description provided"
        registered_agents[url] = agent_card

        # Save to disk immediately
        agents_data = {
            url: agent.model_dump() for url, agent in registered_agents.items()
        }
        save_to_json(agents_data, REGISTERED_AGENTS_FILE)

        # Invalidate embeddings cache since we added a new agent
        invalidate_embeddings_cache()

        await ctx.info(f"Successfully registered agent: {agent_card.name}")
        return {
            "status": "success",
            "agent": agent_card.model_dump(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to register agent: {str(e)}",
        }


@require_a2a_auth
async def unregister_agent(url: str, ctx: Context | None = None) -> dict[str, Any]:
    """
    Unregister an A2A agent from the bridge server.

    Args:
        url: URL of the A2A agent to unregister

    Returns:
        Dictionary with un registration status
    """
    if url not in registered_agents:
        return {
            "status": "error",
            "message": f"Agent not registered: {url}",
        }

    try:
        # Get agent name before removing it
        agent_name = registered_agents[url].name

        # Remove from registered agents
        del registered_agents[url]

        # Clean up any task mappings related to this agent
        # Create a list of task_ids to remove to avoid modifying the dictionary during iteration
        tasks_to_remove = []
        for task_id, entry in task_agent_mapping.items():
            if _task_entry_agent_url(entry) == url:
                tasks_to_remove.append(task_id)

        # Now remove the task mappings
        for task_id in tasks_to_remove:
            del task_agent_mapping[task_id]

        # Save changes to disk immediately
        agents_data = {
            url: agent.model_dump() for url, agent in registered_agents.items()
        }
        save_to_json(agents_data, REGISTERED_AGENTS_FILE)
        save_to_json(task_agent_mapping, TASK_AGENT_MAPPING_FILE)

        # Invalidate embeddings cache since we removed an agent
        invalidate_embeddings_cache()

        if ctx:
            await ctx.info(f"Successfully unregistered agent: {agent_name}")

        return {
            "status": "success",
            "message": f"Successfully unregistered agent: {agent_name}",
            "removed_tasks": len(tasks_to_remove),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error unregistering agent: {str(e)}",
        }


@require_a2a_auth
async def send_message(
    agent_url: str,
    message: str,
    session_id: str | None = None,
    message_id: str | None = None,
    parent_message_id: str | None = None,
    thread_id: str | None = None,
    transaction_id: str | None = None,
    idempotency_key: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Send a message to an A2A agent.

    Args:
        agent_url: URL of the A2A agent
        message: Message to send
        session_id: Conversation context id (A2A ``context_id``); required for multi-turn mapping
        message_id: Id for this turn; auto-generated if omitted
        parent_message_id: Optional prior message id in the same thread
        thread_id: Optional logical thread (distinct from session if needed)
        transaction_id: Optional distributed trace / request id
        idempotency_key: Passed to the agent in metadata; dedup is agent-side
        ctx: Optional MCP context for progress logs

    Returns:
        ``task_id`` plus correlation envelope; see docs/guide/a2a.md
    """
    if agent_url not in registered_agents:
        logger.error("Agent not registered: %s", agent_url)
        return {
            "status": "error",
            "message": f"Agent not registered: {agent_url}",
        }

    agent_card = registered_agents[agent_url]
    outbound_message_id = message_id or str(uuid.uuid4())
    meta = _build_message_metadata(
        session_id,
        parent_message_id,
        thread_id,
        transaction_id,
        idempotency_key,
    )
    async with httpx.AsyncClient() as httpx_client:
        client_factory = _create_client_factory(httpx_client)
        client = client_factory.create(agent_card)
        send_params: dict[str, Any] = {
            "role": "user",
            "parts": [{"type": "text", "text": message}],
            "message_id": outbound_message_id,
        }
        if session_id:
            send_params["context_id"] = session_id
        if meta:
            send_params["metadata"] = meta
        a2a_send_message = Message(**send_params)
        if ctx:
            await ctx.info(f"Sending message to agent: {message}")
            await ctx.info("Processing...")

        complete_response: list[dict[str, Any]] = []
        result_task_id: str | None = None
        sequence = 0
        try:
            async for chunk in client.send_message(a2a_send_message):
                if isinstance(chunk, Message):
                    if chunk.task_id:
                        result_task_id = result_task_id or chunk.task_id
                    sequence += 1
                    _append_message_chunk(complete_response, chunk)
                    if ctx and complete_response and complete_response[-1].get("text"):
                        await ctx.info(str(complete_response[-1]["text"]))

                elif isinstance(chunk, tuple):
                    # Handle tuple of events or single event
                    events = chunk if isinstance(chunk, tuple) else (chunk,)
                    for event in events:
                        if isinstance(event, Task):
                            if not result_task_id:
                                result_task_id = event.id
                                if ctx:
                                    await ctx.info(f"Task ID: {result_task_id}")
                                break
                        ##### Uncomment if we need to send the full task status updates to MCP client
                        #     response = {
                        #         "state": event.status.state.name,
                        #         "messages": "",
                        #         "artifacts": [],
                        #     }
                        #     if event.status.message and hasattr(
                        #         event.status.message, "parts"
                        #     ):
                        #         for part in event.status.message.parts:
                        #             if getattr(part.root, "kind", None) == "text":
                        #                 # Only extract text if part.root is a TextPart
                        #                 if isinstance(part.root, TextPart):
                        #                     response["messages"] = part.root.text
                        #     if event.artifacts:
                        #         response["artifacts"] = [
                        #             artifact.model_dump()
                        #             for artifact in event.artifacts
                        #         ]
                        #     complete_response.append(response)
                        # else:
                        #     # Non-Task event, just log if context provided
                        #     if ctx and event:
                        #         await ctx.info(str(event))

                else:
                    # Unknown chunk type, just log if context provided
                    if ctx and chunk:
                        await ctx.info(str(chunk))

            if result_task_id:
                _persist_task_context(
                    result_task_id,
                    agent_url,
                    session_id,
                    outbound_message_id,
                    parent_message_id,
                    thread_id,
                    transaction_id,
                )

            echoed_session: str | None = session_id
            if complete_response:
                last = complete_response[-1]
                if last.get("session_id"):
                    echoed_session = last.get("session_id") or echoed_session
                meta = (
                    last.get("metadata")
                    if isinstance(last.get("metadata"), dict)
                    else None
                )
                if meta and meta.get("session_id"):
                    echoed_session = meta.get("session_id") or echoed_session

            envelope: dict[str, Any] = {
                "session_id": echoed_session,
                "message_id": outbound_message_id,
                "task_id": result_task_id,
                "sequence": sequence,
                "status": "completed" if result_task_id else "unknown",
            }

            return {
                "status": "success",
                "task_id": result_task_id,
                "session_id": echoed_session,
                "message_id": outbound_message_id,
                "raw": complete_response,
                "envelope": envelope,
            }
        except Exception as e:
            logger.error("Error processing stream events: %s", str(e))
            return {
                "status": "error",
                "message": f"Error processing stream events: {str(e)}",
            }


@require_a2a_auth
async def get_task_result(
    task_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Retrieve the result of a task from an A2A agent.

    Args:
        task_id: ID of the task to retrieve

    Returns:
        Task result minimal payload
    """
    if task_id not in task_agent_mapping:
        return {
            "status": "error",
            "message": f"Task ID not found: {task_id}",
        }

    entry = _normalize_task_entry(task_agent_mapping[task_id])
    agent_url = entry["agent_url"]
    async with httpx.AsyncClient() as httpx_client:
        agent_card = await fetch_agent_card(agent_url)
        client_factory = _create_client_factory(httpx_client)
        client = client_factory.create(
            agent_card,
        )
        if ctx:
            await ctx.info(f"Retrieving task result for task_id: {task_id}")
        result: Any = await client.get_task(TaskQueryParams(id=task_id))
        out: dict[str, Any] = {
            "status": "success",
            "task_id": task_id,
            "raw": str(result),
        }
        if entry.get("session_id"):
            out["session_id"] = entry.get("session_id")
        if entry.get("message_id"):
            out["message_id"] = entry.get("message_id")
        return out


@require_a2a_auth
async def cancel_task(
    task_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Cancel a running task on an A2A agent.
    """
    if task_id not in task_agent_mapping:
        return {"status": "error", "message": f"Task ID not found: {task_id}"}

    entry = _normalize_task_entry(task_agent_mapping[task_id])
    agent_url = entry["agent_url"]
    async with httpx.AsyncClient() as httpx_client:
        agent_card = await fetch_agent_card(agent_url)
        client_factory = _create_client_factory(httpx_client)
        client = client_factory.create(
            agent_card,
        )
        if ctx:
            await ctx.info(f"Cancelling task: {task_id}")
        try:
            # Call client cancel with typed request
            result: Any = await client.cancel_task(TaskIdParams(id=task_id))
            out: dict[str, Any] = {
                "status": "success",
                "task_id": task_id,
                "raw": str(result),
            }
            if entry.get("session_id"):
                out["session_id"] = entry.get("session_id")
            return out
        except Exception as e:
            return {"status": "error", "message": f"Error cancelling task: {str(e)}"}


def load_registered_agents() -> None:
    """Load registered agents from stored data on startup."""
    global registered_agents, task_agent_mapping
    logger.info("Loading saved data...")
    # Load agents data
    agents_data = load_from_json(REGISTERED_AGENTS_FILE)
    for url, agent_data in agents_data.items():
        try:
            registered_agents[url] = AgentCard(**agent_data)
        except Exception:
            registered_agents[url] = _sanitize_agent_card_data(agent_data, url)

    # Load task mappings (migrate legacy string values to dict entries)
    raw_tasks = load_from_json(TASK_AGENT_MAPPING_FILE)
    task_agent_mapping = {
        tid: _normalize_task_entry(val) for tid, val in raw_tasks.items()
    }

    logger.info(
        "Loaded '%s' agents and '%s' task mappings",
        len(registered_agents),
        len(task_agent_mapping),
    )


def get_embedding_adapter() -> Any:
    """Get or initialize the embedding adapter based on environment configuration.

    The function attempts to initialize the configured embedding provider. If initialization
    fails and EMBEDDING_ALLOW_FALLBACK is true, it falls back to sentence-transformers.
    Otherwise, it raises the original exception.

    Returns:
        ModelProviderAdapter: The configured embedding adapter

    Raises:
        Exception: If provider initialization fails and fallback is disabled
    """
    global _embedding_adapter

    if _embedding_adapter is None:
        from mcp_composer.core.tools.model_providers.factory import (
            ModelProviderFactory,
        )

        try:
            _embedding_adapter = ModelProviderFactory.create_embedding_provider(
                provider_name=EMBEDDING_PROVIDER,
                model_name=EMBEDDING_MODEL_NAME,
                model_provider=EMBEDDING_MODEL_PROVIDER,
                api_key=EMBEDDING_API_KEY,
                base_url=EMBEDDING_BASE_URL,
            )
            logger.info(
                "Successfully initialized embedding provider: %s with model: %s",
                EMBEDDING_PROVIDER,
                EMBEDDING_MODEL_NAME,
            )
        except Exception as e:
            error_msg = (
                f"Failed to initialize embedding provider '{EMBEDDING_PROVIDER}' "
                f"with model '{EMBEDDING_MODEL_NAME}': {str(e)}"
            )

            if not EMBEDDING_ALLOW_FALLBACK:
                logger.error(
                    "%s. Fallback is disabled (EMBEDDING_ALLOW_FALLBACK=false). "
                    "Please check your configuration (API key, model name, base URL).",
                    error_msg,
                )
                raise

            # Log prominent warning about fallback
            logger.warning("=" * 80)
            logger.warning("EMBEDDING PROVIDER CONFIGURATION ERROR")
            logger.warning("=" * 80)
            logger.warning("%s", error_msg)
            logger.warning(
                "Falling back to sentence-transformers with model 'all-MiniLM-L6-v2'."
            )
            logger.warning(
                "This may result in different embedding quality and performance."
            )
            logger.warning(
                "To disable fallback and fail on configuration errors, set: "
                "EMBEDDING_ALLOW_FALLBACK=false"
            )
            logger.warning("=" * 80)

            try:
                # Fallback to sentence-transformers
                _embedding_adapter = ModelProviderFactory.create_embedding_provider(
                    provider_name="sentence-transformers",
                    model_name="all-MiniLM-L6-v2",
                )
                logger.info(
                    "Successfully initialized fallback embedding provider: sentence-transformers"
                )
            except Exception as fallback_error:
                logger.error(
                    "Failed to initialize fallback embedding provider: %s",
                    fallback_error,
                )
                raise RuntimeError(
                    f"Both primary ({EMBEDDING_PROVIDER}) and fallback (sentence-transformers) "
                    f"embedding providers failed to initialize"
                ) from fallback_error

    return _embedding_adapter


def generate_embeddings(text: str | None) -> list[float] | list[Any]:
    """Generates embeddings for the given text using the configured embedding provider.

    Args:
        text: The input string for which to generate embeddings.

    Returns:
        A list of embeddings representing the input text.

    Raises:
        AttributeError: If adapter doesn't have expected methods (programming error)
        TypeError: If text is of wrong type (programming error)
    """
    if text is None or not text:
        return []

    try:
        # Get the embedding adapter
        adapter = get_embedding_adapter()

        # Generate embeddings using the adapter
        # Pass model_name if the adapter has it stored (for litellm/ollama)
        model_name = getattr(adapter, "_embedding_model", None)
        if model_name:
            embeddings = adapter.encode(text, model_name=model_name)
        else:
            embeddings = adapter.encode(text)

        return embeddings
    except (ConnectionError, TimeoutError, OSError) as e:
        # Network-related errors
        logger.error("Network error generating embedding: %s", e)
        return []
    except (ValueError, KeyError) as e:
        # Configuration or data-related errors
        logger.error("Configuration/data error generating embedding: %s", e)
        return []
    except (ImportError, ModuleNotFoundError) as e:
        # Missing dependencies
        logger.error("Missing dependency for embedding generation: %s", e)
        return []
    except RuntimeError as e:
        # Runtime errors from the embedding provider
        logger.error("Runtime error generating embedding: %s", e)
        return []
    # Let AttributeError, TypeError, and other programming errors propagate


def load_agent_cards() -> tuple[list[str], list[dict[str, Any]]]:
    """Loads agent card data from JSON files within a specified directory.

    Returns:
        A list containing JSON data from an agent card file found in the specified directory.
        Returns an empty list if the directory is empty, contains no '.json' files,
        or if all '.json' files encounter errors during processing.
    """
    card_uris = []
    agent_cards = []
    agents_data = load_from_json(REGISTERED_AGENTS_FILE)
    for url, agent_data in agents_data.items():
        agent_name = agent_data["name"].replace(" ", "_").lower()
        card_uris.append(f"resource://agent_cards/{agent_name}")
        agent_cards.append(agent_data)
    logger.info("Finished loading agent cards. Found %s cards.", len(agent_cards))
    return card_uris, agent_cards


def invalidate_embeddings_cache() -> None:
    """Invalidate the embeddings cache to force regeneration on next access."""
    global _embeddings_cache, _embeddings_cache_timestamp
    _embeddings_cache = None
    _embeddings_cache_timestamp = None
    logger.debug("Embeddings cache invalidated")


def build_agent_card_embeddings(use_cache: bool = True) -> Any:
    """Loads agent cards, generates embeddings for them, and returns a DataFrame.

    Implements caching to avoid regenerating embeddings on every call.
    The cache is invalidated when agents are registered/unregistered.

    Args:
        use_cache: If True, use cached embeddings if available. If False, force regeneration.

    Returns:
        pd.DataFrame: A Pandas DataFrame containing the original
        'agent_card' data and their corresponding 'Embeddings'. Returns empty
        DataFrame if no agent cards were loaded initially or if an exception occurred
        during the embedding generation process.
    """
    global _embeddings_cache, _embeddings_cache_timestamp

    if not ai_available:
        logger.info("AI dependencies not installed; skipping agent card embeddings")
        return None

    # Return cached embeddings if available and use_cache is True
    if use_cache and _embeddings_cache is not None:
        logger.debug(
            "Using cached agent card embeddings (%s records)", len(_embeddings_cache)
        )
        return _embeddings_cache

    # 1. Load the raw data
    card_uris, agent_cards = load_agent_cards()

    if not agent_cards:
        logger.info("No agent cards found in directory.")
        return pd.DataFrame()

    logger.info("Generating local embeddings for %s agent cards...", len(agent_cards))

    try:
        # 2. Create the DataFrame
        df = pd.DataFrame({"card_uri": card_uris, "agent_card": agent_cards})

        # 3. Apply embedding logic
        # We use json.dumps because the model needs a string, but agent_card is a dict
        df["card_embeddings"] = df["agent_card"].apply(
            lambda card: generate_embeddings(json.dumps(card))
        )

        # 4. Clean up any rows where embedding failed
        df = df[df["card_embeddings"].apply(len) > 0]

        logger.info("Successfully built embedding database with %s records.", len(df))

        # Cache the results
        _embeddings_cache = df
        _embeddings_cache_timestamp = time.time()
        logger.debug(
            "Cached agent card embeddings at timestamp %s", _embeddings_cache_timestamp
        )

        return df

    except Exception as e:
        logger.error("An unexpected error occurred during build: %s.", e, exc_info=True)
        return None


def find_agent(query: str) -> str:
    """Finds the most relevant agent card based on a query string.

    This function takes a user query, typically a natural language question or a task generated by an agent,
    generates its embedding, and compares it against the
    pre-computed embeddings of the loaded agent cards. It uses the dot
    product to measure similarity and identifies the agent card with the
    highest similarity score.

    Args:
        query: The natural language query string used to search for a
                relevant agent.

    Returns:
        The json representing the agent card deemed most relevant
        to the input query based on embedding similarity.
    """
    # 1. Load your pre-computed embeddings
    # Note: Ensure build_agent_card_embeddings() uses the same embedding adapter
    df = build_agent_card_embeddings()
    if not ai_available or df is None or df.empty:
        logger.warning("No agent cards found or DataFrame is empty.")
        return "{}"
    try:
        # 2. Generate embedding for the user query using the configured provider
        adapter = get_embedding_adapter()
        query_emb = adapter.encode(query)

        # Validate that embedding was generated successfully
        if query_emb is None or (hasattr(query_emb, "__len__") and len(query_emb) == 0):
            logger.error("Failed to generate query embedding for query: %s", query)
            return "{}"

        # Convert to numpy array if it's a list
        if isinstance(query_emb, list):
            query_emb = np.array(query_emb)

        # Additional validation after conversion
        if query_emb.size == 0:
            logger.error(
                "Query embedding is empty after conversion for query: %s", query
            )
            return "{}"

        # 3. Calculate similarity
        # We stack the stored embeddings (which should be lists/arrays)
        # and calculate the dot product against our query vector.
        embeddings_stack = np.stack(df["card_embeddings"].tolist())
        dot_products = np.dot(embeddings_stack, query_emb)

        # 4. Find the best match
        best_match_index = np.argmax(dot_products)

        logger.debug(
            "Found best match at index %s with score %s",
            best_match_index,
            dot_products[best_match_index],
        )

        # Return the original JSON/dict for that agent
        return df.iloc[best_match_index]["agent_card"]

    except Exception as e:
        logger.error("Failed to generate query embeddings or find match: %s", e)
        return "{}"


def get_agent_cards() -> str:
    """Retrieves all loaded agent cards as a json / dictionary for the MCP resource endpoint.

    This function serves as the handler for the MCP resource identified by
    the URI 'resource://agent_cards/list'.

    Returns:
        A json / dictionary structured as {'agent_cards': [...]}, where the value is a
        list containing all the loaded agent card dictionaries. Returns
        {'agent_cards': []} if the data cannot be retrieved.
    """
    df = build_agent_card_embeddings()
    resources: dict[str, Any] = {}
    logger.info("Starting read resources")
    if not ai_available or df is None or df.empty:
        resources["agent_cards"] = []
    else:
        resources["agent_cards"] = df["card_uri"].to_list()
    return json.dumps(resources)


def get_agent_card(card_name: str) -> str:
    """Retrieves an agent card as a json / dictionary for the MCP resource endpoint.

    This function serves as the handler for the MCP resource identified by
    the URI 'resource://agent_cards/{card_name}'.

    Returns:
        A json / dictionary
    """
    df = build_agent_card_embeddings()
    resources: dict[str, Any] = {}
    logger.info("Starting read resource resource://agent_cards/%s", card_name)
    if df is None or df.empty:
        resources["agent_card"] = {}
        return json.dumps(resources)

    matched_cards = (
        df.loc[
            df["card_uri"] == f"resource://agent_cards/{card_name}",
            "agent_card",
        ]
    ).to_list()

    resources["agent_card"] = matched_cards[0] if matched_cards else {}
    return json.dumps(resources)
