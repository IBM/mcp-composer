"""
Catalog Composer — skill, agent, and workflow catalog MCP surfaces only.

Use this process when you need catalog management tools without product-specific
auth middleware.

Environment variables:
- MCP_ENABLE_SKILL_CATALOG_MCP: true|false (default true)
- MCP_ENABLE_AGENT_CATALOG_MCP: true|false (default true)
- MCP_ENABLE_WORKFLOW_CATALOG_MCP: true|false (default true)
- MCP_SKILL_CATALOG_LAYERED: true|false (default false) — when true, skill-catalog
  ``list_skills`` uses category-first browse (see MCP server instructions in
  ``skill_catalog_mcp.py``)
- MCP_COMPOSER_TENANT_ID, MCP_COMPOSER_ALLOWED_TOOLS,
  MCP_COMPOSER_SKILL_REFRESH_INTERVAL_SECS — startup skill loader (optional)
- MCP_WORKFLOW_FILES_SYNC: true|false (default true) — publish
  resources/workflows/workflows_*.json bundles to catalog on startup
- MCP_WORKFLOW_FILES_DIR: optional path to workflow JSON directory
- MCP_MODE: http | sse | stdio (default sse)
"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from typing import Iterable

from mcp_composer import MCPComposer
from mcp_composer.core.catalog import CatalogResourceListFilter, SkillManager
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.tools.catalog import (
    get_agent_mcp,
    get_skill_mcp,
    get_workflow_mcp,
)
from mcp_composer.core.tools.catalog.workflow_catalog_mcp import (
    bootstrap_workflow_catalog_from_env,
)
from mcp_composer.core.utils import env_bool_flag
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.store.catalog_factory import get_catalog_db

_log_level = (os.getenv("MCP_COMPOSER_LOG_LEVEL") or "INFO").strip().upper()
logger = LoggerFactory.get_logger(level=_log_level)

_enable_skill_catalog_mcp = env_bool_flag("MCP_ENABLE_SKILL_CATALOG_MCP", default=True)
_enable_agent_catalog_mcp = env_bool_flag("MCP_ENABLE_AGENT_CATALOG_MCP", default=True)
_enable_workflow_catalog_mcp = env_bool_flag(
    "MCP_ENABLE_WORKFLOW_CATALOG_MCP", default=True
)

gw = MCPComposer(name="catalog-composer", auth=None)
_startup_skill_loader_task: asyncio.Task | None = None
_startup_skill_loader: StartupSkillLoader | None = None


def _parse_csv_set(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item and item.strip()}


def _skill_allowed_for_tools(
    skill_allowed_tools: Iterable[str] | None, agent_allowed_tools: set[str]
) -> bool:
    if not agent_allowed_tools:
        return True
    if not skill_allowed_tools:
        return True
    if isinstance(skill_allowed_tools, (set, frozenset)):
        return bool(skill_allowed_tools.intersection(agent_allowed_tools))
    return any(tool in agent_allowed_tools for tool in skill_allowed_tools)


class StartupSkillLoader:
    """Polls load-onstartup skills for runtime refresh."""

    def __init__(self) -> None:
        self._manager = SkillManager(get_catalog_db())
        self._tenant_id = (os.getenv("MCP_COMPOSER_TENANT_ID") or "").strip() or None
        self._agent_allowed_tools = _parse_csv_set(
            os.getenv("MCP_COMPOSER_ALLOWED_TOOLS")
        )
        self._refresh_interval = int(
            os.getenv("MCP_COMPOSER_SKILL_REFRESH_INTERVAL_SECS", "30")
        )
        self._loaded_skill_keys: set[tuple[str, str]] = set()

    async def _load_once(self) -> None:
        result = await self._manager.list(
            CatalogResourceListFilter(
                kind=RegistryResourceKind.SKILL,
                is_latest_only=True,
                status_filter="load-onstartup",
                tenant=self._tenant_id,
                limit=1000,
            )
        )
        filtered = [
            item
            for item in result.skills
            if _skill_allowed_for_tools(
                item.skill.allowed_tools, self._agent_allowed_tools
            )
        ]
        loaded_now = {(item.skill.name, item.skill.version) for item in filtered}
        if loaded_now != self._loaded_skill_keys:
            logger.info(
                "Startup skills refreshed: %d loaded (tenant=%s)",
                len(loaded_now),
                self._tenant_id or "all",
            )
            self._loaded_skill_keys = loaded_now

    async def run_forever(self) -> None:
        while True:
            try:
                await self._load_once()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Startup skill refresh failed: %s", exc)
            await asyncio.sleep(max(self._refresh_interval, 5))

    async def close(self) -> None:
        await self._manager.close()


async def setup_catalog_mcp(composer: MCPComposer) -> None:
    """Mount catalog MCP sub-servers and start the optional startup skill poller."""
    global _startup_skill_loader_task, _startup_skill_loader

    if _enable_skill_catalog_mcp:
        composer.mount(get_skill_mcp(), "")
        logger.info("Skill catalog MCP mounted")
    else:
        logger.info("Skill catalog MCP skipped")

    if _enable_agent_catalog_mcp:
        composer.mount(get_agent_mcp(), "agent-catalog")
        logger.info("Agent catalog MCP mounted")
    else:
        logger.info("Agent catalog MCP skipped")

    if _enable_workflow_catalog_mcp:
        composer.mount(get_workflow_mcp(), "")
        sync_result = await bootstrap_workflow_catalog_from_env()
        if sync_result:
            logger.info(
                "Workflow file sync complete: published=%d directory=%s",
                sync_result.get("published_count", 0),
                sync_result.get("directory"),
            )
        logger.info("Workflow catalog MCP mounted")
    else:
        logger.info("Workflow catalog MCP skipped")

    _startup_skill_loader = StartupSkillLoader()
    await _startup_skill_loader._load_once()
    _startup_skill_loader_task = asyncio.create_task(
        _startup_skill_loader.run_forever()
    )
    logger.info("Startup skill loader started")


async def run_http_mode(composer: MCPComposer) -> None:
    await composer.run_http_async(
        host="127.0.0.1", port=9000, log_level="debug", path="/mcp"
    )


async def run_stdio_mode(composer: MCPComposer) -> None:
    logger.info("Catalog Composer STDIO")
    await composer.run_stdio_async()


async def run_sse_mode(composer: MCPComposer) -> None:
    await composer.run_async(
        transport="sse", host="127.0.0.1", port=9000, log_level="debug"
    )


MODE_HANDLERS = {
    "http": run_http_mode,
    "stdio": run_stdio_mode,
    "sse": run_sse_mode,
}


async def run_composer_mode(composer: MCPComposer, mode: str) -> None:
    handler = MODE_HANDLERS.get(mode)
    if not handler:
        raise ValueError(f"Unsupported MCP_MODE: {mode}. Use 'http', 'sse', or 'stdio'")
    await handler(composer)


async def main() -> None:
    mode = os.getenv("MCP_MODE", "sse").lower()
    logger.info(
        "Starting Catalog Composer in %s mode | skill=%s agent=%s workflow=%s",
        mode,
        _enable_skill_catalog_mcp,
        _enable_agent_catalog_mcp,
        _enable_workflow_catalog_mcp,
    )

    try:
        await setup_catalog_mcp(gw)
        await gw.setup_member_servers()
        logger.info("Member servers setup complete")
        await run_composer_mode(gw, mode)
    finally:
        if _startup_skill_loader_task is not None:
            _startup_skill_loader_task.cancel()
            with suppress(asyncio.CancelledError):
                await _startup_skill_loader_task
        if _startup_skill_loader is not None:
            await _startup_skill_loader.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Catalog Composer stopped by user")
    except Exception as e:
        logger.error("Catalog Composer failed: %s", e, exc_info=True)
        raise
