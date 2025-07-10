from __future__ import annotations 
from typing import Any, Dict, List


_PRIMITIVE_MAP = {
    "string": "str", 
    "integer": "int", 
    "number": "float", 
    "boolean": "bool", 
    "object": "dict", 
}

def _short(schema: Dict[str, Any]) -> str: 
    t = schema.get("type")
    if t == "array": 
        return f"list[{_short(schema.get('items', {}))}]"
    if "enum" in schema: 
        e = "|".join(map(str, schema["enum"][:4]))
        return f"enum({e})"
    return _PRIMITIVE_MAP.get(t, t or "any")

def _flat_props(schema: Dict[str, Any], limit = 4) -> str: 
    props = schema.get("properties", {})
    parts = [f"{k}: {_short(v)}" for k, v in list(props.items())[:limit]]
    if len(props) > limit: 
        parts.append("...")
    return ", ".join(parts)

def compact_signature(schema: Dict[str, Any]) -> str: 

    if schema.get("type") != "object": 
        return _short(schema)
        
    props: Dict[str, Any] = schema.get("properties", {})
    req: set[str] = set(schema.get("required", []))

    req_frag: List[str] = []
    opt_frag: List[str] = []

    for k, v in props.items(): 
        frag = f"{k}: {_short(v)}"
        dest = req_frag if k in req else opt_frag

        if v.get("type") == "object": 
            frag = f"{k}:{{{_flat_props(v)}}}"
        elif v.get("type") == "array" and v.get("items", {}).get("type") == "object": 
            nested_props = _flat_props(v["items"])
            frag = f"{k}: [{{{nested_props}}}]"
        
        dest.append(frag)

    out: List[str] = []
    if req_frag: 
        out.append("required: " + ", ".join(req_frag))
    if opt_frag: 
        out.append("optional: " + ", ".join(opt_frag))
    
    return " | ".join(out)