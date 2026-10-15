# tools package — lazy exports to avoid import cycles with member servers
from __future__ import annotations

from typing import Any

__all__ = [
    "MCPToolManager",
    "SequentialThinkingTool",
    "IBMDocumentSearchTool",
    "IBMDocSearchDirectTool",
    "BaseSpecializedTool",
    "ModelMeshTool",
]

_LAZY = {
    "MCPToolManager": (".tool_manager", "MCPToolManager"),
    "SequentialThinkingTool": (".sequential_thinking_tool", "SequentialThinkingTool"),
    "IBMDocumentSearchTool": (".ibm_document_search_tool", "IBMDocumentSearchTool"),
    "IBMDocSearchDirectTool": (".ibm_doc_search_direct_tool", "IBMDocSearchDirectTool"),
    "BaseSpecializedTool": (".base_specialised_tool", "BaseSpecializedTool"),
    "ModelMeshTool": (".model_mesh_tool", "ModelMeshTool"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name, __name__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
