"""Validation helpers for catalog JSON (agentregistry-aligned rules)."""

from __future__ import annotations

import re

# Skill / prompt names: alphanumeric, underscore, hyphen (pkg/validators/names.go).
_SKILL_OR_PROMPT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Agent manifest name: letter + alphanumeric, min length 2 (ValidateAgentName).
_AGENT_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9]+$")

_PYTHON_KEYWORDS = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
)

# internal/registry/validators/validators.go — range detection
_COMPARATOR_RANGE_RE = re.compile(
    r"^\s*(?:\^|~|>=|<=|>|<|=)\s*v?\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?\s*$"
)
_HYPHEN_RANGE_RE = re.compile(
    r"^\s*v?\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?\s-\s*v?\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?\s*$"
)
_OR_RANGE_RE = re.compile(
    r"^\s*(?:v?\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?\s*)(?:\|\|\s*v?\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?\s*)+$"
)
_DOTTED_VERSION_LIKE_RE = re.compile(
    r"^\s*(?:v?\d+|x|X|\*)(?:\.(?:\d+|x|X|\*)){1,2}(?:-[0-9A-Za-z.-]+)?\s*$"
)


def strip_optional(value: str | None) -> str | None:
    """Strip surrounding whitespace; None stays None."""
    if value is None:
        return None
    return value.strip()


def require_non_empty_after_strip(value: str, field_label: str) -> str:
    """Return stripped string or raise ValueError."""
    s = value.strip()
    if not s:
        raise ValueError(f"{field_label} cannot be empty")
    return s


def validate_skill_or_prompt_name(name: str) -> str:
    """Validate skill or prompt registry name (alphanumeric, _, -)."""
    s = require_non_empty_after_strip(name, "name")
    if not _SKILL_OR_PROMPT_NAME_RE.match(s):
        raise ValueError(
            "invalid name: may only contain letters, numbers, underscores (_), and hyphens (-)"
        )
    return s


# agentskills.io spec: lowercase letters, numbers, hyphens only; max 64 chars;
# no leading/trailing hyphen; no consecutive hyphens.
_AGENTSKILLS_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
_CONSECUTIVE_HYPHENS_RE = re.compile(r"--")


def validate_agentskills_name(name: str) -> str:
    """Validate a skill name against the agentskills.io specification.

    Rules (https://agentskills.io/specification):
    - Max 64 characters.
    - Lowercase letters (a-z), numbers (0-9), and hyphens (-) only.
    - Must not start or end with a hyphen.
    - Must not contain consecutive hyphens.
    """
    s = require_non_empty_after_strip(name, "name")
    if len(s) > 64:
        raise ValueError(f"skill name must be 64 characters or fewer (got {len(s)})")
    if not _AGENTSKILLS_NAME_RE.match(s):
        raise ValueError(
            "skill name may only contain lowercase letters (a-z), numbers (0-9), and hyphens (-); "
            "must not start or end with a hyphen"
        )
    if _CONSECUTIVE_HYPHENS_RE.search(s):
        raise ValueError("skill name must not contain consecutive hyphens (--)")
    return s


def validate_agentskills_description(description: str) -> str:
    """Validate a skill description against the agentskills.io specification (max 1024 chars)."""
    s = require_non_empty_after_strip(description, "description")
    if len(s) > 1024:
        raise ValueError(f"description must be 1024 characters or fewer (got {len(s)})")
    return s


def validate_agentskills_compatibility(compatibility: str) -> str:
    """Validate a skill compatibility string against the agentskills.io spec (max 500 chars)."""
    s = require_non_empty_after_strip(compatibility, "compatibility")
    if len(s) > 500:
        raise ValueError(f"compatibility must be 500 characters or fewer (got {len(s)})")
    return s


def validate_agentskills_instructions(instructions: str) -> str:
    """Validate skill instructions stored in metadata (max 2048 chars).

    Instructions should be a concise LLM routing prompt: key workflows,
    quick-decision tables, and behaviour rules.  Detailed reference material
    belongs in separate files (references/, scripts/) per the agentskills.io
    progressive-disclosure pattern.
    """
    s = require_non_empty_after_strip(instructions, "metadata.instructions")
    if len(s) > 2048:
        raise ValueError(f"metadata.instructions must be 2048 characters or fewer (got {len(s)})")
    return s


def validate_agent_name(name: str) -> str:
    """Validate agent manifest/registry name (Python-identifier-like, no keywords)."""
    s = require_non_empty_after_strip(name, "name")
    if not _AGENT_NAME_RE.match(s):
        raise ValueError(
            "agent name must start with a letter and contain only letters and digits (minimum 2 characters)"
        )
    if s in _PYTHON_KEYWORDS:
        raise ValueError(f"agent name {s!r} is a Python keyword and cannot be used")
    return s


def looks_like_version_range(version: str) -> bool:
    """True if the string looks like a semver range, not a single version."""
    trimmed = version.strip()
    if not trimmed:
        return False
    if _COMPARATOR_RANGE_RE.match(trimmed):
        return True
    if _HYPHEN_RANGE_RE.match(trimmed):
        return True
    if _OR_RANGE_RE.match(trimmed):
        return True
    if _DOTTED_VERSION_LIKE_RE.match(trimmed):
        return "x" in trimmed or "X" in trimmed or "*" in trimmed
    return False


def validate_registry_version(version: str) -> str:
    """Reject reserved 'latest' and range-like version strings."""
    s = require_non_empty_after_strip(version, "version")
    if s == "latest":
        raise ValueError("version string 'latest' is reserved and cannot be used")
    if looks_like_version_range(s):
        raise ValueError(f"version must be a specific version, not a range: {s!r}")
    return s
