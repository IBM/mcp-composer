# config_models.py
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re

AllowedHook = Literal[
    "on_request",
    "on_message",
    "on_list_tools",
    "on_list_resources",
    "on_read_resource",
    "on_list_prompts",
    "on_call_tool",
]
ModeEnum = Literal["enabled", "disabled"]


class Conditions(BaseModel):
    include_tools: List[str] = Field(default_factory=lambda: ["*"])
    exclude_tools: List[str] = Field(default_factory=list)
    include_prompts: List[str] = Field(default_factory=list)
    exclude_prompts: List[str] = Field(default_factory=list)
    include_server_ids: List[str] = Field(default_factory=list)
    exclude_server_ids: List[str] = Field(default_factory=list)


# Optional future-proof “logic steps” (not required by your current design)
class LogicStep(BaseModel):
    use: str
    params: Dict[str, Any] = Field(default_factory=dict)
    # allow “if” in JSON with a safe alias
    if_: Optional[Conditions] = Field(default=None, alias="if")


class HookLogic(BaseModel):
    pre: List[LogicStep] = Field(default_factory=list)
    post: List[LogicStep] = Field(default_factory=list)


class MiddlewareEntry(BaseModel):
    name: str
    description: str = ""
    version: str = Field("0.0.0", pattern=r"^\d+\.\d+\.\d+(?:[-0-9A-Za-z\.]+)?$")
    kind: str
    mode: ModeEnum = "enabled"
    priority: int = Field(100, ge=0, le=10000)
    applied_hooks: List[AllowedHook]
    conditions: Conditions = Field(default_factory=Conditions)
    config: Dict[str, Any] = Field(default_factory=dict)
    # Map each hook to a HookLogic (optional)
    logic: Dict[AllowedHook, HookLogic] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _kind_must_be_module_class(cls, v: str) -> str:
        # minimal check: “module.Class”
        if "." not in v:
            raise ValueError("kind must be 'module.Class' (import path + class name).")
        # Optional: require a valid identifier before/after dot
        mod, clsname = v.rsplit(".", 1)
        ident = r"^[A-Za-z_]\w*$"
        if not re.match(ident, clsname):
            raise ValueError("kind class part must be a valid Python identifier.")
        return v

    @field_validator("applied_hooks")
    @classmethod
    def _hooks_non_empty_unique(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("applied_hooks cannot be empty.")
        if len(set(v)) != len(v):
            raise ValueError("applied_hooks must be unique.")
        return v


class MiddlewareSettings(BaseModel):
    middleware_timeout: int = Field(30, ge=1, le=300)
    fail_on_middleware_error: bool = False
    enable_middleware_api: bool = True
    middleware_health_check_interval: int = Field(60, ge=5, le=3600)


class MiddlewareConfig(BaseModel):
    middleware: List[MiddlewareEntry]
    middleware_settings: MiddlewareSettings = Field(default_factory=MiddlewareSettings)

    @model_validator(mode="after")
    def _unique_names(self):
        names = [m.name for m in self.middleware]
        if len(set(names)) != len(names):
            raise ValueError("All middleware 'name' values must be unique.")
        return self


# ---- helpers to export JSON Schema and load/validate configs -----------------


def export_json_schema() -> Dict[str, Any]:
    """Return a JSON Schema (Draft 2020-12) for the whole config."""
    return MiddlewareConfig.model_json_schema()


def load_and_validate_config(
    path: str, *, ensure_imports: bool = False
) -> MiddlewareConfig:
    import json
    import importlib

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    cfg = MiddlewareConfig.model_validate(raw)
    if ensure_imports:
        # optionally verify that each kind import resolves
        for m in cfg.middleware:
            mod, clsname = m.kind.rsplit(".", 1)
            module = importlib.import_module(mod)
            getattr(module, clsname)  # will raise AttributeError if missing
    return cfg
