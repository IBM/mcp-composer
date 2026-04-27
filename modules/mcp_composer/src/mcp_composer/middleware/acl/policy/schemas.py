"""
Simple schemas for policy-based access control.
"""

from typing import Any
from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    """Authentication context for policy evaluation."""

    user_id: str | None = Field(None, description="User identifier")
    roles: list[str] = Field(default_factory=list, description="User roles")
    agent_id: str | None = Field(None, description="Agent identifier")
    authenticated: bool = Field(False, description="Whether user is authenticated")
    auth_method: str | None = Field(None, description="Authentication method used")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional auth metadata"
    )
