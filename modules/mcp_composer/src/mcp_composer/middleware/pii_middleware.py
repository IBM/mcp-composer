# pii_middleware.py
from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

# ------------------------------
# Defaults: sensitive keys & patterns
# ------------------------------

_DEFAULT_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "jwt",
    "client_secret",
    "private_key",
}

# Conservative, practical detectors (you can add/remove via config)
_DEFAULT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    (
        "JWT",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    ("BEARER", re.compile(r"\bBearer\s+[A-Za-z0-9._\-~+/=]{16,}\b", re.IGNORECASE)),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "GENERIC_SECRET",
        re.compile(
            r"(?i)\b(secret|token|apikey|api_key|session|bearer)\b.{0,3}([A-Za-z0-9_\-]{24,})"
        ),
    ),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    (
        "PHONE",
        re.compile(
            r"(?:(?:\+|00)\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)\d{3,4}[\s\-]?\d{3,4}"
        ),
    ),
]

_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _luhn_check(num: str) -> bool:
    s = [int(d) for d in re.sub(r"[^\d]", "", num)]
    if len(s) < 13:
        return False
    dbl, total = False, 0
    for d in reversed(s):
        total += (d * 2 - 9) if dbl and d > 4 else (d * 2 if dbl else d)
        dbl = not dbl
    return total % 10 == 0


# ------------------------------
# Redaction strategy
# ------------------------------


@dataclass
class RedactionStrategy:
    mode: str = "mask"  # "mask" | "hash" | "tokenize"
    salt: Optional[str] = None
    redaction_text: str = "[REDACTED]"

    def redact_token(self, text: str, tag: str, idx: int) -> str:
        return f"<{tag}_{idx}>"

    def redact_hash(self, text: str, tag: str) -> str:
        h = hashlib.sha256((self.salt or "").encode() + text.encode()).hexdigest()
        return f"[HASH:{tag}:{h[:12]}]"

    def redact_mask(self, text: str, tag: str) -> str:
        return self.redaction_text if self.redaction_text else f"[REDACTED:{tag}]"

    def apply(self, text: str, tag: str, token_idx: Optional[int] = None) -> str:
        if self.mode == "hash":
            return self.redact_hash(text, tag)
        if self.mode == "tokenize":
            return self.redact_token(text, tag, (token_idx or 0))
        # default
        return self.redact_mask(text, tag)


# ------------------------------
# Redactor core
# ------------------------------


@dataclass
class Redactor:
    strategy: RedactionStrategy
    sensitive_keys: set = field(default_factory=lambda: set(_DEFAULT_SENSITIVE_KEYS))
    patterns: List[Tuple[str, re.Pattern]] = field(
        default_factory=lambda: list(_DEFAULT_PATTERNS)
    )
    allowlist_fields: set = field(default_factory=set)

    def _redact_string(self, s: str) -> str:
        # Credit cards (Luhn-gated)
        def _repl_cc(m):
            val = m.group(0)
            return self.strategy.apply(val, "CC") if _luhn_check(val) else val

        out = _CC_RE.sub(_repl_cc, s)

        token_counters: Dict[str, int] = {}
        for tag, pat in self.patterns:

            def repl(m, tag=tag):
                val = m.group(0)
                if self.strategy.mode == "tokenize":
                    token_counters[tag] = token_counters.get(tag, 0) + 1
                    return self.strategy.apply(val, tag, token_counters[tag])
                return self.strategy.apply(val, tag)

            out = pat.sub(repl, out)
        return out

    def _redact_by_key(self, key: str, value: Any) -> Optional[Any]:
        if key.lower() in self.sensitive_keys:
            return self.strategy.apply(str(value), key.upper())
        return None

    def redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                if k in self.allowlist_fields:
                    out[k] = v
                    continue
                keyed = self._redact_by_key(k, v)
                out[k] = keyed if keyed is not None else self.redact_obj(v)
            return out
        if isinstance(obj, list):
            return [self.redact_obj(v) for v in obj]
        if isinstance(obj, str):
            return self._redact_string(obj)
        return obj


# ------------------------------
# Middleware (FastMCP)
# ------------------------------


class SecretsAndPIIMiddleware(Middleware):
    """
    Config-driven secrets & PII redaction.

    Expected config (keys map directly to __init__ kwargs):
      strategy: { mode: "mask"|"hash"|"tokenize", salt?: str, redaction_text?: str }
      redact_inputs: bool = True
      redact_outputs: bool = True
      replace_inputs: bool = False     # if True, passes redacted args to the tool (and restores after)
      allowlist_tools: [str] = []
      allowlist_fields: [str] = []
      sensitive_keys: { add?: [str], remove?: [str] }
      patterns:
        add?: [ { "tag": "...", "regex": "...", "flags": ["IGNORECASE","MULTILINE",...] } ]
        remove?: [ "TAG1", "TAG2" ]
    """

    def __init__(
        self,
        *,
        strategy: Optional[Dict[str, Any]] = None,
        redact_inputs: bool = True,
        redact_outputs: bool = True,
        replace_inputs: bool = False,
        allowlist_tools: Optional[List[str]] = None,
        allowlist_fields: Optional[List[str]] = None,
        sensitive_keys: Optional[Dict[str, List[str]]] = None,
        patterns: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        # Back-compat shorthands:
        sensitive_keys_add: Optional[List[str]] = None,
        sensitive_keys_remove: Optional[List[str]] = None,
        patterns_add: Optional[List[Dict[str, Any]]] = None,
        patterns_remove: Optional[List[str]] = None,
        # Debugging options:
        debug_mode: bool = False,
    ):
        self.redact_inputs = bool(redact_inputs)
        self.redact_outputs = bool(redact_outputs)
        self.replace_inputs = bool(replace_inputs)
        self.allowlist_tools = set(allowlist_tools or [])
        self.debug_mode = debug_mode
        self._logger = logging.getLogger(__name__)

        # strategy
        strat = strategy or {}
        self.redactor = Redactor(
            strategy=RedactionStrategy(
                mode=(strat.get("mode") or "mask"),
                salt=strat.get("salt"),
                redaction_text=strat.get("redaction_text", "[REDACTED]"),
            ),
            allowlist_fields=set(allowlist_fields or []),
        )

        # sensitive keys
        add_keys = set()
        rem_keys = set()
        if sensitive_keys:
            add_keys |= set(sensitive_keys.get("add", []) or [])
            rem_keys |= set(sensitive_keys.get("remove", []) or [])
        if sensitive_keys_add:
            add_keys |= set(sensitive_keys_add)
        if sensitive_keys_remove:
            rem_keys |= set(sensitive_keys_remove)

        self.redactor.sensitive_keys |= add_keys
        self.redactor.sensitive_keys -= rem_keys

        # patterns
        extra_add = []
        extra_remove = []
        if patterns:
            extra_add += patterns.get("add", []) or []
            extra_remove += patterns.get("remove", []) or []
        if patterns_add:
            extra_add += patterns_add
        if patterns_remove:
            extra_remove += patterns_remove

        # remove by TAG
        if extra_remove:
            keep = []
            drop = set(extra_remove)
            for tag, pat in self.redactor.patterns:
                if tag not in drop:
                    keep.append((tag, pat))
            self.redactor.patterns = keep

        # add compiled patterns
        FLAG_MAP = {
            "IGNORECASE": re.IGNORECASE,
            "MULTILINE": re.MULTILINE,
            "DOTALL": re.DOTALL,
            "VERBOSE": re.VERBOSE,
        }
        for item in extra_add:
            tag = item["tag"]
            regex = item["regex"]
            flags = 0
            for name in item.get("flags", []):
                flags |= FLAG_MAP.get(name.upper(), 0)
            self.redactor.patterns.append((tag, re.compile(regex, flags)))

    # ---- Hook helpers ----

    def _tool_is_allowlisted(self, tool: str) -> bool:
        if not tool:
            return False
        return tool in self.allowlist_tools

    def _safe_repr(self, obj: Any, max_length: int = 300) -> str:
        """Safe representation of object for logging"""
        try:
            repr_str = repr(obj)
            if len(repr_str) > max_length:
                return repr_str[:max_length] + "..."
            return repr_str
        except Exception:
            return f"<{type(obj).__name__} object at {id(obj)}>"

    def _remove_pii_from_result(self, result: Any, tool: str) -> Any:
        """
        Enhanced PII removal from results with better error handling and structure support.

        This method handles various result types that FastMCP might return:
        - Simple types (str, dict, list)
        - Complex objects with attributes
        - MCP-specific response objects
        - Nested structures
        """
        if self.debug_mode:
            self._logger.debug(
                f"[{tool}] Attempting PII redaction on result type: {type(result)}"
            )
            self._logger.debug(
                f"[{tool}] Result preview: {self._safe_repr(result, 200)}"
            )

        try:
            # Handle None/empty results
            if result is None:
                return result

            # Handle simple types directly
            if isinstance(result, (str, int, float, bool)):
                if isinstance(result, str):
                    redacted = self.redactor._redact_string(result)
                    if self.debug_mode and redacted != result:
                        self._logger.info(f"[{tool}] String redaction applied")
                    return redacted
                return result

            # Handle standard collections
            if isinstance(result, (dict, list)):
                redacted = self.redactor.redact_obj(result)
                if self.debug_mode:
                    self._logger.info(f"[{tool}] Collection redaction completed")
                return redacted

            # Handle objects with __dict__ (most custom objects)
            if hasattr(result, "__dict__"):
                return self._redact_object_with_dict(result, tool)

            # Handle specific FastMCP response patterns
            if hasattr(result, "content"):
                return self._redact_content_attribute(result, tool)

            if hasattr(result, "data"):
                return self._redact_data_attribute(result, tool)

            if hasattr(result, "text"):
                return self._redact_text_attribute(result, tool)

            # Handle iterables (tuples, sets, etc.)
            if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
                redacted_items = [self.redactor.redact_obj(item) for item in result]
                try:
                    # Try to reconstruct the same type
                    result_type = type(result)
                    redacted = result_type(redacted_items)
                    if self.debug_mode:
                        self._logger.info(f"[{tool}] Iterable redaction completed")
                    return redacted
                except Exception as e:
                    if self.debug_mode:
                        self._logger.warning(
                            f"[{tool}] Failed to reconstruct iterable: {e}"
                        )
                    return redacted_items

            # Last resort: convert to string and redact
            if self.debug_mode:
                self._logger.debug(f"[{tool}] Using string conversion fallback")

            result_str = str(result)
            redacted_str = self.redactor._redact_string(result_str)

            if redacted_str != result_str and self.debug_mode:
                self._logger.info(f"[{tool}] String fallback redaction applied")

            return redacted_str

        except Exception as e:
            self._logger.error(f"[{tool}] PII redaction failed: {str(e)}")
            if self.debug_mode:
                self._logger.error(
                    f"[{tool}] Result structure that failed: {self._safe_repr(result)}"
                )
            return result

    def _redact_object_with_dict(self, result: Any, tool: str) -> Any:
        """Handle objects that have __dict__ attribute"""
        try:
            # Get the object's dictionary
            result_dict = result.__dict__.copy()

            # Redact the dictionary
            redacted_dict = self.redactor.redact_obj(result_dict)

            # Try to reconstruct the original object type
            try:
                # For simple classes, try direct construction
                if hasattr(result, "__class__"):
                    reconstructed = result.__class__(**redacted_dict)
                    if self.debug_mode:
                        self._logger.info(f"[{tool}] Object reconstruction successful")
                    return reconstructed
            except Exception:
                # If reconstruction fails, try updating the original object
                try:
                    for key, value in redacted_dict.items():
                        setattr(result, key, value)
                    if self.debug_mode:
                        self._logger.info(f"[{tool}] Object update successful")
                    return result
                except Exception:
                    pass

            # If all else fails, return the redacted dictionary
            if self.debug_mode:
                self._logger.warning(
                    f"[{tool}] Returning redacted dict instead of object"
                )
            return redacted_dict

        except Exception as e:
            if self.debug_mode:
                self._logger.error(f"[{tool}] Object dict redaction failed: {e}")
            return result

    def _redact_content_attribute(self, result: Any, tool: str) -> Any:
        """Handle objects with 'content' attribute"""
        try:
            content = getattr(result, "content")
            redacted_content = self.redactor.redact_obj(content)

            # Create a copy if possible
            if hasattr(result, "__dict__"):
                result_copy = type(result).__new__(type(result))
                result_copy.__dict__.update(result.__dict__)
                result_copy.content = redacted_content
                if self.debug_mode:
                    self._logger.info(
                        f"[{tool}] Content attribute redaction successful"
                    )
                return result_copy
            else:
                # Modify in place if we can't copy
                setattr(result, "content", redacted_content)
                return result

        except Exception as e:
            if self.debug_mode:
                self._logger.error(f"[{tool}] Content attribute redaction failed: {e}")
            return result

    def _redact_data_attribute(self, result: Any, tool: str) -> Any:
        """Handle objects with 'data' attribute"""
        try:
            data = getattr(result, "data")
            redacted_data = self.redactor.redact_obj(data)

            # Create a copy if possible
            if hasattr(result, "__dict__"):
                result_copy = type(result).__new__(type(result))
                result_copy.__dict__.update(result.__dict__)
                result_copy.data = redacted_data
                if self.debug_mode:
                    self._logger.info(f"[{tool}] Data attribute redaction successful")
                return result_copy
            else:
                # Modify in place if we can't copy
                setattr(result, "data", redacted_data)
                return result

        except Exception as e:
            if self.debug_mode:
                self._logger.error(f"[{tool}] Data attribute redaction failed: {e}")
            return result

    def _redact_text_attribute(self, result: Any, tool: str) -> Any:
        """Handle objects with 'text' attribute"""
        try:
            text = getattr(result, "text")
            if isinstance(text, str):
                redacted_text = self.redactor._redact_string(text)

                # Create a copy if possible
                if hasattr(result, "__dict__"):
                    result_copy = type(result).__new__(type(result))
                    result_copy.__dict__.update(result.__dict__)
                    result_copy.text = redacted_text
                    if self.debug_mode:
                        self._logger.info(
                            f"[{tool}] Text attribute redaction successful"
                        )
                    return result_copy
                else:
                    # Modify in place if we can't copy
                    setattr(result, "text", redacted_text)
                    return result
            else:
                # If text is not a string, use general redaction
                redacted_text = self.redactor.redact_obj(text)
                if hasattr(result, "__dict__"):
                    result_copy = type(result).__new__(type(result))
                    result_copy.__dict__.update(result.__dict__)
                    result_copy.text = redacted_text
                    return result_copy
                else:
                    setattr(result, "text", redacted_text)
                    return result

        except Exception as e:
            if self.debug_mode:
                self._logger.error(f"[{tool}] Text attribute redaction failed: {e}")
            return result

    # ---- Hooks ----

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        tool = getattr(context.message, "name", "") or ""

        # (A) redact inputs (either for logs only, or replace temporarily)
        orig_args = getattr(context.message, "arguments", {})
        if self.redact_inputs and not self._tool_is_allowlisted(tool):
            try:
                red = self.redactor.redact_obj(orig_args)
                # write redacted copy to logger / telemetry if you have a logger
                # Note: context.logger may not be available in all FastMCP versions
                # if hasattr(context, "logger") and context.logger:
                #     try:
                #         context.logger.debug({"tool": tool, "redacted_args": red})
                #     except AttributeError:
                #         pass  # logger not available
                if self.replace_inputs:
                    context.message.arguments = red  # pass redacted to downstream

                if self.debug_mode:
                    self._logger.debug(f"[{tool}] Input redaction completed")

            except Exception as e:
                self._logger.error(f"[{tool}] Input redaction failed: {e}")

        try:
            result = await call_next(context)
        finally:
            # restore originals if we replaced them
            if self.redact_inputs and self.replace_inputs:
                context.message.arguments = orig_args

        # (B) redact outputs using enhanced method
        if self.redact_outputs and not self._tool_is_allowlisted(tool):
            return self._remove_pii_from_result(result, tool)

        return result

    async def on_read_resource(self, context: MiddlewareContext, call_next: CallNext):
        # redact resource contents on the way out
        result = await call_next(context)
        if self.redact_outputs:
            return self._remove_pii_from_result(result, "read_resource")
        return result

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext):
        # optionally scrub descriptions in listings (defensive)
        result = await call_next(context)
        try:
            tools = getattr(result, "tools", None)
            if tools:
                for t in tools:
                    if hasattr(t, "description") and isinstance(t.description, str):
                        t.description = self.redactor._redact_string(t.description)
        except Exception:
            pass
        return result
