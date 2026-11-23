"""Enforce disabled prompts and resources on the composed request paths."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import PromptError, ResourceError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from mcp_composer.core.utils.logger import LoggerFactory

if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer

logger = LoggerFactory.get_logger()

# Mounted resources are exposed as ``scheme://<member-id>/<path>``.
_MEMBER_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://([^/]+)")


class DisabledPromptsResourcesMiddleware(Middleware):
    """Reject disabled member prompts and resources.

    ``MCPComposer`` overrides the list methods and serves them from its own
    managers, so mounted members never show up there, but ``get_prompt`` and
    ``read_resource`` still resolve them by name or URI. This middleware is
    where those two requests are enforced.

    The deny lists are read on every request, so ``disable_prompts`` and
    ``disable_resources`` take effect immediately. Entries may be stored
    unprefixed (member configuration) or as ``f"{member.id}_{name}"`` (the
    management tools); both forms are honoured. Unhealthy members are not
    skipped: a deny list that stops applying when a member is unhealthy would
    fail open.
    """

    def __init__(self, composer: MCPComposer) -> None:
        self._composer = composer

    def _members(self) -> list[Any]:
        # pylint: disable=protected-access
        return list(self._composer._server_manager.list())

    @staticmethod
    def _matches(entries: list[str], member_id: str, name: str) -> bool:
        """True if ``name`` (unprefixed) is listed in either stored form."""
        prefix = f"{member_id}_"
        wanted = name.lower()
        for entry in entries:
            entry_l = str(entry).lower()
            if entry_l == wanted or entry_l == f"{prefix}{wanted}".lower():
                return True
        return False

    def _prompt_denied(self, composed_name: str) -> bool:
        for member in self._members():
            prefix = f"{member.id}_"
            if not composed_name.startswith(prefix):
                continue
            if self._matches(
                member.disabled_prompts, member.id, composed_name[len(prefix) :]
            ):
                return True
        return False

    async def _resource_name(self, uri: str) -> str | None:
        # Resolve through the composer, as the server does when reading.
        for lookup in (
            self._composer.get_resource,
            self._composer.get_resource_template,
        ):
            try:
                found = await lookup(uri)
            except Exception:  # pylint: disable=broad-except
                found = None
            if found is not None:
                return getattr(found, "name", None)
        return None

    async def _resource_denied(self, uri: str) -> bool:
        match = _MEMBER_URI.match(uri)
        if not match:
            return False
        authority = match.group(1)
        members = [m for m in self._members() if m.id == authority]
        if not members or not any(m.disabled_resources for m in members):
            return False
        name = await self._resource_name(uri)
        for member in members:
            if uri in member.disabled_resources:
                return True
            if name and self._matches(member.disabled_resources, member.id, name):
                return True
        return False

    async def on_list_prompts(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        prompts = await call_next(context)
        return [p for p in prompts if not self._prompt_denied(p.name)]

    async def on_get_prompt(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        name = context.message.name
        if self._prompt_denied(name):
            logger.warning("Rejected request for disabled prompt '%s'", name)
            raise PromptError(f"Prompt '{name}' is disabled")
        return await call_next(context)

    async def on_read_resource(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        uri = str(context.message.uri)
        if await self._resource_denied(uri):
            logger.warning("Rejected read of disabled resource '%s'", uri)
            raise ResourceError(f"Resource '{uri}' is disabled")
        return await call_next(context)
