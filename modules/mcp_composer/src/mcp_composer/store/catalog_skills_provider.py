"""catalog_skills_provider.py — DB-backed FastMCP Provider for the skill catalog.

Implements agentskills.io progressive disclosure Level 3:

    Level 1 — catalog_list_skills()       → name + description (~100 tokens)
    Level 2 — catalog_get_skill(name)     → full payload + instructions (<5 000 tokens)
    Level 3 — skill://{name}/SKILL.md     → raw content stored in DB (references,
                                            scripts, extended docs — no token limit)

This Provider exposes every active+latest skill as two MCP resources:

    skill://{name}/SKILL.md        — Markdown file (frontmatter + instructions body)
    skill://{name}/_manifest       — JSON manifest (name, version, status, products, tags)

Usage
-----
Register once when building your FastMCP server::

    from fastmcp import FastMCP
    from catalog_skills_provider import CatalogSkillsProvider

    mcp = FastMCP(
        "skill-catalog",
        providers=[CatalogSkillsProvider()],
    )

The provider uses the same ``get_catalog_db()`` factory as the rest of the app,
so it picks up MCP_DATABASE_TYPE / MCP_DATABASE_URL from the environment.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

from fastmcp import FastMCP
from fastmcp.server.providers.base import Provider
from fastmcp.resources import Resource, TextResource

from mcp_composer.store.catalog_factory import get_catalog_db
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.catalog.skill_manager import SkillManager


# ── helpers ───────────────────────────────────────────────────────────────────


def _frontmatter(data: dict) -> str:
    """Render a dict as YAML frontmatter block (--- ... ---).

    Falls back to a simple key: value format when PyYAML is not installed.
    """
    if _HAS_YAML:
        body = yaml.dump(data, default_flow_style=False, allow_unicode=True).strip()
    else:
        lines = []
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        body = "\n".join(lines)
    return f"---\n{body}\n---\n"


def _render_skill_md(payload: dict, official_meta: dict) -> str:
    """Render a skill DB payload as a SKILL.md string.

    Structure::

        ---
        name: ...
        version: ...
        status: ...
        title: ...
        category: ...
        products: [...]
        tags: [...]
        ---

        {description}

        {metadata.instructions}
    """
    metadata: dict = payload.get("metadata") or {}

    front: dict = {
        "name": payload.get("name", ""),
        "version": payload.get("version", ""),
        "status": official_meta.get("status") or payload.get("status") or "active",
        "title": metadata.get("title") or payload.get("name", ""),
        "category": metadata.get("category", ""),
        "products": metadata.get("products") or [],
        "tags": metadata.get("tags") or [],
        "author": metadata.get("author", ""),
        "license": payload.get("license", ""),
        "isLatest": official_meta.get("is_latest", False),
        "publishedAt": official_meta.get("published_at", ""),
        "updatedAt": official_meta.get("updated_at", ""),
    }
    # Remove empty/falsy values to keep frontmatter tidy
    front = {k: v for k, v in front.items() if v not in (None, "", [], False, 0)}

    parts = [_frontmatter(front)]

    description = payload.get("description", "")
    if description:
        parts.append(description + "\n")

    instructions = metadata.get("instructions", "")
    if instructions:
        parts.append("\n" + instructions + "\n")

    # Append websiteUrl / repository / references / remotes as reference section
    extras: list[str] = []
    if payload.get("websiteUrl"):
        extras.append(f"- Docs: {payload['websiteUrl']}")
    if payload.get("repository"):
        repo = payload["repository"]
        rurl = repo.get("url", "")
        rsrc = repo.get("source")
        if rsrc:
            extras.append(f"- Repository: {rurl} ({rsrc})")
        else:
            extras.append(f"- Repository: {rurl}")
    if payload.get("references"):
        for ref in payload["references"]:
            fn = ref.get("file", "")
            u = ref.get("url", "")
            if fn and u:
                extras.append(f"- {fn}: {u}")
            elif u:
                extras.append(f"- {u}")
    if payload.get("remotes"):
        for r in payload["remotes"]:
            extras.append(f"- Remote MCP: {r.get('url', '')}")
    if extras:
        parts.append("\n## References\n" + "\n".join(extras) + "\n")

    return "\n".join(parts)


def _render_manifest(payload: dict, official_meta: dict) -> str:
    """Render a compact JSON manifest for the skill."""
    metadata: dict = payload.get("metadata") or {}
    manifest = {
        "name": payload.get("name"),
        "version": payload.get("version"),
        "status": official_meta.get("status") or payload.get("status") or "active",
        "isLatest": official_meta.get("is_latest", False),
        "title": metadata.get("title"),
        "category": metadata.get("category"),
        "products": metadata.get("products") or [],
        "tags": metadata.get("tags") or [],
        "author": metadata.get("author"),
        "license": payload.get("license"),
        "websiteUrl": payload.get("websiteUrl"),
        "allowedTools": payload.get("allowed-tools") or [],
        "publishedAt": official_meta.get("published_at"),
        "updatedAt": official_meta.get("updated_at"),
    }
    return json.dumps({k: v for k, v in manifest.items() if v is not None}, indent=2)


# ── Resource types ────────────────────────────────────────────────────────────


class SkillMarkdownResource(TextResource):
    """A skill rendered as a SKILL.md MCP TextResource."""


class SkillManifestResource(TextResource):
    """A skill's JSON manifest exposed as an MCP TextResource."""


# ── Provider ──────────────────────────────────────────────────────────────────


class CatalogSkillsProvider(Provider):
    """FastMCP Provider that exposes the skill catalog as MCP resources.

    Each active+latest skill is served at two URIs:

        skill://{name}/SKILL.md     — Markdown (frontmatter + description + instructions)
        skill://{name}/_manifest    — JSON compact manifest

    The provider manages its own asyncpg pool via the standard ``get_catalog_db()``
    factory.  The pool is opened when the FastMCP server starts and closed on shutdown.
    """

    def __init__(self) -> None:
        super().__init__()
        self._db = get_catalog_db()
        self._mgr: SkillManager | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Open/close the DB pool around the server lifespan."""
        self._mgr = SkillManager(self._db)
        await self._db.initialize()
        try:
            yield
        finally:
            await self._db.close()
            self._mgr = None

    # ── resource listing ──────────────────────────────────────────────────────

    async def _list_resources(self) -> list[Resource]:
        """Return one SKILL.md + one _manifest resource per active+latest skill."""
        if self._mgr is None:
            # Not yet initialized (e.g. during tests without a running server).
            await self._db.initialize()
            self._mgr = SkillManager(self._db)

        result = await self._mgr.list(
            CatalogResourceListFilter(
                kind=RegistryResourceKind.SKILL,
                is_latest_only=True,
                status_filter="active",
                limit=1000,
            )
        )

        resources: list[Resource] = []
        for item in result.skills:
            skill = item.skill
            official_meta = (
                item.meta.official.model_dump(mode="json")
                if item.meta and item.meta.official
                else {}
            )
            payload = skill.model_dump(mode="json", by_alias=False, exclude_none=True)

            name = skill.name
            title = (skill.metadata or {}).get("title") or name

            resources.append(
                SkillMarkdownResource(
                    uri=f"skill://{name}/SKILL.md",  # type: ignore[arg-type]
                    name=f"{title} — SKILL.md",
                    description=(
                        f"Full skill spec for {name} (description + instructions). "
                        f"Fetch this for Level 3 progressive disclosure."
                    ),
                    text=_render_skill_md(payload, official_meta),
                    mime_type="text/markdown",
                )
            )
            resources.append(
                SkillManifestResource(
                    uri=f"skill://{name}/_manifest",  # type: ignore[arg-type]
                    name=f"{title} — manifest",
                    description=(
                        f"JSON manifest for {name}: name, version, status, products, tags."
                    ),
                    text=_render_manifest(payload, official_meta),
                    mime_type="application/json",
                )
            )

        return resources

    # ── resource retrieval ────────────────────────────────────────────────────

    async def _get_resource(self, uri: str, version: str | None = None) -> Resource | None:  # type: ignore[override]
        """Return the resource for *uri*, or None if not found.

        Supports:
            skill://{name}/SKILL.md
            skill://{name}/_manifest
        """
        if not uri.startswith("skill://"):
            return None

        # Parse  skill://{name}/{suffix}
        rest = uri[len("skill://") :]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return None
        name, suffix = parts[0], parts[1]

        if self._mgr is None:
            await self._db.initialize()
            self._mgr = SkillManager(self._db)

        try:
            skill_resp = await self._mgr.get_latest(name)
        except Exception:
            return None

        skill = skill_resp.skill
        official_meta = (
            skill_resp.meta.official.model_dump(mode="json")
            if skill_resp.meta and skill_resp.meta.official
            else {}
        )
        payload = skill.model_dump(mode="json", by_alias=False, exclude_none=True)
        title = (skill.metadata or {}).get("title") or name

        if suffix == "SKILL.md":
            # Prefer stored content column (Level 3 raw asset) if present.
            stored_content = await self._mgr.get_content(name)
            text = (
                stored_content
                if stored_content
                else _render_skill_md(payload, official_meta)
            )
            return SkillMarkdownResource(
                uri=uri,  # type: ignore[arg-type]
                name=f"{title} — SKILL.md",
                description=f"Full skill spec for {name}.",
                text=text,
                mime_type="text/markdown",
            )

        if suffix == "_manifest":
            return SkillManifestResource(
                uri=uri,  # type: ignore[arg-type]
                name=f"{title} — manifest",
                description=f"JSON manifest for {name}.",
                text=_render_manifest(payload, official_meta),
                mime_type="application/json",
            )

        return None


# ── Convenience factory ───────────────────────────────────────────────────────


def build_catalog_mcp() -> FastMCP:
    """Return a FastMCP server with the skill catalog MCP tools AND the skills Provider.

    Mount this into your MCPComposer::

        composer.mount(build_catalog_mcp(), namespace="catalog")

    Or run it standalone::

        mcp = build_catalog_mcp()
        mcp.run()
    """
    from mcp_composer.core.tools.catalog.skill_catalog_mcp import catalog_mcp

    # Attach the provider to the existing catalog_mcp singleton.
    # FastMCP 3.1+ accepts providers= at construction time or via add_provider().
    try:
        catalog_mcp.add_provider(CatalogSkillsProvider())
    except AttributeError:
        # Older FastMCP — providers must be passed at construction; warn and skip.
        import warnings

        warnings.warn(
            "FastMCP < 3.1 detected — CatalogSkillsProvider requires add_provider(). "
            "Upgrade fastmcp to >=3.1.0 for Level 3 resource support.",
            stacklevel=2,
        )
    return catalog_mcp
