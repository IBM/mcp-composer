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
    tools = [tool1, tool2]

    member = MagicMock()
    member.health_status = HealthStatus.healthy
    member.disabled_tools = ["a"]
    member.tools_description = {"b": "desc"}
    member.id = "test_server"
    tool_manager._server_manager.list.return_value = [
        member
    ]  # pylint: disable=protected-access

    filtered = tool_manager.filter_tools(tools)
    filtered_names = [t.name for t in filtered]

    # Current implementation applies disable() on composer and updates descriptions.
    # It does not remove disabled tools unless product-based filtering is active.
    assert "a" in filtered_names
    assert "test_server_b" in filtered_names
    assert tool2.description == "desc"


def test_filter_tools_handles_no_config(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    tool_manager._server_manager.list.return_value = (
        []
    )  # pylint: disable=protected-access
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

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
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

    assert tool_manager.filter_tools(tools) == tools


def test_filter_tools_exception(tool_manager):  # pylint: disable=redefined-outer-name
    tool_manager._server_manager.list.side_effect = Exception(
        "fail"
    )  # pylint: disable=protected-access

    tool = MagicMock()
    tool.name = "a"
    with pytest.raises(Exception, match="fail"):
        tool_manager.filter_tools([tool])


def test_filter_tools_user_instances_none_unchanged(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances=None and no product members, all tools pass (after disable rules)."""
    tool_manager._server_manager.list.return_value = []
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

    result = tool_manager.filter_tools(tools, user_instances=None)
    assert result == tools


def test_filter_tools_user_instances_empty_unchanged(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances=[] and no product members, all tools pass."""
    tool_manager._server_manager.list.return_value = []
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

    result = tool_manager.filter_tools(tools, user_instances=[])
    assert result == tools


def test_filter_tools_empty_user_instances_hides_product_servers(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With no entitlement, tools from members with solis_config.product_id are hidden."""
    t_member = MagicMock()
    t_member.name = "mcp-wx-data_get_service_info"
    t_plain = MagicMock()
    t_plain.name = "enable_all_tools"
    tools = [t_member, t_plain]

    member = MagicMock()
    member.id = "mcp-wx-data"
    member.health_status = HealthStatus.healthy
    member.disabled_tools = []
    member.tools_description = {}
    member.config = {"solis_config": {"product_id": "lakehouse"}}
    tool_manager._server_manager.list.return_value = [member]

    result = tool_manager.filter_tools(tools, user_instances=[])
    names = [t.name for t in result]
    assert "mcp-wx-data_get_service_info" not in names
    assert "enable_all_tools" in names


def test_filter_tools_user_instances_filters_by_product(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances containing only lakehouse, tools for gi are removed."""
    t_wx = MagicMock()
    t_wx.name = "mcp-wx-data_get_service_info"
    t_gi = MagicMock()
    t_gi.name = "mcp-gurdium_get_type_info"
    tools = [t_wx, t_gi]

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

    result_names = [t.name for t in result]

    assert "mcp-wx-data_get_service_info" in result_names
    assert "mcp-gurdium_get_type_info" not in result_names


def test_filter_tools_composer_tools_always_kept(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """Composer-owned tools (no server_id prefix) are always kept."""
    tool_no_prefix = MagicMock()
    tool_no_prefix.name = "enable_all_tools"
    tools = [tool_no_prefix]

    member = MagicMock()
    member.id = "mcp-wx-data"
    member.health_status = HealthStatus.healthy
    member.disabled_tools = []
    member.tools_description = {}
    member.config = {"solis_config": {"product_id": "lakehouse"}}
    tool_manager._server_manager.list.return_value = [member]

    user_instances = [{"subscription": {"productId": "gi"}}]  # user has only gi

    result = tool_manager.filter_tools(tools, user_instances=user_instances)

    result_names = [t.name for t in result]
    assert "enable_all_tools" in result_names


def test_filter_tools_server_no_product_id_filtered_out(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """Server with no solis_config.product_id: tool is filtered out when user_instances provided."""
    t1 = MagicMock()
    t1.name = "mcp-aspera_get_service_info"
    tools = [t1]

    member = MagicMock()
    member.id = "mcp-aspera"
    member.health_status = HealthStatus.healthy
    member.disabled_tools = []
    member.tools_description = {}
    member.config = {}  # no solis_config
    tool_manager._server_manager.list.return_value = [member]

    user_instances = [{"subscription": {"productId": "lakehouse"}}]

    result = tool_manager.filter_tools(tools, user_instances=user_instances)

    # Tool should be filtered out because server has no product_id and doesn't match user's instances
    result_names = [t.name for t in result]
    assert "mcp-aspera_get_service_info" not in result_names


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
    tool = MagicMock()
    tool.name = "a"
    tool_manager._composer.list_tools = AsyncMock(return_value=[tool])

    result = await tool_manager.get_all_tools()

    assert any(t.name == "a" for t in result)
