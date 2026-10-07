"""skill_catalog_mcp.py — Thin MCP tools for the skill catalog.

All database access is mediated exclusively through ``_skill_manager``.
The module-level singleton pattern mirrors the weather_mcp example:

    catalog_mcp = FastMCP("skill-catalog")
    _skill_manager = SkillManager(get_catalog_db())

Any composer mounts this server in one line:

    composer.mount(get_catalog_mcp(), namespace="catalog")

No explicit initialisation step is needed — ``SkillManager`` opens the
DB pool lazily on the first async call.  FastMCP's mount() is a live
link: no remount is needed when the underlying data changes.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx
from fastmcp import FastMCP
from mcp_composer.core.catalog import (
    CatalogResourceListFilter,
    CatalogResourceNotFoundError,
    CatalogVersionCapError,
    InvalidCatalogResourceStatusError,
    SkillManager,
)
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.models.catalog_skill import SkillJSON, SkillResponse
from mcp_composer.core.utils.catalog_validators import validate_agentskills_instructions
from mcp_composer.store.catalog_factory import get_catalog_db
from mcp_composer.store.catalog_skills_provider import CatalogSkillsProvider

# Layered category browse is enabled only when the MCP process sets this env (see server instructions).
_SKILL_CATALOG_LAYERED_ENV = "MCP_SKILL_CATALOG_LAYERED"
_TRUTHY_ENV = frozenset({"true", "1", "yes", "on"})


def _skill_catalog_layered_from_env() -> bool:
    raw = (os.getenv(_SKILL_CATALOG_LAYERED_ENV) or "").strip().lower()
    return raw in _TRUTHY_ENV


# ── module-level singletons ───────────────────────────────────────────────────
# _skill_manager is the only entry point to the DB from this module.
_skill_manager = SkillManager(get_catalog_db())

_catalog_mcp_instructions = """This MCP server exposes the skill catalog.

Main tools:
1. **list_skills** - Browse and search (compact rows by default; verbose=true for full rows)
2. **get_skill** - Full skill JSON by name (optional version; default latest)
3. **load_skill_reference** - One reference file by basename (HTTPS allowlist)

Usage workflow:
1. list_skills to find candidates
2. get_skill(name) to load the document before acting on it
3. load_skill_reference(name, file) when a listed reference body is needed
4. Follow that skill's instructions and allowed-tools for the user task

list_skills: flat pagination by default. If MCP_SKILL_CATALOG_LAYERED is set on this process, first call without category returns categories; then call with category for skills in that category.
"""

catalog_mcp = FastMCP(
    "skill-catalog",
    instructions=_catalog_mcp_instructions,
)

catalog_mcp.add_provider(CatalogSkillsProvider())  # ← add here, stays in catalog module


def get_skill_mcp() -> FastMCP:
    """Return the module-level catalog FastMCP instance (zero-arg, composable)."""
    return catalog_mcp


# ── skill reference fetch (allowlisted HTTPS only) ────────────────────────────

_MAX_REFERENCE_BODY_BYTES = 2 * 1024 * 1024
_REFERENCE_HTTP_TIMEOUT = 30.0
_MAX_VALID_FILES_IN_ERROR = 40


def _collect_reference_entries(resp: SkillResponse) -> list[dict[str, str]]:
    """Merge ``skill.references`` with optional ``_meta.metadata.references``; dedupe by (url, file)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for ref in resp.skill.references or []:
        u, f = ref.url.strip(), ref.file.strip()
        if not u or not f:
            continue
        key = (u, f)
        if key not in seen:
            seen.add(key)
            out.append({"url": u, "file": f})
    meta = resp.meta.metadata if resp.meta else None
    if isinstance(meta, dict):
        extra = meta.get("references")
        if isinstance(extra, list):
            for item in extra:
                if not isinstance(item, dict):
                    continue
                url_val = item.get("url")
                file_val = item.get("file")
                if not isinstance(url_val, str) or not isinstance(file_val, str):
                    continue
                u, f = url_val.strip(), file_val.strip()
                if not u or not f:
                    continue
                key = (u, f)
                if key not in seen:
                    seen.add(key)
                    out.append({"url": u, "file": f})
    return out


def _validate_reference_file_arg(file_arg: str) -> str:
    """Require a basename only (no path segments or ``..``)."""
    f = file_arg.strip()
    if not f:
        raise ValueError("file is a required field")
    if ".." in f or "/" in f or "\\" in f:
        raise ValueError("file must be a basename only (e.g. finops-aws.md), not a path")
    return f


def _find_reference_url(entries: list[dict[str, str]], file_key: str) -> tuple[str, str]:
    """Return (url, matched_file) for the entry whose ``file`` equals ``file_key``."""
    for e in entries:
        if e["file"] == file_key:
            return e["url"], e["file"]
    raise ValueError(
        f"No reference named {file_key!r} for this skill. "
        f"Valid files: {_format_valid_files_hint(entries)}"
    )


def _format_valid_files_hint(entries: list[dict[str, str]]) -> str:
    names = [e["file"] for e in entries]
    if len(names) <= _MAX_VALID_FILES_IN_ERROR:
        return ", ".join(names) if names else "(none)"
    return ", ".join(names[:_MAX_VALID_FILES_IN_ERROR]) + ", …"


async def _https_get_text_allowlisted(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https:// URLs are allowed for skill references")
    async with httpx.AsyncClient(
        timeout=_REFERENCE_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > _MAX_REFERENCE_BODY_BYTES:
                    raise ValueError(
                        f"Reference body exceeds maximum size ({_MAX_REFERENCE_BODY_BYTES} bytes)"
                    )
                chunks.append(chunk)
    raw = b"".join(chunks)
    return raw.decode("utf-8", errors="replace")


# ── tools ─────────────────────────────────────────────────────────────────────


@catalog_mcp.tool()
async def list_skills(
    keywords: str | None = None,
    tenant: str | None = None,
    offset: int = 0,
    limit: int = 50,
    verbose: bool = False,
    category: str | None = None,
) -> dict:
    """Search and browse skills in the catalog.
    Returns a page of active, latest skill records.  All parameters are
    optional — calling with no arguments returns the first 50 active skills
    sorted alphabetically by name.
    See the **skill-catalog** MCP server ``instructions`` for **flat** vs **layered**
    discovery. Layered mode (category index, then skills per category) is enabled
    only when the host sets ``MCP_SKILL_CATALOG_LAYERED``; there is no ``layered``
    parameter on this tool.

    Layered mode (when ``MCP_SKILL_CATALOG_LAYERED`` is truthy in the environment)
    -------------------------------------------------------------------------------
    1. ``catalog_list_skills()`` with no ``category`` — returns ``categories`` (each
       with ``name`` and ``skill_count``). Skills missing ``metadata.category`` are
       grouped under ``(uncategorized)``.
    2. ``catalog_list_skills(category="<name from step 1>")`` — same shape as the flat
       list, but only skills in that category. Then ``catalog_get_skill(name)`` for
       one skill's full document.

    **Flat mode (default env):** single-step paginated skill list. You may still pass
    ``category`` to filter by category without using the category-index hop.

    Response shape (``verbose``)
    ---------------------------
    - ``verbose=false`` (default): each element of ``skills`` is a small object
      ``{ "name", "description", "tags", "category" }`` where ``tags`` comes from
      ``metadata.tags`` and ``category`` from ``metadata.category`` (may be ``null``).
      Uses :meth:`SkillManager.list_summaries` so large ``instructions`` /
      ``references`` are **not** parsed as ``SkillJSON``.
    - ``verbose=true``: each element is the full registry shape
      ``{ "skill": { ... }, "_meta": { ... } }`` (same as historical behaviour).

    Filtering
    ---------
    - ``keywords``  One or more space-separated keywords searched
                    case-insensitively across skill **name**,
                    ``metadata.products``, and ``metadata.tags``.
                    A skill matches if **any** keyword hits any field
                    (OR logic) — useful for multi-product searches.
                    E.g. ``"aspera"`` → skills related to Aspera.
                         ``"aspera watsonx"`` → skills for either product.
    - ``tenant``    Restrict results to skills visible to a specific tenant ID.
    - ``category``  Restrict to ``metadata.category`` (case-insensitive match on
                    the trimmed value). Use ``category="(uncategorized)"`` for skills with
                    no category. In layered mode, omit ``category`` on the first call
                    (category index); pass it on the second call to list skills in that category.

    Pagination
    ----------
    Results are offset-based.  The response ``metadata.next_start`` field gives
    the ``offset`` value for the next page; it is ``null`` on the last page.
    In layered mode, the category index step (no ``category``) returns all
    categories in one response (no pagination).

    Examples
    --------
    Compact list (default):
        ``catalog_list_skills()``

    Full payload per skill:
        ``catalog_list_skills(verbose=true)``

    By keywords (name / product / tag):
        ``catalog_list_skills(keywords="instana")``
        ``catalog_list_skills(keywords="aspera monitoring")``

    Next page:
        ``catalog_list_skills(keywords="instana", offset=20, limit=20)``

    Layered (only when ``MCP_SKILL_CATALOG_LAYERED`` is set for this MCP process):
        ``catalog_list_skills()``
        ``catalog_list_skills(category="observability")``

    Args:
        keywords: Space-separated keywords searched across skill name, products,
                  and tags. Any keyword matching any field returns the skill (OR).
                  E.g. ``"aspera"`` or ``"aspera watsonx.data"``.
        tenant:   Restrict to skills visible to this tenant ID.
        offset:   Zero-based offset of the first result (default 0).
        limit:    Page size, 1–1000 (default 50).
        verbose:  When ``true``, each ``skills`` entry includes the full ``skill``
                  document and ``_meta``. When ``false`` (default), each entry is
                  only ``name``, ``description``, ``tags``, and ``category``.
        category: Filter by ``metadata.category``, or in layered mode the second-hop
                  category name from the index. Uncategorized bucket: ``"(uncategorized)"``.

    Returns:
        Flat mode: ``{"skills": [...], "metadata": {"count": N, "next_start": …}}``.
        Layered index: ``{"layered": true, "categories": [...], "skills": [], "metadata": …}``.
        On DB errors returns empty lists with an ``error`` field instead of
        raising, so callers can handle a missing table gracefully.
    """
    layered_mode = _skill_catalog_layered_from_env()
    category_trim: str | None = None
    try:
        tokens = [t for t in (keywords or "").split() if t] or None
        category_trim = category.strip() if category and category.strip() else None

        if layered_mode and not category_trim:
            categories = await _skill_manager.list_skill_categories(
                keywords=tokens,
                tenant=tenant,
            )
            return {
                "layered": True,
                "categories": categories,
                "skills": [],
                "metadata": {
                    "count": len(categories),
                    "next_start": None,
                },
            }

        fltr = CatalogResourceListFilter(
            kind=RegistryResourceKind.SKILL,
            name_like=None,
            is_latest_only=True,
            status_filter="active",
            keywords=tokens,
            tenant=tenant,
            category=category_trim,
            start=offset,
            limit=limit,
        )
        if verbose:
            result = await _skill_manager.list(fltr)
            data = result.model_dump(by_alias=True)
            skills_out: list[Any] = data["skills"]
            meta = result.metadata
        else:
            compact = await _skill_manager.list_summaries(fltr)
            skills_out = [s.model_dump(mode="json") for s in compact.skills]
            meta = compact.metadata
        out: dict[str, Any] = {
            "skills": skills_out,
            "metadata": {
                "count": meta.count,
                "next_start": meta.next_start,
            },
        }
        if layered_mode:
            out["layered"] = True
        return out
    except Exception as exc:
        err_body: dict[str, Any] = {
            "skills": [],
            "metadata": {"count": 0, "next_start": None},
            "error": str(exc),
        }
        if layered_mode and not category_trim:
            err_body["layered"] = True
            err_body["categories"] = []
        return err_body


@catalog_mcp.tool()
async def get_skill(
    name: str,
    version: str | None = None,
) -> dict:
    """Fetch a skill from the catalog (mirrors GET /v0/skills/{name}/versions/{version|latest}).

    - Omit ``version`` (or pass ``null``) to get the **latest** published
      release — the version marked ``isLatest`` in the registry.
    - Supply ``version`` to retrieve a **specific** historical release.

    Examples
    --------
    Get the current release:
        ``catalog_get_skill(name="ibm-instana-skill")``

    Get a specific historical version:
        ``catalog_get_skill(name="ibm-instana-skill", version="1.0.0")``

    Args:
        name:    Skill name, e.g. ``"ibm-instana-skill"``.  Required.
        version: Exact version string, e.g. ``"1.2.0"``.
                 Omit to fetch the latest version.

    Returns:
        ``{"skill": {...}, "_meta": {"io.modelcontextprotocol.registry/official": {...},
        "metadata": {...} | null}}``.  The ``metadata`` key inside ``_meta`` mirrors DB
        ``catalog_resource_metadata.data`` (how-to-use, COS URLs, references, etc.);
        ``remotes_config`` is omitted (merged into ``skill.remotes``).

    Raises:
        ValueError: If ``name`` is blank or no matching skill / version exists.
    """
    if not name or not name.strip():
        raise ValueError("name is a required field")
    name = name.strip()
    try:
        if version and version.strip():
            result = await _skill_manager.get(name, version.strip())
        else:
            result = await _skill_manager.get_latest(name)
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


@catalog_mcp.tool()
async def load_skill_reference(
    name: str,
    file: str,
    version: str | None = None,
) -> str:
    """Fetch one reference document (Markdown) for a catalog skill over HTTPS.

    Resolves ``file`` against the allowlist from ``skill.references`` and, when
    present, ``_meta.metadata.references``. Only ``https://`` URLs from that merged
    list are fetched — arbitrary URLs are rejected.

    Use after ``catalog_get_skill`` when the model needs the body of a single
    supporting file (progressive loading).

    Args:
        name:    Skill name, e.g. ``"cloud-finops"``.
        file:    Basename only, e.g. ``"finops-aws.md"`` (must match a ``file`` in references).
        version: Omit for latest; otherwise an exact catalog version string.

    Returns:
        A **JSON string** (UTF-8) with object keys ``name``, ``version``, ``file``,
        ``url``, and ``content`` (fetched body as a string; Markdown for ``.md`` URLs).

    Raises:
        ValueError: Blank arguments, skill not found, unknown ``file``, non-HTTPS URL,
                    or HTTP / size errors.
    """
    if not name or not name.strip():
        raise ValueError("name is a required field")
    name = name.strip()
    file_key = _validate_reference_file_arg(file)
    try:
        if version and version.strip():
            result = await _skill_manager.get(name, version.strip())
        else:
            result = await _skill_manager.get_latest(name)
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc

    entries = _collect_reference_entries(result)
    if not entries:
        raise ValueError(
            "This skill has no references in the catalog payload or metadata; " "nothing to load."
        )
    url, matched_file = _find_reference_url(entries, file_key)

    try:
        text = await _https_get_text_allowlisted(url)
    except httpx.HTTPError as exc:
        raise ValueError(f"Failed to fetch reference: {exc}") from exc

    payload = {
        "name": name,
        "version": result.skill.version,
        "file": matched_file,
        "url": url,
        "content": text,
    }
    return json.dumps(payload, ensure_ascii=False)


@catalog_mcp.tool()
async def get_skill_catalog_workflow_guide() -> dict[str, Any]:
    """Return this server's apply-a-skill workflow as JSON (steps, layered flag, notes)."""
    layered = _skill_catalog_layered_from_env()
    steps: list[dict[str, Any]] = [
        {
            "step": 1,
            "phase": "discover",
            "tool": "list_skills",
            "summary": (
                "List candidate skills (compact by default). "
                + (
                    "Layered: omit category for category index, then list_skills(category=...)."
                    if layered
                    else "Flat: paginate with start/limit; optional keywords/category filter."
                )
            ),
        },
        {
            "step": 2,
            "phase": "inspect",
            "tool": "get_skill",
            "summary": "Fetch full skill JSON for the chosen name (version optional for latest).",
        },
        {
            "step": 3,
            "phase": "references",
            "tool": "load_skill_reference",
            "summary": "For each needed reference basename, fetch body (HTTPS allowlist). Skip if not required.",
        },
        {
            "step": 4,
            "phase": "apply",
            "tool": "(host tools + skill policy)",
            "summary": "Execute the user task following merged instructions and allowed-tools until done.",
        },
    ]
    return {
        "pattern": "discover_load_references_apply",
        "layered_catalog_discovery": layered,
        "steps": steps,
        "notes": (
            "Tool names are as on this MCP server; clients may prefix (e.g. catalog_list_skills). "
            "Resources skill://… may substitute for some reference loads where supported."
        ),
    }


@catalog_mcp.tool()
async def add_skill(
    skill_json: str,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Register or update a skill in the catalog (mirrors POST /v0/skills).

    Use this tool to publish a new skill or to update an existing version.
    Re-publishing the same name+version is an upsert — it overwrites the
    stored payload without creating a duplicate.  The most-recently-published
    version is automatically marked as ``isLatest``; all earlier versions of
    the same skill lose that flag.

    ``skill_json`` must be a JSON **string** aligned with the agentskills.io spec:

    Required fields
    ---------------
    - ``name``        (string) Unique skill identifier. Max 64 chars.
                      Lowercase letters (a-z), numbers, and hyphens only.
                      No leading/trailing/consecutive hyphens.
                      Examples: ``"ibm-instana"``, ``"data-intelligence"``
    - ``description`` (string) Max 1024 chars. Should describe what the skill does
                      AND when to use it — include trigger phrases so agents can
                      route to this skill automatically.
    - ``version``     (string) Specific version tag — NOT ``"latest"`` and NOT a
                      range (``"^1.0"``). Examples: ``"1.0.0"``, ``"2.3.1-beta"``

    Optional spec fields (agentskills.io)
    --------------------------------------
    - ``license``       (string) License name or reference, e.g. ``"IBM Internal"``.
    - ``compatibility`` (string) Max 500 chars. Environment requirements — intended
                        product, required packages, network access, etc.
    - ``allowed-tools`` (array of strings) Pre-approved tool names the skill may
                        invoke, e.g. ``["make_tool_call", "ibm_document_search"]``.
    - ``metadata``      (object) Arbitrary key-value map for discovery metadata.
                        Recommended keys:
                        ``title``        — Display name shown in UIs.
                        ``category``     — Grouping tag, e.g. ``"observability"``.
                        ``products``     — (array) IBM product names this skill covers.
                        ``tags``         — (array) Keywords and trigger phrases for routing.
                        ``author``       — Publisher or team name.
                        ``instructions`` — Full LLM prompt content for the skill: workflows,
                                           when-to-use guidance, best practices, response
                                           templates, etc. Plain text or Markdown accepted.

    Optional operational fields
    ---------------------------
    - ``status``      (string) One of ``active`` (default), ``draft``,
                      ``deprecated``, ``deleted``.
    - ``websiteUrl``  (string) Docs or homepage URL.
    - ``repository``  (object) ``{"url": "..."}`` — optional ``source`` (e.g. ``git``) when relevant
    - ``references``  (array)  Each entry: ``{"url": "...", "file": "..."}`` — public-skill mirror of
                      catalog metadata references (bundled file URLs + filenames).
    - ``remotes``     (array)  Each entry: ``{"url": "..."}``
                      Remote MCP server endpoints that expose this skill.

    Minimal example
    ---------------
    ``'{"name": "ibm-instana", "description": "Use when monitoring Instana APM. Trigger on: latency, traces, incidents.", "version": "1.0.0"}'``

    Full example
    ------------
    ``'{"name": "ibm-instana", "description": "...", "version": "1.2.0", "license": "IBM Internal", "compatibility": "Requires Instana agent and API access.", "allowed-tools": ["make_tool_call", "ibm_document_search"], "metadata": {"title": "IBM Instana APM", "category": "observability", "products": ["Instana"], "tags": ["apm", "tracing"], "instructions": "## When to Use\\n\\n..."}}'``

    Args:
        skill_json:  JSON string as described above.
        tenant_ids:  Optional list of tenant IDs that should have access to
                     this skill.  Pass ``null`` / omit to make the skill
                     available to all tenants.

    Returns:
        The saved ``SkillResponse`` as a dict with keys ``skill`` (the stored
        payload) and ``_meta`` (registry metadata: ``isLatest``, ``status``,
        ``publishedAt``, ``updatedAt``).

    Raises:
        ValueError: If ``skill_json`` is malformed, a required field is
                    missing or invalid, or the per-skill version cap is reached.
    """
    try:
        parsed = SkillJSON.model_validate_json(skill_json)
    except Exception as exc:
        raise ValueError(f"Invalid skill_json: {exc}") from exc

    # Enforce instructions length at publish time (not on DB reads).
    if parsed.metadata and "instructions" in parsed.metadata:
        instr = parsed.metadata["instructions"]
        if isinstance(instr, str):
            try:
                validate_agentskills_instructions(instr)
            except ValueError as exc:
                raise ValueError(f"Invalid skill_json: {exc}") from exc

    try:
        result = await _skill_manager.publish(parsed, tenant_ids=tenant_ids)
    except CatalogVersionCapError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


def _parse_skill_bundle(
    raw: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Split a bundle dict into skill document and optional catalog_resource_metadata.data."""
    meta_keys = (
        "catalog_resource_metadata",
        "private_meta",
        "resource_metadata",
        "data",
    )
    found_keys: list[str] = []
    meta: dict[str, Any] | None = None
    for key in meta_keys:
        if key not in raw:
            continue
        val = raw[key]
        if val is None:
            continue
        if not isinstance(val, dict):
            raise ValueError(f"'{key}' must be a JSON object")
        found_keys.append(key)
        meta = val
    if len(found_keys) > 1:
        raise ValueError(
            "Use only one of: catalog_resource_metadata, private_meta, resource_metadata, data"
        )

    resource_body_keys = ("catalog_resource", "skill", "payload")
    present = [k for k in resource_body_keys if k in raw and raw[k] is not None]
    if len(present) > 1:
        raise ValueError(
            "Use only one of: catalog_resource, skill, payload (same agentskills document)"
        )
    if len(present) == 0:
        raise ValueError(
            "Bundle must include 'catalog_resource' (preferred), 'skill', or 'payload' "
            "— the public resource document stored in catalog_resources.payload"
        )
    key = present[0]
    skill_obj = raw[key]
    if not isinstance(skill_obj, dict):
        raise ValueError(f"'{key}' must be a JSON object")
    return skill_obj, meta


@catalog_mcp.tool()
async def publish_skill_bundle(
    bundle_json: str,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Publish a catalog resource row and ``catalog_resource_metadata`` in one call.

    ``bundle_json`` is a JSON **string** with:

    - **catalog_resource** (preferred) *or* **skill** *or* **payload**: the public
      agentskills document stored in ``catalog_resources.payload`` (``kind`` is
      ``skill`` for this tool). Use **catalog_resource** when naming the bundle;
      ``skill`` / ``payload`` are backward-compatible aliases.
    - Optionally exactly one of **catalog_resource_metadata**, **private_meta**,
      **resource_metadata**, or **data**: object stored in
      ``catalog_resource_metadata.data`` (private; not part of the public payload).

    Example::

        {
          "catalog_resource": { "name": "cloud-finops", "description": "...", "version": "1.0.3", ... },
          "catalog_resource_metadata": {
            "how-to-use": "...",
            "reference": "https://...",
            "cos_bundle": { "skill_md_url": "...", "references": [ ... ] }
          }
        }

    ``private_meta`` / ``data`` are accepted aliases for ``catalog_resource_metadata``.

    Args:
        bundle_json: JSON string as above.
        tenant_ids: Optional tenant IDs for the skill row (same as ``catalog_publish_skill``).

    Returns:
        Same shape as ``catalog_publish_skill`` (``skill`` + ``_meta``).

    Raises:
        ValueError: Invalid JSON, bundle shape, skill validation, instructions length,
                    or version cap.
    """
    try:
        raw = json.loads(bundle_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid bundle_json: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("bundle_json must be a JSON object")

    skill_obj, resource_meta = _parse_skill_bundle(raw)

    try:
        parsed = SkillJSON.model_validate(skill_obj)
    except Exception as exc:
        raise ValueError(f"Invalid catalog_resource document: {exc}") from exc

    if parsed.metadata and "instructions" in parsed.metadata:
        instr = parsed.metadata["instructions"]
        if isinstance(instr, str):
            try:
                validate_agentskills_instructions(instr)
            except ValueError as exc:
                raise ValueError(f"Invalid catalog_resource document: {exc}") from exc

    try:
        result = await _skill_manager.publish_with_resource_metadata(
            parsed,
            tenant_ids=tenant_ids,
            resource_metadata=resource_meta,
        )
    except CatalogVersionCapError as exc:
        raise ValueError(str(exc)) from exc
    return result.model_dump(by_alias=True)


@catalog_mcp.tool()
async def delete_skill(name: str, version: str) -> dict:
    """Remove a specific skill version from the catalog (mirrors DELETE /v0/skills/{name}/versions/{version}).

    Permanently deletes the stored record for the given name + version pair.
    If the deleted version was marked ``isLatest``, the most-recently-updated
    remaining version for the same skill is automatically promoted to
    ``isLatest`` so the catalog stays consistent.  If no other versions exist,
    the skill disappears from the catalog entirely.

    Args:
        name:    Skill name, e.g. ``"ibm-instana-skill"``.
        version: Exact version to delete, e.g. ``"1.0.0"``.

    Returns:
        ``{"ok": true, "name": "...", "version": "..."}``

    Raises:
        ValueError: If ``name`` or ``version`` are blank, or if no skill with
                    that name / version exists.
    """
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    try:
        await _skill_manager.delete(name.strip(), version.strip())
    except CatalogResourceNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return {"ok": True, "name": name.strip(), "version": version.strip()}


@catalog_mcp.tool()
async def update_skill_status(
    name: str,
    version: str,
    status: str,
) -> dict:
    """Change the lifecycle status of a skill version without altering its payload.

    Use this to move a skill through its lifecycle without republishing the
    full payload.  Common transitions:

    - ``draft``      → ``active``      Promote a draft to production-ready.
    - ``active``     → ``deprecated``  Signal that a newer version should be
                                       used; existing consumers still work.
    - ``active``     → ``deleted``     Soft-delete; the record stays in the
                                       catalog but signals it is no longer
                                       available.

    The status is written to both the stored payload and the registry
    ``_meta`` block so both views stay consistent.

    Valid values: ``active``, ``draft``, ``deprecated``, ``deleted``.

    Args:
        name:    Skill name, e.g. ``"ibm-instana-skill"``.
        version: Exact version string, e.g. ``"1.2.0"``.
        status:  Target status — one of ``active``, ``draft``, ``deprecated``,
                 ``deleted``.

    Returns:
        ``{"ok": true, "name": "...", "version": "...", "status": "..."}``

    Raises:
        ValueError: If ``name``, ``version``, or ``status`` are blank, the
                    status value is not recognised, or the skill / version does
                    not exist in the catalog.
    """
    if not name or not name.strip() or not version or not version.strip():
        raise ValueError("name and version are required fields")
    if not status or not status.strip():
        raise ValueError("status is a required field")
    try:
        await _skill_manager.update_status(name.strip(), version.strip(), status.strip())
    except (
        CatalogResourceNotFoundError,
        InvalidCatalogResourceStatusError,
    ) as exc:
        raise ValueError(str(exc)) from exc
    return {
        "ok": True,
        "name": name.strip(),
        "version": version.strip(),
        "status": status.strip(),
    }
