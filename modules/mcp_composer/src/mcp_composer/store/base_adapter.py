"""Base database adapter with shared server-config mutation logic."""

from __future__ import annotations

import json
from typing import Any

from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.tools import check_duplicate_tool

from .database import DatabaseInterface

logger = LoggerFactory.get_logger()


class BaseDatabaseAdapter(DatabaseInterface):
    """Shared helpers for server-config mutations across storage backends."""

    # Sentinel value for disable_tools only: a single-item list ["all"] resets
    # the disabled-tools list. Prompts and resources do not support this keyword.
    DISABLE_ALL_KEYWORD = "all"

    @staticmethod
    def _dedupe_list(items: list[str]) -> list[str]:
        """Return a de-duplicated copy of the input list."""
        return list(set(items))

    @staticmethod
    def _ensure_list(value: object) -> list[Any]:
        """Return value when it is already a list, otherwise an empty list."""
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def _extend_or_set_list(
        server: dict[str, Any], field: str, items: list[str]
    ) -> None:
        """Append items to an existing list field, or assign when the field is empty."""
        existing_items = BaseDatabaseAdapter._ensure_list(server.get(field, []))
        if existing_items:
            disabled_items = server.get(field)
            if isinstance(disabled_items, list):
                disabled_items.extend(items)
        else:
            server[field] = items

    @staticmethod
    def _remove_disabled_item_descriptions(
        disabled_items: object,
        descriptions: dict[str, Any],
    ) -> None:
        """Remove description entries for every item in the disabled list."""
        if not disabled_items or not descriptions:
            return
        if not isinstance(disabled_items, list):
            return
        for item in disabled_items:
            descriptions.pop(item, None)

    def _apply_disabled_tools(
        self, server: dict[str, Any], tools: list[str], enable: bool
    ) -> None:
        """Update the disabled_tools list on a server config dict.

        When enable is True, the list is replaced entirely. When enable is False,
        new tools are appended unless the request is a single ``DISABLE_ALL_KEYWORD``
        entry (case-insensitive), which replaces any existing disabled-tools list.
        That keyword is intentionally supported for tools only, not prompts/resources.
        """
        tools = self._dedupe_list(tools)
        if enable:
            server["disabled_tools"] = tools
            return

        if len(tools) == 1 and tools[0].lower() == self.DISABLE_ALL_KEYWORD:
            server["disabled_tools"] = tools
            return

        existing_tools = self._ensure_list(server.get("disabled_tools", []))

        duplicate_tool = check_duplicate_tool(existing_tools, tools)
        if duplicate_tool:
            raise ToolDuplicateError(f"Tool {duplicate_tool} is already removed")

        self._extend_or_set_list(server, "disabled_tools", tools)

    def _apply_disabled_named_items(
        self,
        server: dict[str, Any],
        field: str,
        description_field: str,
        items: list[str],
        item_label: str,
    ) -> None:
        """Append items to a disabled list field and prune matching descriptions.

        Used for disabled_prompts and disabled_resources. Does not support the
        ``DISABLE_ALL_KEYWORD`` sentinel; use enable_* methods to replace lists.
        """
        items = self._dedupe_list(items)
        existing_items = self._ensure_list(server.get(field, []))
        descriptions = server.get(description_field, {})
        if not isinstance(descriptions, dict):
            descriptions = {}
            server[description_field] = descriptions

        duplicate = check_duplicate_tool(existing_items, items)
        if duplicate:
            raise ToolDuplicateError(f"{item_label} {duplicate} is already disabled")

        self._extend_or_set_list(server, field, items)
        self._remove_disabled_item_descriptions(server.get(field), descriptions)

    def _apply_enabled_named_items(
        self, server: dict[str, Any], field: str, items: list[str]
    ) -> None:
        """Replace a disabled list field with the given items."""
        server[field] = self._dedupe_list(items)

    def _apply_tool_description(
        self, server: dict[str, Any], tool: str, description: str
    ) -> None:
        """Set or update a tool description on a server config dict."""
        tools_description = server.get("tools_description")
        if tools_description and isinstance(tools_description, dict):
            tools_description.update({tool: description})
        else:
            server["tools_description"] = {tool: description}

    @staticmethod
    def _default_server_status(config: dict[str, Any]) -> str:
        """Return server status, defaulting to active when unset."""
        return str(config.get("status", "active"))

    @staticmethod
    def _require_server_id(config: dict[str, Any]) -> str:
        """Return the server id from config or raise ValueError if missing."""
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Server config must contain an 'id' field")
        return str(server_id)

    @staticmethod
    def _new_composer_server_stub(
        server_id: str, **fields: object
    ) -> dict[str, object]:
        """Build a minimal composer server document for create-if-missing paths."""
        stub: dict[str, object] = {"id": server_id, "type": "composer"}
        stub.update(fields)
        return stub

    @staticmethod
    def _serialize_json(data: dict[str, Any]) -> str:
        """Serialize a config dict to a JSON string."""
        return json.dumps(data)

    @staticmethod
    def _deserialize_json(raw: str) -> dict[str, Any]:
        """Deserialize a JSON string to a config dict."""
        return json.loads(raw)

    @staticmethod
    def _parse_config(config_data: str | dict[str, Any] | None) -> dict[str, Any]:
        """Parse config data from a JSON string or dict."""
        if config_data is None:
            raise ValueError("Config data cannot be None")
        if isinstance(config_data, str):
            return json.loads(config_data)
        if isinstance(config_data, dict):
            return config_data
        raise TypeError(
            f"Expected str or dict for config data, got {type(config_data).__name__}"
        )
