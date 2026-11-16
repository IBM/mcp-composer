"""Unit tests for DisabledToolsMiddleware."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from mcp_composer.middleware.tool.disabled_tools import DisabledToolsMiddleware


def _composer(composer_disabled=None, members=None):
    members = members or []
    return SimpleNamespace(
        _tool_manager=SimpleNamespace(_disabled_tools=list(composer_disabled or [])),
        _server_manager=SimpleNamespace(list=lambda: members),
    )


def _member(member_id, disabled_tools):
    return SimpleNamespace(id=member_id, disabled_tools=disabled_tools)


def _tools(*names):
    return [SimpleNamespace(name=n) for n in names]


def _call_ctx(name):
    return SimpleNamespace(message=SimpleNamespace(name=name))


async def _list(mw, names):
    call_next = AsyncMock(return_value=_tools(*names))
    result = await mw.on_list_tools(SimpleNamespace(), call_next)
    return [t.name for t in result]


@pytest.mark.asyncio
async def test_member_config_deny_list_is_prefixed():
    composer = _composer(members=[_member("m", ["wipe_records"])])
    mw = DisabledToolsMiddleware(composer)
    assert await _list(mw, ["m_lookup", "m_wipe_records"]) == ["m_lookup"]


@pytest.mark.asyncio
async def test_member_deny_list_does_not_hide_other_members_tool():
    composer = _composer(members=[_member("a", ["wipe"])])
    mw = DisabledToolsMiddleware(composer)
    assert await _list(mw, ["a_wipe", "b_wipe", "wipe"]) == ["b_wipe", "wipe"]


@pytest.mark.asyncio
async def test_composer_level_list_uses_composed_names():
    mw = DisabledToolsMiddleware(_composer(composer_disabled=["m_wipe_records"]))
    assert await _list(mw, ["m_lookup", "m_wipe_records"]) == ["m_lookup"]


@pytest.mark.asyncio
async def test_runtime_changes_take_effect_without_restart():
    composer = _composer()
    mw = DisabledToolsMiddleware(composer)
    assert await _list(mw, ["m_wipe_records"]) == ["m_wipe_records"]
    composer._tool_manager._disabled_tools.append("m_wipe_records")
    assert await _list(mw, ["m_wipe_records"]) == []
    composer._tool_manager._disabled_tools.clear()
    assert await _list(mw, ["m_wipe_records"]) == ["m_wipe_records"]


@pytest.mark.asyncio
async def test_all_sentinel_keeps_only_enable_all_tools():
    mw = DisabledToolsMiddleware(_composer(composer_disabled=["all"]))
    assert await _list(mw, ["m_lookup", "enable_all_tools", "disable_tools"]) == [
        "enable_all_tools"
    ]


@pytest.mark.asyncio
async def test_call_to_disabled_tool_is_rejected_and_not_forwarded():
    composer = _composer(members=[_member("m", ["wipe_records"])])
    mw = DisabledToolsMiddleware(composer)
    call_next = AsyncMock()
    with pytest.raises(ToolError, match="disabled"):
        await mw.on_call_tool(_call_ctx("m_wipe_records"), call_next)
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_call_to_enabled_tool_is_forwarded():
    composer = _composer(members=[_member("m", ["wipe_records"])])
    mw = DisabledToolsMiddleware(composer)
    call_next = AsyncMock(return_value="ok")
    ctx = _call_ctx("m_lookup")
    assert await mw.on_call_tool(ctx, call_next) == "ok"
    call_next.assert_awaited_once_with(ctx)


@pytest.mark.asyncio
async def test_call_rejected_under_all_sentinel_except_enable_all_tools():
    mw = DisabledToolsMiddleware(_composer(composer_disabled=["all"]))
    with pytest.raises(ToolError):
        await mw.on_call_tool(_call_ctx("m_lookup"), AsyncMock())
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_call_ctx("enable_all_tools"), call_next) == "ok"
