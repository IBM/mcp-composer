"""
Core middleware module for MCP Composer.

This module provides the core middleware infrastructure including:
- ComposerMiddleware: Wrapper for enforcing hooks and conditions
- MiddlewareManager: Builds and manages middleware instances
- MiddlewareConfig: Configuration models for middleware setup
- HookFilter: Hook-based filtering middleware
- HookPolicy: Policy evaluation for include/exclude conditions
"""

from .middleware import ComposerMiddleware
from .middleware_manager import MiddlewareManager, _match_glob, _import_kind, _hook_name
from .middleware_config import (
    MiddlewareConfig,
    MiddlewareEntry,
    MiddlewareSettings,
    Conditions,
    LogicStep,
    HookLogic,
    AllowedHook,
    ModeEnum,
    load_and_validate_config,
    export_json_schema,
)
from .hook_filter import HookFilter
from .hook_policy import HookPolicy

__all__ = [
    # Main middleware classes
    "ComposerMiddleware",
    "MiddlewareManager",
    "HookFilter",
    "HookPolicy",
    
    # Configuration models
    "MiddlewareConfig",
    "MiddlewareEntry", 
    "MiddlewareSettings",
    "Conditions",
    "LogicStep",
    "HookLogic",
    "AllowedHook",
    "ModeEnum",
    
    # Utility functions
    "_match_glob",
    "_import_kind", 
    "_hook_name",
    "load_and_validate_config",
    "export_json_schema",
]
