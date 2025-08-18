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
    # More flexible ignore patterns to catch variations
    r"\bignore (all |the )?(previous|earlier|prior) (instructions|message|rules|action|commands?|guidance|directive|context|prompt)\b",
    r"\bignore (everything|all) (that came )?before\b",
    r"\bdisregard (all |the )?(prior|previous|earlier) (context|instructions|guidance|commands?|actions?|prompts?)\b",
    r"\boverride (the )?(system|policy|guardrails|instructions|rules)\b",
    r"\bact as (system|developer|root|admin|administrator)\b",
    r"\breveal (the )?(system|developer|original) (prompt|message|instructions)\b",
    r"\breset (the )?system (prompt|role|instructions|context)\b",
    r"\bbreak out of (your|the) (role|character|instructions|context)\b",
    r"\bstop following (the )?(guidelines|rules|instructions|policy)\b",
    r"\bforget (all |your )?(previous|earlier|prior) (instructions|rules|context|training)\b",
    r"\bstart (over|fresh|again) (with|from|ignoring)\b",
    r"\bpretend (the )?(previous|earlier) (instructions|context|rules) (don't|do not) exist\b",
]

_TOOL_STEERING = [
    r"\bcall (the )?tool\b",
    r"\binvoke (hidden|internal) tool\b",
    r"\buse tool .* with\b",
    r"\bexecute shell\b",
    r"\brun .* on server\b",
    r"\btrigger (the )?tool\b",
    r"\bforce tool execution\b",
]

_DATA_EXFIL = [
    r"\bprint (all )?environment variables\b",
    r"\bshow .*api key\b",
    r"\bread .*secret\b",
    r"\bcat /etc/passwd\b",
    r"\bfetch .*credentials?\b",
    r"\bdump (all )?data\b",
    r"\bextract (sensitive )?information\b",
]

_PROMPT_MANIPULATION = [
    r"\bmodify (the )?prompt\b",
    r"\bchange (your|the) (behavior|instructions)\b",
    r"\bupdate (the )?system (prompt|message)\b",
    r"\breplace (the )?(prompt|instructions)\b",
    r"\binjected? prompt\b",
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
        "prompt_manip": _find_matches(_PROMPT_MANIPULATION, payload_text),
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

    # Enhanced weighted score
    w_override = 0.4 if matches["override"] else 0.0
    w_tool = 0.35 if matches["tool_steer"] else 0.0
    w_exfil = 0.45 if matches["exfil"] else 0.0
    w_prompt = 0.3 if matches["prompt_manip"] else 0.0
    w_urls = 0.25 if matches["disallowed_urls"] else 0.0

    # Multiple signals amplify risk (cap at 1.0)
    active_signals = sum(
        bool(matches[k])
        for k in ["override", "tool_steer", "exfil", "prompt_manip", "disallowed_urls"]
    )

    score = min(
        1.0,
        w_override
        + w_tool
        + w_exfil
        + w_prompt
        + w_urls
        + 0.15 * active_signals,  # Amplification for multiple signals
    )

    return {"score": score, "matches": matches}


def sanitize_text(payload_text: str) -> str:
    """
    Strip obvious jailbreak directives while preserving user intent as a question.
    """
    # Remove common directive lines
    lines = payload_text.splitlines()
    keep: List[str] = []
    all_patterns = (
        _OVERRIDE_PATTERNS + _TOOL_STEERING + _DATA_EXFIL + _PROMPT_MANIPULATION
    )

    for ln in lines:
        if re.search("|".join(all_patterns), ln, flags=re.IGNORECASE):
            continue
        keep.append(ln)

    cleaned = "\n".join(keep).strip()
    # If nothing left, keep a neutral stub
    return (
        cleaned
        if cleaned
        else "Please answer the user's question without violating any policies."
    )


class PromptInjectionMiddleware(Middleware):
    """
    Prompt-injection detector for agent/tool calls and prompt operations.

    Config:
      block_on_high_risk: block operation when risk >= threshold
      threshold: risk threshold in [0,1]
      url_allowlist: iterable of allowed URL prefixes (e.g., ['https://docs.company.com/'])
      use_llm_checker: if provided, async callable(text)-> dict(score:0..1, reason:str)
      sanitize_on_medium: if risk < threshold but non-zero, sanitize the text before operation
      inspect_fields: keys from context.message.arguments to inspect; if None, inspect all strings
      block_prompts: if True, also apply injection detection to prompt operations
      prompt_fields: fields in prompts to inspect for injection attempts
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
        block_prompts: bool = True,
        prompt_fields: Optional[List[str]] = None,
    ):
        self.block_on_high_risk = block_on_high_risk
        self.threshold = threshold
        self.url_allowlist = list(url_allowlist) if url_allowlist else None
        self.use_llm_checker = use_llm_checker
        self.sanitize_on_medium = sanitize_on_medium
        self.inspect_fields = set(inspect_fields) if inspect_fields else None
        self.block_prompts = block_prompts
        self.prompt_fields = (
            set(prompt_fields)
            if prompt_fields
            else {
                "description",
                "content",
                "template",
                "instructions",
                "example",
                "examples",
            }
        )

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

    def _collect_prompt_text(self, prompt_obj: Any) -> List[str]:
        """Collect text from prompt-specific fields"""
        texts: List[str] = []

        if isinstance(prompt_obj, dict):
            for field in self.prompt_fields:
                if field in prompt_obj and isinstance(prompt_obj[field], str):
                    texts.append(prompt_obj[field])
            # Also check arguments if present
            if "arguments" in prompt_obj:
                texts.extend(self._collect_text(prompt_obj["arguments"]))
        elif hasattr(prompt_obj, "__dict__"):
            for field in self.prompt_fields:
                if hasattr(prompt_obj, field):
                    value = getattr(prompt_obj, field)
                    if isinstance(value, str):
                        texts.append(value)
            # Check arguments attribute
            if hasattr(prompt_obj, "arguments"):
                texts.extend(self._collect_text(getattr(prompt_obj, "arguments")))

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
            except Exception as e:
                # Fail open on the LLM check, still keep heuristics
                logger.warning(f"LLM checker failed: {e}")
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

    async def _maybe_sanitize_prompt(
        self, prompt_obj: Any, risky_texts: List[str]
    ) -> Any:
        """Sanitize prompt content in-place"""

        def sanitize_if_risky(text):
            return sanitize_text(text) if text in risky_texts else text

        if isinstance(prompt_obj, dict):
            for field in self.prompt_fields:
                if field in prompt_obj and isinstance(prompt_obj[field], str):
                    prompt_obj[field] = sanitize_if_risky(prompt_obj[field])
            if "arguments" in prompt_obj:
                prompt_obj["arguments"] = await self._maybe_sanitize_arguments(
                    prompt_obj["arguments"], risky_texts
                )
        elif hasattr(prompt_obj, "__dict__"):
            for field in self.prompt_fields:
                if hasattr(prompt_obj, field):
                    value = getattr(prompt_obj, field)
                    if isinstance(value, str):
                        setattr(prompt_obj, field, sanitize_if_risky(value))
            if hasattr(prompt_obj, "arguments"):
                sanitized_args = await self._maybe_sanitize_arguments(
                    getattr(prompt_obj, "arguments"), risky_texts
                )
                setattr(prompt_obj, "arguments", sanitized_args)

        return prompt_obj

    async def _assess_prompts(
        self, prompts: Any, operation_name: str = "prompt_operation"
    ):
        """Assess prompt injection risk in prompt objects"""
        if not self.block_prompts:
            return prompts

        # Handle different prompt structures
        prompt_list = []
        if isinstance(prompts, list):
            prompt_list = prompts
        elif hasattr(prompts, "prompts") and prompts.prompts:
            prompt_list = prompts.prompts
        elif isinstance(prompts, dict) and "prompts" in prompts:
            prompt_list = prompts["prompts"]
        else:
            # Single prompt
            prompt_list = [prompts]

        overall_score = 0.0
        worst_reason = None
        risky_texts = []

        for prompt in prompt_list:
            texts = self._collect_prompt_text(prompt)
            for text in texts:
                assessment = await self._assess(text)
                if assessment["score"] > overall_score:
                    overall_score = assessment["score"]
                    worst_reason = assessment["reason"]
                if assessment["score"] >= 0.15:  # Medium risk threshold
                    risky_texts.append(text)

        # Decide action
        if self.block_on_high_risk and overall_score >= self.threshold:
            raise ToolError(
                f"Prompt injection risk blocked for '{operation_name}' "
                f"(risk={overall_score:.2f}). Reason={worst_reason}"
            )

        # Sanitize medium risk content
        if (
            self.sanitize_on_medium
            and risky_texts
            and 0.15 <= overall_score < self.threshold
        ):
            logger.warning(f"Sanitizing medium-risk prompt content in {operation_name}")
            for prompt in prompt_list:
                await self._maybe_sanitize_prompt(prompt, risky_texts)

        return prompts

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
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

    async def on_list_prompts(self, context: MiddlewareContext, call_next: CallNext):
        """Guard prompt listing operations against injection attempts"""
        result = await call_next(context)

        try:
            # Assess and potentially sanitize prompt content
            sanitized_result = await self._assess_prompts(result, "list_prompts")
            return sanitized_result
        except ToolError:
            # Re-raise blocking errors
            raise
        except Exception as e:
            # Log error but don't fail the operation
            logger.error(f"Error in prompt injection assessment for list_prompts: {e}")
            return result

    async def on_get_prompts(self, context: MiddlewareContext, call_next: CallNext):
        """Guard prompt retrieval operations against injection attempts"""
        result = await call_next(context)
        try:
            # Assess and potentially sanitize prompt content
            sanitized_result = await self._assess_prompts(result, "get_prompts")
            return sanitized_result
        except ToolError:
            # Re-raise blocking errors
            raise
        except Exception as e:
            # Log error but don't fail the operation
            logger.error(f"Error in prompt injection assessment for get_prompts: {e}")
            return result

    async def on_request(self, context: MiddlewareContext, call_next: CallNext):
        """Guard prompt retrieval operations against injection attempts"""
        result = await call_next(context)
        try:
            # Assess and potentially sanitize prompt content
            sanitized_result = await self._assess_prompts(result, "get_prompts")
            return sanitized_result
        except ToolError:
            # Re-raise blocking errors
            raise
        except Exception as e:
            # Log error but don't fail the operation
            logger.error(f"Error in prompt injection assessment for get_prompts: {e}")
            return result
