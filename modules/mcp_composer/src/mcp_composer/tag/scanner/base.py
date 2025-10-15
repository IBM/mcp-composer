from __future__ import annotations
from typing import List
from ..models import ToolDescriptor

class Scanner:
    def collect(self) -> List[ToolDescriptor]:
        raise NotImplementedError