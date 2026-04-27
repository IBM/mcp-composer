from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from .taxonomy import Capability, PiiRisk, HipaaFlag, GdprFlag, Region


class ToolDescriptor(BaseModel):
    id: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)  # free-form
    vendor: str | None = None
    endpoint: str | None = None  # URL or domain hint for residency
    scan_report: dict[str, str] = Field(default_factory=dict)


class PolicyTags(BaseModel):
    pii_risk: PiiRisk = PiiRisk.NONE
    hipaa: HipaaFlag = HipaaFlag.NONE
    gdpr: GdprFlag = GdprFlag.NONE
    residency: dict[str, Any] = Field(
        default_factory=lambda: {
            "required_region": Region.GLOBAL,
            "source_regions": [],
            "cross_border": False,
        }
    )


class TagReport(BaseModel):
    tool: ToolDescriptor
    capabilities: list[Capability] = Field(default_factory=list)
    policy: PolicyTags = Field(default_factory=PolicyTags)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    reports: list[TagReport]
    summary: dict[str, Any] = Field(default_factory=dict)
