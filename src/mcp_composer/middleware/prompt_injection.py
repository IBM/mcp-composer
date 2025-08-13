import re
import asyncio
import time
from typing import Optional, Callable, Dict, Any, List, Iterable
import mcp.types as mt
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.core.utils.logger import LoggerFactory
from fastmcp.exceptions import ToolError

logger = LoggerFactory.get_logger()


_OVERRIDE_PATTERNS = [
    r"\bignore (the )?(previous|earlier) (instructions|message|rules)\b",
    r"\bdisregard (all )?(prior|previous) (context|instructions)\b",
    r"\boverride (the )?(system|policy|guardrails)\b",
    r"\bact as (system|developer|root)\b",
    r"\breveal (the )?(system|developer) (prompt|message)\b",
    r"\breset (the )?system (prompt|role)\b",
]

_TOOL_STEERING = [
    r"\bcall (the )?tool\b",
    r"\binvoke (hidden|internal) tool\b",
    r"\buse tool .* with\b",
    r"\bexecute shell\b",
    r"\brun .* on server\b",
]

_DATA_EXFIL = [
    r"\bprint (all )?environment variables\b",
    r"\bshow .*api key\b",
    r"\bread .*secret\b",
    r"\bcat /etc/passwd\b",
    r"\bfetch .*credentials?\b",
]

_URL_REGEX = r"https?://[^\s]+"


def _find_matches(patterns: Iterable[str], text: str) -> List[str]:
    hits = []
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            hits.append(p)
    return hits


def default_heuristic_score(
    payload_text: str, url_allowlist: Optional[Iterable[str]] = None
) -> Dict[str, Any]:
    """
    Returns a dict with score in [0,1] and matched indicators for explainability.
    """
    matches = {
        "override": _find_matches(_OVERRIDE_PATTERNS, payload_text),
        "tool_steer": _find_matches(_TOOL_STEERING, payload_text),
        "exfil": _find_matches(_DATA_EXFIL, payload_text),
        "disallowed_urls": [],
    }

    # URL allowlist check (domain-prefix matching)
    if url_allowlist:
        urls = re.findall(_URL_REGEX, payload_text, flags=re.IGNORECASE)
        for u in urls:
            if not any(
                u.lower().startswith(domain.lower()) for domain in url_allowlist
            ):
                matches["disallowed_urls"].append(u)

    # Simple weighted score
    w_override = 0.35 if matches["override"] else 0.0
    w_tool = 0.35 if matches["tool_steer"] else 0.0
    w_exfil = 0.45 if matches["exfil"] else 0.0
    w_urls = 0.25 if matches["disallowed_urls"] else 0.0

    # Multiple signals amplify risk (cap at 1.0)
    score = min(
        1.0,
        w_override
        + w_tool
        + w_exfil
        + w_urls
        + 0.15
        * sum(
            bool(matches[k])
            for k in ["override", "tool_steer", "exfil", "disallowed_urls"]
        ),
    )

    return {"score": score, "matches": matches}


def sanitize_text(payload_text: str) -> str:
    """
    Strip obvious jailbreak directives while preserving user intent as a question.
    """
    # Remove common directive lines
    lines = payload_text.splitlines()
    keep: List[str] = []
    for ln in lines:
        if re.search(
            "|".join(_OVERRIDE_PATTERNS + _TOOL_STEERING + _DATA_EXFIL),
            ln,
            flags=re.IGNORECASE,
        ):
            continue
        keep.append(ln)
    cleaned = "\n".join(keep).strip()
    # If nothing left, keep a neutral stub
    return (
        cleaned
        if cleaned
        else "Please answer the user’s question without violating any policies."
    )


class PromptInjectionMiddleware(Middleware):
    """
    Prompt-injection detector for agent/tool calls.

    Config:
      block_on_high_risk: block tool call when risk >= threshold
      threshold: risk threshold in [0,1]
      url_allowlist: iterable of allowed URL prefixes (e.g., ['https://docs.company.com/'])
      use_llm_checker: if provided, async callable(text)-> dict(score:0..1, reason:str)
      sanitize_on_medium: if risk < threshold but non-zero, sanitize the text before calling tool
      inspect_fields: keys from context.message.arguments to inspect; if None, inspect all strings
    """

    def __init__(
        self,
        *,
        block_on_high_risk: bool = True,
        threshold: float = 0.75,
        url_allowlist: Optional[Iterable[str]] = None,
        use_llm_checker: Optional[Callable[[str], Any]] = None,
        sanitize_on_medium: bool = True,
        inspect_fields: Optional[List[str]] = None,
    ):
        self.block_on_high_risk = block_on_high_risk
        self.threshold = threshold
        self.url_allowlist = list(url_allowlist) if url_allowlist else None
        self.use_llm_checker = use_llm_checker
        self.sanitize_on_medium = sanitize_on_medium
        self.inspect_fields = set(inspect_fields) if inspect_fields else None

    def _collect_text(self, obj: Any) -> List[str]:
        texts: List[str] = []
        if isinstance(obj, str):
            texts.append(obj)
        elif isinstance(obj, dict):
            if self.inspect_fields:
                for k in self.inspect_fields:
                    if k in obj and isinstance(obj[k], str):
                        texts.append(obj[k])
            else:
                for v in obj.values():
                    texts.extend(self._collect_text(v))
        elif isinstance(obj, list):
            for v in obj:
                texts.extend(self._collect_text(v))
        return texts

    async def _assess(self, text: str) -> Dict[str, Any]:
        heur = default_heuristic_score(text, self.url_allowlist)
        score = heur["score"]
        reason = heur["matches"]

        # Optional: LLM second opinion (e.g., a compact classifier you provide)
        if self.use_llm_checker:
            try:
                llm_result = await self.use_llm_checker(
                    text
                )  # must return {"score": float, "reason": str}
                # Combine with a max-operator to be conservative
                if isinstance(llm_result, dict) and "score" in llm_result:
                    score = max(score, float(llm_result["score"]))
                    reason = {
                        "heuristics": reason,
                        "llm": llm_result.get("reason", "llm_flagged"),
                    }
            except Exception as _:
                # Fail open on the LLM check, still keep heuristics
                pass

        return {"score": score, "reason": reason}

    async def _maybe_sanitize_arguments(self, args: Any, risky_texts: List[str]) -> Any:
        # Replace exact risky strings with sanitized versions inside the nested args structure
        def _walk(x):
            if isinstance(x, str) and x in risky_texts:
                return sanitize_text(x)
            if isinstance(x, dict):
                return {k: _walk(v) for k, v in x.items()}
            if isinstance(x, list):
                return [_walk(v) for v in x]
            return x

        return _walk(args)

    async def on_call_tool(self, context, call_next):
        # Extract text inputs from tool call arguments
        tool_name = getattr(context.message, "name", "<unknown>")
        arguments = getattr(context.message, "arguments", {}) or {}

        texts = self._collect_text(arguments)
        if not texts:
            return await call_next(context)

        # Aggregate risk across all texts
        overall_score = 0.0
        worst_reason = None
        per_text_scores: Dict[str, float] = {}

        for t in texts:
            assessment = await self._assess(t)
            per_text_scores[t] = assessment["score"]
            if assessment["score"] > overall_score:
                overall_score = assessment["score"]
                worst_reason = assessment["reason"]

        # Decide action
        if self.block_on_high_risk and overall_score >= self.threshold:
            raise ToolError(
                f"Prompt injection risk blocked for '{tool_name}' "
                f"(risk={overall_score:.2f}). Reason={worst_reason}"
            )

        # Sanitize medium risk payloads
        if self.sanitize_on_medium and 0.15 <= overall_score < self.threshold:
            risky_texts = [t for t, s in per_text_scores.items() if s >= 0.15]
            new_args = await self._maybe_sanitize_arguments(arguments, risky_texts)
            # Replace arguments and continue
            orig_args = context.message.arguments
            context.message.arguments = new_args
            try:
                return await call_next(context)
            finally:
                # Restore original in case downstream relies on mutability
                context.message.arguments = orig_args

        # Low risk → proceed
        return await call_next(context)

    async def on_request(self, context, call_next):
        # Optional: also guard generic MCP requests, not just tool calls
        return await call_next(context)
