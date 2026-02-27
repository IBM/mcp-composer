from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest

from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.tools.tool_manager import MCPToolManager
from mcp_composer.core.utils.exceptions import ToolDisableError, ToolDuplicateError

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


@pytest.fixture
def manager():
    composer = MagicMock()
    composer.name = "composer"
    composer.list_tools = AsyncMock(return_value=[])
    composer.disable = MagicMock()
    composer.enable = MagicMock()
    server_manager = MagicMock()
    server_manager.list.return_value = []
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

    tool_manager._composer.disable.assert_called_once_with(names={"a"})
    filtered_names = [tool.name for tool in filtered]
    assert "a" in filtered_names
    assert "test_server_b" in filtered_names
    filtered_tool = next(tool for tool in filtered if tool.name == "test_server_b")
    assert filtered_tool.description == "desc"


def test_filter_tools_handles_no_config(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    tool_manager._server_manager.list.return_value = (
        []
    )  # pylint: disable=protected-access
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

    filtered = tool_manager.filter_tools(tools)
    assert filtered == [tool]


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

    filtered = tool_manager.filter_tools(tools)
    assert filtered == [tool]


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
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

    result = tool_manager.filter_tools(tools, user_instances=None)
    assert result == tools


def test_filter_tools_user_instances_empty_unchanged(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """With user_instances=[], no product-based filtering applied."""
    tool_manager._server_manager.list.return_value = []
    tool = MagicMock()
    tool.name = "a"
    tools = [tool]

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

    result_names = [tool.name for tool in result]
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

    assert any(tool.name == "enable_all_tools" for tool in result)


def test_filter_tools_server_no_product_id_kept(
    tool_manager,
):  # pylint: disable=redefined-outer-name
    """Server with no solis_config.product_id: tool always kept."""
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

    assert any(tool.name == "mcp-aspera_get_service_info" for tool in result)


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
    tool_manager._server_manager.get_document.return_value = {}  # no composer doc
    tool = MagicMock()
    tool.name = "a"
    tool_manager._composer.list_tools = AsyncMock(return_value=[tool])

    result = await tool_manager.get_all_tools()

    assert len(result) == 1
    assert result[0].name == "a"


@pytest.mark.asyncio
async def test_has_tool_for_single_and_multiple_keys(manager):
    manager._composer.list_tools = AsyncMock(
        return_value=[SimpleNamespace(name="a"), SimpleNamespace(name="b")]
    )

    assert await manager.has_tool("a") is True
    assert await manager.has_tool("x") is False
    assert await manager.has_tool(["x", "b"]) is True
    assert await manager.has_tool(["x", "y"]) is False


def test_get_instance_product_id_variants(manager):
    assert (
        manager._get_instance_product_id({"subscription": {"productId": "p1"}}) == "p1"
    )
    assert (
        manager._get_instance_product_id({"subscription": {"product_id": "p2"}}) == "p2"
    )
    assert manager._get_instance_product_id({"productId": "p3"}) == "p3"
    assert manager._get_instance_product_id({"product_id": "p4"}) == "p4"
    assert manager._get_instance_product_id({}) is None


@pytest.mark.asyncio
async def test_disable_tools_all_updates_state_and_db(manager):
    result = await manager.disable_tools(["all"])

    assert manager._disabled_tools == ["all"]
    manager._database.disable_tools.assert_called_once_with(
        ["all"], server_id="composer"
    )
    assert "Successfully disabled tools" in result


@pytest.mark.asyncio
async def test_disable_tools_raises_if_tool_missing(manager):
    manager.has_tool = AsyncMock(return_value=False)

    with pytest.raises(ToolDisableError, match="does not exist"):
        await manager.disable_tools(["missing_tool"])


@pytest.mark.asyncio
async def test_disable_tools_raises_on_duplicate(manager):
    manager._disabled_tools = ["tool_a"]
    manager.has_tool = AsyncMock(return_value=True)

    with pytest.raises(ToolDuplicateError, match="already disabled"):
        await manager.disable_tools(["tool_a"])


@pytest.mark.asyncio
async def test_enable_tools_success_and_persistence(manager):
    manager._disabled_tools = ["tool_a", "tool_b"]

    result = await manager.enable_tools(["tool_a"])

    assert manager._disabled_tools == ["tool_b"]
    manager._composer.enable.assert_called_once_with(names={"tool_a"})
    manager._database.enable_tools.assert_called_once_with(
        ["tool_b"], server_id="composer"
    )
    assert "Enabled ['tool_a'] tools from composer" == result


@pytest.mark.asyncio
async def test_enable_tools_raises_if_not_disabled(manager):
    manager._disabled_tools = ["tool_a"]

    with pytest.raises(ValueError, match="not disabled"):
        await manager.enable_tools(["tool_x"])


@pytest.mark.asyncio
async def test_enable_all_tools_clears_all_marker_and_persists(manager):
    manager._disabled_tools = ["all"]

    result = await manager.enable_all_tools()

    assert manager._disabled_tools == []
    manager._database.enable_tools.assert_called_once_with([], server_id="composer")
    assert result == "Enabled all tools from composer"


@pytest.mark.asyncio
async def test_update_tool_description_strips_server_prefix(manager, monkeypatch):
    manager._server_manager.check_server_exist = MagicMock()
    manager._server_manager.update_tool_description = MagicMock()
    manager.get_all_tools = AsyncMock(return_value=[SimpleNamespace(name="fetch_html")])

    async def _tool_exists(*_args, **_kwargs):
        return None

    monkeypatch.setattr("mcp_composer.core.tools.tool_manager.tool_exist", _tool_exists)

    result = await manager.update_tool_description(
        tool="mcp-server-fetch_fetch_html",
        description="new desc",
        server_id="mcp-server-fetch",
    )

    manager._server_manager.update_tool_description.assert_called_once_with(
        "fetch_html", "new desc", "mcp-server-fetch"
    )
    assert "Updated mcp-server-fetch_fetch_html" in result


@pytest.mark.asyncio
async def test_fetch_server_tools_applies_remove_and_description():
    composer = MagicMock()
    server_manager = MagicMock()
    database = MagicMock()
    manager = MCPToolManager(
        composer=composer, server_manager=server_manager, database=database
    )

    tool_a = SimpleNamespace(name="a", description="old")
    tool_b = SimpleNamespace(name="b", description="old")

    mounted_server = MagicMock()
    mounted_server.server = MagicMock()
    mounted_server.server.list_tools = AsyncMock(return_value=[tool_a, tool_b])
    server_manager._member_servers = {"s1": mounted_server}

    server = SimpleNamespace(id="s1")
    result = await manager.fetch_server_tools(
        server,
        remove=["a"],
        description={"b": "new"},
    )

    names = [t.name for t in result]
    assert "a" not in names
    assert "b" in names
    assert next(t for t in result if t.name == "b").description == "new"


@pytest.mark.asyncio
async def test_filter_tool_by_keyword_returns_ranked_matches(manager, monkeypatch):
    tools = [
        SimpleNamespace(name="mcp-server-fetch_fetch_html", description=""),
        SimpleNamespace(name="mcp-server-fetch_fetch_markdown", description=""),
        SimpleNamespace(name="unrelated_tool", description=""),
    ]
    manager._composer.list_tools = AsyncMock(return_value=tools)
    monkeypatch.setattr(manager, "filter_tools", lambda t: t)

    result = await manager.filter_tool_by_keyword("fetch")

    assert "mcp-server-fetch_fetch_html" in result
    assert "mcp-server-fetch_fetch_markdown" in result


@pytest.mark.asyncio
async def test_disable_composer_tool_with_none_disables_all_listed(manager):
    manager._composer.list_tools = AsyncMock(
        return_value=[SimpleNamespace(name="a"), SimpleNamespace(name="b")]
    )

    result = await manager.disable_composer_tool()

    assert set(manager._disabled_tools) == {"a", "b"}
    assert "Disabled composer tools" in result


@pytest.mark.asyncio
async def test_disable_composer_tool_raises_for_non_existent_specified(manager):
    manager._composer.list_tools = AsyncMock(return_value=[SimpleNamespace(name="a")])

    with pytest.raises(ToolDisableError, match="do not exist"):
        await manager.disable_composer_tool(["a", "missing"])
