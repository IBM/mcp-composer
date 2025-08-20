"""
Simple schemas for policy-based access control.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    """Authentication context for policy evaluation."""

    user_id: Optional[str] = Field(None, description="User identifier")
    roles: List[str] = Field(default_factory=list, description="User roles")
    agent_id: Optional[str] = Field(None, description="Agent identifier")
    authenticated: bool = Field(False, description="Whether user is authenticated")
    auth_method: Optional[str] = Field(None, description="Authentication method used")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional auth metadata"
    )
