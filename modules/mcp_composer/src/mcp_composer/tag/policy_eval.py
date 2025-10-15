from __future__ import annotations
from .models import ScanResult


class PolicyGate:
    def __init__(self, require: list[str] | None = None):
        self.require = require or []

    def evaluate(self, result: ScanResult) -> tuple[bool, list[str]]:
        failures: list[str] = []
        for rule in self.require:
            ok = self._check_rule(result, rule)
            if not ok:
                failures.append(rule)
        return (len(failures) == 0, failures)

    def _check_rule(self, result: ScanResult, rule: str) -> bool:
        if "policy.pii_risk" in rule:
            allowed = [
                x.strip("' \"") for x in rule.split("[")[-1].split("]")[0].split(",")
            ]
            disallowed = [
                r for r in result.reports if str(r["policy"]["pii_risk"]) not in allowed
            ]
            return len(disallowed) == 0
        return True
