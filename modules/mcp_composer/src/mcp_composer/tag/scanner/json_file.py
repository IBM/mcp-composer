from __future__ import annotations
import json
from ..models import ToolDescriptor
from .base import Scanner


class JsonFileScanner(Scanner):
    def __init__(self, path: str) -> None:
        self.path = path

    def collect(self) -> list[ToolDescriptor]:
        data = json.load(open(self.path, encoding="utf-8"))
        tools = []
        for obj in data:
            tools.append(ToolDescriptor(**obj))
        return tools
