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
      metadata/
        <resource-uuid>.json   ← private metadata dict (matches catalog_resources.id)

Default root is ./catalog, overridden by MCP_CATALOG_FILE_PATH env var.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from mcp_composer.core.utils import LoggerFactory

from .catalog_database import CatalogDatabaseInterface

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()

_DEFAULT_ROOT = "catalog"
_LATEST_MARKER = "latest"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CatalogLocalFileAdapter(CatalogDatabaseInterface):
    """Local-filesystem catalog adapter for skills.

    Each skill version is a single JSON file:
        <root>/skills/<name>/<version>.json

    A plain-text marker file keeps track of the latest version:
        <root>/skills/<name>/latest
    """

    def __init__(self, root_path: str | None = None) -> None:
        if root_path is None:
            root_path = os.getenv("MCP_CATALOG_FILE_PATH", _DEFAULT_ROOT)
        self._root = Path(root_path)
        self._skills_dir = self._root / "skills"
        self._prompts_dir = self._root / "prompts"
        self._metadata_dir = self._root / "metadata"
        logger.info(
            "CatalogLocalFileAdapter configured with root: %s", self._root.resolve()
        )

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Create the root directory trees if they do not exist."""
        for d in (self._skills_dir, self._prompts_dir, self._metadata_dir):
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

    # ── skill methods ──────────────────────────────────────────────────────────

    async def save_skill(self, row: dict) -> dict:
        name = row["name"]
        version = row["version"]
        path = self._skill_file(name, version)
        now = _now_iso()

        existing: dict | None = None
        if path.exists():
            try:
                existing = self._read_row(path)
            except Exception:
                existing = None

        stored = {
            "id": existing["id"] if existing else str(uuid.uuid4()),
            "kind": "skill",
            "name": name,
            "version": version,
            "payload": row.get("payload", {}),
            "official_meta": row.get("official_meta", {}),
            "is_latest": bool(row.get("is_latest", False)),
            "tenant_ids": list(row.get("tenant_ids") or []),
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self._write_row(path, stored)

        if row.get("content") is not None:
            self._skill_content_file(name, version).write_text(
                row["content"], encoding="utf-8"
            )

        if stored["is_latest"]:
            self._write_latest_version(name, version)

        logger.debug("Saved skill %s@%s to %s", name, version, path)
        return stored

    async def get_skill(self, name: str, version: str) -> dict | None:
        path = self._skill_file(name, version)
        if not path.exists():
            return None
        return self._read_row(path)

    async def get_skill_by_filter(self, name: str, is_latest: bool) -> dict | None:
        if is_latest:
            version = self._read_latest_version(name)
            if version is None:
                return None
            return await self.get_skill(name, version)

        # Non-latest: return first version whose is_latest flag is False
        skill_dir = self._skill_dir(name)
        if not skill_dir.exists():
            return None
        for p in sorted(skill_dir.glob("*.json")):
            row = self._read_row(p)
            if not row.get("is_latest"):
                return row
        return None

    async def list_skills(
        self,
        *,
        name_like: str | None = None,
        is_latest_only: bool = False,
        status_filter: str | None = None,
        keywords: list[str] | None = None,
        tenant: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        if not self._skills_dir.exists():
            return [], False

        rows: list[dict] = []
        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            name = skill_dir.name
            if name_like and name_like.lower() not in name.lower():
                continue
            for p in sorted(skill_dir.glob("*.json")):
                try:
                    row = self._read_row(p)
                except Exception:
                    continue
                if is_latest_only and not row.get("is_latest"):
                    continue
                if status_filter and (row.get("official_meta", {}).get("status") or "active") != status_filter:
                    continue
                if keywords:
                    meta = row.get("payload", {}).get("metadata") or {}
                    products = [str(v).lower() for v in meta.get("products", [])]
                    tags = [str(v).lower() for v in meta.get("tags", [])]
                    name_lower = row["name"].lower()
                    # Any keyword matching any field is a hit (OR across keywords).
                    if not any(
                        kw in name_lower
                        or any(kw in pr for pr in products)
                        or any(kw in tg for tg in tags)
                        for kw in [k.lower() for k in keywords]
                    ):
                        continue
                if tenant and tenant not in (row.get("tenant_ids") or []):
                    continue
                rows.append(row)

        rows.sort(key=lambda r: r["name"])

        page = rows[offset : offset + limit]
        has_more = (offset + limit) < len(rows)
        return page, has_more

    async def count_skill_versions(self, name: str) -> int:
        skill_dir = self._skill_dir(name)
        if not skill_dir.exists():
            return 0
        return len(list(skill_dir.glob("*.json")))

    async def list_skill_versions_for_name(self, name: str) -> list[dict]:
        """Return all skill JSON rows under ``skills/<name>/``."""
        skill_dir = self._skill_dir(name)
        if not skill_dir.exists():
            return []
        rows: list[dict] = []
        for p in sorted(skill_dir.glob("*.json")):
            try:
                rows.append(self._read_row(p))
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        rows.sort(key=lambda r: r.get("version", ""))
        return rows

    async def delete_skill(self, name: str, version: str) -> None:
        path = self._skill_file(name, version)
        if not path.exists():
            return

        resource_id: str | None = None
        try:
            resource_id = str(self._read_row(path).get("id") or "")
        except Exception:  # pylint: disable=broad-exception-caught
            resource_id = None

        # If this was the latest, remove the marker
        if self._read_latest_version(name) == version:
            self._clear_latest_marker(name)

        path.unlink()
        content_file = self._skill_content_file(name, version)
        if content_file.exists():
            content_file.unlink()
        if resource_id:
            meta_path = self._metadata_file_for_resource_id(resource_id)
            if meta_path.exists():
                meta_path.unlink()
        logger.debug("Deleted skill %s@%s", name, version)

        # Remove the skill directory when it becomes empty
        skill_dir = self._skill_dir(name)
        if skill_dir.exists() and not any(skill_dir.iterdir()):
            skill_dir.rmdir()

    async def update_skill_row(self, name: str, version: str, fields: dict) -> None:
        if not fields:
            return
        path = self._skill_file(name, version)
        if not path.exists():
            return
        row = self._read_row(path)
        for k, v in fields.items():
            row[k] = v
        row["updated_at"] = _now_iso()
        self._write_row(path, row)

        # Keep the latest marker in sync when is_latest changes
        if "is_latest" in fields:
            if fields["is_latest"]:
                self._write_latest_version(name, version)
            elif self._read_latest_version(name) == version:
                self._clear_latest_marker(name)

    # ── prompt helpers ─────────────────────────────────────────────────────────

    def _prompt_dir(self, name: str) -> Path:
        return self._prompts_dir / name

    def _prompt_file(self, name: str, version: str) -> Path:
        return self._prompt_dir(name) / f"{version}.json"

    def _prompt_content_file(self, name: str, version: str) -> Path:
        return self._prompt_dir(name) / f"{version}.content"

    def _prompt_latest_marker(self, name: str) -> Path:
        return self._prompt_dir(name) / _LATEST_MARKER

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

    # ── prompt methods ─────────────────────────────────────────────────────────

    async def save_prompt(self, row: dict) -> dict:
        name = row["name"]
        version = row["version"]
        path = self._prompt_file(name, version)
        now = _now_iso()

        existing: dict | None = None
        if path.exists():
            try:
                existing = self._read_row(path)
            except Exception:
                existing = None

        stored = {
            "id": existing["id"] if existing else str(uuid.uuid4()),
            "kind": "prompt",
            "name": name,
            "version": version,
            "payload": row.get("payload", {}),
            "official_meta": row.get("official_meta", {}),
            "is_latest": bool(row.get("is_latest", False)),
            "tenant_ids": list(row.get("tenant_ids") or []),
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self._write_row(path, stored)

        if row.get("content") is not None:
            self._prompt_content_file(name, version).write_text(
                row["content"], encoding="utf-8"
            )

        if stored["is_latest"]:
            self._write_prompt_latest_version(name, version)

        return stored

    async def get_prompt(self, name: str, version: str) -> dict | None:
        path = self._prompt_file(name, version)
        if not path.exists():
            return None
        return self._read_row(path)

    async def get_prompt_by_filter(self, name: str, is_latest: bool) -> dict | None:
        if is_latest:
            version = self._read_prompt_latest_version(name)
            if version is None:
                return None
            return await self.get_prompt(name, version)

        prompt_dir = self._prompt_dir(name)
        if not prompt_dir.exists():
            return None
        for p in sorted(prompt_dir.glob("*.json")):
            row = self._read_row(p)
            if not row.get("is_latest"):
                return row
        return None

    async def list_prompts(
        self,
        *,
        name_like: str | None,
        is_latest_only: bool,
        status_filter: str | None,
        tenant: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], bool]:
        if not self._prompts_dir.exists():
            return [], False

        rows: list[dict] = []
        for prompt_dir in sorted(self._prompts_dir.iterdir()):
            if not prompt_dir.is_dir():
                continue
            name = prompt_dir.name
            if name_like and name_like.lower() not in name.lower():
                continue
            for p in sorted(prompt_dir.glob("*.json")):
                try:
                    row = self._read_row(p)
                except Exception:
                    continue
                if is_latest_only and not row.get("is_latest"):
                    continue
                if status_filter and (row.get("official_meta", {}).get("status") or "active") != status_filter:
                    continue
                if tenant and tenant not in (row.get("tenant_ids") or []):
                    continue
                rows.append(row)

        rows.sort(key=lambda r: r["name"])
        page = rows[offset : offset + limit]
        has_more = (offset + limit) < len(rows)
        return page, has_more

    async def count_prompt_versions(self, name: str) -> int:
        prompt_dir = self._prompt_dir(name)
        if not prompt_dir.exists():
            return 0
        return len(list(prompt_dir.glob("*.json")))

    async def delete_prompt(self, name: str, version: str) -> None:
        path = self._prompt_file(name, version)
        if not path.exists():
            return

        resource_id: str | None = None
        try:
            resource_id = str(self._read_row(path).get("id") or "")
        except Exception:  # pylint: disable=broad-exception-caught
            resource_id = None

        if self._read_prompt_latest_version(name) == version:
            self._clear_prompt_latest_marker(name)

        path.unlink()
        content_file = self._prompt_content_file(name, version)
        if content_file.exists():
            content_file.unlink()
        if resource_id:
            meta_path = self._metadata_file_for_resource_id(resource_id)
            if meta_path.exists():
                meta_path.unlink()
        prompt_dir = self._prompt_dir(name)
        if prompt_dir.exists() and not any(prompt_dir.iterdir()):
            prompt_dir.rmdir()

    async def update_prompt_row(self, name: str, version: str, fields: dict) -> None:
        if not fields:
            return
        path = self._prompt_file(name, version)
        if not path.exists():
            return
        row = self._read_row(path)
        for k, v in fields.items():
            row[k] = v
        row["updated_at"] = _now_iso()
        self._write_row(path, row)

        if "is_latest" in fields:
            if fields["is_latest"]:
                self._write_prompt_latest_version(name, version)
            elif self._read_prompt_latest_version(name) == version:
                self._clear_prompt_latest_marker(name)

    # ── resource content methods ───────────────────────────────────────────────

    def _content_file(self, kind: str, name: str, version: str) -> Path:
        """Return the path for the raw content file for any resource kind."""
        if kind == "skill":
            return self._skill_content_file(name, version)
        if kind == "prompt":
            return self._prompt_content_file(name, version)
        # Generic fallback for future kinds
        return self._root / f"{kind}s" / name / f"{version}.content"

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

    async def save_resource_metadata(self, resource_id: str, private_meta: dict) -> None:
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