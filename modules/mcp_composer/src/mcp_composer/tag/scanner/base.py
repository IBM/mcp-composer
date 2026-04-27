from __future__ import annotations
from ..models import ToolDescriptor


class Scanner:
    def collect(self) -> list[ToolDescriptor]:
        raise NotImplementedError
