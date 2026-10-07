"""Catalog enums and constants (agentregistry-aligned), colocated with catalog models."""

from __future__ import annotations

from enum import Enum

# Maximum versions per logical resource name (parity with agentregistry registry service).
MAX_VERSIONS_PER_RESOURCE = 10000

# Lifecycle status values shared by all catalog resource kinds (skill, prompt, …).
VALID_CATALOG_RESOURCE_STATUSES: frozenset[str] = frozenset(
    {"active", "draft", "deprecated", "deleted", "deactivated", "load-onstartup"}
)

# Bucket label for skills with no ``metadata.category`` (layered browse + filters).
SKILL_CATALOG_UNCATEGORIZED = "(uncategorized)"


class RegistryResourceKind(str, Enum):
    """Kind of catalog entry in the agentic registry."""

    SKILL = "skill"
    AGENT = "agent"
    PROMPT = "prompt"
    WORKFLOW = "workflow"
