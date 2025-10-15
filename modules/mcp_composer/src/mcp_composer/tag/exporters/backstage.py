from __future__ import annotations
import os
import json
from typing import List
from ..models import TagReport


BACKSTAGE_HEADER = """apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: {name}
  annotations:
    mcptag.capabilities: "{capabilities}"
    mcptag.pii_risk: "{pii}"
    mcptag.gdpr: "{gdpr}"
    mcptag.hipaa: "{hipaa}"
    mcptag.residency: "{residency}"
spec:
  type: service
  owner: unknown
  lifecycle: experimental
"""


class BackstageExporter:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)

    def write(self, reports: List[TagReport]):
        for r in reports:
            name = r.tool.id.replace("/", "-")
            path = os.path.join(self.out_dir, f"{name}.yaml")
            body = BACKSTAGE_HEADER.format(
                name=name,
                capabilities=",".join([str(c) for c in r.capabilities]) or "none",
                pii=str(r.policy.pii_risk),
                gdpr=str(r.policy.gdpr),
                hipaa=str(r.policy.hipaa),
                residency=json.dumps(r.policy.residency),
            )
            with open(path, "w") as f:
                f.write(body)
