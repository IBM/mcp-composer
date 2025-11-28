"""
Enhanced MCP A2A Bridge with improved task management and result retrieval.

This script implements a bridge between the MCP protocol and A2A protocol,
allowing MCP clients to interact with A2A agents.
"""

import os
import uuid
from typing import Any, Dict, List, Optional, cast
import json
from fastmcp import Context
import httpx
from google import genai
import numpy as np
import pandas as pd
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.utils import load_from_json, save_to_json

from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    TaskQueryParams,
    TaskIdParams,
    Message,
    Task,
    TextPart,
)
from a2a.client import ClientFactory, ClientConfig

logger = LoggerFactory.get_logger()

# File paths for persistent storage
REGISTERED_AGENTS_FILE = os.getenv("A2A_AGENT_CONFIG_FILE", "a2a_agent_config.json")
TASK_AGENT_MAPPING_FILE = os.getenv(
    "A2A_TASK_AGENT_MAPPING_FILE", "a2a_task_agent_mapping.json"
)

# Initialize in-memory dictionaries with stored data
registered_agents = {}
task_agent_mapping = {}


def _create_client_factory(httpx_client) -> ClientFactory:
    """
    Create a ClientFactory with default configuration.
    """
    config = {"httpx_client": httpx_client}
    return ClientFactory(config=ClientConfig(**config))


def _sanitize_agent_card_data(raw: Dict[str, Any], fallback_url: str) -> AgentCard:
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
    skills: List[AgentSkill] = []
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


async def fetch_agent_card(url: str) -> AgentCard:
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


async def register_agent(url: str, ctx: Context) -> Dict[str, Any]:
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


async def list_agents() -> List[Dict[str, Any]]:
    """
    List all registered A2A agents.

    Returns:
        List of registered agents
    """
    return [agent.model_dump() for agent in registered_agents.values()]


async def unregister_agent(url: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
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
        for task_id, agent_url in task_agent_mapping.items():
            if agent_url == url:
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


async def send_message(
    agent_url: str,
    message: str,
    ctx: Optional[Context] = None,
) -> Dict[str, Any]:
    """
    Send a message to an A2A agent.

    Args:
        agent_url: URL of the A2A agent
        message: Message to send

    Returns:
        Agent's response with task_id for future reference
    """
    if agent_url not in registered_agents:
        logger.error("Agent not registered: %s", agent_url)
        return {
            "status": "error",
            "message": f"Agent not registered: {agent_url}",
        }

    agent_card = registered_agents[agent_url]
    async with httpx.AsyncClient() as httpx_client:
        client_factory = _create_client_factory(httpx_client)
        client = client_factory.create(agent_card)
        send_params = {
            "role": "user",
            "parts": [{"type": "text", "text": message}],
            "message_id": str(uuid.uuid4()),
        }
        a2a_send_message = Message(**send_params)
        if ctx:
            await ctx.info(f"Sending message to agent: {message}")
            await ctx.info("Processing...")

        complete_response = []
        result_task_id = None
        try:
            async for chunk in client.send_message(a2a_send_message):
                if isinstance(chunk, Message):
                    result_task_id = chunk.task_id
                    # Handle message parts if any
                    parts_text = []
                    for part in chunk.parts:
                        if getattr(part.root, "kind", None) == "text":
                            if isinstance(part.root, TextPart):
                                parts_text.append(part.root.text)
                    if parts_text and ctx:
                        await ctx.info("".join(parts_text))
                    complete_response.append({"messages": "".join(parts_text)})

                elif isinstance(chunk, tuple):
                    # Handle tuple of events or single event
                    events = chunk if isinstance(chunk, tuple) else (chunk,)
                    for event in events:
                        if isinstance(event, Task):
                            if not result_task_id:
                                result_task_id = event.id
                                task_agent_mapping[result_task_id] = agent_url
                                save_to_json(
                                    task_agent_mapping, TASK_AGENT_MAPPING_FILE
                                )
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
            return {
                "status": "success",
                "task_id": result_task_id,
                "raw": complete_response,
            }
        except Exception as e:
            logger.error("Error processing stream events: %s", str(e))
            return {
                "status": "error",
                "message": f"Error processing stream events: {str(e)}",
            }


async def get_task_result(
    task_id: str,
    ctx: Optional[Context] = None,
) -> Dict[str, Any]:
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

    agent_url = task_agent_mapping[task_id]
    async with httpx.AsyncClient() as httpx_client:
        agent_card = await fetch_agent_card(agent_url)
        client_factory = _create_client_factory(httpx_client)
        client = client_factory.create(
            agent_card,
        )
        if ctx:
            await ctx.info(f"Retrieving task result for task_id: {task_id}")
        result: Any = await client.get_task(TaskQueryParams(id=task_id))
        return {"status": "success", "task_id": task_id, "raw": str(result)}


async def cancel_task(
    task_id: str,
    ctx: Optional[Context] = None,
) -> Dict[str, Any]:
    """
    Cancel a running task on an A2A agent.
    """
    if task_id not in task_agent_mapping:
        return {"status": "error", "message": f"Task ID not found: {task_id}"}

    agent_url = task_agent_mapping[task_id]
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
            return {"status": "success", "task_id": task_id, "raw": str(result)}
        except Exception as e:
            return {"status": "error", "message": f"Error cancelling task: {str(e)}"}


def load_registered_agents():
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

    # Load task mappings
    task_agent_mapping = load_from_json(TASK_AGENT_MAPPING_FILE)

    logger.info(
        "Loaded '%s' agents and '%s' task mappings",
        len(registered_agents),
        len(task_agent_mapping),
    )


def generate_embeddings(text):
    """Generates embeddings for the given text using Google Generative AI.

    Args:
        text: The input string for which to generate embeddings.

    Returns:
        A list of embeddings representing the input text.
    """
    try:
        client = genai.Client(api_key="AIzaSyA79l4zIyIufWTzCMJfb1-DJTvUXRVI71s")
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config={"task_type": "retrieval_document"},
        )
        if response.embeddings is not None and len(response.embeddings) > 0:
            return response.embeddings[0].values
        else:
            return []
    except Exception as e:
        logger.error(f"Failed to generate embeddings for text: {e}")
        return []


def load_agent_cards():
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
    logger.info(f"Finished loading agent cards. Found {len(agent_cards)} cards.")
    return card_uris, agent_cards


def build_agent_card_embeddings() -> pd.DataFrame:
    """Loads agent cards, generates embeddings for them, and returns a DataFrame.

    Returns:
        Optional[pd.DataFrame]: A Pandas DataFrame containing the original
        'agent_card' data and their corresponding 'Embeddings'. Returns None
        if no agent cards were loaded initially or if an exception occurred
        during the embedding generation process.
    """
    card_uris, agent_cards = load_agent_cards()
    logger.info("Generating Embeddings for agent cards:%s: %s", card_uris, agent_cards)
    try:
        if agent_cards and len(agent_cards) > 0:
            df = pd.DataFrame({"card_uri": card_uris, "agent_card": agent_cards})
            df["card_embeddings"] = df["agent_card"].apply(
                lambda card: generate_embeddings(json.dumps(card))
            )
            df = df[df["card_embeddings"].apply(len) > 0]
            return df
        logger.info("Done generating embeddings for agent cards")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"An unexpected error occurred : {e}.", exc_info=True)
        return pd.DataFrame()


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
    df = build_agent_card_embeddings()
    if df.empty:
        return "{}"
    client = genai.Client(api_key="AIzaSyA79l4zIyIufWTzCMJfb1-DJTvUXRVI71s")
    try:
        query_embedding = client.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config={"task_type": "retrieval_query"},
        )
        if (
            query_embedding.embeddings is not None
            and len(query_embedding.embeddings) > 0
        ):
            query_emb = cast(list[float], query_embedding.embeddings[0].values)
        else:
            return "{}"
    except Exception as e:
        logger.error(f"Failed to generate query embeddings: {e}")
        return "{}"
    dot_products = np.dot(np.stack(df["card_embeddings"].tolist()), query_emb)
    best_match_index = np.argmax(dot_products)
    logger.debug(
        f"Found best match at index {best_match_index} with score {dot_products[best_match_index]}"
    )
    return df.iloc[best_match_index]["agent_card"]


def get_agent_cards() -> dict:
    """Retrieves all loaded agent cards as a json / dictionary for the MCP resource endpoint.

    This function serves as the handler for the MCP resource identified by
    the URI 'resource://agent_cards/list'.

    Returns:
        A json / dictionary structured as {'agent_cards': [...]}, where the value is a
        list containing all the loaded agent card dictionaries. Returns
        {'agent_cards': []} if the data cannot be retrieved.
    """
    df = build_agent_card_embeddings()
    resources = {}
    logger.info("Starting read resources")
    if df.empty:
        resources["agent_cards"] = []
    else:
        resources["agent_cards"] = df["card_uri"].to_list()
    return resources


def get_agent_card(card_name: str) -> dict:
    """Retrieves an agent card as a json / dictionary for the MCP resource endpoint.

    This function serves as the handler for the MCP resource identified by
    the URI 'resource://agent_cards/{card_name}'.

    Returns:
        A json / dictionary
    """
    df = build_agent_card_embeddings()
    resources = {}
    logger.info(f"Starting read resource resource://agent_cards/{card_name}")
    if df.empty:
        resources["agent_card"] = []
        return resources
    resources["agent_card"] = (
        df.loc[
            df["card_uri"] == f"resource://agent_cards/{card_name}",
            "agent_card",
        ]
    ).to_list()

    return resources
