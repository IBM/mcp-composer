from __future__ import annotations
from typing import Any, Dict, List, Optional
import re
import yaml

try:
    from jsonpath_ng import parse as jsonpath_parse  # optional
except Exception:  # pragma: no cover
    jsonpath_parse = None

class Rule:
    def __init__(self, name: str, when: Dict[str, Any], then: Dict[str, Any]):
        self.name = name
        self.when = when
        self.then = then

    def _match_regex(self, pattern: str, text: str) -> bool:
        return re.search(pattern, text or "", flags=re.I) is not None

    def _match_jsonpath(self, tool: Dict[str, Any], expr: str, pattern: Optional[str]) -> bool:
        if not jsonpath_parse:
            return False
        values = [m.value for m in jsonpath_parse(expr).find(tool)]
        if pattern is None:
            return bool(values)
        return any(self._match_regex(pattern, str(v)) for v in values)

    def matches(self, tool: Dict[str, Any]) -> bool:
        """Support keys: name_regex, desc_regex, input_jsonpath, output_jsonpath, vendor_regex, endpoint_regex"""
        w = self.when or {}
        tests = []
        if "name_regex" in w:
            tests.append(self._match_regex(w["name_regex"], tool.get("name", "")))
        if "desc_regex" in w:
            tests.append(self._match_regex(w["desc_regex"], tool.get("description", "")))
        if "vendor_regex" in w:
            tests.append(self._match_regex(w["vendor_regex"], tool.get("vendor", "")))
        if "endpoint_regex" in w:
            tests.append(self._match_regex(w["endpoint_regex"], tool.get("endpoint", "")))
        if "input_jsonpath" in w:
            expr = w["input_jsonpath"].get("expr")
            pat = w["input_jsonpath"].get("pattern")
            tests.append(self._match_jsonpath(tool.get("input_schema", {}), expr, pat))
        if "output_jsonpath" in w:
            expr = w["output_jsonpath"].get("expr")
            pat = w["output_jsonpath"].get("pattern")
            tests.append(self._match_jsonpath(tool.get("output_schema", {}), expr, pat))
        if not tests:
            return False
        mode = w.get("mode", "all")
        return all(tests) if mode == "all" else any(tests)

    @staticmethod
    def load_all(path: str) -> List["Rule"]:
        data = yaml.safe_load(open(path)) or {}
        rules: List[Rule] = []
        for obj in data.get("rules", []):
            rules.append(Rule(obj.get("name"), obj.get("when", {}), obj.get("then", {})))
        return rules