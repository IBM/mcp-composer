"""catalog_local_file_adapter.py — Filesystem implementation of CatalogDatabaseInterface.

Folder layout:

    <root>/
      skills/
        <name>/
          <version>.json     ← full row dict (id, kind, name, version, payload, …)
          <version>.content  ← raw content (e.g. Markdown); absent when not provided
          latest             ← plain text: version string of the current is_latest row
      prompts/
        <name>/
          <version>.json
          <version>.content
          latest
      agents/
        <name>/
          <version>.json
          <version>.content
          latest
      workflows/
        <name>/
          <version>.json
          <version>.content
          latest
      metadata/
        <resource-uuid>.json   ← private metadata dict (matches catalog_resources.id)

Default root is ./catalog, overridden by MCP_CATALOG_FILE_PATH env var.
"""

from __future__ import annotations

import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from dotenv import find_dotenv, load_dotenv
from mcp_composer.core.models.catalog_constants import (
    SKILL_CATALOG_UNCATEGORIZED,
    RegistryResourceKind,
)
from mcp_composer.core.utils.logger import LoggerFactory

from .catalog_database import CatalogDatabaseInterface

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()

_DEFAULT_ROOT = "catalog"
_LATEST_MARKER = "latest"

_SKILL = RegistryResourceKind.SKILL.value
_PROMPT = RegistryResourceKind.PROMPT.value
_AGENT = RegistryResourceKind.AGENT.value
_WORKFLOW = RegistryResourceKind.WORKFLOW.value


def _expect_kind(kind: str) -> str:
    if kind not in (_SKILL, _PROMPT, _AGENT, _WORKFLOW):
        raise ValueError(f"unsupported catalog kind: {kind!r}")
    return kind


def _reject_unknown_kind(kind: str) -> NoReturn:
    """Fail fast if *kind* is not one of the supported registry kinds."""
    raise ValueError(f"unsupported catalog kind: {kind!r}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CatalogLocalFileAdapter(CatalogDatabaseInterface):
    """Local-filesystem catalog adapter (``skills/``, ``prompts/``, ``agents/``, ``workflows/``)."""

    def __init__(self, root_path: str | None = None) -> None:
        if root_path is None:
            root_path = os.getenv("MCP_CATALOG_FILE_PATH", _DEFAULT_ROOT)
        self._root = Path(root_path)
        self._skills_dir = self._root / "skills"
        self._prompts_dir = self._root / "prompts"
        self._agents_dir = self._root / "agents"
        self._workflows_dir = self._root / "workflows"
        self._metadata_dir = self._root / "metadata"

        # Create dispatch tables for O(1) kind-based routing
        self._file_getters = {
            _SKILL: self._skill_file,
            _PROMPT: self._prompt_file,
            _AGENT: self._agent_file,
            _WORKFLOW: self._workflow_file,
        }
        self._latest_readers = {
            _SKILL: self._read_latest_version,
            _PROMPT: self._read_prompt_latest_version,
            _AGENT: self._read_agent_latest_version,
            _WORKFLOW: self._read_workflow_latest_version,
        }
        self._latest_writers = {
            _SKILL: self._write_latest_version,
            _PROMPT: self._write_prompt_latest_version,
            _AGENT: self._write_agent_latest_version,
            _WORKFLOW: self._write_workflow_latest_version,
        }
        self._latest_clearers = {
            _SKILL: self._clear_latest_marker,
            _PROMPT: self._clear_prompt_latest_marker,
            _AGENT: self._clear_agent_latest_marker,
            _WORKFLOW: self._clear_workflow_latest_marker,
        }

        logger.info(
            "CatalogLocalFileAdapter configured with root: %s", self._root.resolve()
        )

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Create the root directory trees if they do not exist."""
        for d in (
            self._skills_dir,
            self._prompts_dir,
            self._agents_dir,
            self._workflows_dir,
            self._metadata_dir,
        ):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning(
                    "CatalogLocalFileAdapter could not create %s: %s — "
                    "continuing without filesystem persistence.",
                    d,
                    exc,
                )
        logger.info("CatalogLocalFileAdapter ready at %s", self._root.resolve())

    async def close(self) -> None:
        pass

    # ── internal helpers ───────────────────────────────────────────────────────

    def _skill_dir(self, name: str) -> Path:
        return self._skills_dir / name

    def _skill_file(self, name: str, version: str) -> Path:
        return self._skill_dir(name) / f"{version}.json"

    def _skill_content_file(self, name: str, version: str) -> Path:
        return self._skill_dir(name) / f"{version}.content"

    def _latest_marker(self, name: str) -> Path:
        return self._skill_dir(name) / _LATEST_MARKER

    def _prompt_dir(self, name: str) -> Path:
        return self._prompts_dir / name

    def _prompt_file(self, name: str, version: str) -> Path:
        return self._prompt_dir(name) / f"{version}.json"

    def _prompt_content_file(self, name: str, version: str) -> Path:
        return self._prompt_dir(name) / f"{version}.content"

    def _prompt_latest_marker(self, name: str) -> Path:
        return self._prompt_dir(name) / _LATEST_MARKER

    def _agent_dir(self, name: str) -> Path:
        return self._agents_dir / name

    def _agent_file(self, name: str, version: str) -> Path:
        return self._agent_dir(name) / f"{version}.json"

    def _agent_content_file(self, name: str, version: str) -> Path:
        return self._agent_dir(name) / f"{version}.content"

    def _agent_latest_marker(self, name: str) -> Path:
        return self._agent_dir(name) / _LATEST_MARKER

    def _workflow_dir(self, name: str) -> Path:
        return self._workflows_dir / name

    def _workflow_file(self, name: str, version: str) -> Path:
        return self._workflow_dir(name) / f"{version}.json"

    def _workflow_content_file(self, name: str, version: str) -> Path:
        return self._workflow_dir(name) / f"{version}.content"

    def _workflow_latest_marker(self, name: str) -> Path:
        return self._workflow_dir(name) / _LATEST_MARKER

    def _read_row(self, path: Path) -> dict:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _write_row(self, path: Path, row: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(row, fh, indent=2, default=str)

    def _read_latest_version(self, name: str) -> str | None:
        marker = self._latest_marker(name)
        if not marker.exists():
            return None
        return marker.read_text(encoding="utf-8").strip() or None

    def _write_latest_version(self, name: str, version: str) -> None:
        self._latest_marker(name).write_text(version, encoding="utf-8")

    def _clear_latest_marker(self, name: str) -> None:
        marker = self._latest_marker(name)
        if marker.exists():
            marker.unlink()

    def _read_prompt_latest_version(self, name: str) -> str | None:
        marker = self._prompt_latest_marker(name)
        if not marker.exists():
            return None
        return marker.read_text(encoding="utf-8").strip() or None

    def _write_prompt_latest_version(self, name: str, version: str) -> None:
        self._prompt_latest_marker(name).write_text(version, encoding="utf-8")

    def _clear_prompt_latest_marker(self, name: str) -> None:
        marker = self._prompt_latest_marker(name)
        if marker.exists():
            marker.unlink()

    def _read_agent_latest_version(self, name: str) -> str | None:
        marker = self._agent_latest_marker(name)
        if not marker.exists():
            return None
        return marker.read_text(encoding="utf-8").strip() or None

    def _write_agent_latest_version(self, name: str, version: str) -> None:
        self._agent_latest_marker(name).write_text(version, encoding="utf-8")

    def _clear_agent_latest_marker(self, name: str) -> None:
        marker = self._agent_latest_marker(name)
        if marker.exists():
            marker.unlink()

    def _read_workflow_latest_version(self, name: str) -> str | None:
        marker = self._workflow_latest_marker(name)
        if not marker.exists():
            return None
        return marker.read_text(encoding="utf-8").strip() or None

    def _write_workflow_latest_version(self, name: str, version: str) -> None:
        self._workflow_latest_marker(name).write_text(version, encoding="utf-8")

    def _clear_workflow_latest_marker(self, name: str) -> None:
        marker = self._workflow_latest_marker(name)
        if marker.exists():
            marker.unlink()

    def _resource_file(self, kind: str, name: str, version: str) -> Path:
        _expect_kind(kind)
        getter = self._file_getters.get(kind)
        if getter:
            return getter(name, version)
        _reject_unknown_kind(kind)

    def _read_latest_version_for_kind(self, kind: str, name: str) -> str | None:
        reader = self._latest_readers.get(kind)
        if reader:
            return reader(name)
        _reject_unknown_kind(kind)

    def _write_latest_version_for_kind(
        self, kind: str, name: str, version: str
    ) -> None:
        writer = self._latest_writers.get(kind)
        if writer:
            writer(name, version)
        else:
            _reject_unknown_kind(kind)

    def _clear_latest_marker_for_kind(self, kind: str, name: str) -> None:
        clearer = self._latest_clearers.get(kind)
        if clearer:
            clearer(name)
        else:
            _reject_unknown_kind(kind)

    # ── kind-aware resources ───────────────────────────────────────────────────

    async def save_resource(self, kind: str, row: dict) -> dict:
        kind = _expect_kind(kind)
        name = row["name"]
        version = row["version"]
        path = self._resource_file(kind, name, version)
        now = _now_iso()

        existing: dict | None = None
        if path.exists():
            try:
                existing = self._read_row(path)
            except Exception:
                existing = None

        stored = {
            "id": existing["id"] if existing else str(uuid.uuid4()),
            "kind": kind,
            "name": name,
            "version": version,
            "payload": row.get("payload", {}),
            "official_meta": row.get("official_meta", {}),
            "is_latest": bool(row.get("is_latest", False)),
            "tenant_ids": list(row.get("tenant_ids") or []),
            # agent_card: raw A2A well-known card JSON stored verbatim
            "agent_card": (
                row.get("agent_card")
                if row.get("agent_card")
                else (existing.get("agent_card") if existing else None)
            ),
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self._write_row(path, stored)

        if row.get("content") is not None:
            if kind == _SKILL:
                content_path = self._skill_content_file(name, version)
            elif kind == _PROMPT:
                content_path = self._prompt_content_file(name, version)
            elif kind == _AGENT:
                content_path = self._agent_content_file(name, version)
            elif kind == _WORKFLOW:
                content_path = self._workflow_content_file(name, version)
            else:
                _reject_unknown_kind(kind)
            content_path.write_text(row["content"], encoding="utf-8")

        if stored["is_latest"]:
            self._write_latest_version_for_kind(kind, name, version)

        logger.debug("Saved %s %s@%s to %s", kind, name, version, path)
        return stored

    async def get_resource(self, kind: str, name: str, version: str) -> dict | None:
        path = self._resource_file(_expect_kind(kind), name, version)
        if not path.exists():
            return None
        return self._read_row(path)

    async def get_resource_by_filter(
        self, kind: str, name: str, is_latest: bool
    ) -> dict | None:
        kind = _expect_kind(kind)
        if is_latest:
            ver = self._read_latest_version_for_kind(kind, name)
            if ver is None:
                return None
            return await self.get_resource(kind, name, ver)

        if kind == _SKILL:
            base = self._skill_dir(name)
        elif kind == _PROMPT:
            base = self._prompt_dir(name)
        elif kind == _AGENT:
            base = self._agent_dir(name)
        elif kind == _WORKFLOW:
            base = self._workflow_dir(name)
        else:
            _reject_unknown_kind(kind)
        if not base.exists():
            return None
        for p in sorted(base.glob("*.json")):
            row = self._read_row(p)
            if not row.get("is_latest"):
                return row
        return None

    async def list_resources(
        self,
        kind: str,
        *,
        name_like: str | None = None,
        is_latest_only: bool = False,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        kind = _expect_kind(kind)
        if kind == _SKILL:
            base_dir = self._skills_dir
        elif kind == _PROMPT:
            base_dir = self._prompts_dir
        elif kind == _AGENT:
            base_dir = self._agents_dir
        elif kind == _WORKFLOW:
            base_dir = self._workflows_dir
        else:
            _reject_unknown_kind(kind)
        if not base_dir.exists():
            return [], False

        rows: list[dict] = []
        for res_dir in sorted(base_dir.iterdir()):
            if not res_dir.is_dir():
                continue
            name = res_dir.name
            if name_like and name_like.lower() not in name.lower():
                continue
            for p in sorted(res_dir.glob("*.json")):
                try:
                    row = self._read_row(p)
                except Exception:
                    continue
                if is_latest_only and not row.get("is_latest"):
                    continue
                if (
                    status_filter
                    and (row.get("official_meta", {}).get("status") or "active")
                    != status_filter
                ):
                    continue
                if keywords and kind == _SKILL:
                    meta = row.get("payload", {}).get("metadata") or {}
                    products = [str(v).lower() for v in meta.get("products", [])]
                    tags = [str(v).lower() for v in meta.get("tags", [])]
                    name_lower = row["name"].lower()
                    if not any(
                        kw in name_lower
                        or any(kw in pr for pr in products)
                        or any(kw in tg for tg in tags)
                        for kw in [k.lower() for k in keywords]
                    ):
                        continue
                if category is not None and kind == _SKILL:
                    raw_cat = category.strip()
                    meta = row.get("payload", {}).get("metadata") or {}
                    cat_val = meta.get("category")
                    if (
                        not raw_cat
                        or raw_cat.lower() == SKILL_CATALOG_UNCATEGORIZED.lower()
                    ):
                        if isinstance(cat_val, str) and cat_val.strip():
                            continue
                    else:
                        if (
                            not isinstance(cat_val, str)
                            or cat_val.strip().lower() != raw_cat.lower()
                        ):
                            continue
                if tenant and tenant not in (row.get("tenant_ids") or []):
                    continue
                rows.append(row)

        rows.sort(key=lambda r: r["name"])
        page = rows[offset : offset + limit]
        has_more = (offset + limit) < len(rows)
        return page, has_more

    async def list_distinct_skill_categories(
        self,
        *,
        is_latest_only: bool = True,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
    ) -> list[dict[str, Any]]:
        rows, _ = await self.list_resources(
            _SKILL,
            name_like=None,
            is_latest_only=is_latest_only,
            status_filter=status_filter,
            keywords=keywords,
            tenant=tenant,
            category=None,
            offset=0,
            limit=1_000_000,
        )
        labels: list[str] = []
        for r in rows:
            meta = r.get("payload", {}).get("metadata") or {}
            cat = meta.get("category")
            if isinstance(cat, str) and cat.strip():
                labels.append(cat.strip())
            else:
                labels.append(SKILL_CATALOG_UNCATEGORIZED)
        counts = Counter(labels)
        return [
            {"name": name, "skill_count": counts[name]}
            for name in sorted(counts.keys())
        ]

    async def count_resource_versions(self, kind: str, name: str) -> int:
        kind = _expect_kind(kind)
        if kind == _SKILL:
            base = self._skill_dir(name)
        elif kind == _PROMPT:
            base = self._prompt_dir(name)
        elif kind == _AGENT:
            base = self._agent_dir(name)
        elif kind == _WORKFLOW:
            base = self._workflow_dir(name)
        else:
            _reject_unknown_kind(kind)
        if not base.exists():
            return 0
        return len(list(base.glob("*.json")))

    async def delete_resource(self, kind: str, name: str, version: str) -> None:
        kind = _expect_kind(kind)
        path = self._resource_file(kind, name, version)
        if not path.exists():
            return

        resource_id: str | None = None
        try:
            resource_id = str(self._read_row(path).get("id") or "")
        except Exception:  # pylint: disable=broad-exception-caught
            resource_id = None

        if self._read_latest_version_for_kind(kind, name) == version:
            self._clear_latest_marker_for_kind(kind, name)

        path.unlink()
        if kind == _SKILL:
            content_file = self._skill_content_file(name, version)
        elif kind == _PROMPT:
            content_file = self._prompt_content_file(name, version)
        elif kind == _AGENT:
            content_file = self._agent_content_file(name, version)
        elif kind == _WORKFLOW:
            content_file = self._workflow_content_file(name, version)
        else:
            _reject_unknown_kind(kind)
        if content_file.exists():
            content_file.unlink()
        if resource_id:
            meta_path = self._metadata_file_for_resource_id(resource_id)
            if meta_path.exists():
                meta_path.unlink()
        logger.debug("Deleted %s %s@%s", kind, name, version)

        if kind == _SKILL:
            parent = self._skill_dir(name)
        elif kind == _PROMPT:
            parent = self._prompt_dir(name)
        elif kind == _AGENT:
            parent = self._agent_dir(name)
        elif kind == _WORKFLOW:
            parent = self._workflow_dir(name)
        else:
            _reject_unknown_kind(kind)
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

    async def update_resource_row(
        self, kind: str, name: str, version: str, fields: dict
    ) -> None:
        if not fields:
            return
        kind = _expect_kind(kind)
        path = self._resource_file(kind, name, version)
        if not path.exists():
            return
        row = self._read_row(path)
        for k, v in fields.items():
            row[k] = v
        row["updated_at"] = _now_iso()
        self._write_row(path, row)

        if "is_latest" in fields:
            if fields["is_latest"]:
                self._write_latest_version_for_kind(kind, name, version)
            elif self._read_latest_version_for_kind(kind, name) == version:
                self._clear_latest_marker_for_kind(kind, name)

    async def list_resource_versions_for_name(self, kind: str, name: str) -> list[dict]:
        """Return all JSON rows for ``kind`` and ``name`` (every version)."""
        kind = _expect_kind(kind)
        if kind == _SKILL:
            base_dir = self._skill_dir(name)
        elif kind == _PROMPT:
            base_dir = self._prompt_dir(name)
        elif kind == _AGENT:
            base_dir = self._agent_dir(name)
        elif kind == _WORKFLOW:
            base_dir = self._workflow_dir(name)
        else:
            _reject_unknown_kind(kind)
        if not base_dir.exists():
            return []
        rows: list[dict] = []
        for p in sorted(base_dir.glob("*.json")):
            try:
                rows.append(self._read_row(p))
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        rows.sort(key=lambda r: r.get("version", ""))
        return rows

    # ── resource content methods ───────────────────────────────────────────────

    def _content_file(self, kind: str, name: str, version: str) -> Path:
        """Return the path for the raw content file for any resource kind."""
        if kind == _SKILL:
            return self._skill_content_file(name, version)
        if kind == _PROMPT:
            return self._prompt_content_file(name, version)
        if kind == _AGENT:
            return self._agent_content_file(name, version)
        if kind == _WORKFLOW:
            return self._workflow_content_file(name, version)
        _reject_unknown_kind(kind)

    async def get_resource_content(
        self, kind: str, name: str, version: str
    ) -> str | None:
        """Return the raw content string for (kind, name, version), or None if absent."""
        path = self._content_file(kind, name, version)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    async def save_resource_content(
        self, kind: str, name: str, version: str, content: str
    ) -> None:
        """Write raw content to the sibling <version>.content file."""
        path = self._content_file(kind, name, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # ── resource metadata methods ──────────────────────────────────────────────

    def _metadata_file_for_resource_id(self, resource_id: str) -> Path:
        return self._metadata_dir / f"{resource_id}.json"

    async def save_resource_metadata(
        self, resource_id: str, private_meta: dict
    ) -> None:
        path = self._metadata_file_for_resource_id(resource_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_row(path, private_meta)

    async def get_resource_metadata(self, resource_id: str) -> dict | None:
        path = self._metadata_file_for_resource_id(resource_id)
        if not path.exists():
            return None
        return self._read_row(path)

    async def delete_resource_metadata(self, resource_id: str) -> None:
        path = self._metadata_file_for_resource_id(resource_id)
        if path.exists():
            path.unlink()
