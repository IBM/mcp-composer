"""Disabled prompts and resources must be refused on the real request path.

These tests mount a real FastMCP member on a real ``MCPComposer`` and call it
through an in-process ``Client``, so the composed ``get_prompt`` and
``read_resource`` handlers are what is exercised.
"""

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from mcp_composer import MCPComposer
from mcp_composer.core.member_servers.member_server import MemberMCPServer


def _member_server(reads: list[str]) -> FastMCP:
    member = FastMCP("member")

    @member.prompt
    def secret_prompt() -> str:
        return "SECRET PROMPT"

    @member.prompt
    def open_prompt() -> str:
        return "OPEN PROMPT"

    @member.resource("res://secret", name="secret_res")
    def secret_res() -> str:
        reads.append("secret")
        return "SECRET RESOURCE"

    @member.resource("res://open", name="open_res")
    def open_res() -> str:
        return "OPEN RESOURCE"

    @member.resource("res://items/{item_id}", name="item_tmpl")
    def item_tmpl(item_id: str) -> str:
        reads.append(f"item-{item_id}")
        return f"item-{item_id}"

    return member


def _compose(
    member_id: str = "m",
    disabled_prompts: list[str] | None = None,
    disabled_resources: list[str] | None = None,
    reads: list[str] | None = None,
) -> MCPComposer:
    composer = MCPComposer("composer", config=[])
    composer.mount(_member_server(reads if reads is not None else []), member_id)
    record = MemberMCPServer(
        id=member_id,
        endpoint="http://127.0.0.1:1/mcp",
        type="http",
        config={"id": member_id},
        label="",
        tags=[],
        tool_count=None,
        disabled_prompts=list(disabled_prompts or []),
        tools_description={},
    )
    record.disabled_resources = list(disabled_resources or [])
    composer._server_manager.add_member(
        member_id, record
    )  # pylint: disable=protected-access
    return composer


async def _prompt(client: Client, name: str) -> str:
    return (await client.get_prompt(name)).messages[0].content.text


async def _read(client: Client, uri: str) -> str:
    return (await client.read_resource(uri))[0].text


@pytest.mark.asyncio
async def test_control_nothing_disabled_is_served():
    async with Client(_compose()) as client:
        assert await _prompt(client, "m_secret_prompt") == "SECRET PROMPT"
        assert await _read(client, "res://m/secret") == "SECRET RESOURCE"
        assert await _read(client, "res://m/items/5") == "item-5"


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", ["secret_prompt", "m_secret_prompt"])
async def test_disabled_prompt_is_refused_in_both_stored_forms(stored):
    async with Client(_compose(disabled_prompts=[stored])) as client:
        with pytest.raises(Exception, match="disabled"):
            await _prompt(client, "m_secret_prompt")
        assert await _prompt(client, "m_open_prompt") == "OPEN PROMPT"


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", ["secret_res", "m_secret_res", "SECRET_RES"])
async def test_disabled_resource_is_refused_and_not_read(stored):
    reads: list[str] = []
    composer = _compose(disabled_resources=[stored], reads=reads)
    async with Client(composer) as client:
        with pytest.raises(Exception, match="disabled"):
            await _read(client, "res://m/secret")
        assert await _read(client, "res://m/open") == "OPEN RESOURCE"
    assert "secret" not in reads, "the member ran the disabled resource"


@pytest.mark.asyncio
async def test_disabled_resource_template_is_refused():
    reads: list[str] = []
    composer = _compose(disabled_resources=["item_tmpl"], reads=reads)
    async with Client(composer) as client:
        with pytest.raises(Exception, match="disabled"):
            await _read(client, "res://m/items/5")
    assert reads == []


@pytest.mark.asyncio
async def test_disabled_resource_matches_by_uri_too():
    composer = _compose(disabled_resources=["res://m/secret"])
    async with Client(composer) as client:
        with pytest.raises(Exception, match="disabled"):
            await _read(client, "res://m/secret")


@pytest.mark.asyncio
async def test_deny_list_of_one_member_does_not_hide_another_members_item():
    composer = MCPComposer("composer", config=[])
    for member_id, disabled in (("a", ["secret_prompt"]), ("b", [])):
        composer.mount(_member_server([]), member_id)
        record = MemberMCPServer(
            id=member_id,
            endpoint="http://127.0.0.1:1/mcp",
            type="http",
            config={"id": member_id},
            label="",
            tags=[],
            tool_count=None,
            disabled_prompts=disabled,
            tools_description={},
        )
        composer._server_manager.add_member(
            member_id, record
        )  # pylint: disable=protected-access
    async with Client(composer) as client:
        with pytest.raises(Exception, match="disabled"):
            await _prompt(client, "a_secret_prompt")
        assert await _prompt(client, "b_secret_prompt") == "SECRET PROMPT"


@pytest.mark.asyncio
async def test_runtime_changes_take_effect_without_restart():
    composer = _compose()
    record = composer._server_manager.get("m")  # pylint: disable=protected-access
    async with Client(composer) as client:
        assert await _prompt(client, "m_secret_prompt") == "SECRET PROMPT"
        record.disabled_prompts = ["secret_prompt"]
        with pytest.raises(Exception, match="disabled"):
            await _prompt(client, "m_secret_prompt")
        record.disabled_prompts = []
        assert await _prompt(client, "m_secret_prompt") == "SECRET PROMPT"


@pytest.mark.asyncio
async def test_unhealthy_member_deny_list_still_applies():
    from mcp_composer.core.member_servers.member_server import HealthStatus

    composer = _compose(disabled_prompts=["secret_prompt"])
    composer._server_manager.get("m").health_status = (
        HealthStatus.unhealthy
    )  # pylint: disable=protected-access
    async with Client(composer) as client:
        with pytest.raises(Exception, match="disabled"):
            await _prompt(client, "m_secret_prompt")


@pytest.mark.asyncio
async def test_disabled_tools_enforcement_is_unaffected():
    composer = _compose()
    async with Client(composer) as client:
        with pytest.raises(ToolError):
            await client.call_tool("m_does_not_exist", {})


@pytest.mark.asyncio
async def test_config_supplied_deny_lists_reach_the_member_at_mount_time():
    """``disabled_resources`` from config must be stored, like ``disabled_prompts``."""
    from unittest.mock import AsyncMock, MagicMock, patch

    reads: list[str] = []
    composer = MCPComposer("composer", config=[])
    builder = MagicMock()
    builder.build = AsyncMock(return_value=_member_server(reads))
    config = {
        "id": "m",
        "type": "http",
        "endpoint": "http://127.0.0.1:1/mcp",
        "disabled_prompts": ["secret_prompt"],
        "disabled_resources": ["secret_res"],
    }
    with patch("mcp_composer.core.composer.MCPServerBuilder", return_value=builder):
        await composer._mount_member_server(config)  # pylint: disable=protected-access

    async with Client(composer) as client:
        with pytest.raises(Exception, match="disabled"):
            await _prompt(client, "m_secret_prompt")
        with pytest.raises(Exception, match="disabled"):
            await _read(client, "res://m/secret")
        assert await _read(client, "res://m/open") == "OPEN RESOURCE"
    assert reads == []
