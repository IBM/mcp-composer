import re
import hashlib
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
import mcp.types as mt

# ---- Config & Utilities ------------------------------------------------------

_SENSITIVE_KEYS = {
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

# Regex patterns (conservative to avoid over-redaction)
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    (
        "JWT",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    ("BEARER", re.compile(r"\bBearer\s+[A-Za-z0-9._\-~+/=]{16,}\b", re.IGNORECASE)),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    # Not perfect, but practical for many secrets (base64-ish 32–64 chars preceded by key-ish words)
    (
        "GENERIC_SECRET",
        re.compile(
            r"(?i)\b(secret|token|apikey|api_key|session|bearer)\b.{0,3}([A-Za-z0-9_\-]{24,})"
        ),
    ),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    # Phone (very conservative): +CC…. or (0x)… followed by 7–12 digits
    (
        "PHONE",
        re.compile(
            r"(?:(?:\+|00)\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)\d{3,4}[\s\-]?\d{3,4}"
        ),
    ),
]


def _luhn_check(num: str) -> bool:
    s = [int(d) for d in re.sub(r"[^\d]", "", num)]
    if len(s) < 13:
        return False
    dbl = False
    total = 0
    for d in reversed(s):
        total += (d * 2 - 9) if dbl and d > 4 else (d * 2 if dbl else d)
        dbl = not dbl
    return total % 10 == 0


_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _mask(s: str) -> str:
    if not s:
        return ""
    if len(s) <= 4:
        return "****"
    return s[:2] + "****" + s[-2:]


def _sha256(s: str, salt: Optional[str]) -> str:
    h = hashlib.sha256()
    if salt:
        h.update(salt.encode())
    h.update(s.encode())
    return h.hexdigest()


@dataclass
class RedactionStrategy:
    mode: str = "mask"  # "mask" | "hash" | "tokenize"
    salt: Optional[str] = None

    def redact(self, text: str, tag: str, token_index: Optional[int] = None) -> str:
        if self.mode == "mask":
            return f"[REDACTED:{tag}]"
        if self.mode == "hash":
            return f"[HASH:{tag}:{_sha256(text, self.salt)[:12]}]"
        if self.mode == "tokenize":
            idx = token_index if token_index is not None else 0
            return f"<{tag}_{idx}>"
        return "[REDACTED]"


# ---- Redactor core -----------------------------------------------------------


@dataclass
class Redactor:
    strategy: RedactionStrategy
    allowlist_tools: set = field(default_factory=set)
    allowlist_fields: set = field(default_factory=set)
    include_pii: bool = True
    include_secrets: bool = True

    def _redact_string(self, s: str) -> str:
        original = s

        # Credit cards (Luhn-gated)
        def _repl_cc(m):
            val = m.group(0)
            return self.strategy.redact(val, "CC") if _luhn_check(val) else val

        s = _CC_RE.sub(_repl_cc, s)

        # Other patterns
        token_counters: Dict[str, int] = {}
        for tag, pat in _PATTERNS:

            def repl(m, tag=tag):
                val = m.group(0)
                if self.strategy.mode == "tokenize":
                    token_counters[tag] = token_counters.get(tag, 0) + 1
                    return self.strategy.redact(val, tag, token_counters[tag])
                return self.strategy.redact(val, tag)

            s = pat.sub(repl, s)

        return s

    def _redact_by_key(self, key: str, value: Any) -> Any:
        # If key looks sensitive, nuke the value
        if key.lower() in _SENSITIVE_KEYS:
            if isinstance(value, str):
                return self.strategy.redact(value, key.upper())
            return self.strategy.redact(str(value), key.upper())
        return None  # means: unchanged

    def redact_obj(self, obj: Any, path: Tuple[str, ...] = ()) -> Any:
        # Dicts
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k in self.allowlist_fields:
                    out[k] = v
                    continue
                key_redacted = self._redact_by_key(k, v)
                if key_redacted is not None:
                    out[k] = key_redacted
                else:
                    out[k] = self.redact_obj(v, path + (k,))
            return out
        # Lists
        if isinstance(obj, list):
            return [self.redact_obj(v, path + (str(i),)) for i, v in enumerate(obj)]
        # Strings
        if isinstance(obj, str):
            return self._redact_string(obj)
        # Other primitives
        return obj


# ---- Middleware --------------------------------------------------------------


class SecretsAndPIIMiddleware(Middleware):
    """
    Redacts secrets & PII in tool inputs and outputs.

    Config:
      strategy: RedactionStrategy(mode="mask"|"hash"|"tokenize", salt="optional")
      allowlist_tools: tools that should not be redacted (e.g., decryptor)
      allowlist_fields: field names exempt from key-based redaction
      redact_inputs: redact arguments before call_next (for logs/telemetry)
      redact_outputs: redact returned values from tools/resources
    """

    def __init__(
        self,
        *,
        strategy: RedactionStrategy = RedactionStrategy(mode="mask"),
        allowlist_tools: Optional[List[str]] = None,
        allowlist_fields: Optional[List[str]] = None,
        redact_inputs: bool = True,
        redact_outputs: bool = True,
    ):
        self.redactor = Redactor(
            strategy=strategy,
            allowlist_tools=set(allowlist_tools or []),
            allowlist_fields=set(allowlist_fields or []),
        )
        self.redact_inputs = redact_inputs
        self.redact_outputs = redact_outputs

    # Hooks: adjust names to your framework if different
    async def on_message(self, context, call_next):
        # Optionally redact raw messages before any logging
        return await call_next(context)

    async def on_call_tool(self, context, call_next):
        tool = getattr(context.message, "name", "")
        if tool not in self.redactor.allowlist_tools:
            if self.redact_inputs:
                # Redact arguments in-place (but keep a copy to restore if needed)
                args = getattr(context.message, "arguments", {})
                try:
                    redacted = self.redactor.redact_obj(args)
                    # Safe place to log redacted args:
                    if getattr(context, "logger", None):
                        context.logger.debug({"tool": tool, "redacted_args": redacted})
                    # Replace only for logging/propagation; if downstream needs originals,
                    # you can also keep originals in context.state
                    context.message.arguments = redacted
                except Exception:
                    pass

        # Perform the call
        result = await call_next(context)

        if self.redact_outputs and tool not in self.redactor.allowlist_tools:
            try:
                return self.redactor.redact_obj(result)
            except Exception:
                return result

        return result

    async def on_read_resource(self, context, call_next):
        # Redact file/resource content when returning to caller
        result = await call_next(context)
        if self.redact_outputs:
            try:
                return self.redactor.redact_obj(result)
            except Exception:
                return result
        return result

    async def on_list_tools(self, context, call_next):
        # Optionally redact descriptions in listings (rare, but safe)
        result = await call_next(context)
        try:
            for t in getattr(result, "tools", []):
                if hasattr(t, "description") and isinstance(t.description, str):
                    t.description = self.redactor._redact_string(t.description)
        except Exception:
            pass
        return result
