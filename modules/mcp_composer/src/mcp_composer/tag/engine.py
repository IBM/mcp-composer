from __future__ import annotations
from typing import List, Dict, Any
from .models import ToolDescriptor, TagReport, ScanResult
from .taxonomy import Capability, PiiRisk, Region
from .rule_dsl import Rule

PII_FIELD_HINTS = {
    "email",
    "ssn",
    "dob",
    "passport",
    "phone",
    "address",
    "ip",
    "device_id",
    "cookie",
}
PHI_HINTS = {
    "patient",
    "medical",
    "diagnosis",
    "treatment",
    "provider",
    "icd",
    "cpt",
    "npi",
}


class TagEngine:
    def __init__(self, rules: List[Rule], policy_cfg: Dict[str, Any] | None = None):
        self.rules = rules
        self.policy_cfg = policy_cfg or {}

    def _infer_residency(self, endpoint: str | None) -> Dict[str, Any]:
        if not endpoint:
            return {
                "required_region": str(Region.GLOBAL),
                "source_regions": [],
                "cross_border": False,
            }
        endpoint_lower = endpoint.lower()
        if any(
            t in endpoint_lower for t in ["eu", ".eu", "europe", ".ie", ".de", ".fr"]
        ):
            region = Region.EU
        elif any(t in endpoint_lower for t in ["us", ".us", "america", ".com"]):
            region = Region.US
        elif any(t in endpoint_lower for t in ["ap", "apac", ".sg", ".jp", ".au"]):
            region = Region.APAC
        else:
            region = Region.GLOBAL
        return {
            "required_region": str(region),
            "source_regions": [],
            "cross_border": False,
        }

    def _pii_risk_from_schema(self, schema: Dict[str, Any]) -> PiiRisk:
        text = str(schema).lower()
        hits = sum(1 for k in PII_FIELD_HINTS if k in text)
        if hits >= 3:
            return PiiRisk.HIGH
        if hits == 2:
            return PiiRisk.MEDIUM
        if hits == 1:
            return PiiRisk.LOW
        return PiiRisk.NONE

    def _phi_hint(self, text: str) -> bool:
        tl = (text or "").lower()
        return any(h in tl for h in PHI_HINTS)

    def tag_tool(
        self, tool: ToolDescriptor, rules: List[Rule] | None = None
    ) -> TagReport:
        r = TagReport(tool=tool)
        rules = rules or self.rules

        # 1) Apply DSL rules
        for rule in rules:
            if rule.matches(tool.model_dump()):
                then = rule.then or {}
                r.evidence.setdefault("rules", []).append(rule.name)
                for cap in then.get("add_capabilities", []):
                    try:
                        r.capabilities.append(Capability(cap))
                    except Exception:
                        r.evidence.setdefault("unknown_capabilities", []).append(cap)
                policy = then.get("policy", {})
                if "pii_risk" in policy:
                    r.policy.pii_risk = (
                        r.policy.pii_risk
                        if r.policy.pii_risk != PiiRisk.NONE
                        else PiiRisk(policy["pii_risk"])
                    )  # conservative merge
                if "hipaa" in policy:
                    r.policy.hipaa = policy["hipaa"]
                if "gdpr" in policy:
                    r.policy.gdpr = policy["gdpr"]
                if "residency" in policy:
                    r.policy.residency.update(policy["residency"])  # override keys

        # 2) Heuristics (schema-based PII)
        schema_text = {**tool.input_schema, **tool.output_schema}
        risk = self._pii_risk_from_schema(schema_text)
        if risk.value > r.policy.pii_risk.value:
            r.policy.pii_risk = risk
            r.evidence.setdefault("pii_fields", []).append("schema_hints")

        # 3) Residency from endpoint hint (unless explicitly set by rules)
        if r.policy.residency.get("required_region") == str(Region.GLOBAL):
            r.policy.residency = self._infer_residency(tool.endpoint)

        # 4) HIPAA heuristics
        if self._phi_hint(tool.description):
            r.policy.hipaa = "possible" if r.policy.hipaa == "none" else r.policy.hipaa

        return r

    def scan(self, tools: List[ToolDescriptor]) -> ScanResult:
        reports = [self.tag_tool(t) for t in tools]
        summary = {
            "count": len(reports),
            "capability_counts": {},
            "pii_risk_counts": {},
        }
        for rep in reports:
            for c in rep.capabilities:
                summary["capability_counts"][str(c)] = (
                    summary["capability_counts"].get(str(c), 0) + 1
                )
            pr = rep.policy.pii_risk
            summary["pii_risk_counts"][str(pr)] = (
                summary["pii_risk_counts"].get(str(pr), 0) + 1
            )
        return ScanResult(reports=reports, summary=summary)
