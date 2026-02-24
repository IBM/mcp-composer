from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.tools.tool_manager import MCPToolManager

# pylint: disable=protected-access


# Fixture to reuse tool_manager setup
@pytest.fixture
def tool_manager():
    composer = MagicMock()
    server_manager = MagicMock()
    database = MagicMock()
    return MCPToolManager(
        composer=composer, server_manager=server_manager, database=database
    )


# ---------- Sync Tests ----------


def test_unmount_removes_server(tool_manager):  # pylint: disable=redefined-outer-name
    mock_server = MagicMock()
    mock_server.prefix = "server1"
    other_server = MagicMock()
    other_server.prefix = "other"
    tool_manager._composer._mounted_servers = [
        mock_server,
        other_server,
    ]  # pylint: disable=protected-access

    tool_manager.unmount("server1")

    assert all(
        s.prefix != "server1" for s in tool_manager._composer._mounted_servers
    )  # pylint: disable=protected-access


def test_filter_tools_removes_and_updates(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    tool1 = MagicMock()
    tool1.name = "a"
    tool2 = MagicMock()
    tool2.name = "test_server_b"
    tool2.description = "original description"
    tools = {"a": tool1, "test_server_b": tool2}

    member = MagicMock()
    member.health_status = HealthStatus.healthy
    member.disabled_tools = ["a"]
    member.tools_description = {"b": "desc"}
    member.id = "test_server"
    tool_manager._server_manager.list.return_value = [
        member
    ]  # pylint: disable=protected-access

    filtered = tool_manager.filter_tools(tools)

    assert "a" not in filtered
    assert "test_server_b" in filtered
    assert filtered["test_server_b"].description == "desc"


def test_filter_tools_handles_no_config(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    tool_manager._server_manager.list.return_value = (
        []
    )  # pylint: disable=protected-access
    tools = {"a": MagicMock()}
    tools["a"].name = "a"

    assert tool_manager.filter_tools(tools) == tools


def test_filter_tools_handles_unhealthy(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    member = MagicMock(
        health_status=HealthStatus.unhealthy, disabled_tools=["a"], tools_description={}
    )
    tool_manager._server_manager.list.return_value = [
        member
    ]  # pylint: disable=protected-access
    tools = {"a": MagicMock()}
    tools["a"].name = "a"

    assert tool_manager.filter_tools(tools) == tools


def test_filter_tools_exception(tool_manager):  # pylint: disable=redefined-outer-name
    tool_manager._server_manager.list.side_effect = Exception(
        "fail"
    )  # pylint: disable=protected-access

    with pytest.raises(Exception, match="fail"):
        tool_manager.filter_tools({"a": MagicMock()})


def test_filter_tools_user_instances_none_unchanged(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances=None, behavior is unchanged (no product-based filtering)."""
    tool_manager._server_manager.list.return_value = []
    tools = {"a": MagicMock()}
    tools["a"].name = "a"

    result = tool_manager.filter_tools(tools, user_instances=None)
    assert result == tools


def test_filter_tools_user_instances_empty_unchanged(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances=[], no product-based filtering applied."""
    tool_manager._server_manager.list.return_value = []
    tools = {"a": MagicMock()}
    tools["a"].name = "a"

    result = tool_manager.filter_tools(tools, user_instances=[])
    assert result == tools


def test_filter_tools_user_instances_filters_by_product(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances containing only lakehouse, tools for gi are removed."""
    t_wx = MagicMock()
    t_wx.name = "mcp-wx-data_get_service_info"
    t_gi = MagicMock()
    t_gi.name = "mcp-gurdium_get_type_info"
    tools = {"mcp-wx-data_get_service_info": t_wx, "mcp-gurdium_get_type_info": t_gi}

    member_wx = MagicMock()
    member_wx.id = "mcp-wx-data"
    member_wx.health_status = HealthStatus.healthy
    member_wx.disabled_tools = []
    member_wx.tools_description = {}
    member_wx.config = {"solis_config": {"product_id": "lakehouse"}}

    member_gi = MagicMock()
    member_gi.id = "mcp-gurdium"
    member_gi.health_status = HealthStatus.healthy
    member_gi.disabled_tools = []
    member_gi.tools_description = {}
    member_gi.config = {"solis_config": {"product_id": "gi"}}

    tool_manager._server_manager.list.return_value = [member_wx, member_gi]

    user_instances = [{"subscription": {"productId": "lakehouse"}}]

    result = tool_manager.filter_tools(tools, user_instances=user_instances)

    assert "mcp-wx-data_get_service_info" in result
    assert "mcp-gurdium_get_type_info" not in result


def test_filter_tools_composer_tools_always_kept(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """Composer-owned tools (no server_id prefix) are always kept."""
    tool_no_prefix = MagicMock()
    tool_no_prefix.name = "enable_all_tools"
    tools = {"enable_all_tools": tool_no_prefix}

    member = MagicMock()
    member.id = "mcp-wx-data"
    member.health_status = HealthStatus.healthy
    member.disabled_tools = []
    member.tools_description = {}
    member.config = {"solis_config": {"product_id": "lakehouse"}}
    tool_manager._server_manager.list.return_value = [member]

    user_instances = [{"subscription": {"productId": "gi"}}]  # user has only gi

    result = tool_manager.filter_tools(tools, user_instances=user_instances)

    assert "enable_all_tools" in result


def test_filter_tools_server_no_product_id_kept(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """Server with no solis_config.product_id: tool always kept."""
    t1 = MagicMock()
    t1.name = "mcp-aspera_get_service_info"
    tools = {"mcp-aspera_get_service_info": t1}

    member = MagicMock()
    member.id = "mcp-aspera"
    member.health_status = HealthStatus.healthy
    member.disabled_tools = []
    member.tools_description = {}
    member.config = {}  # no solis_config
    tool_manager._server_manager.list.return_value = [member]

    user_instances = [{"subscription": {"productId": "lakehouse"}}]

    result = tool_manager.filter_tools(tools, user_instances=user_instances)

    assert "mcp-aspera_get_service_info" in result


# ---------- Async Tests ----------


@pytest.mark.asyncio
async def test_load_custom_tools_handles_import(
    tool_manager, monkeypatch
):  # pylint: disable=redefined-outer-name
    monkeypatch.setattr("mcp_composer.core.tools.tool_manager.custom_tools", None)
    monkeypatch.setattr(
        "mcp_composer.core.tools.tool_manager.generate_tool_from_curl",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "mcp_composer.core.tools.tool_manager.generate_tool_from_open_api",
        AsyncMock(return_value={}),
    )

    result = await tool_manager.load_custom_tools()

    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fetch_server_tools_and_update_desc(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    mock_server = MagicMock()
    mock_server.id = "s1"

    mounted = MagicMock()
    mounted.prefix = "s1"
    mounted.server.get_tools = AsyncMock(return_value={"t1": MagicMock()})

    tool_manager._mounted_servers = [mounted]  # pylint: disable=protected-access

    result = await tool_manager.fetch_server_tools(
        mock_server, remove=["s1_t1"], description={"s1_t1": "desc"}
    )

    assert "s1_t1" not in result or result["s1_t1"].description == "desc"


@pytest.mark.asyncio
async def test_get_all_tools_specific(
    tool_manager, monkeypatch
):  # pylint: disable=redefined-outer-name
    tool_manager._server_manager.get.return_value = (
        MagicMock()
    )  # pylint: disable=protected-access
    tool_manager._server_manager.get_document.return_value = (
        MagicMock()
    )  # pylint: disable=protected-access

    monkeypatch.setattr(
        "mcp_composer.core.tools.tool_manager.get_server_doc_info", lambda doc: ([], {})
    )
    monkeypatch.setattr(
        "mcp_composer.core.tools.tool_manager.MCPToolManager.fetch_server_tools",
        AsyncMock(return_value={"a": MagicMock()}),
    )

    result = await tool_manager.get_all_tools(server_id="s1")

    assert "a" in result


@pytest.mark.asyncio
async def test_get_all_tools_default(
    tool_manager, monkeypatch
):  # pylint: disable=redefined-outer-name
    monkeypatch.setattr(
        "mcp_composer.core.tools.tool_manager.MCPToolManager.get_tools",
        AsyncMock(return_value={"a": MagicMock()}),
    )

    result = await tool_manager.get_all_tools()

    assert "a" in result
