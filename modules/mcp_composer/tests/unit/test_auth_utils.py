"""Unit tests for auth_utils (tool name to server_id resolution)."""

import pytest

from mcp_composer.middleware.auth_utils import tool_name_to_server_id


def test_tool_name_to_server_id_with_prefix():
    """Tool name with server prefix returns prefix before first '_'."""
    assert tool_name_to_server_id("mcp-server1_make_tool_call") == "mcp-server1"
    assert tool_name_to_server_id("mcp-server2_list_tools") == "mcp-server2"
    assert tool_name_to_server_id("server_foo") == "server"


def test_tool_name_to_server_id_no_underscore():
    """Tool name without '_' (composer-owned) returns None."""
    assert tool_name_to_server_id("healthcheck") is None
    assert tool_name_to_server_id("listtools") is None


def test_tool_name_to_server_id_leading_underscore():
    """Tool name starting with '_' has no valid prefix (empty before _)."""
    assert tool_name_to_server_id("_private_tool") is None


def test_tool_name_to_server_id_empty_or_invalid():
    """Empty string or non-string returns None."""
    assert tool_name_to_server_id("") is None
    assert tool_name_to_server_id(None) is None  # type: ignore[arg-type]


def test_tool_name_to_server_id_single_segment():
    """Single segment with no underscore returns None."""
    assert tool_name_to_server_id("onlyone") is None


def test_tool_name_to_server_id_one_underscore():
    """Single underscore gives prefix (e.g. composer tool with underscore)."""
    assert tool_name_to_server_id("make_tool_call") == "make"


def test_tool_name_to_server_id_multiple_underscores():
    """Only the substring before the first '_' is the server_id."""
    assert tool_name_to_server_id("srv_tool_sub_op") == "srv"
