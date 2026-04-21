"""catalog_exceptions.py — Shared errors for catalog resource managers (skill, prompt, agent, workflow, …)."""

from __future__ import annotations

from mcp_composer.core.models.catalog_constants import (
    MAX_VERSIONS_PER_RESOURCE,
    RegistryResourceKind,
    VALID_CATALOG_RESOURCE_STATUSES,
)

_KIND_LABEL: dict[str, str] = {
    RegistryResourceKind.SKILL.value: "Skill",
    RegistryResourceKind.PROMPT.value: "Prompt",
    RegistryResourceKind.AGENT.value: "Agent",
    RegistryResourceKind.WORKFLOW.value: "Workflow",
}


def _kind_label(kind: str) -> str:
    return _KIND_LABEL.get(kind, kind.replace("-", " ").title())


class CatalogResourceNotFoundError(KeyError):
    """Raised when a (name, version) pair is absent for the given catalog ``kind``."""

    def __init__(self, kind: str, name: str, version: str) -> None:
        self.kind = kind
        self.name = name
        self.version = version
        label = _kind_label(kind)
        super().__init__(f"{label} not found: {name}@{version}")


class CatalogVersionCapError(ValueError):
    """Raised when publishing would exceed :data:`MAX_VERSIONS_PER_RESOURCE`."""

    def __init__(self, kind: str, name: str, count: int) -> None:
        self.kind = kind
        self.name = name
        self.count = count
        label = _kind_label(kind)
        super().__init__(
            f"{label} '{name}' has reached the maximum version limit "
            f"({count}/{MAX_VERSIONS_PER_RESOURCE})"
        )


class InvalidCatalogResourceStatusError(ValueError):
    """Raised when a caller supplies an unrecognised lifecycle status."""

    def __init__(self, kind: str, status: str) -> None:
        self.kind = kind
        self.status = status
        label = _kind_label(kind)
        super().__init__(
            f"Invalid {label.lower()} status {status!r}. "
            f"Must be one of: {sorted(VALID_CATALOG_RESOURCE_STATUSES)}"
        )
