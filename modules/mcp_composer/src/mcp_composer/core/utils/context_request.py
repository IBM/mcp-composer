from fastmcp.server.middleware import  MiddlewareContext
from typing import Any, Dict, List
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.middleware.auth_context_middleware import HEADER_USER_INSTANCES
import json
logger = LoggerFactory.get_logger()

def get_http_request(context: MiddlewareContext) -> Any:
        """Get the HTTP request from context, or None if unavailable."""
        fastmcp_ctx = getattr(context, "fastmcp_context", None)
        if fastmcp_ctx is None:
            logger.debug("get_request: no fastmcp_context")
            return None
        request_context = getattr(fastmcp_ctx, "request_context", None)
        return getattr(request_context, "request", None) if request_context else None

def _normalize_to_instance_list(raw: Any) -> List[Dict]:
    """Turn raw header/identity value into a list of instance dicts."""
    if raw is None:
        return []
    if isinstance(raw, list):
        if len(raw) == 1 and isinstance(raw[0], dict):
            inner = raw[0].get("userInstances") or raw[0].get("user_instances")
            if isinstance(inner, list):
                return inner
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("userInstances"), list):
            return raw["userInstances"]
        if isinstance(raw.get("user_instances"), list):
            return raw["user_instances"]
        return [raw]
    return []


def extract_user_instances(request: Any) -> List[Dict]:
    """Extract user instances from user.identity or X-User-Instances header."""
    raw: Any = None
    request_state = getattr(request, "state", None)
    if request_state and getattr(request_state, "user", None):
        identity = getattr(request_state.user, "identity", None)
        if identity:
            if isinstance(identity, dict):
                raw = identity.get("userInstances")
                if not isinstance(raw, list) and isinstance(identity.get("instances"), dict):
                    raw = (identity["instances"] or {}).get("userInstances") or (identity["instances"] or {}).get("user_instances")
            else:
                raw = getattr(identity, "userInstances", None) or getattr(identity, "user_instances", None)
    if raw is None:
        headers = getattr(request, "headers", None) or {}
        raw_header = headers.get(HEADER_USER_INSTANCES) or headers.get("X-User-Instances") or headers.get("x-User-Instances") or ""
        if raw_header:
            try:
                raw = json.loads(raw_header)
            except json.JSONDecodeError as e:
                logger.warning("X-User-Instances header JSON invalid: %s", e)
    return _normalize_to_instance_list(raw)