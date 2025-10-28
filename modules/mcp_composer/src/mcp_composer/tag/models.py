from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .taxonomy import Capability, PiiRisk, HipaaFlag, GdprFlag, Region


class ToolDescriptor(BaseModel):
    id: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)  # free-form
    vendor: Optional[str] = None
    endpoint: Optional[str] = None  # URL or domain hint for residency
    scan_report: Dict[str, str] = Field(default_factory=dict)


class PolicyTags(BaseModel):
    pii_risk: PiiRisk = PiiRisk.NONE
    hipaa: HipaaFlag = HipaaFlag.NONE
    gdpr: GdprFlag = GdprFlag.NONE
    residency: Dict[str, Any] = Field(
        default_factory=lambda: {
            "required_region": Region.GLOBAL,
            "source_regions": [],
            "cross_border": False,
        }
    )


class TagReport(BaseModel):
    tool: ToolDescriptor
    capabilities: List[Capability] = Field(default_factory=list)
    policy: PolicyTags = Field(default_factory=PolicyTags)
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    reports: List[TagReport]
    summary: Dict[str, Any] = Field(default_factory=dict)
