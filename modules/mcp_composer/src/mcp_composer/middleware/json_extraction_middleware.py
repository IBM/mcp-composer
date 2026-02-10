"""Middleware to extract JSON from tool call arguments that contain text before JSON."""

import json
import re
from typing import Any, Dict
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class JSONExtractionMiddleware(Middleware):
    """
    Middleware that extracts JSON from tool call arguments when they contain
    reasoning text before the actual JSON arguments.
    
    This handles cases where LLM agents include reasoning/thinking text
    before the JSON arguments, causing FastMCP parsing to fail.
    """
    
    def _extract_json_from_string(self, text: str) -> Dict[str, Any]:
        """Extract JSON object from string that may contain text before JSON."""
        if not isinstance(text, str):
            return {"raw": str(text)}
        
        # Find the last '{' that likely starts a JSON object
        start_idx = text.rfind('{')
        if start_idx == -1:
            # Try to find JSON array
            start_idx = text.rfind('[')
            if start_idx == -1:
                logger.warning("No JSON found in string, wrapping as dict")
                return {"raw": text}
        # Try to parse from the found position onwards
        json_str = text[start_idx:]
        try:
            parsed = json.loads(json_str)
            return parsed if isinstance(parsed, dict) else {"data": parsed}
        except json.JSONDecodeError:
            # Try to find balanced JSON by counting braces
            brace_count = 0
            end_idx = len(json_str)
            for i, char in enumerate(json_str):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            if brace_count == 0:
                try:
                    return json.loads(json_str[:end_idx])
                except json.JSONDecodeError:
                    pass
            
            # Last resort: try regex to find JSON-like structures
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            logger.warning("Could not extract valid JSON from string, wrapping as dict")
            return {"raw": text}
    
    def _clean_arguments(self, arguments: Any) -> Dict[str, Any]:
        """Clean arguments that might contain mixed content."""
        if isinstance(arguments, str):
            return self._extract_json_from_string(arguments)
        
        if not isinstance(arguments, dict):
            return {"raw": arguments}
        
        cleaned = {}
        for key, value in arguments.items():
            if isinstance(value, str) and '{' in value:
                if not value.strip().startswith('{'):
                    try:
                        cleaned[key] = self._extract_json_from_string(value)
                    except (ValueError, json.JSONDecodeError):
                        cleaned[key] = value
                else:
                    try:
                        cleaned[key] = json.loads(value)
                    except json.JSONDecodeError:
                        cleaned[key] = value
            else:
                cleaned[key] = value
        
        return cleaned
    
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        """Intercept tool calls and clean arguments if needed."""
        arguments = getattr(context.message, "arguments", {}) or {}
        
        # Check if arguments need cleaning
        if isinstance(arguments, str) or any(
            isinstance(v, str) and '{' in v and not v.strip().startswith('{')
            for v in (arguments.values() if isinstance(arguments, dict) else [])
        ):
            logger.debug("Cleaning arguments that may contain text before JSON")
            cleaned = self._clean_arguments(arguments)
            
            # Update context with cleaned arguments
            if cleaned != arguments:
                context.message.arguments = cleaned
                logger.debug("Cleaned arguments: %s -> %s", type(arguments), type(cleaned))
        
        return await call_next(context)
