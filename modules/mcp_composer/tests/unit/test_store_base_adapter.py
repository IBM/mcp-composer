"""Tests for store/base_adapter.py shared mutation helpers."""

import json

import pytest
from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.store.base_adapter import BaseDatabaseAdapter


class _TestAdapter(BaseDatabaseAdapter):
    """Minimal concrete adapter for testing protected helpers."""

    def load_all_servers(self):
        return []

    def add_server(self, config):
        pass

    def remove_server(self, server_id):
        pass

    def get_document(self, server_id):
        return {}

    def enable_tools(self, tools, server_id):
        pass

    def disable_tools(self, tools, server_id):
        pass

    def update_tool_description(self, tool, description, server_id):
        pass

    def enable_prompts(self, prompts, server_id):
        pass

    def disable_prompts(self, prompts, server_id):
        pass

    def enable_resources(self, resources, server_id):
        pass

    def disable_resources(self, resources, server_id):
        pass

    def mark_deactivated(self, server_id):
        pass

    def get_server_status(self, server_id):
        return "unknown"

    def update_server_config(self, config):
        pass

    def load_all_resources(self):
        return []

    def upsert_resource(self, resource):
        pass

    def delete_resource(self, resource_id):
        pass

    def load_all_prompts(self):
        return []

    def add_prompt(self, prompt):
        pass

    def remove_prompt(self, prompt_name):
        pass

    def get_prompt(self, prompt_name):
        return {}

    def register_server(self, config):
        pass

    def append_server_endpoint(self, server_id, entry):
        return True

    def remove_server_endpoint(self, server_id, entry):
        return "not_found"

    def ping(self):
        return True


@pytest.fixture
def adapter():
    return _TestAdapter()


class TestBaseDatabaseAdapterHelpers:
    def test_dedupe_list(self, adapter):
        assert sorted(adapter._dedupe_list(["a", "b", "a"])) == ["a", "b"]

    def test_apply_disabled_tools_enable_overwrites(self, adapter):
        server = {"id": "s1", "disabled_tools": ["old"]}
        adapter._apply_disabled_tools(server, ["new"], enable=True)
        assert server["disabled_tools"] == ["new"]

    def test_apply_disabled_tools_disable_new_list(self, adapter):
        server = {"id": "s1"}
        adapter._apply_disabled_tools(server, ["tool_a"], enable=False)
        assert server["disabled_tools"] == ["tool_a"]

    def test_apply_disabled_tools_disable_extends(self, adapter):
        server = {"id": "s1", "disabled_tools": ["tool_a"]}
        adapter._apply_disabled_tools(server, ["tool_b"], enable=False)
        assert server["disabled_tools"] == ["tool_a", "tool_b"]

    def test_apply_disabled_tools_all_clears_existing(self, adapter):
        server = {"id": "s1", "disabled_tools": ["tool_a"]}
        adapter._apply_disabled_tools(server, ["all"], enable=False)
        assert server["disabled_tools"] == ["all"]

    def test_apply_disabled_tools_duplicate_raises(self, adapter):
        server = {"id": "s1", "disabled_tools": ["tool_a"]}
        with pytest.raises(ToolDuplicateError, match="already removed"):
            adapter._apply_disabled_tools(server, ["tool_a"], enable=False)

    def test_apply_disabled_tools_empty_list_no_op_on_existing(self, adapter):
        server = {"id": "s1", "disabled_tools": ["tool_a"]}
        adapter._apply_disabled_tools(server, [], enable=False)
        assert server["disabled_tools"] == ["tool_a"]

    def test_apply_disabled_tools_empty_list_sets_empty(self, adapter):
        server = {"id": "s1"}
        adapter._apply_disabled_tools(server, [], enable=False)
        assert server["disabled_tools"] == []

    def test_apply_disabled_tools_empty_list_enable_clears(self, adapter):
        server = {"id": "s1", "disabled_tools": ["tool_a"]}
        adapter._apply_disabled_tools(server, [], enable=True)
        assert server["disabled_tools"] == []

    def test_disable_all_keyword_constant(self, adapter):
        server = {"id": "s1", "disabled_tools": ["tool_a"]}
        adapter._apply_disabled_tools(
            server, [BaseDatabaseAdapter.DISABLE_ALL_KEYWORD], enable=False
        )
        assert server["disabled_tools"] == [BaseDatabaseAdapter.DISABLE_ALL_KEYWORD]

    def test_apply_disabled_named_items_does_not_support_all_keyword(self, adapter):
        server = {"id": "s1", "disabled_prompts": ["p1"]}
        adapter._apply_disabled_named_items(
            server,
            "disabled_prompts",
            "prompts_description",
            ["all"],
            "Prompt",
        )
        assert "all" in server["disabled_prompts"]
        assert "p1" in server["disabled_prompts"]

    def test_apply_disabled_named_items_removes_descriptions(self, adapter):
        server = {
            "id": "s1",
            "prompts_description": {"p1": "desc", "p2": "keep"},
        }
        adapter._apply_disabled_named_items(
            server, "disabled_prompts", "prompts_description", ["p1"], "Prompt"
        )
        assert server["disabled_prompts"] == ["p1"]
        assert "p1" not in server["prompts_description"]
        assert server["prompts_description"]["p2"] == "keep"

    def test_apply_disabled_named_items_duplicate_raises(self, adapter):
        server = {"id": "s1", "disabled_resources": ["r1"]}
        with pytest.raises(ToolDuplicateError, match="already disabled"):
            adapter._apply_disabled_named_items(
                server,
                "disabled_resources",
                "resources_description",
                ["r1"],
                "Resource",
            )

    def test_apply_enabled_named_items(self, adapter):
        server = {"id": "s1", "disabled_prompts": ["old"]}
        adapter._apply_enabled_named_items(server, "disabled_prompts", ["new"])
        assert server["disabled_prompts"] == ["new"]

    def test_apply_tool_description_updates_existing(self, adapter):
        server = {"id": "s1", "tools_description": {"t1": "old"}}
        adapter._apply_tool_description(server, "t1", "updated")
        assert server["tools_description"]["t1"] == "updated"

    def test_apply_tool_description_creates_dict(self, adapter):
        server = {"id": "s1"}
        adapter._apply_tool_description(server, "t1", "desc")
        assert server["tools_description"] == {"t1": "desc"}

    def test_default_server_status(self):
        assert BaseDatabaseAdapter._default_server_status({}) == "active"
        assert (
            BaseDatabaseAdapter._default_server_status({"status": "deactivated"})
            == "deactivated"
        )

    def test_require_server_id_valid(self):
        assert BaseDatabaseAdapter._require_server_id({"id": "s1"}) == "s1"

    def test_require_server_id_missing_raises(self):
        with pytest.raises(ValueError, match="'id' field"):
            BaseDatabaseAdapter._require_server_id({})

    def test_new_composer_server_stub(self):
        stub = BaseDatabaseAdapter._new_composer_server_stub(
            "s1", disabled_tools=["t1"]
        )
        assert stub == {"id": "s1", "type": "composer", "disabled_tools": ["t1"]}

    def test_json_round_trip(self):
        data = {"id": "s1", "status": "active"}
        serialized = BaseDatabaseAdapter._serialize_json(data)
        assert BaseDatabaseAdapter._deserialize_json(serialized) == data

    def test_parse_config_from_dict(self):
        data = {"id": "s1"}
        assert BaseDatabaseAdapter._parse_config(data) == data

    def test_parse_config_from_json_string(self):
        assert BaseDatabaseAdapter._parse_config('{"id": "s1"}') == {"id": "s1"}

    def test_parse_config_none_raises(self):
        with pytest.raises(ValueError, match="cannot be None"):
            BaseDatabaseAdapter._parse_config(None)

    def test_parse_config_unexpected_type_raises(self):
        with pytest.raises(TypeError, match="Expected str or dict"):
            BaseDatabaseAdapter._parse_config(123)

    def test_deserialize_json_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            BaseDatabaseAdapter._deserialize_json("not-json")
