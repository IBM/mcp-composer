from __future__ import annotations
from typing import List
import json
from ..models import ToolDescriptor
from .base import Scanner

class JsonFileScanner(Scanner):
    def __init__(self, path: str):
        self.path = path

    def collect(self) -> List[ToolDescriptor]:
        data = json.load(open(self.path))
        tools = []
        for obj in data:
            tools.append(ToolDescriptor(**obj))
        return tools