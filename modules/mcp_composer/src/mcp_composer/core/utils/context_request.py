import ast
import json

from fastmcp.server.middleware import MiddlewareContext
from typing import Any
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.middleware.auth_context_middleware import HEADER_USER_INSTANCES

logger = LoggerFactory.get_logger()
_ALLOWED = (bool, str, bytes, int, float)


def _attr(span, key: str, value: Any):
    try:
        if value is None:
            return
        if isinstance(value, (list, tuple)):
            cleaned = [v for v in value if isinstance(v, _ALLOWED)]
            if cleaned:
                span.set_attribute(key, cleaned)
            return
        if isinstance(value, _ALLOWED):
            span.set_attribute(key, value)
            return
        span.set_attribute(key, str(value))
    except Exception:
        pass


def _get_nested(obj: Any, dotted: str) -> Any:
    """Get nested attr or dict key via dotted path, e.g. 'fastmcp_context.fastmcp.name'."""
    cur = obj
    for part in dotted.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def ctx_get(context: MiddlewareContext, *names, default=None):
    """Try dotted names on context, then on context.message."""
    for name in names:
        val = _get_nested(context, name)
        if val is not None:
            return val
        msg = getattr(context, "message", None)
        if msg is not None:
            val = _get_nested(msg, name)
            if val is not None:
                return val
    return default


def _normalize_to_instance_list(raw: Any) -> list[dict[str, Any]]:
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


def extract_user_instances(request: Any) -> list[dict[str, Any]]:
    """
    Extract user instances from request.

    Checks in order:
    1. request.state.user.token_data['user_instances'] (ISV authentication)
    2. X-User-Instances header (legacy/fallback)
    """
    if request is None:
        return []

    raw: Any = None

    # First check request.state.user.token_data (ISV authentication)
    request_state = getattr(request, "state", None)
    if request_state and getattr(request_state, "user", None):
        token_data = getattr(request_state.user, "token_data", None)
        if token_data and isinstance(token_data, dict):
            raw = token_data.get("user_instances")
            if raw:
                logger.debug(
                    "Extracted %d user instances from token_data",
                    len(raw) if isinstance(raw, list) else 0,
                )
                return _normalize_to_instance_list(raw)

    # Fallback to X-User-Instances header
    headers = getattr(request, "headers", None) or {}
    raw_header = headers.get(HEADER_USER_INSTANCES)

    if raw_header:
        raw_header = raw_header.strip()
        try:
            raw = json.loads(raw_header)
            if isinstance(raw, str):
                raw = json.loads(raw)
        except json.JSONDecodeError:
            try:
                # Handle escaped quotes (e.g. "[{\"id\":\"...\"}]" with outer quotes stripped)
                unescaped = raw_header.replace('\\"', '"')
                raw = json.loads(unescaped)
                if isinstance(raw, str):
                    raw = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    raw = ast.literal_eval(raw_header)
                except (ValueError, SyntaxError) as e:
                    logger.warning(
                        "X-User-Instances header invalid (not JSON or Python literal): %s",
                        e,
                    )

        if raw:
            logger.debug(
                "Extracted %d user instances from header",
                len(raw) if isinstance(raw, list) else 0,
            )

    return _normalize_to_instance_list(raw)
